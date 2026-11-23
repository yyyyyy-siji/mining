"""OFFLINE mocked official API contract; never proves LIVE Zhihu access."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
import httpx
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
import pytest

from signal_miner.auth import get_api_key_dependency
from signal_miner.connectors.zhihu_search import ZHIHU_SEARCH_URL, preview_zhihu_search
from signal_miner.routes import connectors
from signal_miner.settings import AppSettings
from signal_miner.utils.source_platforms import get_source_platform_policy

SECRET = "OFFLINE-test-secret-not-a-real-credential"
NOW = datetime(2026, 11, 5, 6, 0, 0, tzinfo=timezone.utc)


def item(**overrides):
    value = {
        "Title": "离线结构样本：每周导出报表", "ContentType": "Article", "ContentID": "123456789",
        "ContentText": "摘要：每周重复复制报表。", "AuthorName": "离线作者",
        "Url": "https://zhuanlan.zhihu.com/p/123456789?utm_source=offline&utm_medium=openapi_platform",
        "CommentCount": 2, "VoteUpCount": 5,
        "CreateTime": int((NOW - timedelta(days=2)).timestamp()),
        "EditTime": int((NOW - timedelta(hours=1)).timestamp()),
        "CommentInfoList": [{"Content": "精选评论，仅有内容，没有评论ID。"}],
        "AuthorAvatar": "", "AuthorBadge": "", "AuthorBadgeText": "",
        "AuthorityLevel": "2", "RankingScore": 0.9,
    }
    value.update(overrides)
    return value


def payload(items=None, **overrides):
    value = {"Code": 0, "Message": "success", "Data": {
        "HasMore": False, "SearchHashId": "OFFLINE-search-id", "Items": [item()] if items is None else items,
    }}
    value.update(overrides)
    return value


def make_app(secret=SECRET, key=""):
    app = FastAPI()
    app.state.runtime = SimpleNamespace(
        settings=SimpleNamespace(zhihu_access_secret=SecretStr(secret)),
        llm=SimpleNamespace(call_structured=AsyncMock()),
    )
    dependency = get_api_key_dependency(SimpleNamespace(api_key=key))
    app.include_router(connectors.router, prefix="/api/v1", dependencies=[Depends(dependency)])
    return app


@pytest.fixture
def mock_network(monkeypatch):
    original = connectors._PreviewHTTPClient
    calls = []

    def install(handler):
        def record(request):
            calls.append(request)
            return handler(request)
        transport = httpx.MockTransport(record)
        monkeypatch.setattr(connectors, "_PreviewHTTPClient", lambda: original(transport=transport))
        return calls

    return install


async def post(app, body=None, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/api/v1/connectors/zhihu/preview", json={"query": "报表"} if body is None else body, **kwargs,
        )


async def test_status_is_read_only_boolean_readiness_and_missing_secret_is_zero_network(mock_network):
    calls = mock_network(lambda request: pytest.fail("Missing secret/status must not contact any upstream"))
    async with AsyncClient(transport=ASGITransport(app=make_app("")), base_url="http://test") as client:
        status = await client.get("/api/v1/connectors/zhihu/status")
        missing = await client.post("/api/v1/connectors/zhihu/preview", json={"query": "报表"})
    assert status.status_code == 200
    assert set(status.json()) == {"configured", "capabilities", "limitations", "setup_url", "configuration_hint"}
    assert status.json()["configured"] is False
    assert status.json()["setup_url"] == "https://developer.zhihu.com/profile"
    assert "ZHIHU_ACCESS_SECRET" in status.json()["configuration_hint"]
    assert missing.status_code == 503 and "未配置" in missing.json()["detail"]
    assert calls == []


async def test_configured_status_does_not_test_or_expose_secret(mock_network):
    calls = mock_network(lambda request: pytest.fail("Status may not consume API calls"))
    async with AsyncClient(transport=ASGITransport(app=make_app()), base_url="http://test") as client:
        response = await client.get("/api/v1/connectors/zhihu/status")
    assert response.json()["configured"] is True
    assert SECRET not in response.text
    assert "不代表" in "".join(response.json()["limitations"])
    assert calls == []


@pytest.mark.parametrize("path,method", [
    ("/api/v1/connectors/zhihu/status", "get"),
    ("/api/v1/connectors/zhihu/preview", "post"),
])
async def test_both_routes_inherit_existing_api_auth(mock_network, path, method):
    calls = mock_network(lambda request: pytest.fail("Unauthenticated request must not contact upstream"))
    async with AsyncClient(transport=ASGITransport(app=make_app(key="local-key")), base_url="http://test") as client:
        for headers in ({}, {"X-API-Key": "wrong"}):
            response = await client.request(method, path, json={"query": "报表"} if method == "post" else None, headers=headers)
            assert response.status_code == 401
    assert calls == []


@pytest.mark.parametrize("body", [
    {}, {"query": ""}, {"query": "  \t"}, {"query": "x" * 201}, {"query": 5},
    {"query": "报表", "count": 0}, {"query": "报表", "count": 11}, {"query": "报表", "count": True},
    {"query": "报表", "count": "5"}, {"query": "报表", "days": 0}, {"query": "报表", "days": 366},
    {"query": "报表", "url": "https://evil.invalid"}, {"query": "报表", "access_secret": "browser-key"},
])
async def test_invalid_input_never_contacts_network(mock_network, body):
    calls = mock_network(lambda request: pytest.fail("Invalid input must not reach network"))
    response = await post(make_app(), body)
    assert response.status_code == 422
    assert calls == []


def test_offline_success_retains_raw_item_query_id_original_utm_and_separate_times():
    original = item()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload([original]))

    with connectors._PreviewHTTPClient(transport=httpx.MockTransport(handler)) as client:
        result = preview_zhihu_search(client, access_secret=SECRET, query="  报表  ", count=5, days=30, now=NOW)
    assert len(calls) == 1
    request = calls[0]
    assert str(request.url).startswith(ZHIHU_SEARCH_URL + "?")
    assert request.headers["Authorization"] == "Bearer " + SECRET
    assert request.headers["X-Request-Timestamp"] == str(int(NOW.timestamp()))
    assert SECRET not in str(request.url)
    assert request.url.params["Query"] == "报表"
    assert request.url.params["Count"] == "5"
    assert request.url.params["SortBy"] == f"CreateTime:desc:({int((NOW - timedelta(days=30)).timestamp())},{int(NOW.timestamp())})"
    lead = result["leads"][0]
    assert lead["title"] == original["Title"] and lead["excerpt"] == original["ContentText"]
    assert lead["source_url"] == original["Url"]
    assert lead["external_id"] == original["ContentID"] and lead["entity_type"] == "article"
    assert lead["content_nature"] == "api_excerpt"
    assert lead["source_created_at"] == (NOW - timedelta(days=2)).isoformat()
    assert lead["source_updated_at"] == (NOW - timedelta(hours=1)).isoformat()
    assert lead["source_captured_at"] == NOW.isoformat()
    assert lead["curated_comments"] == [original["CommentInfoList"][0]["Content"]]
    provenance = lead["provenance"]
    assert provenance["raw_payload"]["original"] == original
    assert provenance["raw_payload"]["search_hash_id"] == "OFFLINE-search-id"
    assert provenance["raw_payload"]["request"]["Query"] == "报表"
    assert provenance["raw_payload"]["request"]["Count"] == 5
    assert provenance["excerpt_sha256"] == hashlib.sha256(original["ContentText"].encode()).hexdigest()
    assert provenance["curated_comments_nature"] == "curated_comment"
    assert result["summary"]["written"] == 0
    assert result["summary"]["opportunity_analysis_allowed"] is False
    assert SECRET not in json.dumps(result, ensure_ascii=False)
    assert "Authorization" not in json.dumps(result, ensure_ascii=False)


async def test_preview_does_not_call_llm_or_database_and_empty_is_genuine(mock_network, monkeypatch):
    calls = mock_network(lambda request: httpx.Response(200, json=payload([])))
    monkeypatch.setattr(connectors, "get_session_factory", lambda: pytest.fail("Lead preview must not use business DB"))
    app = make_app()
    response = await post(app)
    assert response.status_code == 200
    assert response.json()["leads"] == []
    assert response.json()["summary"]["status"] == "empty"
    assert len(calls) == 1
    app.state.runtime.llm.call_structured.assert_not_called()


async def test_missing_creation_author_comment_attributes_stay_unknown(mock_network):
    original = item()
    del original["CreateTime"]
    del original["AuthorName"]
    mock_network(lambda request: httpx.Response(200, json=payload([original])))
    response = await post(make_app())
    assert response.status_code == 200
    lead = response.json()["leads"][0]
    assert "source_created_at" not in lead
    assert "source_created_at" not in lead["provenance"]
    assert lead["author_name"] is None
    assert lead["curated_comments"] == [original["CommentInfoList"][0]["Content"]]
    assert "comment_id" not in json.dumps(lead)
    assert lead["source_updated_at"] != lead["source_captured_at"]


@pytest.mark.parametrize("code,expected,word", [
    (10001, 400, "参数"), (20001, 502, "鉴权"), (30001, 429, "受限"),
    (90001, 502, "异常"), (12345, 502, "未知"),
])
async def test_business_error_never_looks_like_empty_or_leaks_body(mock_network, code, expected, word):
    calls = mock_network(lambda request: httpx.Response(200, json={"Code": code, "Message": SECRET, "Data": SECRET}))
    response = await post(make_app())
    assert response.status_code == expected
    assert word in response.json()["detail"]
    assert "leads" not in response.json() and SECRET not in response.text
    assert len(calls) == 1


@pytest.mark.parametrize("code,expected", [(400, 400), (401, 502), (403, 502), (429, 429), (500, 502), (302, 502)])
async def test_http_errors_are_safe_no_redirect_or_retry(mock_network, code, expected):
    calls = mock_network(lambda request: httpx.Response(code, text=SECRET, headers={"Location": "https://evil.invalid"}))
    response = await post(make_app())
    assert response.status_code == expected
    assert SECRET not in response.text and len(calls) == 1


@pytest.mark.parametrize("replacement", [
    None, [], {"Code": "0"}, {"Code": False}, {"Code": 0, "Data": []},
    {"Code": 0, "Data": {"Items": [], "SearchHashId": "id", "HasMore": "false"}},
    {"Code": 0, "Data": {"Items": {}, "SearchHashId": "id", "HasMore": False}},
    {"Code": 0, "Data": {"Items": [], "HasMore": False}},
])
async def test_invalid_envelope_is_not_empty(mock_network, replacement):
    mock_network(lambda request: httpx.Response(200, json=replacement))
    response = await post(make_app())
    assert response.status_code == 502 and "leads" not in response.json()


@pytest.mark.parametrize("overrides", [
    {"ContentType": "video"}, {"ContentType": 1}, {"ContentID": 123}, {"ContentID": ""},
    {"Url": "https://zhihu.com.evil.invalid/p/123456789"},
    {"Url": "http://zhuanlan.zhihu.com/p/123456789"},
    {"Url": "https://user:pass@zhuanlan.zhihu.com/p/123456789"},
    {"Url": "https://zhuanlan.zhihu.com:444/p/123456789"},
    {"Url": "https://zhuanlan.zhihu.com/p/111"},
    {"Url": "https://www.zhihu.com/question/123456789"},
    {"Url": "https://zhuanlan.zhihu.com/p/123456789?access_secret=upstream-value"},
    {"ContentText": None}, {"CommentInfoList": {}}, {"CommentInfoList": ["text"]},
    {"CommentInfoList": [{"Content": 3}]}, {"CreateTime": "1710000000"}, {"CreateTime": True},
    {"EditTime": -1}, {"AuthorName": []}, {"VoteUpCount": False},
    {"RankingScore": "0.9"}, {"AuthorAvatar": []},
])
async def test_invalid_item_types_ids_and_platform_urls_are_rejected(mock_network, overrides):
    mock_network(lambda request: httpx.Response(200, json=payload([item(**overrides)])))
    response = await post(make_app())
    assert response.status_code == 502


@pytest.mark.parametrize("entity,url", [
    ("Question", "https://www.zhihu.com/question/123456789?utm_source=offline"),
    ("Answer", "https://www.zhihu.com/question/7654321/answer/123456789?utm_source=offline"),
    ("Answer", "https://www.zhihu.com/answer/123456789?utm_source=offline"),
])
async def test_known_question_answer_entities_preserve_identity(mock_network, entity, url):
    mock_network(lambda request: httpx.Response(200, json=payload([item(ContentType=entity, Url=url)])))
    response = await post(make_app())
    assert response.status_code == 200
    assert response.json()["leads"][0]["entity_type"] == entity.lower()
    assert response.json()["leads"][0]["source_url"] == url


@pytest.mark.parametrize("inject", [
    {"ContentText": SECRET}, {"Authorization": "Bearer some-other-value"},
    {"nested": {"access_secret": "another-secret"}},
    {"Secret": "another-secret"},
])
async def test_secret_echo_and_auth_fields_cannot_enter_export(mock_network, inject, caplog):
    mock_network(lambda request: httpx.Response(200, json=payload([item(**inject)])))
    response = await post(make_app())
    assert response.status_code == 502
    assert SECRET not in response.text and SECRET not in caplog.text
    assert "another-secret" not in response.text


async def test_excess_items_is_rejected_without_auto_pagination(mock_network):
    calls = mock_network(lambda request: httpx.Response(200, json=payload([item(), item()])))
    response = await post(make_app(), {"query": "报表", "count": 1})
    assert response.status_code == 502 and len(calls) == 1


class CountingStream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.consumed = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.consumed += 1
            yield chunk

    def close(self):
        self.closed = True


async def test_shared_streaming_budget_stops_before_reading_unbounded_body(mock_network):
    stream = CountingStream([b"x" * 1_000_000, b"x" * 1_000_000, b"x", b"unread"])
    calls = mock_network(lambda request: httpx.Response(200, stream=stream))
    response = await post(make_app())
    assert response.status_code == 502
    assert stream.consumed == 3 and stream.closed and len(calls) == 1


async def test_shared_timeout_is_safe(mock_network, caplog):
    def fail(request):
        raise httpx.ReadTimeout(SECRET, request=request)
    mock_network(fail)
    response = await post(make_app())
    assert response.status_code == 504 and SECRET not in response.text and SECRET not in caplog.text


async def test_zhihu_and_existing_community_share_busy_lock(mock_network):
    entered = threading.Event()
    finish = threading.Event()

    def wait(request):
        entered.set()
        assert finish.wait(timeout=3)
        return httpx.Response(200, json=payload([]))

    calls = mock_network(wait)
    async with AsyncClient(transport=ASGITransport(app=make_app()), base_url="http://test") as client:
        first = asyncio.create_task(client.post("/api/v1/connectors/zhihu/preview", json={"query": "报表"}))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            second = await client.post("/api/v1/connectors/community/preview", json={"source": "v2ex"})
            third = await client.post("/api/v1/connectors/zhihu/preview", json={"query": "报表"})
            status = await client.get("/api/v1/connectors/zhihu/status")
            assert second.status_code == third.status_code == 429
            assert status.status_code == 200 and len(calls) == 1
        finally:
            finish.set()
        assert (await first).status_code == 200


async def test_wait_timeout_does_not_release_shared_lock_while_worker_runs(mock_network, monkeypatch):
    entered = threading.Event()
    finish = threading.Event()

    def wait(request):
        entered.set()
        assert finish.wait(timeout=3)
        return httpx.Response(200, json=payload([]))

    mock_network(wait)
    monkeypatch.setattr(connectors, "COMMUNITY_WAIT_SECONDS", 0.03)
    response = await post(make_app())
    try:
        assert entered.is_set() and response.status_code == 504
        assert "可能仍在收尾" in response.json()["detail"]
        assert (await post(make_app())).status_code == 429
    finally:
        finish.set()
        for _ in range(100):
            if not connectors._community_preview_lock.locked():
                break
            await asyncio.sleep(0.01)
    assert not connectors._community_preview_lock.locked()


def test_secret_environment_setting_has_masked_repr_and_json(monkeypatch):
    monkeypatch.setenv("ZHIHU_ACCESS_SECRET", SECRET)
    settings = AppSettings(_env_file=None)
    assert isinstance(settings.zhihu_access_secret, SecretStr)
    assert settings.zhihu_access_secret.get_secret_value() == SECRET
    assert SECRET not in repr(settings)
    assert SECRET not in settings.model_dump_json()
    assert SECRET not in repr(settings.model_dump())
    assert "official_api" in get_source_platform_policy("zhihu").acquisition_methods


def test_response_does_not_mutate_original_item():
    source = payload()
    before = deepcopy(source)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=source))
    with connectors._PreviewHTTPClient(transport=transport) as client:
        preview_zhihu_search(client, access_secret=SECRET, query="报表", now=NOW)
    assert source == before
