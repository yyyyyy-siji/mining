"""OFFLINE only: pinned export shapes and real local child-process lifecycle.

No fixture is evidence of successful platform collection/login.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import ssl
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tenacity import Future, RetryError

from signal_miner.auth import get_api_key_dependency
from signal_miner.connectors import mediacrawler_runner as runners
from signal_miner.connectors.mediacrawler_adapter import (
    PIN,
    ExportError,
    adapt_exports,
    read_task_exports,
    source_time,
    validate_item_url,
)
from signal_miner.db.models import Base
from signal_miner.pipeline import runner as pipeline_runner
from signal_miner.routes import feedback, mediacrawler
from signal_miner.routes.feedback import IngestRequest, _prepare_ingest_data
from signal_miner.settings import AppSettings
from signal_miner.utils.source_evidence import _stable_source_url

XHS_ID = "64abcdef0123456789abcdef"
XHS_URL = f"https://www.xiaohongshu.com/explore/{XHS_ID}?xsec_token=content-access&xsec_source=pc_search"
START = "2026-11-06T08:00:00+00:00"
END = "2026-11-06T08:01:00+00:00"


def task(platform="xhs", **extra):
    return dict(id="OFFLINE-task", platform=platform, mode="search", query="OFFLINE需求", url="",
        max_posts=3, max_comments=8, started_at=START, ended_at=END, **extra)


def exports(platform="xhs"):
    common = {"creator_hash": "anonymized-not-user-id", "nickname": "用***", "last_modify_ts": 1793952000000}
    if platform == "xhs":
        return {"contents": [dict(common, note_id=XHS_ID, title="标题非正文", desc="OFFLINE手动统计很麻烦", time=1793952000000, last_update_time=1793952060000, note_url=XHS_URL)],
            "comments": [dict(common, note_id=XHS_ID, comment_id="c1", content="OFFLINE希望自动汇总", create_time=1793952010000, parent_comment_id="")]}
    if platform == "bili":
        return {"contents": [dict(common, video_id="123", title="标题非口播", desc="OFFLINE简介", create_time=1793952000, video_url="https://www.bilibili.com/video/av123")],
            "comments": [dict(common, video_id="123", comment_id="c1", content="OFFLINE一级评论", create_time=1793952010, parent_comment_id="0")]}
    return {"contents": [dict(common, note_id="123", content="OFFLINE微博正文", create_time=1793952000, note_url="https://m.weibo.cn/detail/123")],
        "comments": [dict(common, note_id="123", comment_id="c1", content="OFFLINE一级评论", create_time=1793952010, parent_comment_id="0")]}


@pytest.mark.parametrize("platform", ["xhs", "bili", "wb"])
def test_actual_normalized_shapes_provenance_and_ingest_contract(platform):
    original = exports(platform)
    result = adapt_exports(original, task(platform))
    post, comment = result["items"]
    assert len(result["items"]) == 2
    assert post["raw_payload"]["record"] == original["contents"][0]
    assert post["raw_payload"]["task"]["id"] == "OFFLINE-task"
    assert post["raw_payload"]["upstream_pin"] == PIN
    assert post["source_created_at"] == "2026-11-06T08:00:00+00:00"
    assert comment["source_created_at"] == "2026-11-06T08:00:10+00:00"
    assert post["source_captured_at"] == "2026-11-06T08:00:00+00:00"
    assert post["author_name"] is None
    assert "匿名化" in post["source_note"]
    assert comment["external_url"] == post["external_url"] == comment["parent_url"]
    assert comment["parent_id"] == post["external_id"]
    assert comment["locator_level"] == "parent_page"
    assert comment["external_id"] == "c1"
    assert post["text"] != post["subject"]
    for item in result["items"]:
        prepared = _prepare_ingest_data(IngestRequest(**item))
        assert prepared["context"]["source_evidence"]["authenticity"] == "not_verified"
        assert prepared["context"]["raw_payload"] == item["raw_payload"]
    if platform == "bili":
        assert "500" in post["coverage_scope"] and "不是视频口播" in post["coverage_scope"]


def test_missing_parent_body_bad_urls_credential_fields_and_unknowns():
    records = exports()
    records["contents"] += [dict(records["contents"][0], desc="", title="不能补造正文"), dict(records["contents"][0], note_url="https://evil.invalid/explore/" + XHS_ID), dict(records["contents"][0], cookies="SHOULD_NOT_ESCAPE")]
    records["comments"] += [dict(records["comments"][0], note_id="other"), dict(records["comments"][0], parent_comment_id="sub"), dict(records["comments"][0], comment_id="", create_time=None, content="未知时间和ID")]
    result = adapt_exports(records, task())
    assert len(result["items"]) == 3
    last = result["items"][-1]
    assert last["source_created_at"] is None and last["external_id"] is None and last["author_name"] is None
    assert result["summary"]["skip_reasons"] == {"duplicate_parent_record": 1, "invalid_source_url": 1, "credential_fields": 1, "missing_task_parent": 1, "sub_comment_not_covered": 1}
    assert "SHOULD_NOT_ESCAPE" not in json.dumps(result)
    for key in ("set_cookie", "api_key", "proxy-authorization", "storage_state"):
        unsafe = exports()
        unsafe["contents"][0][key] = "DO_NOT_EXPORT"
        assert adapt_exports(unsafe, task())["items"] == []


def test_hard_post_and_comment_bounds_and_distinct_parent_identity():
    records = exports("wb")
    records["contents"] = [dict(records["contents"][0], note_id=str(n), note_url=f"https://m.weibo.cn/detail/{n}") for n in range(1, 6)]
    records["comments"] = [dict(records["comments"][0], note_id=str(n), comment_id=f"{n}-{c}") for n in range(1, 6) for c in range(12)]
    result = adapt_exports(records, task("wb"))
    assert len(result["items"]) == 27
    assert result["summary"]["posts"] == 3 and result["summary"]["comments"] == 24
    assert {i["parent_id"] for i in result["items"] if i["entity_type"] == "comment"} == {"1", "2", "3"}


def test_comments_survive_empty_parent_body_and_capture_time_is_not_end_time():
    records = exports("bili")
    records["contents"][0]["desc"] = ""
    records["comments"][0].pop("last_modify_ts")
    result = adapt_exports(records, task("bili"))
    assert len(result["items"]) == 1
    assert result["items"][0]["entity_type"] == "comment"
    assert result["items"][0]["parent_id"] == "123"
    assert result["items"][0]["source_captured_at"] is None
    assert result["summary"]["posts"] == 0 and result["summary"]["parent_objects"] == 1
    records = exports()
    records["contents"][0]["note_id"] = "a"  # substring is not identity
    result = adapt_exports(records, task())
    assert result["items"] == [] and result["summary"]["skip_reasons"]["source_id_url_mismatch"] == 1


def test_repeated_parent_versions_cannot_bypass_limits_first_valid_body_wins():
    records = exports()
    first = records["contents"][0]
    records["contents"] = [dict(first, desc="")] + [dict(first, desc=f"version-{n}") for n in range(100)]
    result = adapt_exports(records, dict(task(), max_posts=1))
    posts = [item for item in result["items"] if item["entity_type"] != "comment"]
    assert len(posts) == 1 and posts[0]["text"] == "version-0"
    assert posts[0]["raw_payload"]["record"] == dict(first, desc="version-0")
    assert len(result["items"]) <= 30
    assert result["summary"]["skip_reasons"]["duplicate_parent_record"] == 99


def test_preflight_requires_actual_marker_pin_browser_and_interpreter(tmp_path, monkeypatch):
    assert runners.preflight(tmp_path)["ready"] is False
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    browser = tmp_path / "browsers" / "chromium"
    browser.parent.mkdir()
    browser.touch()
    browser.chmod(0o700)
    checkout = tmp_path / "upstream"
    checkout.mkdir()
    (checkout / "LICENSE").touch()
    marker = {"pin": PIN, "node_version": "OFFLINE", "browser_executable": str(browser), "help_verified": True, "dependencies_verified": True}
    (tmp_path / "installed.json").write_text(json.dumps(marker))

    def run(argv, **_kwargs):
        if "rev-parse" in argv:
            return SimpleNamespace(stdout=PIN)
        if "status" in argv:
            return SimpleNamespace(stdout="")
        return SimpleNamespace(stdout=str(tmp_path / ".venv"))

    monkeypatch.setattr(runners.subprocess, "run", run)
    assert runners.preflight(tmp_path)["ready"] is True
    marker["pin"] = "wrong"
    (tmp_path / "installed.json").write_text(json.dumps(marker))
    assert runners.preflight(tmp_path)["ready"] is False


@pytest.mark.parametrize("value", [None, "", 0, "bad", True, 1, 1793952000000])
def test_unknown_or_wrong_unit_source_time(value):
    assert source_time(value, milliseconds=False) is None


@pytest.mark.parametrize("platform,url", [("xhs", "https://www.xiaohongshu.com/user/profile/abc"), ("xhs", "https://evil.invalid/explore/"+XHS_ID), ("bili", "https://www.bilibili.com/"), ("wb", "https://weibo.com/search?q=x"), ("wb", "https://u:p@m.weibo.cn/detail/1"), ("wb", "file:///detail/123")])
def test_invalid_item_links(platform, url):
    with pytest.raises(ValueError):
        validate_item_url(platform, url)


def test_requests_whitelist_and_xhs_policy_still_checks_domain():
    for changes in ({"platform": "dy"}, {"query": "a,b"}, {"max_posts": 4}, {"max_comments": 9}, {"cookies": "secret"}, {"query": ""}):
        with pytest.raises(ValidationError):
            mediacrawler.CollectionTaskRequest(**dict({"platform": "xhs", "query": "需求"}, **changes))
    detail = mediacrawler.CollectionTaskRequest(platform="xhs", mode="detail", url=XHS_URL)
    assert detail.max_posts == 1 and detail.url == XHS_URL
    item = adapt_exports(exports(), task())["items"][0]
    assert _prepare_ingest_data(IngestRequest(**item))["context"]["capture_method"] == "crawler"
    with pytest.raises(HTTPException):
        _prepare_ingest_data(IngestRequest(**dict(item, external_url="https://www.v2ex.com/t/1")))
    with pytest.raises(ValueError):
        validate_item_url("xhs", XHS_URL + ",https://www.xiaohongshu.com/explore/" + XHS_ID)
    with pytest.raises(ValueError):
        validate_item_url("xhs", XHS_URL + "\n")
    assert runners.preflight(runners.PROJECT_ROOT / "frontend" / "static" / "private")["reason"] == "runtime_inside_public_static_path"


def write_output(directory, *, fmt="jsonl", mode="search", rows=None):
    target = directory / "data" / "xhs" / fmt / f"{mode}_contents_2026-11-06.{fmt}"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(rows or exports()["contents"]) if fmt == "json" else "\n".join(json.dumps(row) for row in (rows or exports()["contents"])), encoding="utf-8")
    return target


@pytest.mark.parametrize("fmt", ["json", "jsonl"])
def test_isolated_export_reader(fmt, tmp_path):
    write_output(tmp_path, fmt=fmt)
    result = read_task_exports(tmp_path, platform="xhs", mode="search", started_at=datetime.now(timezone.utc).isoformat())
    assert result["contents"] == exports()["contents"]


@pytest.mark.parametrize("bad", ["oversize", "stale", "symlink", "wrong_platform", "wrong_mode", "rows", "malformed", "nan"])
def test_export_limits_and_foreign_paths(tmp_path, bad):
    target = write_output(tmp_path)
    if bad == "oversize":
        target.write_bytes(b"a" * 2_000_001)
    elif bad == "stale":
        os.utime(target, (1, 1))
    elif bad == "symlink":
        target.unlink()
        target.symlink_to(Path(__file__).resolve())
    elif bad == "wrong_platform":
        target.parent.parent.rename(target.parent.parent.with_name("wb"))
    elif bad == "wrong_mode":
        target.rename(target.with_name(target.name.replace("search", "detail")))
    elif bad == "rows":
        target.write_text("\n".join("{}" for _ in range(201)))
    elif bad == "nan":
        target.write_text('{"number":NaN}')
    else:
        target.write_text("invalid-json")
    with pytest.raises(ExportError):
        read_task_exports(tmp_path, platform="xhs", mode="search", started_at=datetime.now(timezone.utc).isoformat())


def load_bridge():
    spec = importlib.util.spec_from_file_location("mining_mediacrawler_bridge", runners.BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OfflinePage:
    def __init__(self):
        self.calls = []

    async def goto(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return "OFFLINE-navigation"


class OfflineBrowserContext:
    def __init__(self):
        self.pages = []

    async def new_page(self):
        page = OfflinePage()
        self.pages.append(page)
        return page


@pytest.mark.parametrize("url", ["https://www.xiaohongshu.com", "https://www.xiaohongshu.com/"])
async def test_only_first_controlled_xhs_home_default_wait_changes(url):
    context = OfflineBrowserContext()
    load_bridge().configure_initial_home_navigation("xhs", context)
    page = await context.new_page()
    assert await page.goto(url) == "OFFLINE-navigation"
    assert page.calls[0] == (url, {"wait_until": "domcontentloaded", "timeout": 30_000})
    await page.goto(url)
    assert page.calls[1] == (url, {})
    other_page = await context.new_page()
    await other_page.goto(url)
    assert other_page.calls == [(url, {})]


@pytest.mark.parametrize("url", ["https://www.xiaohongshu.com/explore", "https://www.xiaohongshu.com/?query=1", "https://www.xiaohongshu.com/#fragment", "https://xiaohongshu.com", "https://www.xiaohongshu.com.evil.invalid", "https://www.rednote.com", "http://www.xiaohongshu.com"])
async def test_nonexact_home_navigation_and_later_home_are_unmodified(url):
    context = OfflineBrowserContext()
    load_bridge().configure_initial_home_navigation("xhs", context)
    page = await context.new_page()
    await page.goto(url)
    await page.goto("https://www.xiaohongshu.com")
    assert page.calls == [(url, {}), ("https://www.xiaohongshu.com", {})]


@pytest.mark.parametrize("wait_until", ["load", "networkidle", "domcontentloaded", "commit"])
async def test_explicit_wait_and_all_other_navigation_options_are_preserved(wait_until):
    context = OfflineBrowserContext()
    load_bridge().configure_initial_home_navigation("xhs", context)
    page = await context.new_page()
    options = {"wait_until": wait_until, "timeout": 4000, "referer": "https://safe.example/"}
    await page.goto("https://www.xiaohongshu.com", **options)
    await page.goto("https://www.xiaohongshu.com")
    assert page.calls == [("https://www.xiaohongshu.com", options), ("https://www.xiaohongshu.com", {})]


@pytest.mark.parametrize("timeout,expected", [(None, 30_000), (0, 30_000), (60_000, 30_000), (float("inf"), 30_000), (5000, 5000), (30_000, 30_000)])
async def test_target_default_navigation_timeout_remains_bounded(timeout, expected):
    context = OfflineBrowserContext()
    load_bridge().configure_initial_home_navigation("xhs", context)
    page = await context.new_page()
    await page.goto("https://www.xiaohongshu.com", wait_until=None, timeout=timeout, referer="https://safe.example/")
    assert page.calls == [("https://www.xiaohongshu.com", {"wait_until": "domcontentloaded", "timeout": expected, "referer": "https://safe.example/"})]


@pytest.mark.parametrize("platform", ["bili", "wb"])
async def test_other_platform_browser_contexts_unchanged(platform):
    context = OfflineBrowserContext()
    original = context.new_page
    assert load_bridge().configure_initial_home_navigation(platform, context) is context
    assert context.new_page == original
    page = await context.new_page()
    await page.goto("https://www.xiaohongshu.com")
    assert page.calls == [("https://www.xiaohongshu.com", {})]


async def test_home_failure_is_not_retried_and_keeps_navigation_diagnostic(tmp_path):
    context = OfflineBrowserContext()
    bridge = load_bridge()
    page = OfflinePage()

    async def fail(url, **kwargs):
        page.calls.append((url, kwargs))
        raise TimeoutError("OFFLINE URL_COOKIE_SECRET")

    page.goto = fail

    async def first_page():
        return page

    context.new_page = first_page
    bridge.configure_initial_home_navigation("xhs", context)
    await context.new_page()
    with pytest.raises(TimeoutError) as caught:
        await page.goto("https://www.xiaohongshu.com")
    assert len(page.calls) == 1
    diagnostic = bridge.build_failure_diagnostic(caught.value, "navigating_platform", tmp_path / "upstream")
    assert diagnostic["category"] == "timeout" and diagnostic["phase"] == "navigating_platform"
    assert "URL_COOKIE_SECRET" not in json.dumps(diagnostic)


def diagnostic_error(upstream, message, exception_type=RuntimeError):
    namespace = {"failure": exception_type, "private": message}
    # OFFLINE synthetic traceback: source, message and locals must never export.
    compiled = compile("def nested(n):\n if n: return nested(n-1)\n raise failure(private)\nnested(8)\n", str(upstream / "media_platform/xhs/core.py"), "exec")
    try:
        exec(compiled, namespace)
    except Exception as error:
        return error
    raise AssertionError("expected offline exception")


def test_finite_diagnostic_never_saves_error_text_locals_or_absolute_paths(tmp_path):
    bridge = load_bridge()
    upstream, directory = tmp_path / "upstream", tmp_path / "task"
    directory.mkdir()
    secrets = "Cookie=a1=COOKIE_SECRET https://private.example/path?token=URL_SECRET sk-MODEL_SECRET ZHIHU_SECRET"
    error = diagnostic_error(upstream, secrets)
    bridge.write_failure_diagnostic(error, "launching_browser", directory, upstream)
    encoded = (directory / "diagnostic.json").read_text()
    data = json.loads(encoded)
    assert len(encoded.encode()) <= 4096 and len(data["frames"]) == 5
    assert data["exception_type"] == "RuntimeError" and data["phase"] == "launching_browser"
    assert data["category"] == "runtime_error"
    assert all(frame["file"] == "upstream/media_platform/xhs/core.py" and frame["function"] == "nested" for frame in data["frames"])
    for forbidden in ("COOKIE_SECRET", "URL_SECRET", "MODEL_SECRET", "ZHIHU_SECRET", "https:", "Cookie", str(tmp_path), "raise failure", "private"):
        assert forbidden not in encoded
    assert runners.read_failure_diagnostic(directory) == data
    bridge.write_failure_diagnostic(ValueError("cleanup secret"), "cleaning_up", directory, upstream)
    assert (directory / "diagnostic.json").read_text() == encoded  # original location retained


@pytest.mark.parametrize("message,error_type,category", [
    ("Cookie=SECRET CERTIFICATE_VERIFY_FAILED https://secret.invalid", RuntimeError, "certificate_error"),
    ("net::ERR_CERT_AUTHORITY_INVALID token=SECRET", RuntimeError, "certificate_error"),
    ("Socket path too long /private/SECRET", RuntimeError, "browser_socket_path_limit"),
    ("Cookie=SECRET", TimeoutError, "timeout"),
    ("Cookie=SECRET", ConnectionError, "connection_error"),
    ("SECRET", ssl.SSLCertVerificationError, "certificate_error"),
])
def test_known_errors_map_only_to_finite_categories(tmp_path, message, error_type, category):
    data = load_bridge().build_failure_diagnostic(diagnostic_error(tmp_path / "upstream", message, error_type), "navigating_platform", tmp_path / "upstream")
    assert data["category"] == category and "SECRET" not in json.dumps(data)


@pytest.mark.parametrize("bad", ["message", "oversize", "absolute", "traversal", "function", "phase", "category", "frames", "line", "symlink", "type"])
def test_diagnostic_reader_rejects_untrusted_fields_and_bad_shapes(tmp_path, bad):
    directory = tmp_path / "task"
    directory.mkdir()
    bridge = load_bridge()
    bridge.write_failure_diagnostic(diagnostic_error(tmp_path / "upstream", "SECRET"), "collecting", directory, tmp_path / "upstream")
    path = directory / "diagnostic.json"
    data = json.loads(path.read_text())
    if bad == "message":
        data["message"] = "Cookie=SHOULD_NOT_ESCAPE"
    elif bad == "oversize":
        path.write_text(" " * 4097)
        assert runners.read_failure_diagnostic(directory) is None
        return
    elif bad == "symlink":
        path.unlink()
        path.symlink_to(Path(__file__).resolve())
        assert runners.read_failure_diagnostic(directory) is None
        return
    elif bad == "absolute":
        data["frames"][0]["file"] = "/Users/private/SECRET.py"
    elif bad == "traversal":
        data["frames"][0]["file"] = "upstream/../../SECRET.py"
    elif bad == "function":
        data["frames"][0]["function"] = "https://SECRET"
    elif bad == "phase":
        data["phase"] = "Cookie=SECRET"
    elif bad == "category":
        data["category"] = "SECRET"
    elif bad == "frames":
        data["frames"].append(data["frames"][0])
    elif bad == "line":
        data["frames"][0]["line"] = True
    else:
        data["exception_type"] = "Type-Cookie=SECRET"
    path.write_text(json.dumps(data))
    assert runners.read_failure_diagnostic(directory) is None


def test_diagnostics_skip_cancellation_zero_exit_and_sanitize_names(tmp_path):
    bridge = load_bridge()
    for error in (asyncio.CancelledError(), SystemExit(0)):
        bridge.write_failure_diagnostic(error, "cleaning_up", tmp_path, tmp_path / "upstream")
    assert not (tmp_path / "diagnostic.json").exists()
    unsafe_class = type("Bad-Class-https://SECRET", (RuntimeError,), {})
    data = bridge.build_failure_diagnostic(unsafe_class("Cookie=SECRET"), "UNKNOWN SECRET", tmp_path / "upstream")
    assert data["exception_type"] == "unknown" and data["phase"] == "initializing" and data["frames"] == []
    connection = ConnectionError("Cookie=SECRET")
    connection.__cause__ = ssl.SSLCertVerificationError("URL_SECRET")
    assert bridge.build_failure_diagnostic(connection, "collecting", tmp_path / "upstream")["category"] == "certificate_error"
    assert bridge.build_failure_diagnostic(RuntimeError("net::ERR_CONNECTION_CLOSED Cookie=SECRET"), "navigating_platform", tmp_path / "upstream")["category"] == "connection_error"
    assert bridge.build_failure_diagnostic(RuntimeError("net::ERR_TIMED_OUT Cookie=SECRET"), "navigating_platform", tmp_path / "upstream")["category"] == "timeout"


def test_terminal_receipt_exposes_only_validated_diagnostic(tmp_path):
    bridge = load_bridge()
    bridge.write_failure_diagnostic(diagnostic_error(tmp_path / "upstream", "Cookie=SECRET https://secret.invalid"), "launching_browser", tmp_path, tmp_path / "upstream")
    manager = runners.MediaCrawlerRunner(str(tmp_path))
    receipt = dict(task(), status="failed", dir=tmp_path, diagnostic=runners.read_failure_diagnostic(tmp_path))
    data = manager.public(receipt)
    assert data["diagnostic"]["phase"] == "launching_browser"
    assert "SECRET" not in json.dumps(data) and str(tmp_path) not in json.dumps(data)
    for status in ("cancelled", "timed_out", "completed"):
        assert manager.public(dict(receipt, status=status))["diagnostic"] is None


@pytest.mark.parametrize("platform", ["xhs", "bili", "wb"])
async def test_search_list_is_bounded_before_detail_work(platform):
    bridge = load_bridge()
    rows = [{"id": n} for n in range(20)]
    metrics = {}
    if platform == "wb":
        core = SimpleNamespace(filter_search_result_card=lambda cards: cards)
        bridge.apply_search_bounds(platform, 3, core_module=core, report=metrics)
        actual = core.filter_search_result_card(rows)
    else:
        async def fetch(_self):
            return {"items" if platform == "xhs" else "result": rows, "has_more": False}
        name = "get_note_by_keyword" if platform == "xhs" else "search_video_by_keyword"
        fake = type("FakeClient", (), {name: fetch})
        bridge.apply_search_bounds(platform, 3, fake, report=metrics)
        result = await getattr(fake(), name)()
        actual = result["items" if platform == "xhs" else "result"]
        if platform == "xhs":
            assert result["has_more"] is True
    assert len(actual) == 3 and metrics == {"search_page_objects": 20, "selected_objects": 3}


def test_bootstrap_safe_config_and_clean_env(tmp_path, monkeypatch):
    config = SimpleNamespace()
    load_bridge().controlled_config(config, {"max_posts": 3, "max_comments": 8, "task_dir": str(tmp_path / "tasks" / "id")}, tmp_path)
    assert config.ENABLE_CDP_MODE is False and config.CDP_CONNECT_EXISTING is False
    assert config.HEADLESS is False and config.MAX_CONCURRENCY_NUM == 1
    assert config.ENABLE_GET_SUB_COMMENTS is False and config.ENABLE_GET_MEDIA is False
    assert config.ENABLE_IP_PROXY is False and config.COOKIES == ""
    assert str(tmp_path / "profiles" / "%s") == config.USER_DATA_DIR
    for key in ("OPENAI_API_KEY", "ZHIHU_ACCESS_SECRET", "HTTP_PROXY", "DATABASE_URL", "COOKIES"):
        monkeypatch.setenv(key, "MUST_NOT_INHERIT")
    env = runners.clean_child_environment(tmp_path)
    assert "MUST_NOT_INHERIT" not in json.dumps(env)
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "browsers")


CHILD = '''import json,sys,time,pathlib,os
m=json.loads(pathlib.Path(sys.argv[1]).read_text()); scenario=sys.argv[2]
if scenario=='sleep': time.sleep(60)
if scenario=='domestic_sleep':
 (pathlib.Path(m['task_dir'])/'phase.json').write_text(json.dumps({'phase':'waiting_for_domestic_page'}));time.sleep(60)
if scenario in ('fail','fail_bad_diag'):
 d={'version':1,'exception_type':'RuntimeError','phase':'launching_browser','category':'runtime_error','frames':[{'file':'upstream/media_platform/xhs/core.py','function':'launch_browser','line':1}]}
 if scenario=='fail_bad_diag': d['message']='Cookie=DO_NOT_FORWARD'
 (pathlib.Path(m['task_dir'])/'diagnostic.json').write_text(json.dumps(d))
 print('cookie=DO_NOT_FORWARD',file=sys.stderr);sys.exit(17)
if scenario=='success':
 p=pathlib.Path(m['task_dir'])/'data'/'xhs'/'jsonl'/'search_contents_2026-11-06.jsonl';p.parent.mkdir(parents=True);p.write_text(json.dumps({'note_id':'64abcdef0123456789abcdef','note_url':'https://www.xiaohongshu.com/explore/64abcdef0123456789abcdef','desc':'OFFLINE local subprocess'}))
'''


@pytest.fixture
def local_runner(tmp_path, monkeypatch):
    (tmp_path / "upstream").mkdir()
    monkeypatch.setattr(runners, "preflight", lambda _root: {"ready": True})
    real_spawn = asyncio.create_subprocess_exec
    evidence = []
    manager = runners.MediaCrawlerRunner(str(tmp_path))
    manager.offline_scenario = "success"

    async def spawn(*argv, **kwargs):
        evidence.append((argv, kwargs))
        manifest = argv[-1]
        return await real_spawn(sys.executable, "-c", CHILD, manifest, manager.offline_scenario, **kwargs)

    monkeypatch.setattr(runners.asyncio, "create_subprocess_exec", spawn)
    return manager, evidence


async def test_real_local_subprocess_completion_isolated_and_no_shell(local_runner):
    manager, evidence = local_runner
    response = await manager.start(mediacrawler.CollectionTaskRequest(platform="xhs", query="OFFLINE").model_dump())
    await manager.get(response["id"])["watcher"]
    assert manager.get(response["id"])["status"] == "completed"
    assert manager.results(response["id"])["items"][0]["text"] == "OFFLINE local subprocess"
    argv, kwargs = evidence[0]
    assert "--manifest" in argv and kwargs["start_new_session"] is True
    assert kwargs["stdout"] == asyncio.subprocess.DEVNULL and kwargs["stderr"] == asyncio.subprocess.DEVNULL
    assert "shell" not in kwargs and manager.active_id is None


@pytest.mark.parametrize("scenario,status", [("fail", "failed"), ("fail_bad_diag", "failed"), ("empty", "empty")])
async def test_failed_and_empty_are_not_success(local_runner, scenario, status):
    manager, _ = local_runner
    manager.offline_scenario = scenario
    response = await manager.start(mediacrawler.CollectionTaskRequest(platform="xhs", query="OFFLINE").model_dump())
    await manager.get(response["id"])["watcher"]
    assert manager.get(response["id"])["status"] == status
    assert "DO_NOT_FORWARD" not in json.dumps(manager.public(manager.get(response["id"])))
    diagnostic = manager.public(manager.get(response["id"]))["diagnostic"]
    if scenario == "fail":
        assert diagnostic["phase"] == "launching_browser"
    else:
        assert diagnostic is None
    if status == "failed":
        with pytest.raises(runners.RunnerError):
            manager.results(response["id"])


async def test_concurrency_cancel_and_timeout(local_runner):
    manager, _ = local_runner
    manager.offline_scenario = "sleep"
    response = await manager.start(mediacrawler.CollectionTaskRequest(platform="xhs", query="OFFLINE").model_dump())
    with pytest.raises(runners.RunnerError, match="task_already_running"):
        await manager.start({})
    stopped = await manager.stop(response["id"])
    assert stopped["status"] == "cancelled" and manager.active_id is None
    manager.timeout = .03
    response = await manager.start(mediacrawler.CollectionTaskRequest(platform="xhs", query="OFFLINE").model_dump())
    await manager.get(response["id"])["watcher"]
    assert manager.get(response["id"])["status"] == "timed_out"
    assert manager.active_id is None


async def test_missing_runtime_and_start_failure(local_runner, monkeypatch):
    assert runners.DEFAULT_RUNTIME.name == "mediacrawler-runtime"
    manager, _ = local_runner
    monkeypatch.setattr(runners, "preflight", lambda _root: {"ready": False, "reason": "not_installed"})
    with pytest.raises(runners.RunnerError, match="not_installed"):
        await manager.start({})
    monkeypatch.setattr(runners, "preflight", lambda _root: {"ready": True})

    async def broken(*_args, **_kwargs):
        raise OSError("private error must not escape")
    monkeypatch.setattr(runners.asyncio, "create_subprocess_exec", broken)
    response = await manager.start(mediacrawler.CollectionTaskRequest(platform="xhs", query="OFFLINE").model_dump())
    assert response["status"] == "failed" and response["error_code"] == "process_start_failed"
    assert manager.active_id is None and "private error" not in json.dumps(response)


async def test_authenticated_routes_preview_is_read_only(local_runner):
    manager, _ = local_runner
    app = FastAPI()
    app.state.mediacrawler = manager
    app.include_router(mediacrawler.router, prefix="/api/v1", dependencies=[Depends(get_api_key_dependency(AppSettings(api_key="test-key")))])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for method, path in (("GET", "/status"), ("POST", "/tasks"), ("GET", "/tasks/id"), ("POST", "/tasks/id/stop"), ("GET", "/tasks/id/results")):
            response = await client.request(method, "/api/v1/mediacrawler" + path, json={})
            assert response.status_code == 401
        headers = {"X-API-Key": "test-key"}
        response = await client.post("/api/v1/mediacrawler/tasks", headers=headers, json={"platform": "xhs", "query": "OFFLINE"})
        assert response.status_code == 202, response.text
        task_id = response.json()["id"]
        await manager.get(task_id)["watcher"]
        assert (await client.get(f"/api/v1/mediacrawler/tasks/{task_id}/results", headers=headers)).status_code == 200
        assert not list(manager.runtime.rglob("*.db"))


async def test_xhs_token_idempotency_keeps_original_snapshot(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'isolated.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    for module in (feedback, pipeline_runner):
        monkeypatch.setattr(module, "get_session_factory", lambda: factory)
    app = FastAPI()
    app.include_router(feedback.router, prefix="/api/v1")
    item = adapt_exports(exports(), task())["items"][0]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/feedback/ingest", json=item)
        assert first.status_code == 201, first.text
        first_id = first.json()["feedback_id"]
        changed = deepcopy(item)
        changed["external_url"] = XHS_URL.replace("content-access", "new-access").replace("pc_search", "another-source")
        second = await client.post("/api/v1/feedback/ingest", json=changed)
        assert second.json()["feedback_id"] == first_id  # existing receipt's duplicate flag is not reliable
        changed["external_url"] = changed["external_url"].replace(XHS_ID, "65abcdef0123456789abcdef")
        changed["external_id"] = "65abcdef0123456789abcdef"
        third = await client.post("/api/v1/feedback/ingest", json=changed)
        assert third.json()["feedback_id"] != first_id
        snapshot = (await client.get(f"/api/v1/feedback/{first_id}/source-snapshot")).json()
        assert snapshot["external_url"] == XHS_URL and snapshot["raw_payload"] == item["raw_payload"]
        assert snapshot["snapshot_verification"]["status"] == "verified"
    await engine.dispose()
    assert _stable_source_url("https://news.ycombinator.com/item?id=1") != _stable_source_url("https://news.ycombinator.com/item?id=2")
    assert _stable_source_url("https://www.v2ex.com/t/1?xsec_token=a") != _stable_source_url("https://www.v2ex.com/t/1?xsec_token=b")


class OfflineManualLogin:
    def __init__(self, url="https://www.xiaohongshu.com/explore?xsec_token=URL_ACCESS_SECRET", cookies=None):
        self.original_called = False
        self.checked_baselines = []
        self.context_page = SimpleNamespace(
            url=url,
            locator=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("must not click upstream qrcode XPath")),
        )
        cookie_rows = [
            {"name": "other", "value": "ignore"},
            {"name": "web_session", "value": "OLD_SESSION_SECRET"},
            {"name": "web_session", "value": "BASELINE_SESSION_SECRET"},
        ] if cookies is None else cookies

        async def get_cookies():
            return cookie_rows

        self.browser_context = SimpleNamespace(cookies=get_cookies)

    async def login_by_qrcode(self):
        self.original_called = True
        return "ORIGINAL_QRCODE_LOGIN"

    async def check_login_state(self, no_logged_in_session=None):
        self.checked_baselines.append(no_logged_in_session)
        return True


@pytest.mark.parametrize("url", [
    "https://www.xiaohongshu.com",
    "https://www.xiaohongshu.com/explore?xsec_token=URL_ACCESS_SECRET",
    "https://xiaohongshu.com/",
    "https://www.xiaohongshu.com:443/user/profile/123",
])
async def test_xhs_manual_login_waits_for_user_without_clicking_or_leaking_session(tmp_path, url):
    bridge = load_bridge()
    phases = []

    def record_phase(value):
        phases.append(value)
        (tmp_path / "phase.json").write_text(json.dumps({"phase": value}), encoding="utf-8")

    login_cls = type("FakeXhsLogin", (OfflineManualLogin,), {})
    bridge.configure_login_entry("xhs", login_cls, record_phase)
    instance = login_cls(url=url)
    assert await instance.login_by_qrcode() is True
    assert instance.original_called is False
    assert instance.checked_baselines == ["BASELINE_SESSION_SECRET"]
    assert phases == ["waiting_for_login", "collecting"]

    (tmp_path / "phase.json").write_text(json.dumps({"phase": "waiting_for_login"}), encoding="utf-8")
    manager = runners.MediaCrawlerRunner(str(tmp_path))
    receipt = manager.public(dict(task("xhs"), status="running", dir=tmp_path))
    assert receipt["status"] == "waiting_for_login"
    assert "请在专用页面手动点击登录，程序正在等待" in receipt["message"]
    assert "已显示二维码" not in receipt["message"]
    encoded = json.dumps(receipt, ensure_ascii=False)
    for secret in ("BASELINE_SESSION_SECRET", "OLD_SESSION_SECRET", "URL_ACCESS_SECRET"):
        assert secret not in encoded


@pytest.mark.parametrize("bad_url,exception_type", [
    ("http://www.xiaohongshu.com/", "XHSPageNonHTTPSError"),
    ("chrome-error://chromewebdata/", "XHSPageBrowserError"),
    ("about:blank", "XHSPageAboutBlankError"),
    ("https://www.xiaohongshu.com.evil.invalid/", "XHSPageHostNotAllowedError"),
    ("https://evil.invalid/https://www.xiaohongshu.com", "XHSPageHostNotAllowedError"),
    ("https://user:PASSWORD_SECRET@www.xiaohongshu.com/", "XHSPagePortOrCredentialsError"),
    ("https://www.xiaohongshu.com:8443/", "XHSPagePortOrCredentialsError"),
    ("", "XHSPageInvalidURLError"),
    (None, "XHSPageInvalidURLError"),
])
async def test_xhs_manual_login_rejects_non_official_or_error_pages_before_waiting(tmp_path, bad_url, exception_type):
    bridge = load_bridge()
    phases = []
    login_cls = type("FakeXhsLogin", (OfflineManualLogin,), {})
    bridge.configure_login_entry("xhs", login_cls, phases.append)
    instance = login_cls(url=bad_url)

    async def must_not_read_cookies():
        raise AssertionError("invalid page must not read session state")

    instance.browser_context.cookies = must_not_read_cookies
    with pytest.raises(RuntimeError) as caught:
        await instance.login_by_qrcode()
    assert phases == []
    assert instance.checked_baselines == []
    assert instance.original_called is False
    assert caught.value.args == ()
    bridge.write_failure_diagnostic(caught.value, " starting_crawler".strip(), tmp_path, tmp_path / "upstream")
    diagnostic = runners.read_failure_diagnostic(tmp_path)
    assert diagnostic["exception_type"] == exception_type
    assert diagnostic["category"] == "runtime_error"
    for forbidden in ("PASSWORD_SECRET", "evil.invalid", "chromewebdata"):
        assert forbidden not in json.dumps(diagnostic)


@pytest.mark.parametrize("value,reason,exception_type", [
    ("about:blank?token=URL_SECRET#COOKIE_SECRET", "about_blank", "XHSPageAboutBlankError"),
    ("chrome-error://chromewebdata/?url=https://PRIVATE_HOST_SECRET/&token=URL_SECRET", "browser_error_page", "XHSPageBrowserError"),
    ("chrome://network-error/?token=URL_SECRET", "browser_error_page", "XHSPageBrowserError"),
    ("http://www.xiaohongshu.com/?token=URL_SECRET", "non_https", "XHSPageNonHTTPSError"),
    ("file:///private/PRIVATE_PATH_SECRET?token=URL_SECRET", "non_https", "XHSPageNonHTTPSError"),
    ("https://PRIVATE_HOST_SECRET.invalid/?Cookie=COOKIE_SECRET&key=MODEL_SECRET", "host_not_allowed", "XHSPageHostNotAllowedError"),
    ("https://www.xiaohongshu.com:444/?token=URL_SECRET", "port_or_credentials_not_allowed", "XHSPagePortOrCredentialsError"),
    ("https://user:PASSWORD_SECRET@www.xiaohongshu.com/?token=URL_SECRET", "port_or_credentials_not_allowed", "XHSPagePortOrCredentialsError"),
    ("https://@www.xiaohongshu.com/?token=URL_SECRET", "port_or_credentials_not_allowed", "XHSPagePortOrCredentialsError"),
    ("https://www.xiaohongshu.com:notaport/?token=URL_SECRET", "invalid_url", "XHSPageInvalidURLError"),
    ("https://[INVALID_HOST_SECRET", "invalid_url", "XHSPageInvalidURLError"),
    ("https:///PRIVATE_PATH_SECRET", "invalid_url", "XHSPageInvalidURLError"),
    ("not-a-url COOKIE_SECRET", "invalid_url", "XHSPageInvalidURLError"),
    (" https://www.xiaohongshu.com/?token=URL_SECRET", "invalid_url", "XHSPageInvalidURLError"),
    ("https://www.xiaohongshu.com/\n?token=URL_SECRET", "invalid_url", "XHSPageInvalidURLError"),
    (b"https://www.xiaohongshu.com/COOKIE_SECRET", "invalid_url", "XHSPageInvalidURLError"),
])
def test_xhs_page_check_saves_only_fixed_reason_classes(tmp_path, value, reason, exception_type):
    bridge = load_bridge()
    page = SimpleNamespace(url=value)
    assert bridge._official_xhs_page_reason(page) == reason
    assert bridge._official_xhs_page(page) is False
    with pytest.raises(RuntimeError) as caught:
        bridge._require_official_xhs_page(page)
    assert type(caught.value).__name__ == exception_type and caught.value.args == ()
    bridge.write_failure_diagnostic(caught.value, "navigating_platform", tmp_path, tmp_path / "upstream")
    diagnostic = runners.read_failure_diagnostic(tmp_path)
    assert diagnostic["exception_type"] == exception_type
    manager = runners.MediaCrawlerRunner(str(tmp_path))
    receipt = manager.public(dict(task("xhs"), status="failed", dir=tmp_path, diagnostic=diagnostic))
    encoded = json.dumps(receipt)
    for private in ("URL_SECRET", "COOKIE_SECRET", "PRIVATE_HOST_SECRET", "PRIVATE_PATH_SECRET", "MODEL_SECRET", "PASSWORD_SECRET", "INVALID_HOST_SECRET", "https://", "chromewebdata", str(tmp_path)):
        assert private not in encoded


def test_xhs_page_reason_handles_unavailable_property_without_message_export(tmp_path):
    bridge = load_bridge()

    class UnavailablePage:
        @property
        def url(self):
            raise ValueError("Cookie=COOKIE_SECRET https://PRIVATE_HOST_SECRET/?key=MODEL_SECRET")

    assert bridge._official_xhs_page_reason(UnavailablePage()) == "invalid_url"
    with pytest.raises(bridge.XHSPageInvalidURLError) as caught:
        bridge._require_official_xhs_page(UnavailablePage())
    encoded = json.dumps(bridge.build_failure_diagnostic(caught.value, "navigating_platform", tmp_path / "upstream"))
    assert not any(value in encoded for value in ("COOKIE_SECRET", "PRIVATE_HOST_SECRET", "MODEL_SECRET"))


def test_xhs_page_guard_has_exactly_six_fixed_failure_reasons_and_keeps_official_success():
    bridge = load_bridge()
    assert set(bridge._XHS_PAGE_FAILURES) == {"about_blank", "browser_error_page", "non_https", "host_not_allowed", "port_or_credentials_not_allowed", "invalid_url"}
    assert len(set(bridge._XHS_PAGE_FAILURES.values())) == 6
    for url in ("https://www.xiaohongshu.com", "https://xiaohongshu.com:443/explore?xsec_token=URL_SECRET", "HTTPS://WWW.XIAOHONGSHU.COM/explore"):
        page = SimpleNamespace(url=url)
        assert bridge._official_xhs_page_reason(page) == "allowed"
        assert bridge._official_xhs_page(page) is True
        assert bridge._require_official_xhs_page(page) is None


@pytest.mark.parametrize("outcome", [
    False,
    None,
    "truthy_string",
    RuntimeError("Wait failed with BASELINE_SESSION_SECRET"),
    TimeoutError("Timed out with BASELINE_SESSION_SECRET"),
    "redirected_to_untrusted",
    "redirected_to_rednote",
])
async def test_xhs_manual_login_requires_true_confirmation_and_official_page_before_collecting(tmp_path, outcome):
    bridge = load_bridge()
    phases = []
    login_cls = type("FakeXhsLogin", (OfflineManualLogin,), {})
    bridge.configure_login_entry("xhs", login_cls, phases.append)
    instance = login_cls()

    async def check_state(no_logged_in_session=None):
        instance.checked_baselines.append(no_logged_in_session)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome in ("redirected_to_untrusted", "redirected_to_rednote"):
            instance.context_page.url = "https://www.rednote.com/?session=BASELINE_SESSION_SECRET" if outcome == "redirected_to_rednote" else "https://evil.invalid/callback?session=BASELINE_SESSION_SECRET"
            return True
        return outcome

    instance.check_login_state = check_state
    with pytest.raises((RuntimeError, TimeoutError)) as caught:
        await instance.login_by_qrcode()
    if outcome in ("redirected_to_untrusted", "redirected_to_rednote"):
        assert type(caught.value).__name__ == "XHSPageHostNotAllowedError"
    assert phases == ["waiting_for_login"]
    assert "collecting" not in phases
    assert instance.checked_baselines == ["BASELINE_SESSION_SECRET"]
    bridge.write_failure_diagnostic(caught.value, phases[-1], tmp_path, tmp_path / "upstream")
    manager = runners.MediaCrawlerRunner(str(tmp_path))
    receipt = manager.public(dict(task("xhs"), status="failed", dir=tmp_path, diagnostic=runners.read_failure_diagnostic(tmp_path)))
    encoded = json.dumps(receipt, ensure_ascii=False)
    for forbidden in ("BASELINE_SESSION_SECRET", "OLD_SESSION_SECRET", "URL_ACCESS_SECRET", "evil.invalid"):
        assert forbidden not in encoded


async def test_xhs_manual_login_propagates_cancellation_cleanly(tmp_path):
    bridge = load_bridge()
    phases = []
    login_cls = type("FakeXhsLogin", (OfflineManualLogin,), {})
    bridge.configure_login_entry("xhs", login_cls, phases.append)
    instance = login_cls()

    async def cancelled_wait(no_logged_in_session=None):
        instance.checked_baselines.append(no_logged_in_session)
        raise asyncio.CancelledError()

    instance.check_login_state = cancelled_wait
    with pytest.raises(asyncio.CancelledError) as caught:
        await instance.login_by_qrcode()
    assert phases == ["waiting_for_login"]
    bridge.write_failure_diagnostic(caught.value, phases[-1], tmp_path, tmp_path / "upstream")
    assert not (tmp_path / "diagnostic.json").exists()


@pytest.mark.parametrize("platform", ["bili", "wb"])
async def test_other_platforms_keep_original_login_by_qrcode(tmp_path, platform):
    bridge = load_bridge()
    phases = []
    login_cls = type("FakeOtherLogin", (OfflineManualLogin,), {})
    bridge.configure_login_entry(platform, login_cls, phases.append)
    instance = login_cls(url="https://not-xhs.example/")
    assert await instance.login_by_qrcode() == "ORIGINAL_QRCODE_LOGIN"
    assert instance.original_called is True
    assert instance.checked_baselines == []
    assert phases == ["waiting_for_login", "collecting"]
    (tmp_path / "phase.json").write_text(json.dumps({"phase": "waiting_for_login"}), encoding="utf-8")
    manager = runners.MediaCrawlerRunner(str(tmp_path))
    receipt = manager.public(dict(task(platform), status="running", dir=tmp_path))
    assert receipt["status"] == "waiting_for_login"
    assert receipt["message"] == runners.MESSAGES["waiting_for_login"]


@pytest.mark.parametrize("url", ["https://www.rednote.com/", "https://rednote.com:443/explore?token=URL_SECRET"])
async def test_initial_redirect_pause_precedes_client_cookies_pong_and_manual_login(tmp_path, monkeypatch, url):
    bridge = load_bridge()
    phases, events = [], []
    login_cls = type("FakeXhsLogin", (OfflineManualLogin,), {})
    login = login_cls(url=url)
    login.context_page.is_closed = lambda: False
    original_cookies = login.browser_context.cookies

    async def cookies():
        events.append("cookies")
        return await original_cookies()

    login.browser_context.cookies = cookies

    async def pong():
        events.append("pong")
        return False

    class Crawler:
        context_page = login.context_page

        async def create_xhs_client(self, proxy):
            assert proxy is None
            events.append("client")
            await cookies()
            return SimpleNamespace(pong=pong)

    def phase(value):
        phases.append(value)
        (tmp_path / "phase.json").write_text(json.dumps({"phase": value}))

    poll_calls = []

    async def local_poll(delay):
        poll_calls.append(delay)
        assert events == [] and login.checked_baselines == [] and login.original_called is False
        assert phases == ["waiting_for_domestic_page"]
        receipt = runners.MediaCrawlerRunner(str(tmp_path)).public(dict(task("xhs"), status="running", dir=tmp_path))
        assert receipt["status"] == "waiting_for_domestic_page" and receipt["terminal"] is False
        assert "请勿在国际页登录" in receipt["message"] and "尚未读取登录态或采集" in receipt["message"]
        assert "URL_SECRET" not in json.dumps(receipt)
        if len(poll_calls) == 2:
            login.context_page.url = "https://www.xiaohongshu.com/explore?xsec_token=DOMESTIC_SECRET"

    monkeypatch.setattr(bridge, "asyncio", SimpleNamespace(sleep=local_poll, CancelledError=asyncio.CancelledError))
    bridge.configure_initial_domestic_gate("xhs", Crawler, phase)
    bridge.configure_login_entry("xhs", login_cls, phase)
    client = await Crawler().create_xhs_client(None)
    assert await client.pong() is False
    assert await login.login_by_qrcode() is True
    assert poll_calls == [2, 2]
    assert phases == ["waiting_for_domestic_page", "navigating_platform", "waiting_for_login", "collecting"]
    assert events == ["client", "cookies", "pong", "cookies"]
    assert login.checked_baselines == ["BASELINE_SESSION_SECRET"] and login.original_called is False
    assert bridge._official_xhs_page(SimpleNamespace(url=url)) is False  # no domestic allowlist expansion


@pytest.mark.parametrize("url", [
    "https://www.rednote.com.evil.invalid/", "https://evil.invalid/rednote.com",
    "http://www.rednote.com/", "https://user:PASSWORD_SECRET@www.rednote.com/",
    "https://@www.rednote.com/", "https://www.rednote.com:8443/",
    "https://www.rednote.com:notaport/", "chrome-error://chromewebdata/",
    "about:blank", "https://www.rednote.com./", "https://other.rednote.com/",
])
async def test_only_exact_initial_redirect_can_pause_without_cookie_or_request_access(monkeypatch, url):
    bridge = load_bridge()
    phases = []
    page = SimpleNamespace(url=url, is_closed=lambda: False)

    class Crawler:
        context_page = page

        async def create_xhs_client(self):
            raise AssertionError("must not read cookies or send requests")

    async def must_not_poll(_delay):
        raise AssertionError("must fail instead of pausing")

    monkeypatch.setattr(bridge, "asyncio", SimpleNamespace(sleep=must_not_poll))
    bridge.configure_initial_domestic_gate("xhs", Crawler, phases.append)
    with pytest.raises(RuntimeError):
        await Crawler().create_xhs_client()
    assert phases == [] and bridge._initial_rednote_page(page) is False


@pytest.mark.parametrize("destination,closed", [
    ("https://evil.invalid/?key=URL_SECRET", False),
    ("http://www.xiaohongshu.com/", False),
    ("chrome-error://chromewebdata/", False),
    ("about:blank", False),
    ("https://www.rednote.com/", True),
])
async def test_domestic_pause_fails_if_same_page_becomes_disallowed_or_closes(tmp_path, monkeypatch, destination, closed):
    bridge = load_bridge()
    phases = []
    page = SimpleNamespace(url="https://www.rednote.com/?token=URL_SECRET", is_closed=lambda: False)

    async def local_poll(delay):
        assert delay == 2
        page.url = destination
        page.is_closed = lambda: closed

    monkeypatch.setattr(bridge, "asyncio", SimpleNamespace(sleep=local_poll, CancelledError=asyncio.CancelledError))
    with pytest.raises(RuntimeError) as caught:
        await bridge.wait_for_initial_domestic_page(page, phases.append)
    assert phases == ["waiting_for_domestic_page"]
    bridge.write_failure_diagnostic(caught.value, phases[-1], tmp_path, tmp_path / "upstream")
    diagnostic = runners.read_failure_diagnostic(tmp_path)
    assert diagnostic["phase"] == "waiting_for_domestic_page"
    if closed:
        assert diagnostic["exception_type"] == "XHSPageClosedError"
    encoded = json.dumps(diagnostic)
    assert not any(value in encoded for value in ("URL_SECRET", "evil.invalid", "chromewebdata", str(tmp_path)))


async def test_domestic_pause_cancel_propagates_without_initializing_client(tmp_path, monkeypatch):
    bridge = load_bridge()
    entered = asyncio.Event()
    phases = []
    page = SimpleNamespace(url="https://www.rednote.com/", is_closed=lambda: False)

    class Crawler:
        context_page = page

        async def create_xhs_client(self):
            raise AssertionError("client must remain unopened")

    async def local_poll(delay):
        assert delay == 2
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(bridge, "asyncio", SimpleNamespace(sleep=local_poll, CancelledError=asyncio.CancelledError))
    bridge.configure_initial_domestic_gate("xhs", Crawler, phases.append)
    pending = asyncio.create_task(Crawler().create_xhs_client())
    await asyncio.wait_for(entered.wait(), 1)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError) as caught:
        await pending
    assert phases == ["waiting_for_domestic_page"]
    bridge.write_failure_diagnostic(caught.value, phases[-1], tmp_path, tmp_path / "upstream")
    assert not (tmp_path / "diagnostic.json").exists()


async def test_domestic_gate_is_once_only_and_later_redirection_never_repauses():
    bridge = load_bridge()
    phases = []
    page = SimpleNamespace(url="https://www.xiaohongshu.com/", is_closed=lambda: False)
    clients = []

    class Crawler:
        context_page = page

        async def create_xhs_client(self):
            clients.append("created")
            return "OFFLINE-client"

    bridge.configure_initial_domestic_gate("xhs", Crawler, phases.append)
    crawler = Crawler()
    assert await crawler.create_xhs_client() == "OFFLINE-client"
    page.url = "https://www.rednote.com/"
    with pytest.raises(bridge.XHSPageHostNotAllowedError):
        await crawler.create_xhs_client()
    assert clients == ["created"] and phases == ["navigating_platform"]


@pytest.mark.parametrize("platform", ["bili", "wb"])
def test_domestic_gate_does_not_touch_other_platform_classes(platform):
    crawler_class = type("OtherCrawler", (), {})
    load_bridge().configure_initial_domestic_gate(platform, crawler_class, lambda _phase: None)
    assert not hasattr(crawler_class, "create_xhs_client")


@pytest.mark.parametrize("action,expected", [("stop", "cancelled"), ("timeout", "timed_out")])
async def test_domestic_pause_task_can_stop_or_timeout_and_never_offers_partial_results(local_runner, action, expected):
    manager, _ = local_runner
    manager.offline_scenario = "domestic_sleep"
    if action == "timeout":
        manager.timeout = .1
    receipt = await manager.start(mediacrawler.CollectionTaskRequest(platform="xhs", query="OFFLINE").model_dump())
    item = manager.get(receipt["id"])
    if action == "stop":
        for _ in range(100):
            if (item["dir"] / "phase.json").exists():
                break
            await asyncio.sleep(.01)
        assert manager.public(item)["status"] == "waiting_for_domestic_page"
        await manager.stop(receipt["id"])
    else:
        await item["watcher"]
    assert manager.public(item)["status"] == expected and manager.active_id is None
    with pytest.raises(runners.RunnerError, match="results_not_available"):
        manager.results(receipt["id"])


@pytest.fixture
def offline_xhs_errors(monkeypatch):
    # OFFLINE exports matching the statically read pin's RequestError subclasses.
    module = ModuleType("media_platform.xhs.exception")
    from httpx import RequestError

    for name in ("PlatformAccessError", "IPBlockError", "DataFetchError", "NoteNotFoundError"):
        setattr(module, name, type(name, (RequestError,), {"__module__": module.__name__}))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


def retry_error_with_trace(root, upstream):
    error = RetryError(Future.construct(3, root, True))
    namespace = {"failure": error}
    code = compile("def post():\n raise failure\npost()\n", str(upstream / "media_platform/xhs/client.py"), "exec")
    try:
        exec(code, namespace)
    except RetryError as outer:
        return outer
    raise AssertionError("expected real local RetryError")


@pytest.mark.parametrize("name,category", [
    ("PlatformAccessError", "platform_access_restricted"),
    ("IPBlockError", "platform_ip_blocked"),
    ("DataFetchError", "data_fetch_error"),
    ("NoteNotFoundError", "content_unavailable"),
])
def test_real_tenacity_root_changes_diagnostic_and_safe_hint(tmp_path, offline_xhs_errors, name, category):
    bridge = load_bridge()
    private = "Cookie=COOKIE_SECRET https://HOST_SECRET/?token=URL_SECRET response=BODY_SECRET CERTIFICATE_VERIFY_FAILED"
    root = diagnostic_error(tmp_path / "upstream", private, getattr(offline_xhs_errors, name))
    outer = retry_error_with_trace(root, tmp_path / "upstream")
    assert outer.__cause__ is None and outer.__context__ is None
    bridge.write_failure_diagnostic(outer, "collecting", tmp_path, tmp_path / "upstream")
    result = runners.read_failure_diagnostic(tmp_path)
    assert result["version"] == 2 and result["exception_type"] == "RetryError"
    assert result["root_exception_type"] == name and result["category"] == category
    assert result["frames"][-1]["function"] == "post"
    assert len(result["root_frames"]) == 5 and all(frame["function"] == "nested" for frame in result["root_frames"])
    assert len((tmp_path / "diagnostic.json").read_bytes()) <= 4096
    manager = runners.MediaCrawlerRunner(str(tmp_path))
    receipt = manager.public(dict(task("xhs"), status="failed", dir=tmp_path, diagnostic=result))
    assert receipt["message"] == runners.FAILURE_HINTS[category]
    encoded = json.dumps(receipt)
    assert not any(value in encoded for value in ("COOKIE_SECRET", "HOST_SECRET", "URL_SECRET", "BODY_SECRET", str(tmp_path)))
    if name == "PlatformAccessError":
        assert "不能仅据此判断登录失效" in receipt["message"]
    bridge.write_failure_diagnostic(ValueError("cleanup COOKIE_SECRET"), "cleaning_up", tmp_path, tmp_path / "upstream")
    assert runners.read_failure_diagnostic(tmp_path) == result


@pytest.mark.parametrize("kind,category,root_name", [
    ("json", "response_json_error", "JSONDecodeError"),
    ("connect", "connection_error", "ConnectionError"),
    ("timeout", "timeout", "TimeoutError"),
    ("certificate", "certificate_error", "SSLCertVerificationError"),
    ("unknown", "runtime_error", "ValueError"),
])
def test_retry_and_cause_context_keep_known_categories_without_text_export(tmp_path, kind, category, root_name):
    bridge = load_bridge()
    roots = {"json": json.JSONDecodeError("COOKIE_SECRET", "BODY_SECRET", 0),
        "connect": ConnectionError("COOKIE_SECRET"), "timeout": TimeoutError("URL_SECRET"),
        "certificate": ssl.SSLCertVerificationError("TOKEN_SECRET"), "unknown": ValueError("BODY_SECRET")}
    root = roots[kind]
    middle = RuntimeError("PRIVATE_RESPONSE_SECRET")
    middle.__context__ = root
    outer = retry_error_with_trace(middle, tmp_path / "upstream")
    data = bridge.build_failure_diagnostic(outer, "collecting", tmp_path / "upstream")
    assert data["root_exception_type"] == root_name and data["category"] == category
    assert not any(secret in json.dumps(data) for secret in ("COOKIE_SECRET", "BODY_SECRET", "URL_SECRET", "TOKEN_SECRET", "PRIVATE_RESPONSE_SECRET"))


@pytest.mark.parametrize("line,category", [(164, "platform_verification_required"), (163, "runtime_error")])
def test_verification_requires_exact_pinned_raise_location(tmp_path, line, category):
    bridge = load_bridge()
    namespace = {"private": "Cookie=COOKIE_SECRET URL_SECRET BODY_SECRET"}
    code = compile("\n" * (line - 2) + "def request():\n raise Exception(private)\nrequest()\n", str(tmp_path / "upstream/media_platform/xhs/client.py"), "exec")
    try:
        exec(code, namespace)
    except Exception as root:
        data = bridge.build_failure_diagnostic(retry_error_with_trace(root, tmp_path / "upstream"), "collecting", tmp_path / "upstream")
    assert data["root_exception_type"] == "Exception" and data["category"] == category
    assert "COOKIE_SECRET" not in json.dumps(data)


def test_names_or_generic_login_words_do_not_fabricate_platform_or_authentication_category(tmp_path):
    bridge = load_bridge()
    spoof = type("PlatformAccessError", (RuntimeError,), {})
    for root in (spoof("login expired CAPTCHA COOKIE_SECRET"), RuntimeError("login expired CAPTCHA COOKIE_SECRET")):
        data = bridge.build_failure_diagnostic(retry_error_with_trace(root, tmp_path / "upstream"), "collecting", tmp_path / "upstream")
        assert data["category"] == "runtime_error"
        manager = runners.MediaCrawlerRunner(str(tmp_path))
        receipt = manager.public(dict(task("xhs"), status="failed", dir=tmp_path, diagnostic=data))
        assert "原因尚未确定" in receipt["message"] and "登录后重试" not in receipt["message"]


@pytest.mark.parametrize("kind", ["missing", "pending", "cancelled", "success", "malformed", "fake", "subclass"])
def test_retry_future_missing_pending_failed_or_untrusted_is_bounded_unknown(tmp_path, kind):
    bridge = load_bridge()
    if kind == "fake":
        class Fake:
            def exception(self, *_args, **_kwargs):
                raise AssertionError("arbitrary Future method must not run")
        attempt = Fake()
    elif kind == "subclass":
        class Untrusted(Future):
            def exception(self, *_args, **_kwargs):
                raise AssertionError("subclass Future method must not run")
        attempt = Untrusted.construct(1, RuntimeError("COOKIE_SECRET"), True)
    else:
        attempt = Future(1)
        if kind == "cancelled":
            attempt.cancel()
        elif kind == "success":
            attempt.set_result(False)
        elif kind == "malformed":
            attempt.set_exception("COOKIE_SECRET")
    error = RetryError(attempt)
    if kind == "missing":
        del error.last_attempt
    started = time.monotonic()
    data = bridge.build_failure_diagnostic(error, "collecting", tmp_path / "upstream")
    assert time.monotonic() - started < .5
    assert data["root_exception_type"] == "unknown" and data["root_frames"] == []
    assert data["category"] == "runtime_error" and "COOKIE_SECRET" not in json.dumps(data)


def test_future_read_never_calls_overridden_methods_or_exception_string(tmp_path):
    bridge = load_bridge()

    class Poison:
        def __repr__(self):
            raise AssertionError("repr must not execute")

        def __str__(self):
            raise AssertionError("str must not execute")

    class PrivateError(RuntimeError):
        def __str__(self):
            raise AssertionError("exception str must not execute")

    root = PrivateError(Poison())
    attempt = Future.construct(1, root, True)
    attempt.exception = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("overridden future method"))
    data = bridge.build_failure_diagnostic(RetryError(attempt), "collecting", tmp_path / "upstream")
    assert data["root_exception_type"] == "PrivateError" and data["category"] == "runtime_error"


def test_future_with_locked_condition_does_not_block_diagnostics(tmp_path):
    bridge = load_bridge()
    attempt = Future.construct(1, RuntimeError("COOKIE_SECRET"), True)
    entered, release = threading.Event(), threading.Event()

    def hold():
        with attempt._condition:
            entered.set()
            release.wait(1)

    worker = threading.Thread(target=hold)
    worker.start()
    assert entered.wait(1)
    started = time.monotonic()
    try:
        data = bridge.build_failure_diagnostic(RetryError(attempt), "collecting", tmp_path / "upstream")
        assert time.monotonic() - started < .5
        assert data["root_exception_type"] == "unknown"
    finally:
        release.set()
        worker.join(2)


@pytest.mark.parametrize("kind", ["cycle", "depth"])
def test_exception_cycles_and_deep_chains_are_limited_to_eight_nodes(tmp_path, kind):
    bridge = load_bridge()
    outer = RuntimeError("COOKIE_SECRET")
    current = outer
    for _ in range(12 if kind == "depth" else 2):
        current.__cause__ = RuntimeError("URL_SECRET")
        current = current.__cause__
    if kind == "cycle":
        current.__context__ = outer
    chain, resolved = bridge._exception_chain(outer)
    assert len(chain) <= 8 and resolved is False
    data = bridge.build_failure_diagnostic(outer, "collecting", tmp_path / "upstream")
    assert data["root_exception_type"] == "unknown" and data["root_frames"] == []


@pytest.mark.parametrize("bad", ["root_type", "root_frames", "root_absolute", "root_traversal", "root_line", "root_extra", "missing_root", "v1_extra", "future_version", "unknown_category", "over4096"])
def test_v2_root_schema_rejects_forged_or_oversized_diagnostics(tmp_path, bad):
    bridge = load_bridge()
    root = diagnostic_error(tmp_path / "upstream", "COOKIE_SECRET")
    data = bridge.build_failure_diagnostic(retry_error_with_trace(root, tmp_path / "upstream"), "collecting", tmp_path / "upstream")
    if bad == "root_type":
        data["root_exception_type"] = "A" * 81
    elif bad == "root_frames":
        data["root_frames"].append(data["root_frames"][0])
    elif bad == "root_absolute":
        data["root_frames"][0]["file"] = "/private/COOKIE_SECRET.py"
    elif bad == "root_traversal":
        data["root_frames"][0]["file"] = "upstream/../COOKIE_SECRET.py"
    elif bad == "root_line":
        data["root_frames"][0]["line"] = True
    elif bad == "root_extra":
        data["root_frames"][0]["response"] = "BODY_SECRET"
    elif bad == "missing_root":
        data.pop("root_frames")
    elif bad == "v1_extra":
        data["version"] = 1
    elif bad == "future_version":
        data["version"] = 3
    elif bad == "unknown_category":
        data["category"] = "login_expired_COOKIE_SECRET"
    else:
        data["root_exception_type"] = "A" * 4097
    (tmp_path / "diagnostic.json").write_text(json.dumps(data))
    assert runners.read_failure_diagnostic(tmp_path) is None


def test_v1_diagnostics_still_read_and_v2_keeps_root_group_and_size_bounded(tmp_path):
    bridge = load_bridge()
    data = bridge.build_failure_diagnostic(diagnostic_error(tmp_path / "upstream", "BODY_SECRET"), "collecting", tmp_path / "upstream")
    assert len(data["frames"]) <= 5 and len(data["root_frames"]) <= 5
    assert len(json.dumps(data).encode()) <= 4096
    old = {key: value for key, value in data.items() if key not in {"root_exception_type", "root_frames"}}
    old["version"] = 1
    (tmp_path / "diagnostic.json").write_text(json.dumps(old))
    assert runners.read_failure_diagnostic(tmp_path) == old
    (tmp_path / "diagnostic.json").write_text(json.dumps(data))
    assert runners.read_failure_diagnostic(tmp_path) == data

