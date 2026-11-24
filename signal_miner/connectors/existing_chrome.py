"""Bounded DOM collection through an explicitly authorized, borrowed Chrome.

No browser process, cookie/storage API, platform HTTP client or generic script API
is used. A tiny CDP transport attaches only to the selected domestic platform target.
Closing this collector closes its WebSocket, never the browser or its targets.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit
from uuid import uuid4

from signal_miner.connectors.existing_chrome_adapter import (
    CAPTURE_VERSION,
    DEFAULT_TASK_TIMEOUT,
    HOSTS,
    MAX_COMMENTS,
    MAX_POSTS,
    MAX_TEXT,
    NOTE_PATH,
    PLATFORM_CONFIGS,
    SELECTOR_VERSION,
    SUPPORTED_PLATFORMS,
    TERMINAL,
    ChromeError,
    _absolute_time,
    _extract_detail_id,
    _now,
    adapt_dom,
    detect_platform,
    validate_url,
)
from signal_miner.connectors.existing_chrome_scripts import (
    ALLOWED_DOM_SCRIPTS,
    NAVIGATION_DOM_SCRIPT,
    NOTE_DOM_SCRIPT,
    PLATFORM_SCRIPTS,
    SEARCH_DOM_SCRIPT,
)
from signal_miner.connectors.existing_chrome_transport import DOMTransport

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "ALLOWED_DOM_SCRIPTS",
    "CAPTURE_VERSION",
    "ChromeError",
    "DEFAULT_TASK_TIMEOUT",
    "DOMTransport",
    "ExistingChromeCollector",
    "HOSTS",
    "MAX_COMMENTS",
    "MAX_POSTS",
    "MAX_TEXT",
    "NAVIGATION_DOM_SCRIPT",
    "NOTE_DOM_SCRIPT",
    "NOTE_PATH",
    "PLATFORM_CONFIGS",
    "PLATFORM_SCRIPTS",
    "SEARCH_DOM_SCRIPT",
    "SELECTOR_VERSION",
    "SUPPORTED_PLATFORMS",
    "TERMINAL",
    "_absolute_time",
    "_extract_detail_id",
    "_now",
    "adapt_dom",
    "default_discovery_file",
    "detect_platform",
    "read_endpoint",
    "validate_url",
]


def default_discovery_file() -> Path:
    """Chrome stable's default user-data root; never accepts a client path."""
    if sys.platform == "darwin":
        root = Path.home() / "Library/Application Support/Google/Chrome"
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Google/Chrome/User Data"
    else:
        root = Path(os.environ.get("CHROME_CONFIG_HOME") or os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "google-chrome"
    return root / "DevToolsActivePort"


def read_endpoint() -> str:
    """Read exactly bounded discovery metadata, never /json/version or cookies."""
    try:
        path = default_discovery_file()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError
            data = stream.read(4097)
        lines = data.decode("ascii").splitlines()
        if len(data) > 4096 or len(lines) != 2:
            raise ValueError
        port, route = lines
        if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
            raise ValueError
        if not re.fullmatch(r"/devtools/browser(?:/[A-Za-z0-9_-]{1,200})?", route):
            raise ValueError
        return f"ws://127.0.0.1:{int(port)}{route}"
    except FileNotFoundError as exc:
        raise ChromeError("remote_debugging_not_enabled_or_chrome_not_running", "未发现 Chrome 当前会话端点。请在已运行 Chrome 的 chrome://inspect/#remote-debugging 启用本次调试授权；这不代表未登录。") from exc
    except PermissionError as exc:
        raise ChromeError("browser_profile_access_denied", "宿主应用无法读取 Chrome 的连接发现文件。请检查 macOS 对宿主应用访问 Google Chrome 文件夹的授权。") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise ChromeError("invalid_endpoint_metadata", "Chrome 连接发现信息无效或尚未写入完成；未探测其他端口。") from exc



class ExistingChromeCollector:
    """One persistent connection and at most one bounded, cancellable task."""

    def __init__(self, *, transport_factory=None, endpoint_reader: Callable | None = None,
                 task_timeout: float = DEFAULT_TASK_TIMEOUT, page_wait: float = 20, comment_wait: float = 3):
        self._transport_factory = transport_factory or DOMTransport.connect
        self._endpoint_reader = endpoint_reader or read_endpoint
        self._task_timeout, self._page_wait = min(task_timeout, DEFAULT_TASK_TIMEOUT), page_wait
        self._detach_budget = min(0.5, self._task_timeout / 10)
        self._comment_wait = min(comment_wait, 5)
        self._transport = None
        self._connection_job = None
        self._task_job = None
        self._batch_job = None
        self._tabs = {}
        self._tab_meta = {}
        self._tasks = {}
        self._batches = {}
        self._status = "disconnected"
        self._message = "尚未连接当前 Chrome。"
        self._active_task = None
        self._active_batch = None
        self._lock = asyncio.Lock()

    def status(self) -> dict:
        # Pure local state: no discovery, port probing, browser access or prompt.
        state, message = self._status, self._message
        if self._transport is not None and self._transport.closed:
            state, message = "disconnected", "Chrome 传输已断开；可重新请求连接。"
        return {"status": state, "message": message, "active_task": self._active_task,
                "active_batch": self._active_batch,
                "capabilities": {"platform": "xiaohongshu", "platforms": list(SUPPORTED_PLATFORMS), "modes": ["current", "search", "detail"],
                                 "max_posts": MAX_POSTS, "max_comments": MAX_COMMENTS, "task_timeout_seconds": DEFAULT_TASK_TIMEOUT,
                                 "batch_concurrency": 3,
                                 "capture_version": CAPTURE_VERSION, "dom_scope": "loaded_public_dom_only",
                                 "browser_launch": False, "automatic_ingest": False}}

    async def connect(self) -> dict:
        async with self._lock:
            if self.status()["status"] in {"connected", "connecting"}:
                return self.status()
            if self._transport is not None:
                await self._transport.stop()
                self._transport = None
            self._status, self._message = "connecting", "正在请求连接已运行的 Chrome；请留意 Chrome 的本次授权提示。"
            self._connection_job = asyncio.create_task(self._connect())
            return self.status()

    async def _connect(self):
        try:
            if self._transport_factory == DOMTransport.connect and importlib.util.find_spec("websockets") is None:
                raise ChromeError("dependency_unavailable", "请安装项目可选依赖 signal-miner[browser]。", 503)
            endpoint = await asyncio.to_thread(self._endpoint_reader)
            self._transport = await self._transport_factory(endpoint)
            self._status, self._message = "connected", "已连接当前 Chrome；仅读取您选中的国内小红书、B站、微博、知乎或抖音页面。"
        except ChromeError as exc:
            auth = {"remote_debugging_not_enabled_or_chrome_not_running", "authorization_or_connection_timeout", "connection_not_authorized"}
            self._status = "authorization_required" if exc.code in auth else "unavailable"
            self._message = exc.message
        except asyncio.CancelledError:
            raise
        except Exception:
            self._status, self._message = "unavailable", "Chrome 连接发生未知错误；未启动浏览器或重试登录。"

    async def disconnect(self) -> dict:
        async with self._lock:
            if self._connection_job and not self._connection_job.done():
                self._connection_job.cancel()
                with suppress(asyncio.CancelledError):
                    await self._connection_job
            if self._active_task:
                await self.stop(self._active_task)
            if self._active_batch:
                await self.stop_batch(self._active_batch)
            if self._transport is not None:
                with suppress(Exception):
                    await self._transport.stop()
            self._transport, self._tabs, self._tab_meta = None, {}, {}
            self._status, self._message = "disconnected", "已断开采集连接，Chrome 和用户标签保持打开。"
            return self.status()

    async def close(self):
        await self.disconnect()

    def _connected(self):
        if self.status()["status"] != "connected":
            raise ChromeError("not_connected", "请先连接当前 Chrome。")
        return self._transport

    async def tabs(self) -> dict:
        transport = self._connected()
        response = await transport.command("Target.getTargets")
        result = []
        live = {}
        live_meta = {}
        prior = {target: temp_id for temp_id, target in self._tabs.items()}
        for info in response.get("targetInfos", []):
            if info.get("type") != "page" or not info.get("targetId"):
                continue
            try:
                url = validate_url(info.get("url"))
            except ChromeError:
                continue
            platform = detect_platform(url) or "xiaohongshu"
            temp_id = prior.get(info["targetId"]) or uuid4().hex
            title = str(info.get("title", ""))[:500]
            live[temp_id] = info["targetId"]
            live_meta[temp_id] = {"target_id": info["targetId"], "platform": platform, "url": url, "title": title}
            result.append({"id": temp_id, "title": title, "url": url, "platform": platform})
        self._tabs = live
        self._tab_meta = live_meta
        return {"tabs": result}

    async def start(self, payload: dict) -> dict:
        self._connected()
        if self._active_task or self._active_batch:
            raise ChromeError("task_already_running", "已有一个当前 Chrome 采集任务，请先等待或停止。")
        if payload["tab_id"] not in self._tabs:
            raise ChromeError("tab_not_found", "所选标签已失效，请刷新目标标签。", 404)
        identifier = uuid4().hex
        task = {**payload, "id": identifier, "status": "running", "message": "正在读取所选页面已加载的正文与评论。",
                "phase": "queued", "progress": {"current": 0, "total": payload["max_posts"], "percent": 0, "label": "已提交采集任务"},
                "error": None, "created_at": _now(), "finished_at": None, "summary": None}
        # Only the last 30 task batches are retained in this connection's memory.
        for old in list(self._tasks)[:-29]:
            self._tasks.pop(old)
        self._tasks[identifier] = task
        self._active_task = identifier
        self._task_job = asyncio.create_task(self._run(task, self._tabs[payload["tab_id"]]))
        return self.public(task)

    @staticmethod
    def public(task) -> dict:
        return {key: task.get(key) for key in ("id", "status", "phase", "progress", "mode", "tab_id", "message", "error", "created_at", "finished_at", "summary")} | {"terminal": task["status"] in TERMINAL}

    def get(self, identifier: str) -> dict:
        if identifier not in self._tasks:
            raise ChromeError("task_not_found", "当前会话中没有该采集任务。", 404)
        return self._tasks[identifier]

    async def stop(self, identifier: str) -> dict:
        task = self.get(identifier)
        if task["status"] == "running" and self._task_job:
            self._task_job.cancel()
            with suppress(asyncio.CancelledError):
                await self._task_job
            # Handles cancellation before the coroutine's first instruction.
            if task["status"] == "running":
                task.update(status="cancelled", message="采集已停止，未生成可导入批次。", finished_at=_now())
                self._active_task = None
        return self.public(task)

    def results(self, identifier: str) -> dict:
        task = self.get(identifier)
        if task["status"] != "completed":
            raise ChromeError("results_not_ready", "只有成功完成的任务才有可预览原文批次。")
        return task["result"]

    async def _run(self, task, target):
        try:
            result = await asyncio.wait_for(self._collect(task, target), self._task_timeout - self._detach_budget)
            task.update(status="completed", result=result, summary=result["summary"], message="原文材料已生成，可预览并选择导入。")
        except asyncio.CancelledError:
            task.update(status="cancelled", message="采集已停止，未生成可导入批次。")
        except TimeoutError:
            task.update(status="failed", message="采集超过总时限，未生成批次。", error={"code": "task_timeout", "message": "采集超过总时限，未生成批次。"})
        except ChromeError as exc:
            task.update(status="failed", message=exc.message, error={"code": exc.code, "message": exc.message, "phase": task["phase"]})
        except Exception:
            task.update(status="failed", message="采集发生未知错误，未生成批次。", error={"code": "unknown_collection_error", "message": "采集发生未知错误，未生成批次。"})
        finally:
            task["finished_at"] = _now()
            self._active_task = None

    async def _target_url(self, target, *, note=False, allow_pending_empty=False, platform: str | None = None):
        try:
            info = await self._connected().command("Target.getTargetInfo", {"targetId": target})
        except ChromeError as exc:
            if exc.code == "cdp_command_failed":
                raise ChromeError("tab_closed", "所选 Chrome 标签已关闭或不可访问。") from exc
            raise
        raw_url = info.get("targetInfo", {}).get("url")
        if allow_pending_empty and raw_url == "":
            return ""
        return validate_url(raw_url, note=note, platform=platform)

    async def _navigate(self, transport, target, session, url, *, platform: str | None = None):
        source_url = await self._target_url(target)
        destination = validate_url(url, platform=platform)
        resolved_platform = platform or detect_platform(destination) or "xiaohongshu"
        result = await transport.command("Page.navigate", {"url": destination}, session_id=session)
        if result.get("errorText"):
            raise ChromeError("navigation_failed", "Chrome 未能打开所选页面。")
        try:
            await asyncio.wait_for(
                self._navigation_handoff(transport, target, session, source_url, destination, platform=resolved_platform),
                self._page_wait,
            )
        except TimeoutError as exc:
            raise ChromeError("navigation_document_timeout", "等待目标文档切换超时；未读取旧页面内容。") from exc

    @staticmethod
    def _requested_document(current, destination, *, platform: str = "xiaohongshu"):
        parsed, wanted = urlsplit(current), urlsplit(destination)
        cfg = PLATFORM_CONFIGS[platform]
        note_id = _extract_detail_id(platform, wanted.path)
        if note_id:
            actual_id = _extract_detail_id(platform, parsed.path)
            return bool(actual_id and actual_id.lower() == note_id.lower())
        if unquote(parsed.path.rstrip("/")) != unquote(wanted.path.rstrip("/")):
            return False
        actual_query, expected_query = parse_qs(parsed.query), parse_qs(wanted.query)
        return all(actual_query.get(key) == expected_query.get(key) for key in cfg["search_query_keys"])

    @staticmethod
    def _same_source_document(current, source):
        parsed, prior = urlsplit(current), urlsplit(source)
        return (parsed.hostname, parsed.path.rstrip("/"), parsed.query) == (prior.hostname, prior.path.rstrip("/"), prior.query)

    async def _navigation_handoff(self, transport, target, session, source, destination, *, platform: str = "xiaohongshu"):
        nav_script = PLATFORM_SCRIPTS[platform]["navigation"]
        while True:
            # The old source is allowed only during this self-initiated navigation.
            # Chromium may also briefly report an empty targetInfo.url at commit.
            # A different domestic page, international site or error URL is fatal.
            target_url = await self._target_url(target, allow_pending_empty=True)
            target_matches = bool(target_url) and self._requested_document(target_url, destination, platform=platform)
            if target_url and not target_matches and not self._same_source_document(target_url, source):
                raise ChromeError("target_changed", "导航期间所选标签切换到了另一页面，采集停止。")
            try:
                output = await transport.command("Runtime.evaluate", {
                    "expression": nav_script, "returnByValue": True, "awaitPromise": False,
                }, session_id=session)
            except ChromeError as exc:
                if exc.code != "execution_context_changed":
                    raise
                await asyncio.sleep(0.05)
                continue
            if output.get("exceptionDetails"):
                raise ChromeError("navigation_metadata_failed", "无法核对目标文档切换状态。")
            meta = output.get("result", {}).get("value")
            if not isinstance(meta, dict) or meta.get("error"):
                raise ChromeError("invalid_target_url", "所选标签的当前文档已跳转到不支持的地址。")
            document_url = validate_url(meta.get("url"), platform=platform)
            document_matches = self._requested_document(document_url, destination, platform=platform)
            if not document_matches and not self._same_source_document(document_url, source):
                raise ChromeError("target_changed", "导航期间文档切换到了另一页面，采集停止。")
            if target_matches and document_matches and meta.get("ready_state") in {"interactive", "complete"}:
                return
            await asyncio.sleep(0.05)

    async def _dom(self, transport, target, session, *, search=False, want_comments=False, platform: str = "xiaohongshu"):
        deadline = asyncio.get_running_loop().time() + self._page_wait
        comment_deadline = None
        last_error = "content_missing"
        scripts = PLATFORM_SCRIPTS[platform]
        while True:
            await self._target_url(target, note=not search, platform=platform)
            output = await transport.command("Runtime.evaluate", {
                "expression": scripts["search"] if search else scripts["note"],
                "returnByValue": True, "awaitPromise": platform == "bilibili" and not search,
            }, session_id=session)
            if output.get("exceptionDetails"):
                raise ChromeError("dom_read_failed", "固定正文选择器未能读取所选页面。")
            record = output.get("result", {}).get("value")
            if not isinstance(record, dict):
                raise ChromeError("dom_read_failed", "固定正文选择器未返回可用材料。")
            last_error = record.get("error")
            if not last_error:
                if not search and want_comments and not record.get("comments") and not record.get("comment_empty_explicit"):
                    if comment_deadline is None:
                        comment_deadline = asyncio.get_running_loop().time() + self._comment_wait
                    if asyncio.get_running_loop().time() < comment_deadline:
                        await asyncio.sleep(0.25)
                        continue
                await self._target_url(target, note=not search, platform=platform)
                if not search:
                    validate_url(record.get("url"), note=True, platform=platform)
                return record
            if last_error in {"access_gate", "invalid_target_url"}:
                message = "所选页面出现登录或验证遮罩；本次未读取材料，未重试登录。" if last_error == "access_gate" else "所选页面已跳转到不支持的地址，采集停止。"
                raise ChromeError(last_error, message)
            if asyncio.get_running_loop().time() >= deadline:
                raise ChromeError(last_error, "未在限定时间内找到已加载的正文或实际搜索结果；未用标题补正文。")
            await asyncio.sleep(0.25)

    @staticmethod
    def _resolve_search_candidates(found: dict, search_url: str, max_posts: int, *, platform: str = "xiaohongshu") -> list[tuple[str, str | None]]:
        entries = found.get("notes")
        if not isinstance(entries, list):
            entries = [found] if (found.get("url") or found.get("search_result_href")) else []
        candidates = []
        for entry in entries[:max_posts]:
            if not isinstance(entry, dict):
                continue
            actual = entry.get("url")
            original_href = actual
            if not actual and entry.get("search_result_href"):
                href = entry["search_result_href"]
                original_href = href
                parsed = urlsplit(href)
                if parsed.fragment or parsed.hostname not in HOSTS or not re.fullmatch(r"/search_result/[a-fA-F0-9]{24}/?", parsed.path):
                    raise ChromeError("invalid_search_result", "实际搜索结果链接超出支持范围。")
                actual = urlunsplit((parsed.scheme, parsed.netloc, "/explore/" + parsed.path.rstrip("/").split("/")[-1], parsed.query, ""))
                validate_url(actual, note=True, platform=platform)
            resolved = validate_url(urljoin(search_url, actual or ""), note=True, platform=platform)
            candidates.append((resolved, original_href))
        if not candidates:
            raise ChromeError("search_result_missing", f"未在当前搜索结果中找到可用的{PLATFORM_CONFIGS[platform]['label']}内容链接。")
        return candidates

    @staticmethod
    def _merge_note_batches(batches: list[dict], task: dict, *, skipped_empty: int = 0) -> dict:
        if len(batches) == 1 and not skipped_empty:
            return batches[0]
        items = [item for batch in batches for item in batch["items"]]
        posts = sum(batch["summary"]["post_count"] for batch in batches)
        comments = sum(batch["summary"]["comment_count"] for batch in batches)
        incomplete = []
        for batch in batches:
            for reason in batch["summary"]["incomplete_reasons"]:
                if reason not in incomplete:
                    incomplete.append(reason)
        if skipped_empty:
            incomplete.append(f"跳过 {skipped_empty} 篇无正文描述的搜索结果（如纯图/视频笔记）。")
        coverage = f"共 {posts} 篇已加载笔记描述正文（请求上限 {task['max_posts']} 篇），每篇最多 {task['max_comments']} 条已加载顶层评论；不遍历或加载更多。"
        coverages = {batch["summary"]["comment_coverage"] for batch in batches}
        comment_coverage = "not_requested" if not task["max_comments"] else "loaded_comments" if comments > 0 else "explicit_empty" if coverages == {"explicit_empty"} else "unknown"
        return {
            "items": items,
            "summary": {
                "post_count": posts,
                "comment_count": comments,
                "item_count": len(items),
                "comment_coverage": comment_coverage,
                "coverage": coverage,
                "incomplete_reasons": incomplete,
                "capture_version": CAPTURE_VERSION,
                "source_captured_at": batches[-1]["summary"]["source_captured_at"],
            },
        }

    @staticmethod
    def _set_progress(task, *, phase: str, current: int, total: int, percent: int, label: str):
        task["phase"] = phase
        task["progress"] = {"current": current, "total": total, "percent": max(0, min(100, percent)), "label": label}

    async def _collect(self, task, target):
        transport = self._connected()
        platform = task.get("platform")
        self._set_progress(task, phase="validate_source", current=0, total=task["max_posts"], percent=5, label="正在校验当前标签")
        initial_url = await self._target_url(target, note=task["mode"] == "current", platform=platform)
        if not platform:
            platform = detect_platform(task.get("url") or initial_url) or "xiaohongshu"
            task["platform"] = platform
        cfg = PLATFORM_CONFIGS[platform]
        attached = await transport.command("Target.attachToTarget", {"targetId": target, "flatten": True})
        session = attached["sessionId"]
        try:
            if task["mode"] == "search":
                self._set_progress(task, phase="navigate_search", current=0, total=task["max_posts"], percent=10, label=f"正在打开{cfg['label']}搜索结果页")
                search_url = cfg["search_url"](task["query"])
                await self._navigate(transport, target, session, search_url, platform=platform)
                self._set_progress(task, phase="read_search_results", current=0, total=task["max_posts"], percent=18, label="正在提取搜索结果列表")
                found = await self._dom(transport, target, session, search=True, platform=platform)
                candidates = self._resolve_search_candidates(found, search_url, task["max_posts"], platform=platform)
                total = len(candidates)
                batches, skipped_empty = [], 0
                for index, (resolved, original_href) in enumerate(candidates, start=1):
                    self._set_progress(task, phase="navigate_note", current=index - 1, total=total, percent=20 + int((index - 1) / total * 75), label=f"正在打开第 {index}/{total} 条内容")
                    await self._navigate(transport, target, session, resolved, platform=platform)
                    expected_note_id = _extract_detail_id(platform, urlsplit(resolved).path)
                    self._set_progress(task, phase="read_note", current=index - 1, total=total, percent=20 + int((index - 0.5) / total * 75), label=f"正在读取第 {index}/{total} 条内容与评论")
                    try:
                        record = await self._dom(transport, target, session, want_comments=task["max_comments"] > 0, platform=platform)
                        if _extract_detail_id(platform, urlsplit(record["url"]).path) != expected_note_id:
                            raise ChromeError("target_changed", "所选标签已切换到另一条内容，本次材料未生成。")
                        note_result = adapt_dom(record, task)
                    except ChromeError as exc:
                        if exc.code in {"body_missing", "content_missing"} and len(candidates) > 1:
                            skipped_empty += 1
                            continue
                        raise
                    if original_href:
                        for item in note_result["items"]:
                            item["raw_payload"]["search_result_href"] = original_href
                            item["raw_payload"]["navigated_note_url"] = record["url"]
                    batches.append(note_result)
                    self._set_progress(task, phase="read_note", current=index, total=total, percent=20 + int(index / total * 75), label=f"已完成第 {index}/{total} 条内容读取")
                if not batches:
                    raise ChromeError("body_missing", "搜索结果中的条目均未找到已加载的正文；标题不能代替正文。")
                result = self._merge_note_batches(batches, task, skipped_empty=skipped_empty)
                self._set_progress(task, phase="complete", current=total, total=total, percent=100, label="采集完成")
                return result

            if task["mode"] == "detail":
                self._set_progress(task, phase="navigate_note", current=0, total=1, percent=35, label="正在打开指定链接")
                await self._navigate(transport, target, session, validate_url(task["url"], note=True, platform=platform), platform=platform)
                expected_note_id = _extract_detail_id(platform, urlsplit(task["url"]).path)
            else:
                expected_note_id = _extract_detail_id(platform, urlsplit(initial_url).path)
            self._set_progress(task, phase="read_note", current=0, total=1, percent=70, label="正在读取正文与评论")
            record = await self._dom(transport, target, session, want_comments=task["max_comments"] > 0, platform=platform)
            if _extract_detail_id(platform, urlsplit(record["url"]).path) != expected_note_id:
                raise ChromeError("target_changed", "所选标签已切换到另一条内容，本次材料未生成。")
            result = adapt_dom(record, task)
            self._set_progress(task, phase="complete", current=1, total=1, percent=100, label="采集完成")
            return result
        finally:
            # Detach our session only, even on timeout/cancel. Do not close target.
            with suppress(Exception):
                await asyncio.wait_for(
                    transport.command("Target.detachFromTarget", {"sessionId": session}),
                    self._detach_budget,
                )

    # ------------------------------------------------------------------
    # Multi-platform concurrent batch collection
    # ------------------------------------------------------------------

    async def start_batch(self, payload: dict) -> dict:
        self._connected()
        if self._active_task or self._active_batch:
            raise ChromeError("task_already_running", "已有一个当前 Chrome 采集任务，请先等待或停止。")
        tab_ids = list(dict.fromkeys(payload.get("tab_ids") or []))
        if not tab_ids:
            raise ChromeError("tab_not_found", "请至少选择一个平台标签。", 422)
        missing = [tid for tid in tab_ids if tid not in self._tabs]
        if missing:
            raise ChromeError("tab_not_found", "所选标签中有已失效的页面，请刷新目标标签后重试。", 404)

        batch_id = uuid4().hex
        mode = payload.get("mode", "search")
        max_posts = int(payload.get("max_posts", 5)) if mode == "search" else 1
        max_comments = int(payload.get("max_comments", 10))
        subtasks = []
        for tid in tab_ids:
            meta = self._tab_meta.get(tid, {})
            platform = meta.get("platform") or "xiaohongshu"
            label = PLATFORM_CONFIGS.get(platform, {}).get("label", platform)
            subtasks.append({
                "id": uuid4().hex,
                "tab_id": tid,
                "target_id": self._tabs[tid],
                "platform": platform,
                "platform_label": label,
                "title": meta.get("title", ""),
                "mode": mode,
                "query": payload.get("query", ""),
                "url": "",
                "max_posts": max_posts,
                "max_comments": max_comments,
                "pipeline_profile": payload.get("pipeline_profile") or "product_feedback",
                "status": "queued",
                "phase": "queued",
                "progress": {"current": 0, "total": max_posts, "percent": 0, "label": f"{label}：排队中"},
                "message": "等待开始采集",
                "error": None,
                "summary": None,
                "items": [],
                "created_at": _now(),
                "finished_at": None,
            })

        batch = {
            "id": batch_id,
            "status": "running",
            "mode": mode,
            "query": payload.get("query", ""),
            "max_posts": max_posts,
            "max_comments": max_comments,
            "pipeline_profile": payload.get("pipeline_profile") or "product_feedback",
            "concurrency": max(1, min(3, int(payload.get("concurrency", 3)))),
            "created_at": _now(),
            "finished_at": None,
            "message": f"正在并发采集 {len(subtasks)} 个平台标签…",
            "subtasks": subtasks,
            "summary": None,
            "result": None,
        }
        for old in list(self._batches)[:-19]:
            self._batches.pop(old)
        self._batches[batch_id] = batch
        self._active_batch = batch_id
        self._batch_job = asyncio.create_task(self._run_batch(batch))
        return self.public_batch(batch)

    def get_batch(self, batch_id: str) -> dict:
        if batch_id not in self._batches:
            raise ChromeError("task_not_found", "当前会话中没有该多平台采集批次。", 404)
        return self._batches[batch_id]

    @staticmethod
    def _rebuild_batch_result(batch: dict) -> None:
        all_items: list[dict] = []
        by_platform: dict[str, dict] = {}
        completed_tabs = 0
        failed_tabs = 0
        total_posts = 0
        total_comments = 0
        for st in batch["subtasks"]:
            p = st["platform"]
            st_items = st.get("items") or []
            if st["status"] == "completed":
                completed_tabs += 1
                all_items.extend(st_items)
                p_posts = sum(1 for it in st_items if it.get("entity_type") == "post")
                p_comments = len(st_items) - p_posts
                total_posts += p_posts
                total_comments += p_comments
            elif st["status"] == "failed":
                failed_tabs += 1
            entry = by_platform.setdefault(
                p,
                {
                    "platform": p,
                    "label": st["platform_label"],
                    "status": st["status"],
                    "post_count": 0,
                    "comment_count": 0,
                    "item_count": 0,
                    "error": st["error"],
                },
            )
            if st["status"] == "completed":
                p_posts = sum(1 for it in st_items if it.get("entity_type") == "post")
                entry["post_count"] += p_posts
                entry["comment_count"] += len(st_items) - p_posts
                entry["item_count"] += len(st_items)
                entry["status"] = "completed"
                entry["error"] = None
            elif entry["status"] != "completed":
                entry["status"] = st["status"]
                entry["error"] = st["error"]

        summary = {
            "post_count": total_posts,
            "comment_count": total_comments,
            "item_count": len(all_items),
            "completed_tabs": completed_tabs,
            "failed_tabs": failed_tabs,
            "total_tabs": len(batch["subtasks"]),
            "by_platform": by_platform,
            "coverage": f"多平台共完成 {completed_tabs}/{len(batch['subtasks'])} 个标签，合计正文 {total_posts} 篇、评论 {total_comments} 条。",
            "capture_version": CAPTURE_VERSION,
            "source_captured_at": _now(),
        }
        batch["summary"] = summary
        batch["result"] = {"items": all_items, "summary": summary}

    @staticmethod
    def public_batch(batch: dict) -> dict:
        subtasks = batch["subtasks"]
        total_pct = int(sum((st.get("progress") or {}).get("percent", 0) for st in subtasks) / max(len(subtasks), 1))
        completed_n = sum(1 for st in subtasks if st["status"] == "completed")
        failed_n = sum(1 for st in subtasks if st["status"] == "failed")
        return {
            "id": batch["id"],
            "status": batch["status"],
            "terminal": batch["status"] in TERMINAL,
            "mode": batch["mode"],
            "query": batch["query"],
            "max_posts": batch["max_posts"],
            "max_comments": batch["max_comments"],
            "pipeline_profile": batch["pipeline_profile"],
            "message": batch["message"],
            "created_at": batch["created_at"],
            "finished_at": batch["finished_at"],
            "progress": {
                "current": completed_n + failed_n,
                "total": len(subtasks),
                "percent": 100 if batch["status"] == "completed" else total_pct,
                "label": batch["message"],
            },
            "summary": batch["summary"],
            "subtasks": [
                {
                    "id": st["id"],
                    "tab_id": st["tab_id"],
                    "platform": st["platform"],
                    "platform_label": st["platform_label"],
                    "title": st["title"],
                    "status": st["status"],
                    "phase": st["phase"],
                    "progress": st["progress"],
                    "message": st["message"],
                    "error": st["error"],
                    "summary": st["summary"],
                    "item_count": len(st.get("items") or []),
                }
                for st in subtasks
            ],
        }

    async def _run_single_subtask(self, st: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            st["status"] = "running"
            st["message"] = f"正在采集 {st['platform_label']}…"
            try:
                res = await asyncio.wait_for(
                    self._collect(st, st["target_id"]),
                    self._task_timeout - self._detach_budget,
                )
                st["items"] = res["items"]
                st["summary"] = res["summary"]
                st["status"] = "completed"
                st["error"] = None
                st["message"] = f"采集完成：{res['summary']['post_count']} 篇正文、{res['summary']['comment_count']} 条评论"
                self._set_progress(st, phase="complete", current=st["max_posts"], total=st["max_posts"], percent=100, label=st["message"])
            except asyncio.CancelledError:
                st["status"] = "cancelled"
                st["message"] = "已取消"
                raise
            except TimeoutError:
                st["status"] = "failed"
                st["error"] = {"code": "task_timeout", "message": f"{st['platform_label']} 采集超过总时限。"}
                st["message"] = st["error"]["message"]
            except ChromeError as exc:
                st["status"] = "failed"
                st["error"] = {"code": exc.code, "message": exc.message, "phase": st["phase"]}
                st["message"] = exc.message
            except Exception:
                st["status"] = "failed"
                st["error"] = {"code": "unknown_collection_error", "message": f"{st['platform_label']} 采集发生未知错误。"}
                st["message"] = st["error"]["message"]
            finally:
                st["finished_at"] = _now()

    async def _run_batch(self, batch: dict, target_subtasks: list[dict] | None = None) -> None:
        sem = asyncio.Semaphore(batch["concurrency"])
        to_run = target_subtasks if target_subtasks is not None else batch["subtasks"]
        try:
            await asyncio.gather(*(self._run_single_subtask(st, sem) for st in to_run))
            self._rebuild_batch_result(batch)
            completed_n = sum(1 for st in batch["subtasks"] if st["status"] == "completed")
            failed_n = sum(1 for st in batch["subtasks"] if st["status"] == "failed")
            if completed_n > 0:
                batch["status"] = "completed"
                batch["message"] = (
                    f"多平台采集完成：{completed_n} 个平台成功"
                    + (f"，{failed_n} 个平台失败（可单独重试）" if failed_n else "")
                    + f"，共 {batch['summary']['item_count']} 条原文材料。"
                )
            else:
                batch["status"] = "failed"
                batch["message"] = f"所选 {failed_n} 个平台均未采集到材料，请检查对应标签状态后重试。"
        except asyncio.CancelledError:
            batch["status"] = "cancelled"
            batch["message"] = "多平台采集已停止。"
        finally:
            batch["finished_at"] = _now()
            self._active_batch = None

    async def retry_batch_tab(self, batch_id: str, tab_id: str) -> dict:
        self._connected()
        if self._active_task or self._active_batch:
            raise ChromeError("task_already_running", "当前有正在运行的采集任务，请先等待完成。")
        batch = self.get_batch(batch_id)
        subtask = next((st for st in batch["subtasks"] if st["tab_id"] == tab_id), None)
        if subtask is None:
            raise ChromeError("tab_not_found", "该批次中未找到指定平台标签。", 404)
        if tab_id not in self._tabs:
            raise ChromeError("tab_not_found", "该标签页已关闭或失效，请先刷新目标标签。", 404)
        subtask["target_id"] = self._tabs[tab_id]
        subtask["status"] = "queued"
        subtask["phase"] = "queued"
        subtask["error"] = None
        subtask["items"] = []
        subtask["summary"] = None
        subtask["finished_at"] = None
        subtask["progress"] = {"current": 0, "total": subtask["max_posts"], "percent": 0, "label": f"正在重试 {subtask['platform_label']}"}
        batch["status"] = "running"
        batch["finished_at"] = None
        batch["message"] = f"正在重试 {subtask['platform_label']}…"
        self._active_batch = batch_id
        self._batch_job = asyncio.create_task(self._run_batch(batch, target_subtasks=[subtask]))
        return self.public_batch(batch)

    async def stop_batch(self, batch_id: str) -> dict:
        batch = self.get_batch(batch_id)
        if batch["status"] == "running" and self._batch_job:
            self._batch_job.cancel()
            with suppress(asyncio.CancelledError):
                await self._batch_job
            if batch["status"] == "running":
                batch.update(status="cancelled", message="多平台采集已停止。", finished_at=_now())
                self._active_batch = None
        return self.public_batch(batch)

    def batch_results(self, batch_id: str) -> dict:
        batch = self.get_batch(batch_id)
        if batch["status"] != "completed" or not batch.get("result"):
            raise ChromeError("results_not_ready", "只有至少有一个平台成功完成的批次才有可预览结果。")
        return batch["result"]
