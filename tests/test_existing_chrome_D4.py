"""OFFLINE tests; fixtures never prove successful real-platform collection.

The owned Chrome for Testing check routes a synthetic HTTPS page locally, and
executes exactly the production DOM expression. Ordinary Chrome is never opened.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import urlsplit, urlunsplit

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
import pytest

from signal_miner.auth import get_api_key_dependency
from signal_miner.connectors import existing_chrome as chrome
from signal_miner.routes import existing_chrome as routes
from signal_miner.routes.feedback import IngestRequest, _prepare_ingest_data
from signal_miner.settings import AppSettings

NOTE_ID = "64abcdef0123456789abcdef"
NOTE_URL = f"https://www.xiaohongshu.com/explore/{NOTE_ID}?xsec_token=fixture-access"
CID = "77abcdef0123456789abcdef"


def payload(**extra):
    return dict(tab_id="selected", mode="current", query="", url="", max_posts=1, max_comments=3, **extra)


def record():
    return {
        "url": NOTE_URL, "title": "OFFLINE 标题不能补正文", "body": "离线正文" * 300,
        "body_clipped": False, "body_limit": False, "source_time_display": "09-25 上海",
        "source_created_at": None, "comment_container_present": True,
        "comments": [
            {"text": "OFFLINE 自动统计很麻烦", "comment_id": None, "parent_comment_id": None,
             "source_time_display": "昨天", "source_created_at": None},
            {"text": "OFFLINE 导入反复重复", "comment_id": CID, "parent_comment_id": None,
             "source_time_display": "2026-11-11", "source_created_at": "2026-11-11T08:00:00+08:00"},
            {"text": "OFFLINE 希望知道原文在哪", "comment_id": "fake-ordinal-3", "parent_comment_id": None},
            {"text": "OFFLINE 第四条必须不返回", "comment_id": None},
        ],
        "cookie": "PRIVATE_COOKIE_MUST_NOT_LEAVE", "localStorage": "PRIVATE_STORAGE_MUST_NOT_LEAVE",
        "author": {"username": "ACCOUNT_MUST_NOT_LEAVE"},
    }


class FakeTransport:
    def __init__(self):
        self.closed = False
        self.calls = []
        self.url = NOTE_URL
        self.data = record()
        self.gate = None
        self.stop_calls = 0
        self.targets = [
            {"targetId": "target-selected", "type": "page", "title": "OFFLINE 笔记", "url": NOTE_URL},
            {"targetId": "personal", "type": "page", "title": "PRIVATE_TITLE", "url": "https://mail.example/private"},
            {"targetId": "account", "type": "page", "title": "PRIVATE_ACCOUNT", "url": "https://www.xiaohongshu.com/user/profile/abc"},
            {"targetId": "international", "type": "page", "title": "PRIVATE_INTL", "url": "https://www.rednote.com/explore"},
        ]

    async def command(self, method, params=None, *, session_id=None):
        self.calls.append((method, params or {}, session_id))
        if method == "Target.getTargets":
            return {"targetInfos": deepcopy(self.targets)}
        if method == "Target.getTargetInfo":
            if self.url == "closed":
                raise chrome.ChromeError("cdp_command_failed", "safe")
            return {"targetInfo": {"url": self.url}}
        if method == "Target.attachToTarget":
            return {"sessionId": "selected-session"}
        if method == "Runtime.evaluate":
            if self.gate:
                await self.gate.wait()
            if params["expression"] == chrome.NAVIGATION_DOM_SCRIPT:
                return {"result": {"value": {"url": self.url, "ready_state": "complete"}}}
            if params["expression"] == chrome.SEARCH_DOM_SCRIPT:
                return {"result": {"value": {"url": NOTE_URL}}}
            data = deepcopy(self.data)
            data["url"] = self.url
            return {"result": {"value": data}}
        if method == "Page.navigate":
            self.url = params["url"]
            return {"frameId": "owned-frame"}
        return {}

    async def stop(self):
        self.stop_calls += 1
        self.closed = True


async def connected(**kwargs):
    transport = FakeTransport()
    factory = AsyncMock(return_value=transport)
    reader = lambda: "ws://127.0.0.1:12345/devtools/browser/OFFLINE"  # noqa: E731
    collector = chrome.ExistingChromeCollector(transport_factory=factory, endpoint_reader=reader, **kwargs)
    state = await collector.connect()
    assert state["status"] == "connecting"
    await collector._connection_job
    assert collector.status()["status"] == "connected"
    tabs = await collector.tabs()
    return collector, transport, tabs["tabs"][0]["id"]


@pytest.mark.parametrize("value", [
    "https://xiaohongshu.com/", "https://www.xiaohongshu.com/explore",
    "https://www.xiaohongshu.com/search_result?keyword=test", NOTE_URL,
    "https://www.xiaohongshu.com/search_result_ai?keyword=test",
    f"https://xiaohongshu.com/discovery/item/{NOTE_ID}/",
])
def test_public_url_allowlist(value):
    assert chrome.validate_url(value) == value


@pytest.mark.parametrize("value", [
    "http://www.xiaohongshu.com/explore", "https://xiaohongshu.com.evil.test/explore",
    "https://www.xiaohongshu.com@evil.test/explore", "https://me:pw@www.xiaohongshu.com/",
    "https://www.xiaohongshu.com:443/", "https://www.xiaohongshu.com/user/profile/id",
    "https://www.rednote.com/explore", "file:///etc/passwd", "javascript:alert(1)",
    "https://www.xiaohongshu.com/explore/not-a-note", NOTE_URL + "#comment-1",
    "https://www.xiaohongshu.com\\@evil.test/explore", "https://www.xiaohongshu.com/\n",
    "https://www.xiaohongshu.com/../user/profile/id", None,
])
def test_url_rejects_account_international_and_authority_tricks(value):
    with pytest.raises(chrome.ChromeError):
        chrome.validate_url(value)


@pytest.mark.parametrize("content", [
    "9222\n/devtools/browser/fixture-id\n", "54321\n/devtools/browser\n",
])
def test_discovery_reads_both_lines_without_fixed_port(tmp_path, monkeypatch, content):
    path = tmp_path / "DevToolsActivePort"
    path.write_text(content)
    monkeypatch.setattr(chrome, "default_discovery_file", lambda: path)
    endpoint = chrome.read_endpoint()
    assert endpoint == "ws://127.0.0.1:" + str(int(content.splitlines()[0])) + content.splitlines()[1]


@pytest.mark.parametrize("content", [
    "9222", "0\n/devtools/browser/id", "65536\n/devtools/browser/id", "abc\n/devtools/browser/id",
    "1234\n/devtools/browser/../x", "1234\nhttp://evil.test", "1234\n/devtools/browser/id?secret=s",
    "1234\n/devtools/browser/id\nEXTRA", "1\n/devtools/browser/" + "x" * 5000,
])
def test_discovery_rejects_unsafe_metadata_without_echoing_it(tmp_path, monkeypatch, content):
    path = tmp_path / "DevToolsActivePort"
    path.write_text(content)
    monkeypatch.setattr(chrome, "default_discovery_file", lambda: path)
    with pytest.raises(chrome.ChromeError) as error:
        chrome.read_endpoint()
    assert error.value.code == "invalid_endpoint_metadata"
    assert content not in error.value.message


def test_discovery_missing_and_denied_are_distinct(tmp_path, monkeypatch):
    monkeypatch.setattr(chrome, "default_discovery_file", lambda: tmp_path / "missing")
    with pytest.raises(chrome.ChromeError) as missing:
        chrome.read_endpoint()
    assert missing.value.code == "remote_debugging_not_enabled_or_chrome_not_running"
    monkeypatch.setattr(chrome.os, "open", lambda *args: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(chrome.ChromeError) as denied:
        chrome.read_endpoint()
    assert denied.value.code == "browser_profile_access_denied"
    assert "登录" not in denied.value.message


def test_dom_mapping_full_body_unknown_identity_and_ingest_contract():
    result = chrome.adapt_dom(record(), payload() | {"id": "OFFLINE"})
    assert result["summary"]["post_count"] == 1
    assert result["summary"]["comment_count"] == 3
    post, first, second, third = result["items"]
    assert len(post["text"]) > 512
    assert post["text"] == record()["body"]
    assert post["subject"] != post["text"]
    assert first["external_id"] is None and third["external_id"] is None
    assert first["parent_comment_id"] is None
    assert second["external_id"] == CID
    assert first["source_created_at"] is None
    assert second["source_created_at"] == "2026-11-11T00:00:00+00:00"
    assert post["source_created_at"] is None
    for item in result["items"]:
        prepared = _prepare_ingest_data(IngestRequest.model_validate(item))
        assert prepared["context"]["capture_version"] == chrome.CAPTURE_VERSION
        assert item["source_captured_at"] is not None
        assert item["capture_method"] == "crawler"
        assert item.get("author_name") is None
    exported = json.dumps(result)
    assert "PRIVATE_COOKIE_MUST_NOT_LEAVE" not in exported
    assert "PRIVATE_STORAGE_MUST_NOT_LEAVE" not in exported
    assert "ACCOUNT_MUST_NOT_LEAVE" not in exported
    assert "第四条" not in exported


def test_dom_does_not_fill_missing_body_with_title_or_fabricate_timestamps():
    data = record() | {"body": ""}
    with pytest.raises(chrome.ChromeError) as error:
        chrome.adapt_dom(data, payload() | {"id": "OFFLINE"})
    assert error.value.code == "body_missing"
    assert chrome._absolute_time("2026-11-11") is None
    assert chrome._absolute_time("2026-11-11T00:00:00") is None
    assert chrome._absolute_time("2026-99-11T00:00:00Z") is None


def test_body_fragment_safety_cap_zero_comments_and_reply_exclusion():
    data = record() | {"body_clipped": True, "body_limit": True, "body": "长" * 100_001}
    result = chrome.adapt_dom(data, payload() | {"id": "OFFLINE", "max_comments": 0})
    assert len(result["items"]) == 1
    assert len(result["items"][0]["text"]) == 100_000
    assert result["items"][0]["raw_payload"]["body_fragment"] is True
    assert any("折叠" in reason for reason in result["summary"]["incomplete_reasons"])
    data = record()
    data["comments"][0]["parent_comment_id"] = CID
    result = chrome.adapt_dom(data, payload() | {"id": "OFFLINE", "max_comments": 1})
    assert result["summary"]["comment_count"] == 1
    assert result["items"][1]["external_id"] == CID


@pytest.mark.asyncio
async def test_status_is_inert_and_connect_is_persistent_explicit_and_tabs_are_filtered():
    touched = []
    collector = chrome.ExistingChromeCollector(endpoint_reader=lambda: touched.append(True))
    for _ in range(3):
        assert collector.status()["status"] == "disconnected"
    assert not touched
    collector, transport, tab = await connected()
    tabs = await collector.tabs()
    assert tabs["tabs"][0]["id"] == tab
    assert len(tabs["tabs"]) == 1
    assert "PRIVATE_" not in json.dumps(tabs)
    await collector.connect()
    assert collector.status()["status"] == "connected"
    assert transport.stop_calls == 0
    await collector.disconnect()
    assert transport.stop_calls == 1
    assert collector.status()["status"] == "disconnected"
    assert all(call[0] == "Target.getTargets" for call in transport.calls)


@pytest.mark.asyncio
async def test_discovery_failure_maps_truthful_local_status():
    def missing():
        raise chrome.ChromeError("remote_debugging_not_enabled_or_chrome_not_running", "not login evidence")
    factory = AsyncMock()
    collector = chrome.ExistingChromeCollector(endpoint_reader=missing, transport_factory=factory)
    assert (await collector.connect())["status"] == "connecting"
    await collector._connection_job
    assert collector.status()["status"] == "authorization_required"
    factory.assert_not_called()
    await collector.close()


@pytest.mark.asyncio
async def test_connection_cancel_closes_only_owned_transport():
    gate = asyncio.Event()
    async def factory(endpoint):
        await gate.wait()
    collector = chrome.ExistingChromeCollector(transport_factory=factory, endpoint_reader=lambda: "OFFLINE")
    await collector.connect()
    await asyncio.sleep(0.01)
    await collector.disconnect()
    assert collector.status()["status"] == "disconnected"
    assert collector._connection_job.cancelled()


@pytest.mark.asyncio
async def test_ai_search_tab_is_selectable_for_navigation_but_not_current_dom():
    collector, transport, _ = await connected()
    ai_url = "https://www.xiaohongshu.com/search_result_ai?keyword=OFFLINE"
    transport.targets = [{"targetId": "ai-page", "type": "page", "title": "OFFLINE AI 搜索", "url": ai_url}]
    transport.url = ai_url
    tab = (await collector.tabs())["tabs"][0]
    task = await collector.start(payload() | {"tab_id": tab["id"]})
    await collector._task_job
    assert collector.get(task["id"])["error"]["code"] == "invalid_target_url"
    assert not any(method == "Runtime.evaluate" for method, _, _ in transport.calls)
    task = await collector.start(payload() | {"tab_id": tab["id"], "mode": "detail", "url": NOTE_URL})
    await collector._task_job
    assert collector.get(task["id"])["status"] == "completed"
    assert transport.url == NOTE_URL
    await collector.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["current", "detail", "search"])
async def test_task_completion_borrowed_protection_and_result_boundaries(mode):
    collector, transport, tab = await connected()
    body = payload() | {"tab_id": tab, "mode": mode}
    if mode == "detail":
        body["url"] = NOTE_URL
    if mode == "search":
        body["query"] = "OFFLINE 汇总工具"
    task = await collector.start(body)
    assert task["status"] == "running" and task["terminal"] is False
    with pytest.raises(chrome.ChromeError):
        collector.results(task["id"])
    await collector._task_job
    done = collector.public(collector.get(task["id"]))
    assert done["status"] == "completed" and done["terminal"] is True
    assert collector.results(task["id"])["summary"]["item_count"] == 4
    methods = {call[0] for call in transport.calls}
    assert methods <= chrome.DOMTransport.BROWSER_METHODS | chrome.DOMTransport.SESSION_METHODS
    assert "Target.attachToTarget" in methods and "Target.detachFromTarget" in methods
    assert all(session in {None, "selected-session"} for _, _, session in transport.calls)
    await collector.close()
    assert transport.stop_calls == 1
    assert not any("close" in name.lower() or "cookie" in name.lower() or "storage" in name.lower() or "network" in name.lower() or "launch" in name.lower() for name in methods)


@pytest.mark.asyncio
async def test_busy_cancel_and_new_task_keep_batches_distinct():
    collector, transport, tab = await connected()
    transport.gate = asyncio.Event()
    first = await collector.start(payload() | {"tab_id": tab})
    with pytest.raises(chrome.ChromeError) as busy:
        await collector.start(payload() | {"tab_id": tab})
    assert busy.value.code == "task_already_running"
    stopped = await collector.stop(first["id"])
    assert stopped["status"] == "cancelled"
    with pytest.raises(chrome.ChromeError):
        collector.results(first["id"])
    transport.gate = None
    transport.data["body"] = "OFFLINE 下一批独立正文"
    second = await collector.start(payload() | {"tab_id": tab})
    await collector._task_job
    assert second["id"] != first["id"]
    assert collector.results(second["id"])["items"][0]["text"] == "OFFLINE 下一批独立正文"
    assert collector.get(first["id"])["status"] == "cancelled"
    await collector.close()


@pytest.mark.asyncio
async def test_task_total_timeout_and_disconnect_are_not_success():
    collector, transport, tab = await connected(task_timeout=0.05)
    transport.gate = asyncio.Event()
    task = await collector.start(payload() | {"tab_id": tab})
    await collector._task_job
    result = collector.get(task["id"])
    assert result["status"] == "failed" and result["error"]["code"] == "task_timeout"
    with pytest.raises(chrome.ChromeError):
        collector.results(task["id"])
    task = await collector.start(payload() | {"tab_id": tab})
    await collector.disconnect()
    assert collector.get(task["id"])["status"] == "cancelled"
    assert transport.stop_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("bad,code", [
    ("closed", "tab_closed"), ("https://www.rednote.com/explore", "invalid_target_url"),
    ("chrome-error://chromewebdata/", "invalid_target_url"),
])
async def test_closed_redirect_and_browser_error_fail_before_attach(bad, code):
    collector, transport, tab = await connected()
    transport.url = bad
    task = await collector.start(payload() | {"tab_id": tab})
    await collector._task_job
    assert collector.get(task["id"])["error"]["code"] == code
    assert not any(method == "Target.attachToTarget" for method, _, _ in transport.calls)
    await collector.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["access_gate", "body_missing", "content_missing"])
async def test_dom_error_survives_without_false_completed(code):
    collector, transport, tab = await connected(page_wait=0)
    transport.data = {"error": code}
    task = await collector.start(payload() | {"tab_id": tab})
    await collector._task_job
    assert collector.get(task["id"])["status"] == "failed"
    assert collector.get(task["id"])["error"]["code"] == code
    with pytest.raises(chrome.ChromeError):
        collector.results(task["id"])
    await collector.close()


@pytest.mark.asyncio
async def test_comments_wait_for_late_dom_and_unknown_is_distinct_from_explicit_empty():
    collector, transport, tab = await connected(comment_wait=0.3)
    transport.data["comments"] = []
    transport.data["comment_container_present"] = False
    async def add_comments():
        await asyncio.sleep(0.1)
        transport.data = record()
    late = asyncio.create_task(add_comments())
    task = await collector.start(payload() | {"tab_id": tab})
    await collector._task_job
    await late
    assert collector.results(task["id"])["summary"]["comment_count"] == 3
    transport.data["comments"] = []
    transport.data["comment_empty_explicit"] = False
    task = await collector.start(payload() | {"tab_id": tab})
    await collector._task_job
    reasons = collector.results(task["id"])["summary"]["incomplete_reasons"]
    assert any("不能认定真实零评论" in reason for reason in reasons)
    transport.data["comment_empty_explicit"] = True
    task = await collector.start(payload() | {"tab_id": tab})
    await collector._task_job
    reasons = collector.results(task["id"])["summary"]["incomplete_reasons"]
    assert not any("真实零评论" in reason for reason in reasons)
    await collector.close()


class DelayedDocumentTransport(FakeTransport):
    """Page.navigate ACKs first; target URL and document commit separately."""

    def __init__(self, *, stuck=False, redirect=None, context_change=False, empty_target_at_commit=False):
        super().__init__()
        self.url = "https://www.xiaohongshu.com/search_result_ai?keyword=OFFLINE-old"
        self.targets[0]["url"] = self.url
        self.transitions = None
        self.step = 0
        self.stuck, self.redirect, self.context_change = stuck, redirect, context_change
        self.empty_target_at_commit = empty_target_at_commit
        self.content_reads = []

    async def command(self, method, params=None, *, session_id=None):
        if method == "Page.navigate":
            self.calls.append((method, params, session_id))
            desired = params["url"]
            parsed = urlsplit(desired)
            if parsed.path == "/search_result":
                desired = urlunsplit((parsed.scheme, parsed.netloc, "/search_result/", parsed.query, ""))
            first_target = "" if self.empty_target_at_commit else self.url
            self.transitions = [(first_target, self.url), (desired, self.url), (desired, desired)]
            if self.redirect:
                self.transitions[1] = (self.redirect, self.redirect)
            self.step = 0
            return {"frameId": "owned-fixture"}
        if method == "Target.getTargetInfo" and self.transitions:
            self.calls.append((method, params, session_id))
            return {"targetInfo": {"url": self.transitions[self.step][0]}}
        if method == "Runtime.evaluate" and params["expression"] == chrome.NAVIGATION_DOM_SCRIPT and self.transitions:
            self.calls.append((method, params, session_id))
            if self.context_change and self.step == 1:
                self.context_change = False
                raise chrome.ChromeError("execution_context_changed", "safe fixture context handoff")
            document_url = self.transitions[self.step][1]
            if not self.stuck:
                self.step = min(self.step + 1, 2)
                if self.step == 2:
                    self.url = self.transitions[2][0]
            return {"result": {"value": {"url": document_url, "ready_state": "complete"}}}
        if method == "Runtime.evaluate" and params["expression"] in {chrome.SEARCH_DOM_SCRIPT, chrome.NOTE_DOM_SCRIPT}:
            # A content read in an old execution context would reproduce the bug.
            assert self.step == 2
            self.content_reads.append(params["expression"])
        return await super().command(method, params, session_id=session_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("context_change,empty_target_at_commit", [(False, False), (True, False), (False, True), (True, True)])
async def test_navigation_waits_for_target_and_document_not_just_page_navigate_ack(context_change, empty_target_at_commit):
    transport = DelayedDocumentTransport(context_change=context_change, empty_target_at_commit=empty_target_at_commit)
    collector = chrome.ExistingChromeCollector(
        transport_factory=AsyncMock(return_value=transport), endpoint_reader=lambda: "OFFLINE", page_wait=1,
    )
    await collector.connect()
    await collector._connection_job
    tab = (await collector.tabs())["tabs"][0]["id"]
    task = await collector.start(payload() | {"tab_id": tab, "mode": "search", "query": "记账软件 求推荐"})
    await collector._task_job
    done = collector.get(task["id"])
    assert done["status"] == "completed", done["error"]
    assert done["phase"] == "complete"
    assert transport.content_reads == [chrome.SEARCH_DOM_SCRIPT, chrome.NOTE_DOM_SCRIPT]
    navigations = [params["url"] for method, params, _ in transport.calls if method == "Page.navigate"]
    assert "/search_result?keyword=" in navigations[0]
    assert "type=51" in navigations[0]
    assert collector.results(task["id"])["summary"]["item_count"] == 4
    await collector.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_target_at_commit", [False, True])
async def test_navigation_old_document_times_out_without_reading_its_body(empty_target_at_commit):
    transport = DelayedDocumentTransport(stuck=True, empty_target_at_commit=empty_target_at_commit)
    collector = chrome.ExistingChromeCollector(
        transport_factory=AsyncMock(return_value=transport), endpoint_reader=lambda: "OFFLINE", page_wait=0.1,
    )
    await collector.connect()
    await collector._connection_job
    tab = (await collector.tabs())["tabs"][0]["id"]
    task = await collector.start(payload() | {"tab_id": tab, "mode": "detail", "url": NOTE_URL})
    await collector._task_job
    error = collector.get(task["id"])["error"]
    assert error["code"] == "navigation_document_timeout"
    assert error["phase"] == "navigate_note"
    assert not transport.content_reads
    await collector.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("redirect", ["https://www.rednote.com/explore", "https://www.xiaohongshu.com/user/profile/PRIVATE"])
async def test_navigation_redirect_is_immediately_rejected_not_retried(redirect):
    transport = DelayedDocumentTransport(redirect=redirect)
    collector = chrome.ExistingChromeCollector(
        transport_factory=AsyncMock(return_value=transport), endpoint_reader=lambda: "OFFLINE", page_wait=1,
    )
    await collector.connect()
    await collector._connection_job
    tab = (await collector.tabs())["tabs"][0]["id"]
    task = await collector.start(payload() | {"tab_id": tab, "mode": "detail", "url": NOTE_URL})
    await collector._task_job
    error = collector.get(task["id"])["error"]
    assert error["code"] == "invalid_target_url"
    assert error["phase"] == "navigate_note"
    assert not transport.content_reads
    assert transport.step == 1
    await collector.close()


@pytest.mark.parametrize("extra", [
    {"max_posts": 21}, {"max_posts": 2, "mode": "current"}, {"max_comments": 51}, {"max_comments": -1}, {"query": "not current"},
    {"mode": "search", "query": "one,two"}, {"mode": "search", "query": ""},
    {"mode": "detail", "url": "https://www.rednote.com/explore"},
    {"endpoint": "ws://evil.test:1234"}, {"script": "document.cookie"},
])
def test_task_request_validates_fixed_scope(extra):
    with pytest.raises(ValidationError):
        routes.ChromeTaskRequest.model_validate(payload() | extra)


@pytest.mark.asyncio
async def test_authenticated_api_contract_and_error_propagation():
    collector, transport, tab = await connected()
    app = FastAPI()
    app.state.existing_chrome = collector
    auth = get_api_key_dependency(AppSettings(api_key="OFFLINE-secret"))
    app.include_router(routes.router, prefix="/api/v1", dependencies=[Depends(auth)])
    base = "/api/v1/existing-chrome"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(base + "/status")).status_code == 401
        client.headers["X-API-Key"] = "OFFLINE-secret"
        assert (await client.get(base + "/status")).json()["status"] == "connected"
        assert (await client.get(base + "/tabs")).json()["tabs"][0]["id"] == tab
        bad = await client.post(base + "/tasks", json=payload() | {"tab_id": "stale"})
        assert bad.status_code == 404 and bad.json()["detail"]["code"] == "tab_not_found"
        started = await client.post(base + "/tasks", json=payload() | {"tab_id": tab})
        assert started.status_code == 202
        identifier = started.json()["id"]
        await collector._task_job
        assert (await client.get(base + f"/tasks/{identifier}")).json()["terminal"] is True
        assert (await client.get(base + f"/tasks/{identifier}/results")).json()["summary"]["post_count"] == 1
        assert (await client.post(base + f"/tasks/{identifier}/stop")).json()["status"] == "completed"
        assert (await client.get(base + "/tasks/missing/results")).status_code == 404
        assert (await client.post(base + "/disconnect")).json()["status"] == "disconnected"
    assert transport.stop_calls == 1


@pytest.mark.asyncio
async def test_cross_site_cannot_connect_collect_or_disconnect_even_without_api_key():
    collector = chrome.ExistingChromeCollector(endpoint_reader=lambda: pytest.fail("must not inspect Chrome"))
    app = FastAPI()
    app.state.existing_chrome = collector
    app.include_router(routes.router, prefix="/api/v1")
    base = "/api/v1/existing-chrome"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:18000") as client:
        for origin in ["https://evil.test", "http://127.0.0.1:18001", "http://localhost:18000", "null", "http://127.0.0.1:18000/evil"]:
            for path in ["/connect", "/disconnect", "/tasks"]:
                result = await client.post(base + path, headers={"Origin": origin}, json=payload())
                assert result.status_code == 403
                assert result.json()["detail"]["code"] == "cross_origin_forbidden"
        assert collector.status()["status"] == "disconnected"
        rebound = await client.post(base + "/connect", headers={"Host": "rebound.example:18000", "Origin": "http://rebound.example:18000"})
        assert rebound.status_code == 403
        for headers in [{}, {"Origin": "http://127.0.0.1:18000"}]:
            assert (await client.get(base + "/status", headers=headers)).status_code == 200
            assert (await client.post(base + "/disconnect", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_real_local_websocket_transport_and_remote_error_are_bounded():
    """Real loopback wire test, synthetic CDP server, no Chrome access."""
    from websockets.asyncio.server import serve
    seen = []
    async def handler(socket):
        async for raw in socket:
            packet = json.loads(raw)
            seen.append(packet)
            if packet["method"] == "Target.getTargets":
                result = {"targetInfos": []}
                response = {"id": packet["id"], "result": result}
            else:
                response = {"id": packet["id"], "error": {"message": "PRIVATE_REMOTE_DETAIL"}}
            await socket.send(json.dumps(response))
    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        transport = await chrome.DOMTransport.connect(f"ws://127.0.0.1:{port}/devtools/browser/OFFLINE")
        assert await transport.command("Target.getTargets") == {"targetInfos": []}
        with pytest.raises(chrome.ChromeError) as error:
            await transport.command("Target.getTargetInfo", {"targetId": "missing"})
        assert error.value.code == "cdp_command_failed"
        assert "PRIVATE_REMOTE_DETAIL" not in error.value.message
        await transport.stop()
    assert {packet["method"] for packet in seen} == {"Target.getTargets", "Target.getTargetInfo"}


class FakeSocket:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self.incoming.get()
        if value is None:
            raise StopAsyncIteration
        return value

    async def send(self, packet):
        value = json.loads(packet)
        self.sent.append(value)
        result = {"sessionId": "selected-session"} if value["method"] == "Target.attachToTarget" else {}
        await self.incoming.put(json.dumps({"id": value["id"], "result": result}))

    async def close(self):
        self.closed = True
        await self.incoming.put(None)


@pytest.mark.asyncio
async def test_wire_allowlist_and_borrowed_browser_protection():
    socket = FakeSocket()
    wire = chrome.DOMTransport(socket)
    for method in ["Browser.close", "Target.closeTarget", "Target.setAutoAttach", "Storage.getCookies", "Network.enable", "Browser.getVersion"]:
        with pytest.raises(chrome.ChromeError):
            await wire.command(method)
    with pytest.raises(chrome.ChromeError):
        await wire.command("Runtime.evaluate", {"expression": "document.cookie"}, session_id="not-attached")
    await wire.command("Target.attachToTarget", {"targetId": "selected", "flatten": True})
    with pytest.raises(chrome.ChromeError):
        await wire.command("Runtime.evaluate", {"expression": "document.cookie"}, session_id="selected-session")
    with pytest.raises(chrome.ChromeError):
        await wire.command("Page.navigate", {"url": "https://evil.test"}, session_id="selected-session")
    await wire.command("Runtime.evaluate", {"expression": chrome.NOTE_DOM_SCRIPT, "returnByValue": True}, session_id="selected-session")
    await wire.stop()
    assert socket.closed
    assert {packet["method"] for packet in socket.sent} == {"Target.attachToTarget", "Runtime.evaluate"}
    assert wire.closed


@pytest.mark.asyncio
async def test_wire_send_disconnect_has_deterministic_safe_error():
    socket = FakeSocket()
    socket.send = AsyncMock(side_effect=OSError("PRIVATE_SOCKET_DETAIL"))
    wire = chrome.DOMTransport(socket)
    with pytest.raises(chrome.ChromeError) as error:
        await wire.command("Target.getTargets")
    assert error.value.code == "transport_disconnected"
    assert "PRIVATE_SOCKET_DETAIL" not in error.value.message
    assert wire.closed
    await wire.stop()


@pytest.mark.asyncio
async def test_wire_context_handoff_has_specific_safe_error_not_generic_retry():
    socket = FakeSocket()
    async def changing_context(raw):
        packet = json.loads(raw)
        await socket.incoming.put(json.dumps({"id": packet["id"], "error": {
            "code": -32000, "message": "Execution context was destroyed. PRIVATE_NAVIGATION_DETAIL",
        }}))
    socket.send = changing_context
    wire = chrome.DOMTransport(socket)
    wire.sessions.add("selected-session")
    with pytest.raises(chrome.ChromeError) as error:
        await wire.command("Runtime.evaluate", {"expression": chrome.NAVIGATION_DOM_SCRIPT}, session_id="selected-session")
    assert error.value.code == "execution_context_changed"
    assert "PRIVATE_NAVIGATION_DETAIL" not in error.value.message
    await wire.stop()


@pytest.mark.asyncio
async def test_real_owned_browser_reads_exact_fixed_dom_script_offline():
    """A real renderer, completely synthetic HTTPS page, no ordinary Chrome."""
    playwright = pytest.importorskip("playwright.async_api")
    executable = Path.home() / "Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    if not executable.exists():
        pytest.skip("Owned Chrome for Testing fixture runtime is unavailable")
    html = f"""<!doctype html><meta charset='utf-8'>
      <main id='noteContainer'><section class='note-content'>
      <h1 id='detail-title'>OFFLINE 标题</h1><div id='detail-desc'>{'离线原文' * 300}</div>
      <div class='date'>09-25</div></section><div class='comments-container'>
      <div class='comment-item' id='comment-{CID}'><div class='content'>OFFLINE 第一条</div>
        <time datetime='2026-11-11T08:00:00+08:00'>昨天</time>
        <div class='reply-container'><div class='comment-item'><div class='content'>REPLY_MUST_NOT_LEAVE</div></div></div>
      </div><div class='comment-item' data-comment-id='fake-2'><div class='content'>OFFLINE 第二条</div></div>
      <div class='comment-item' style='display:none'><div class='content'>HIDDEN_MUST_NOT_LEAVE</div></div>
      <div class='comment-item'><div class='content'>OFFLINE 第三条</div></div>
      <div class='comment-item'><div class='content'>FOURTH_MUST_NOT_LEAVE</div></div></div></main>
      <aside class='recommend'>RECOMMENDATION_MUST_NOT_LEAVE</aside>
      <section style='display:none'>ACCOUNT_MUST_NOT_LEAVE</section>
      <script>window.__INITIAL_STATE__={{cookie:'STATE_MUST_NOT_LEAVE'}};</script>"""
    async with playwright.async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=str(executable), headless=True)
        try:
            context = await browser.new_context()
            await context.route("**/*", lambda route: route.fulfill(status=200, body=html, content_type="text/html"))
            page = await context.new_page()
            await page.goto(NOTE_URL)
            result = await page.evaluate(chrome.NOTE_DOM_SCRIPT)
            assert len(result["body"]) == 1200
            assert result["title"] == "OFFLINE 标题"
            assert len(result["comments"]) == 4
            assert result["comments"][0]["comment_id"] == CID
            assert result["comments"][1]["comment_id"] is None
            assert result["comments"][0]["source_created_at"] == "2026-11-11T08:00:00+08:00"
            assert result["source_created_at"] is None  # The comment's <time> cannot become post time.
            assert "REPLY_MUST_NOT_LEAVE" not in json.dumps(result)
            assert "HIDDEN_MUST_NOT_LEAVE" not in json.dumps(result)
            assert "RECOMMENDATION_MUST_NOT_LEAVE" not in json.dumps(result)
            assert "ACCOUNT_MUST_NOT_LEAVE" not in json.dumps(result)
            assert "STATE_MUST_NOT_LEAVE" not in json.dumps(result)
            await page.locator("#detail-desc").evaluate("el => {el.style.height='12px';el.style.overflow='hidden';}")
            assert (await page.evaluate(chrome.NOTE_DOM_SCRIPT))["body_clipped"] is True
            await page.locator(".note-content > .date").evaluate("el => el.remove()")
            assert (await page.evaluate(chrome.NOTE_DOM_SCRIPT))["source_created_at"] is None
            await page.locator("#detail-desc").evaluate("el => el.remove()")
            assert (await page.evaluate(chrome.NOTE_DOM_SCRIPT))["error"] == "body_missing"
            await page.set_content("<div class='login-modal'>OFFLINE gate</div>")
            assert (await page.evaluate(chrome.NOTE_DOM_SCRIPT))["error"] == "access_gate"
            await page.goto("https://www.xiaohongshu.com/search_result_ai?keyword=OFFLINE-old")
            assert (await page.evaluate(chrome.SEARCH_DOM_SCRIPT))["error"] == "invalid_target_url"
            await page.goto("https://www.xiaohongshu.com/search_result/?keyword=记账软件%20求推荐&type=51")
            meta = await page.evaluate(chrome.NAVIGATION_DOM_SCRIPT)
            assert meta["ready_state"] == "complete"
            assert chrome.ExistingChromeCollector._requested_document(meta["url"], "https://www.xiaohongshu.com/search_result?keyword=记账软件%20求推荐&type=51")
            await page.set_content(f"<section class='note-item'><a class='cover' href='/search_result/{NOTE_ID}?xsec_token=OFFLINE'>OFFLINE real-result-shaped link</a></section>")
            found = await page.evaluate(chrome.SEARCH_DOM_SCRIPT)
            assert f"/search_result/{NOTE_ID}?" in found["notes"][0]["search_result_href"]
        finally:
            # This process/context are test-owned, not the user's ordinary Chrome.
            await browser.close()


@pytest.mark.asyncio
async def test_multi_post_search_collects_multiple_notes_and_skips_bodyless_notes():
    second_id = "77abcdef0123456789abcdef"
    third_id = "88abcdef0123456789abcdef"

    class MultiSearchTransport(DelayedDocumentTransport):
        async def command(self, method, params=None, *, session_id=None):
            res = await super().command(method, params, session_id=session_id)
            if method == "Runtime.evaluate" and params["expression"] == chrome.SEARCH_DOM_SCRIPT:
                return {"result": {"value": {"notes": [
                    {"search_result_href": f"https://www.xiaohongshu.com/search_result/{NOTE_ID}?xsec_token=OFFLINE"},
                    {"search_result_href": f"https://www.xiaohongshu.com/search_result/{second_id}?xsec_token=OFFLINE2"},
                    {"search_result_href": f"https://www.xiaohongshu.com/search_result/{third_id}?xsec_token=OFFLINE3"},
                ]}}}
            if method == "Runtime.evaluate" and params["expression"] == chrome.NOTE_DOM_SCRIPT:
                if second_id in self.url:
                    return {"result": {"value": {"error": "body_missing"}}}
                note_data = record()
                note_data["url"] = self.url
                note_data["body"] = "OFFLINE 笔记正文 " + (third_id if third_id in self.url else NOTE_ID)
                return {"result": {"value": note_data}}
            return res

    transport = MultiSearchTransport()
    collector = chrome.ExistingChromeCollector(
        transport_factory=AsyncMock(return_value=transport), endpoint_reader=lambda: "OFFLINE", page_wait=1,
    )
    await collector.connect()
    await collector._connection_job
    tab = (await collector.tabs())["tabs"][0]["id"]
    task = await collector.start(payload() | {"tab_id": tab, "mode": "search", "query": "记账软件 求推荐", "max_posts": 3, "max_comments": 2})
    await collector._task_job
    done = collector.get(task["id"])
    assert done["status"] == "completed", done["error"]
    batch = collector.results(task["id"])
    assert batch["summary"]["post_count"] == 2
    assert batch["summary"]["comment_count"] == 4
    assert any("跳过 1 篇无正文描述" in r for r in batch["summary"]["incomplete_reasons"])
    await collector.close()
