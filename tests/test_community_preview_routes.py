"""Offline HTTP/DB assertions for web community preview; no LIVE acquisition."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
import httpx
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from signal_miner.auth import get_api_key_dependency
from signal_miner.connectors import community_samples
from signal_miner.db.models import Base, RawFeedbackRow, ThemeRow
from signal_miner.routes import connectors
from signal_miner.routes.feedback import IngestRequest, _prepare_ingest_data
from signal_miner.routes.health import router as health_router


def hit(item_id="510001", **overrides):
    result = {
        "objectID": item_id, "author": "community user", "story_id": 510001,
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "title": "Ask HN: How do you export reports?",
        "story_text": "<p>I manually export reports every week &amp; lose hours.</p>",
        "comment_text": "<p>I need a reliable report export.</p>",
        "story_title": "Ask HN: Export problems", "parent_id": 510000,
    }
    result.update(overrides)
    return result


def atom(*, published=None, updated="2026-11-04T10:00:00Z", omit_published=False):
    published = published or (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    publication = "" if omit_published else f"<published>{published}</published>"
    return f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <id>topic/1170000</id><title>导出工具&lt;img src=x&gt;</title>
      <link rel="alternate" href="https://www.v2ex.com/t/1170000#reply0"/>
      <author><name>原作者</name></author>{publication}<updated>{updated}</updated>
      <content type="html">&lt;p&gt;每周手动复制报表 &amp;amp; 图表。&lt;/p&gt;</content>
    </entry></feed>'''.encode()


def make_app(key=""):
    app = FastAPI()
    app.state.runtime = SimpleNamespace(llm=SimpleNamespace(call_structured=AsyncMock()))
    auth = get_api_key_dependency(SimpleNamespace(api_key=key))
    app.include_router(connectors.router, prefix="/api/v1", dependencies=[Depends(auth)])
    app.include_router(health_router)
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


async def post(app, payload, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v1/connectors/community/preview", json=payload, **kwargs)


@pytest.mark.parametrize("key_header,expected", [(None, 401), ("wrong", 401), ("test-key", 200)])
async def test_preview_inherits_existing_router_auth(mock_network, key_header, expected):
    calls = mock_network(lambda request: httpx.Response(200, json={"hits": [], "nbPages": 0}))
    response = await post(make_app("test-key"), {"source": "hn"}, headers={"X-API-Key": key_header} if key_header else {})
    assert response.status_code == expected
    assert len(calls) == (2 if expected == 200 else 0)


@pytest.mark.parametrize("payload", [
    {}, {"source": "reddit"}, {"source": "hn", "query": "x" * 201},
    {"source": "hn", "days": 0}, {"source": "hn", "days": 366},
    {"source": "hn", "limit": 0}, {"source": "hn", "limit": 31},
    {"source": "hn", "days": "30"}, {"source": "hn", "limit": True},
    {"source": "hn", "kind": "news"}, {"source": "v2ex", "v2ex_node": "all"},
    {"source": "hn", "url": "https://evil.invalid"},
    {"source": "hn", "output": "/tmp/unwanted.json"},
    {"source": "hn", "max_requests": 100},
    {"source": "v2ex", "node": "qna"},
])
async def test_bad_or_unknown_fields_fail_before_network(mock_network, payload):
    calls = mock_network(lambda request: pytest.fail("invalid input must not use network"))
    response = await post(make_app(), payload)
    assert response.status_code == 422
    assert calls == []


async def test_hn_returns_actual_sources_and_ingest_contract_without_llm(mock_network):
    original = hit()
    calls = mock_network(lambda request: httpx.Response(200, json={"hits": [original], "nbPages": 1}))
    app = make_app()
    response = await post(app, {"source": "hn", "limit": 1, "query": "reports", "days": 365, "kind": "ask"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["source"] == "hn"
    assert body["summary"]["requests"] == body["summary"]["fetched"] == body["summary"]["collected"] == 1
    assert body["summary"]["written"] == 0 and body["summary"]["output"] is None
    assert body["summary"]["query"] == "reports" and body["summary"]["days"] == 365
    assert body["summary"]["published_from"] < body["summary"]["published_to"]
    item = body["items"][0]
    assert item["text"] == "I manually export reports every week & lose hours."
    assert item["external_url"] == "https://news.ycombinator.com/item?id=510001"
    assert item["raw_payload"]["original"] == original
    assert item["capture_method"] == "official_api"
    assert _prepare_ingest_data(IngestRequest.model_validate(item))["external_url"] == item["external_url"]
    assert calls[0].url.params["query"] == "reports"
    assert calls[0].extensions["timeout"]["read"] <= 8
    app.state.runtime.llm.call_structured.assert_not_called()


async def test_v2ex_time_fields_public_feed_and_limit_are_preserved(mock_network):
    publication = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    calls = mock_network(lambda request: httpx.Response(200, content=atom(published=publication)))
    response = await post(make_app(), {"source": "v2ex", "v2ex_node": "ideas", "limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert [str(call.url) for call in calls] == ["https://www.v2ex.com/feed/ideas.xml"]
    assert body["summary"]["requests"] == 1
    item = body["items"][0]
    assert item["raw_payload"]["published_at"] == publication
    assert item["raw_payload"]["updated_at"] == "2026-11-04T10:00:00Z"
    assert item["raw_payload"]["acquisition_kind"] == "public_feed"
    assert item["capture_method"] == "crawler"
    assert item["text"] == "每周手动复制报表 & 图表。"
    assert _prepare_ingest_data(IngestRequest.model_validate(item))["external_url"] == item["external_url"]


async def test_v2ex_missing_publication_is_empty_not_updated_fallback(mock_network):
    mock_network(lambda request: httpx.Response(200, content=atom(omit_published=True)))
    response = await post(make_app(), {"source": "v2ex"})
    assert response.status_code == 200
    assert response.json()["items"] == []
    summary = response.json()["summary"]
    assert summary["status"] == "empty"
    assert summary["skip_reasons"] == {"missing_published_at": 1}


async def test_hn_fixed_three_request_budget_and_bounded_status(mock_network):
    calls = mock_network(lambda request: httpx.Response(200, json={"hits": [hit()], "nbPages": 100}))
    response = await post(make_app(), {"source": "hn", "limit": 30, "kind": "ask"})
    assert response.status_code == 200
    body = response.json()
    assert len(calls) == body["summary"]["requests"] == 3
    assert len(body["items"]) == 1
    assert body["summary"]["status"] == "bounded"
    assert body["summary"]["stop_reason"] == "request_limit"
    assert body["summary"]["skip_reasons"] == {"duplicate_id": 2}


@pytest.mark.parametrize("network_response", [
    httpx.Response(403, text="SECRET_INTERNAL_TOKEN"),
    httpx.Response(200, text="not json SECRET_INTERNAL_TOKEN"),
    httpx.Response(302, headers={"Location": "https://evil.invalid/SECRET_INTERNAL_TOKEN"}),
])
async def test_network_errors_are_not_empty_success_and_never_redirect(mock_network, network_response):
    calls = mock_network(lambda request: network_response)
    response = await post(make_app(), {"source": "hn"})
    assert response.status_code == 502
    assert "SECRET_INTERNAL_TOKEN" not in response.text
    assert len(calls) == 1
    assert "items" not in response.json()


async def test_network_timeout_returns_safe_504(mock_network):
    def fail(request):
        raise httpx.ReadTimeout("SECRET_INTERNAL_TOKEN", request=request)
    mock_network(fail)
    response = await post(make_app(), {"source": "hn"})
    assert response.status_code == 504
    assert "SECRET_INTERNAL_TOKEN" not in response.text


async def test_sources_exhausted_is_real_empty(mock_network):
    mock_network(lambda request: httpx.Response(200, json={"hits": [], "nbPages": 0}))
    response = await post(make_app(), {"source": "hn"})
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["summary"]["status"] == "empty"


async def test_invalid_provenance_from_collector_is_rejected_not_rendered(monkeypatch, mock_network):
    mock_network(lambda request: pytest.fail("stub collector must not read HTTP"))
    bad = {"text": "original", "external_url": "https://example.com/mock/not-real"}
    summary = community_samples.CollectionSummary(query="", days=30, limit=10, kinds=["ask_hn"])
    monkeypatch.setattr(connectors, "collect_samples", lambda *args, **kwargs: ([bad], summary))
    response = await post(make_app(), {"source": "hn"})
    assert response.status_code == 502
    assert "example.com" not in response.text


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


@pytest.mark.parametrize("source", ["hn", "v2ex"])
async def test_web_stops_stream_at_two_mb_instead_of_reading_whole_body(mock_network, source):
    stream = CountingStream([b"x" * 1_000_000, b"x" * 1_000_000, b"x", b"unread"])
    calls = mock_network(lambda request: httpx.Response(200, stream=stream))
    response = await post(make_app(), {"source": source})
    assert response.status_code == 502
    assert len(calls) == 1
    assert stream.consumed == 3 and stream.closed


async def test_compressed_response_is_rejected_before_read_or_expansion(mock_network):
    stream = CountingStream([b"never expanded or decoded"])
    calls = mock_network(lambda request: httpx.Response(
        200, headers={"Content-Encoding": "gzip"}, stream=stream,
    ))
    response = await post(make_app(), {"source": "hn"})
    assert response.status_code == 502
    assert calls[0].headers["Accept-Encoding"] == "identity"
    assert stream.consumed == 0 and stream.closed


def test_stream_accepts_exact_response_limit_and_enforces_cumulative_budget(monkeypatch):
    stream = CountingStream([b"x" * 1_000_000, b"x" * 1_000_000])
    with connectors._PreviewHTTPClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))) as client:
        response = client.get("https://hn.algolia.com/api/v1/search_by_date")
    assert len(response.content) == 2_000_000
    assert stream.consumed == 2 and stream.closed
    monkeypatch.setattr(connectors, "COMMUNITY_MAX_TOTAL_BYTES", 10)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=CountingStream([b"123456"])))
    with connectors._PreviewHTTPClient(transport=transport) as client:
        assert client.get("https://hn.algolia.com/api/v1/search_by_date").content == b"123456"
        with pytest.raises(ValueError, match="byte budget"):
            client.get("https://hn.algolia.com/api/v1/search_by_date")


def test_total_time_budget_expiry_stops_stream(monkeypatch):
    monkeypatch.setattr(connectors, "COMMUNITY_HTTP_BUDGET_SECONDS", 0)
    with (
        connectors._PreviewHTTPClient(transport=httpx.MockTransport(lambda request: pytest.fail("no network after deadline"))) as client,
        pytest.raises(httpx.TimeoutException),
    ):
        client.get("https://hn.algolia.com/api/v1/search_by_date")


def test_slow_stream_crossing_deadline_stops_before_next_chunk(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(connectors, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    class SlowStream(CountingStream):
        def __iter__(self):
            self.consumed += 1
            yield b"first"
            clock[0] = 21.0
            self.consumed += 1
            yield b"after deadline"
            self.consumed += 1
            yield b"must stay unread"

    stream = SlowStream([])
    with (
        connectors._PreviewHTTPClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))) as client,
        pytest.raises(httpx.TimeoutException),
    ):
        client.get("https://hn.algolia.com/api/v1/search_by_date")
    assert stream.consumed == 2 and stream.closed


async def test_busy_preview_does_not_block_health_and_second_request_gets_429(mock_network):
    entered = threading.Event()
    finish = threading.Event()

    def wait(request):
        entered.set()
        assert finish.wait(timeout=3)
        return httpx.Response(200, json={"hits": [], "nbPages": 0})

    mock_network(wait)
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = asyncio.create_task(client.post("/api/v1/connectors/community/preview", json={"source": "hn", "kind": "ask"}))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            health = await asyncio.wait_for(client.get("/health"), timeout=0.5)
            assert health.status_code == 200
            second = await client.post("/api/v1/connectors/community/preview", json={"source": "v2ex"})
            assert second.status_code == 429
        finally:
            finish.set()
        assert (await first).status_code == 200


async def test_http_wait_timeout_does_not_claim_thread_cancelled_or_release_busy_early(monkeypatch, mock_network):
    entered = threading.Event()
    finish = threading.Event()

    def wait(request):
        entered.set()
        assert finish.wait(timeout=3)
        return httpx.Response(200, json={"hits": [], "nbPages": 0})

    mock_network(wait)
    monkeypatch.setattr(connectors, "COMMUNITY_WAIT_SECONDS", 0.03)
    response = await post(make_app(), {"source": "hn", "kind": "ask"})
    try:
        assert entered.is_set()
        assert response.status_code == 504
        assert "可能仍在收尾" in response.json()["detail"]
        assert (await post(make_app(), {"source": "v2ex"})).status_code == 429
    finally:
        finish.set()
        # The synchronous worker really finishes before the next test begins.
        for _ in range(100):
            if not connectors._community_preview_lock.locked():
                break
            await asyncio.sleep(0.01)
    assert not connectors._community_preview_lock.locked()


async def test_preview_leaves_all_temporary_database_tables_unchanged(tmp_path, mock_network, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'preview.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all([
            RawFeedbackRow(id="existing", source_type="custom", source_id="custom_api", dedupe_key="existing", content={"text": "old"}, context={}, author={}, pipeline_profile="product_feedback"),
            ThemeRow(id="old-theme", name="Existing theme", status="reviewed"),
        ])
        await session.commit()

    async def snapshot():
        async with factory() as session:
            return {table.name: [dict(row) for row in (await session.execute(table.select())).mappings()]
                    for table in Base.metadata.sorted_tables}

    monkeypatch.setattr(connectors, "get_session_factory", lambda: factory)
    before = await snapshot()
    mock_network(lambda request: httpx.Response(200, json={"hits": [hit()], "nbPages": 1}))
    assert (await post(make_app(), {"source": "hn", "limit": 1})).status_code == 200
    assert await snapshot() == before
    await engine.dispose()


def test_packaged_collector_and_original_import_are_same_functions():
    from scripts import collect_community_opportunity_samples as wrapper

    assert wrapper.collect_samples is community_samples.collect_samples
    assert wrapper.collect_v2ex_samples is community_samples.collect_v2ex_samples
    assert wrapper.main is community_samples.main
