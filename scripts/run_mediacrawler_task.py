"""Controlled standalone bridge, executed only by the isolated upstream Python.

No MINING imports; upstream files and license remain unmodified.
"""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import Future as ConcurrentFuture
import importlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import ssl
import sys
import threading
import traceback
from types import ModuleType
from urllib.parse import urlsplit

import httpx
from tenacity import Future, RetryError

DIAGNOSTIC_PHASES = frozenset({
    "initializing", "importing_upstream", "configuring", "starting_crawler",
    "launching_browser", "navigating_platform", "waiting_for_domestic_page", "waiting_for_login", "collecting", "cleaning_up",
})


def _safe_name(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", value) else "unknown"


def _retry_exception(error):
    """Only an installed Tenacity RetryError/Future; never arbitrary callbacks."""
    if type(error) is not RetryError:
        return None
    attempt = error.__dict__.get("last_attempt")
    if type(attempt) is not Future:
        return None
    fields = attempt.__dict__
    condition = fields.get("_condition")
    if type(condition) is not threading.Condition:
        return None
    lock = condition.__dict__.get("_lock")
    if type(lock) is not type(threading.RLock()) or not lock.acquire(blocking=False):
        return None
    try:
        # Completed/cancelled only: no waiting for a pending future, no repr(),
        # and bypass a replaced instance exception() method with the real base.
        state = fields.get("_state")
        if type(state) is not str or state not in {"FINISHED", "CANCELLED", "CANCELLED_AND_NOTIFIED"}:
            return None
        value = ConcurrentFuture.exception(attempt, timeout=0)
        return value if isinstance(value, BaseException) else None
    except Exception:
        return None
    finally:
        lock.release()


def _exception_chain(error):
    """At most eight distinct exception nodes; explicit cause precedes context."""
    chain, seen = [], set()
    current = error
    while isinstance(current, BaseException) and len(chain) < 8:
        chain.append(current)
        seen.add(id(current))
        candidates = (
            _retry_exception(current),
            BaseException.__cause__.__get__(current),
            BaseException.__context__.__get__(current),
        )
        candidates = [value for value in candidates if isinstance(value, BaseException)]
        next_error = next((value for value in candidates if id(value) not in seen), None)
        if next_error is None:
            return chain, not candidates and not isinstance(current, RetryError)
        current = next_error
    return chain, False


def _repository_frames(error, upstream):
    frames = []
    bridge = Path(__file__).resolve()
    upstream = upstream.resolve()
    for index, (frame, line) in enumerate(traceback.walk_tb(BaseException.__traceback__.__get__(error))):
        if index >= 64:
            break
        filename = Path(frame.f_code.co_filename).resolve()
        if filename == bridge:
            relative = "mining/scripts/run_mediacrawler_task.py"
        elif filename.is_relative_to(upstream):
            relative = "upstream/" + filename.relative_to(upstream).as_posix()
        else:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_./-]{1,180}", relative) or ".." in relative.split("/"):
            continue
        frames.append({"file": relative, "function": _safe_name(frame.f_code.co_name), "line": line})
    return frames[-5:]


def _module_exception(module_name, class_name):
    module = sys.modules.get(module_name)
    if not isinstance(module, ModuleType):
        return None
    value = ModuleType.__getattribute__(module, "__dict__").get(class_name)
    return value if isinstance(value, type) and issubclass(value, BaseException) else None


def _error_category(chain, upstream):
    """Known classes/precise pinned source evidence; never export raw messages."""
    category, priority = "runtime_error", 0
    known_types = {
        name: _module_exception("media_platform.xhs.exception", name) for name in
        ("PlatformAccessError", "IPBlockError", "DataFetchError", "NoteNotFoundError")
    }
    known_categories = {"PlatformAccessError": ("platform_access_restricted", 70),
        "IPBlockError": ("platform_ip_blocked", 70), "DataFetchError": ("data_fetch_error", 40),
        "NoteNotFoundError": ("content_unavailable", 40)}
    playwright_timeout = _module_exception("playwright._impl._errors", "TimeoutError")
    for current in chain:
        selected = next((known_categories[name] for name, cls in known_types.items() if cls is not None and type(current) is cls), None)
        if selected is None and isinstance(current, json.JSONDecodeError):
            selected = ("response_json_error", 50)
        if selected is None and type(current) is Exception and any(
            frame == {"file": "upstream/media_platform/xhs/client.py", "function": "request", "line": 164}
            for frame in _repository_frames(current, upstream)
        ):
            # Fixed pin client.py:158-164 raises this only for HTTP 461/471.
            selected = ("platform_verification_required", 90)
        if selected is None:
            # Base slot only: do not execute __str__/repr or arbitrary args objects.
            args = BaseException.args.__get__(current)
            message = args[0][:16384] if args and type(args[0]) is str else ""
            if "Socket path too long" in message or "AF_UNIX path too long" in message:
                selected = ("browser_socket_path_limit", 110)
            elif isinstance(current, (ssl.SSLCertVerificationError, ssl.CertificateError)) or any(marker in message for marker in (
                "CERTIFICATE_VERIFY_FAILED", "net::ERR_CERT_AUTHORITY_INVALID", "net::ERR_CERT_DATE_INVALID", "net::ERR_CERT_COMMON_NAME_INVALID",
            )):
                selected = ("certificate_error", 100)
            elif isinstance(current, (TimeoutError, httpx.TimeoutException)) or playwright_timeout is not None and isinstance(current, playwright_timeout) or "net::ERR_TIMED_OUT" in message:
                selected = ("timeout", 80)
            elif isinstance(current, (ConnectionError, httpx.ConnectError, socket.gaierror)) or any(marker in message for marker in (
                "net::ERR_CONNECTION_REFUSED", "net::ERR_CONNECTION_RESET", "net::ERR_CONNECTION_CLOSED", "net::ERR_NAME_NOT_RESOLVED",
            )):
                selected = ("connection_error", 60)
        if selected is not None and selected[1] > priority:
            category, priority = selected
    return category


def build_failure_diagnostic(error, phase, upstream):
    """v2 preserves the outer exception and adds a bounded, resolved root cause."""
    chain, resolved = _exception_chain(error)
    root = chain[-1] if chain and resolved else None
    root_name = _safe_name(type(root).__name__) if root is not None else "unknown"
    return {"version": 2, "exception_type": _safe_name(type(error).__name__),
        "phase": phase if phase in DIAGNOSTIC_PHASES else "initializing",
        "category": _error_category(chain, upstream), "frames": _repository_frames(error, upstream),
        "root_exception_type": root_name,
        "root_frames": _repository_frames(root, upstream) if root is not None and root_name != "unknown" else []}


def write_failure_diagnostic(error, phase, task_dir, upstream):
    if isinstance(error, asyncio.CancelledError) or isinstance(error, SystemExit) and error.code in (None, 0):
        return
    try:
        data = json.dumps(build_failure_diagnostic(error, phase, upstream), allow_nan=False).encode("utf-8")
        if len(data) > 4096:
            return
        # Preserve the first failure; cleanup must not overwrite its location.
        descriptor = os.open(task_dir / "diagnostic.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    except Exception:
        pass  # finite diagnostics must never mask the original failure


def apply_search_bounds(platform, limit, client_class=None, core_module=None, report=None):
    """Trim search results BEFORE upstream schedules detail/comment work.

    Search endpoint page size remains upstream-defined (10/20); only the first
    requested objects participate in subsequent detail and comment requests.
    """
    report = report if report is not None else {}
    if platform == "wb":
        original = core_module.filter_search_result_card

        def limited_cards(cards):
            rows = original(cards)
            report["search_page_objects"] = len(rows)
            report["selected_objects"] = min(len(rows), limit)
            return rows[:limit]

        core_module.filter_search_result_card = limited_cards
        return
    method = "get_note_by_keyword" if platform == "xhs" else "search_video_by_keyword"
    original = getattr(client_class, method)
    key = "items" if platform == "xhs" else "result"

    async def limited_page(self, *args, **kwargs):
        response = await original(self, *args, **kwargs)
        rows = response.get(key, [])
        report["search_page_objects"] = len(rows)
        if platform == "xhs":
            rows = [row for row in rows if row.get("model_type") not in {"rec_query", "hot_query"}]
        response[key] = rows[:limit]
        report["selected_objects"] = len(response[key])
        if platform == "xhs":
            # Core otherwise drops a nonempty final page before processing it.
            response["has_more"] = bool(response[key])
        return response

    setattr(client_class, method, limited_page)


def controlled_config(config, manifest, runtime):
    values = {
        "ENABLE_CDP_MODE": False, "CDP_CONNECT_EXISTING": False,
        "HEADLESS": False, "SAVE_LOGIN_STATE": True,
        "USER_DATA_DIR": str(runtime / "profiles" / "%s"),
        "ENABLE_IP_PROXY": False, "ENABLE_GET_MEIDAS": False,
        "ENABLE_GET_MEDIA": False, "ENABLE_GET_SUB_COMMENTS": False,
        "ENABLE_GET_COMMENTS": manifest["max_comments"] > 0,
        "ENABLE_GET_WORDCLOUD": False, "MAX_CONCURRENCY_NUM": 1,
        "COOKIES": "",
        "CRAWLER_MAX_SLEEP_SEC": 2, "BILI_SEARCH_MODE": "normal",
        "ENABLE_WEIBO_FULL_TEXT": True, "SAVE_DATA_OPTION": "jsonl",
        "SAVE_DATA_PATH": str(Path(manifest["task_dir"]) / "data"),
        "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES": manifest["max_comments"],
        "CRAWLER_MAX_NOTES_COUNT": manifest["max_posts"],
    }
    for key, value in values.items():
        setattr(config, key, value)


def configure_initial_home_navigation(platform, context):
    """Only the controlled XHS first page's first default official-home goto.

    No global Page patch, retry, TLS change or timeout extension. Other pages,
    URLs, explicit wait conditions and subsequent navigations keep their calls.
    """
    if platform != "xhs":
        return context
    original_new_page = context.new_page
    first_page = True

    async def new_page(*args, **kwargs):
        nonlocal first_page
        selected = first_page
        first_page = False
        context.new_page = original_new_page
        page = await original_new_page(*args, **kwargs)
        if not selected:
            return page
        original_goto = page.goto
        first_navigation = True

        async def goto(url, **options):
            nonlocal first_navigation
            initial = first_navigation
            first_navigation = False
            page.goto = original_goto
            if initial and url in {"https://www.xiaohongshu.com", "https://www.xiaohongshu.com/"} and options.get("wait_until") is None:
                options["wait_until"] = "domcontentloaded"
                timeout = options.get("timeout")
                # Keep an explicitly shorter positive bound; otherwise enforce
                # the pin's original 30-second default, including timeout=0.
                if type(timeout) not in (int, float) or not 0 < timeout <= 30_000:
                    options["timeout"] = 30_000
            return await original_goto(url, **options)

        page.goto = goto
        return page

    context.new_page = new_page
    return context


class XHSPageAboutBlankError(RuntimeError):
    """The controlled page is about:blank."""


class XHSPageBrowserError(RuntimeError):
    """The controlled page is a browser error page."""


class XHSPageNonHTTPSError(RuntimeError):
    """The controlled page is not HTTPS."""


class XHSPageHostNotAllowedError(RuntimeError):
    """The controlled page host is outside the fixed allowlist."""


class XHSPagePortOrCredentialsError(RuntimeError):
    """The controlled page has disallowed port or user information."""


class XHSPageInvalidURLError(RuntimeError):
    """The controlled page URL is absent or invalid."""


class XHSPageClosedError(RuntimeError):
    """The controlled page was closed while domestic access was pending."""


_XHS_PAGE_FAILURES = {
    "about_blank": XHSPageAboutBlankError,
    "browser_error_page": XHSPageBrowserError,
    "non_https": XHSPageNonHTTPSError,
    "host_not_allowed": XHSPageHostNotAllowedError,
    "port_or_credentials_not_allowed": XHSPagePortOrCredentialsError,
    "invalid_url": XHSPageInvalidURLError,
}


def _official_xhs_page_reason(page):
    """Fixed enum only; never return arbitrary URL components or page content."""
    try:
        value = page.url
        if not isinstance(value, str) or not value or value != value.strip() or any(ord(char) < 32 for char in value):
            return "invalid_url"
        parsed = urlsplit(value)
        if parsed.scheme == "about" and parsed.path == "blank":
            return "about_blank"
        if parsed.scheme in {"chrome-error", "edge-error"} or parsed.scheme == "chrome" and parsed.hostname in {"chromewebdata", "network-error"}:
            return "browser_error_page"
        if not parsed.scheme:
            return "invalid_url"
        if parsed.scheme != "https":
            return "non_https"
        host, port = parsed.hostname, parsed.port
        if not parsed.netloc or not host:
            return "invalid_url"
        if port not in (None, 443) or parsed.username is not None or parsed.password is not None:
            return "port_or_credentials_not_allowed"
        if host not in {"www.xiaohongshu.com", "xiaohongshu.com"}:
            return "host_not_allowed"
        return "allowed"
    except (ValueError, TypeError, AttributeError):
        return "invalid_url"


def _official_xhs_page(page):
    """Retain the boolean guard contract; all failures remain fail-closed."""
    return _official_xhs_page_reason(page) == "allowed"


def _require_official_xhs_page(page):
    reason = _official_xhs_page_reason(page)
    if reason != "allowed":
        # No message/URL data: existing finite exception_type carries the reason.
        raise _XHS_PAGE_FAILURES[reason]()


def _initial_rednote_page(page):
    """Recognize only the known redirect for pausing, never for collection."""
    try:
        value = page.url
        if not isinstance(value, str) or not value or value != value.strip() or any(ord(char) < 32 for char in value):
            return False
        parsed = urlsplit(value)
        return parsed.scheme == "https" and parsed.hostname in {"www.rednote.com", "rednote.com"} and parsed.port in (None, 443) and parsed.username is None and parsed.password is None
    except (ValueError, TypeError, AttributeError):
        return False


def _require_page_open(page):
    check = getattr(page, "is_closed", None)
    if check is not None and check():
        raise XHSPageClosedError()


async def wait_for_initial_domestic_page(page, phase):
    """Local URL polling only, bounded by the existing task timeout/cancellation."""
    _require_page_open(page)
    if _official_xhs_page(page):
        return
    if not _initial_rednote_page(page):
        _require_official_xhs_page(page)
    phase("waiting_for_domestic_page")
    while True:
        await asyncio.sleep(2)
        _require_page_open(page)
        if _official_xhs_page(page):
            return
        if not _initial_rednote_page(page):
            _require_official_xhs_page(page)


def configure_initial_domestic_gate(platform, crawler_class, phase):
    """Pause before the pin's first client creation reads cookies or calls pong."""
    if platform != "xhs":
        return
    original_client = crawler_class.create_xhs_client

    async def create_client(self, *args, **kwargs):
        if not getattr(self, "_mining_initial_domestic_gate_used", False):
            self._mining_initial_domestic_gate_used = True
            await wait_for_initial_domestic_page(self.context_page, phase)
            phase("navigating_platform")
        _require_page_open(self.context_page)
        _require_official_xhs_page(self.context_page)
        return await original_client(self, *args, **kwargs)

    crawler_class.create_xhs_client = create_client


def configure_login_entry(platform, login_class, phase):
    """XHS user opens login manually; other platforms retain their original entry."""
    original_login = login_class.login_by_qrcode

    async def login(self, *args, **kwargs):
        if platform != "xhs":
            phase("waiting_for_login")
            result = await original_login(self, *args, **kwargs)
            phase("collecting")
            return result
        _require_official_xhs_page(self.context_page)
        # Baseline remains only in this child process. Equivalent to the pinned
        # cookie converter's last-value lookup, without constructing a cookie string.
        baseline = None
        for cookie in await self.browser_context.cookies():
            if cookie.get("name") == "web_session":
                baseline = cookie.get("value")
        phase("waiting_for_login")
        confirmed = await self.check_login_state(no_logged_in_session=baseline)
        if confirmed is not True:
            raise RuntimeError("Manual login was not confirmed on the official page")
        _require_official_xhs_page(self.context_page)
        phase("collecting")
        return True

    login_class.login_by_qrcode = login


def execute_task(args, runtime, manifest, phase):
    upstream = runtime / "upstream"
    sys.path.insert(0, str(upstream))
    os.chdir(upstream)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    # Prevent future upstream dotenv additions from importing MINING .env values.
    import dotenv
    dotenv.load_dotenv = lambda *_a, **_k: False
    dotenv.dotenv_values = lambda *_a, **_k: {}
    phase("importing_upstream")
    module = importlib.import_module("main")
    if args.upstream_help:
        sys.argv = ["main.py", "--help"]
        asyncio.run(module.main())
        return
    task_dir = Path(manifest["task_dir"]).resolve()
    phase("configuring")
    controlled_config(module.config, manifest, runtime)
    platform = manifest["platform"]
    details = {
        "xhs": ("xhs", "XiaoHongShuClient", "XiaoHongShuLogin"),
        "bili": ("bilibili", "BilibiliClient", "BilibiliLogin"),
        "wb": ("weibo", "WeiboClient", "WeiboLogin"),
    }
    package, client_name, login_name = details[platform]
    report = {}
    if manifest["mode"] == "search":
        client_module = importlib.import_module(f"media_platform.{package}.client")
        core = importlib.import_module(f"media_platform.{package}.core")
        apply_search_bounds(platform, manifest["max_posts"], getattr(client_module, client_name), core, report)
    crawler_class = module.CrawlerFactory.CRAWLERS[platform]
    configure_initial_domestic_gate(platform, crawler_class, phase)
    original_launch = crawler_class.launch_browser

    async def tracked_launch(self, *a, **kw):
        phase("launching_browser")
        result = await original_launch(self, *a, **kw)
        configure_initial_home_navigation(platform, result)
        phase("navigating_platform")
        return result

    crawler_class.launch_browser = tracked_launch
    login = getattr(importlib.import_module(f"media_platform.{package}.login"), login_name)
    configure_login_entry(platform, login, phase)
    # QR remains in the dedicated browser; do not open an unrelated image app.
    importlib.import_module("tools.utils").show_qrcode = lambda *_a, **_kw: None
    argv = ["main.py", "--platform", platform, "--lt", "qrcode", "--type", manifest["mode"],
        "--get_comment", str(manifest["max_comments"] > 0).lower(),
        "--get_sub_comment", "false", "--get_media", "false", "--headless", "false",
        "--save_data_option", "jsonl", "--save_data_path", str(task_dir / "data"),
        "--crawler_max_notes_count", str(manifest["max_posts"]),
        "--max_comments_count_singlenotes", str(manifest["max_comments"]),
        "--max_concurrency_num", "1", "--enable_ip_proxy", "false"]
    if manifest["mode"] == "search":
        argv += ["--keywords", manifest["query"], "--start", "1"]
    else:
        url = manifest["url"]
        # Weibo's specified-ID parser expects a note ID; XHS keeps access query.
        target = url.split("?", 1)[0].rstrip("/").split("/")[-1] if platform == "wb" else url
        argv += ["--specified_id", target]
    sys.argv = argv
    phase("starting_crawler")

    async def run():
        current = asyncio.current_task()
        loop = asyncio.get_running_loop()
        # Graceful cancellation closes only this task's browser context, including
        # browser children Playwright may launch in a separate process group.
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, current.cancel)
        try:
            await module.main()
        except BaseException as error:
            write_failure_diagnostic(error, phase(None), task_dir, upstream)
            raise
        finally:
            phase("cleaning_up")
            try:
                await asyncio.wait_for(module.async_cleanup(), timeout=5)
            except BaseException as error:
                write_failure_diagnostic(error, "cleaning_up", task_dir, upstream)
                raise
            finally:
                (task_dir / "bounds.json").write_text(json.dumps(report), encoding="utf-8")

    asyncio.run(run())


def main():
    parser = argparse.ArgumentParser(description="MINING controlled MediaCrawler subprocess")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--upstream-help", action="store_true")
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    if args.upstream_help:
        execute_task(args, runtime, None, lambda _value: None)
        return
    if args.manifest is None:
        parser.error("--manifest required for an explicit task")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    task_dir = Path(manifest["task_dir"]).resolve()
    if not task_dir.is_relative_to(runtime / "tasks") or task_dir != args.manifest.resolve().parent:
        raise ValueError("invalid task directory")
    current_phase = "initializing"

    def phase(value):
        nonlocal current_phase
        if value is not None:
            if value not in DIAGNOSTIC_PHASES:
                raise ValueError("unsupported finite phase")
            current_phase = value
            (task_dir / "phase.json").write_text(json.dumps({"phase": value}), encoding="utf-8")
        return current_phase

    try:
        execute_task(args, runtime, manifest, phase)
    except BaseException as error:
        write_failure_diagnostic(error, current_phase, task_dir, runtime / "upstream")
        raise


if __name__ == "__main__":
    main()
