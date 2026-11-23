"""Offline HN collector contracts; these mocks are not live acquisition evidence."""

from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from scripts import collect_community_opportunity_samples as collector
from signal_miner.routes.feedback import IngestRequest, _prepare_ingest_data

NOW = datetime(2026, 11, 3, 9, tzinfo=timezone.utc)


def hit(item_id="50340001", *, kind="ask_hn", **overrides):
    result = {
        "objectID": item_id,
        "created_at_i": int((NOW - timedelta(days=1)).timestamp()),
        "created_at": "2026-11-02T09:00:00Z",
        "author": "sample_author",
        "title": "Ask HN: Which workflow needs improvement?",
        "story_text": "<p>I copy reports &amp; charts every week.</p><p>It takes hours.</p>",
        "comment_text": "<p>I cannot export a useful report.</p>",
        "story_id": 50330000 if kind == "comment" else int(item_id),
        "story_title": "Ask HN: What is missing?",
        "story_url": "https://news.ycombinator.com/item?id=50330000",
        "parent_id": 50330001 if kind == "comment" else None,
    }
    result.update(overrides)
    return result


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def response(hits, pages=1):
    return httpx.Response(200, json={"hits": hits, "nbPages": pages})


def test_html_entities_paragraphs_links_and_literal_markup():
    assert collector.clean_html(
        "<p>Tom &amp; Sue&nbsp;need <a href='https://hn.algolia.com'>export</a>.</p>"
        "<p>&lt;literal&gt; &#x4E2D;&#25991;<br>next</p><script>bad()</script>"
    ) == "Tom & Sue need export.\n<literal> 中文\nnext"
    assert collector.clean_html(None) == ""


def test_payload_preserves_original_and_passes_actual_ingest_contract():
    original = hit(kind="comment")
    payload, reason = collector.normalize_hit(
        original, kind="comment", api_request_url=collector.API_URL,
        collected_at=NOW, cutoff=NOW - timedelta(days=30),
    )
    assert reason is None
    assert payload["text"] == "I cannot export a useful report."
    assert payload["external_url"] == "https://news.ycombinator.com/item?id=50340001"
    assert payload["raw_payload"]["original"] == original
    assert payload["raw_payload"]["parent"]["url"].endswith("id=50330001")
    assert payload["raw_payload"]["story"]["url"].endswith("id=50330000")
    assert payload["raw_payload"]["story"]["title"] == "Ask HN: What is missing?"
    assert payload["raw_payload"]["platform"] == "hacker_news"
    assert payload["raw_payload"]["published_at"] == "2026-11-02T09:00:00+00:00"
    assert payload["raw_payload"]["goldset_authorization"] == "not_assessed"
    prepared = _prepare_ingest_data(IngestRequest.model_validate(payload))
    assert prepared["external_url"] == payload["external_url"]
    assert prepared["context"]["capture_method"] == "official_api"
    assert prepared["context"]["raw_payload"] == payload["raw_payload"]


def test_title_only_ask_uses_actual_title_and_empty_comment_is_skipped():
    kwargs = {"api_request_url": collector.API_URL, "collected_at": NOW, "cutoff": NOW - timedelta(days=2)}
    payload, _ = collector.normalize_hit(hit(story_text=None), kind="ask_hn", **kwargs)
    assert payload["text"] == "Ask HN: Which workflow needs improvement?"
    payload, reason = collector.normalize_hit(hit(comment_text=""), kind="comment", **kwargs)
    assert payload is None and reason == "empty_text"


@pytest.mark.parametrize("overrides,reason", [
    ({"objectID": "1&bad=1"}, "invalid_id"),
    ({"objectID": True}, "invalid_id"),
    ({"deleted": True}, "deleted_or_dead"),
    ({"created_at_i": None, "created_at": "bad"}, "invalid_timestamp"),
    ({"created_at_i": 0}, "outside_time_window"),
    ({"created_at_i": int((NOW + timedelta(days=1)).timestamp())}, "outside_time_window"),
])
def test_invalid_hits_are_skipped_explicitly(overrides, reason):
    payload, actual = collector.normalize_hit(
        hit(**overrides), kind="ask_hn", api_request_url=collector.API_URL,
        collected_at=NOW, cutoff=NOW - timedelta(days=2),
    )
    assert payload is None and actual == reason


def test_bounded_pagination_alternates_and_propagates_filters():
    calls = []

    def handle(request):
        params = dict(request.url.params)
        calls.append(params)
        kind = params["tags"]
        number = str(50340001 + len(calls))
        return response([hit(number, kind=kind)], pages=10)

    with client_for(handle) as client:
        items, summary = collector.collect_samples(client, query="reports", days=7, limit=3, now=NOW)
    assert len(items) == 3
    assert [call["tags"] for call in calls] == ["ask_hn", "comment", "ask_hn"]
    assert [call["page"] for call in calls] == ["0", "0", "1"]
    assert all(call["query"] == "reports" for call in calls)
    assert all(call["numericFilters"] == f"created_at_i>={int((NOW - timedelta(days=7)).timestamp())}" for call in calls)
    assert all(int(call["hitsPerPage"]) <= collector.PAGE_SIZE for call in calls)
    assert summary.requests == summary.fetched == summary.collected == 3
    assert summary.skipped == 0 and summary.stop_reason == "sample_limit"


def test_duplicates_and_empty_hits_have_accurate_counts_at_request_bound():
    def handle(request):
        return response([hit()], pages=999)

    with client_for(handle) as client:
        items, summary = collector.collect_samples(client, kind="ask", limit=10, max_requests=3, now=NOW)
    assert len(items) == 1
    assert summary.requests == summary.fetched == 3
    assert summary.skipped == 2 and summary.skip_reasons == {"duplicate_id": 2}
    assert summary.collected == 1
    assert summary.status == "bounded" and summary.stop_reason == "request_limit"


def test_empty_results_are_valid_and_stop_paging():
    with client_for(lambda request: response([], pages=0)) as client:
        items, summary = collector.collect_samples(client, limit=20, now=NOW)
    assert items == [] and summary.status == "empty"
    assert summary.requests == 2 and summary.stop_reason == "sources_exhausted"
    assert summary.fetched == summary.skipped == summary.collected == 0


@pytest.mark.parametrize("api_response", [
    httpx.Response(403, text="forbidden"),
    httpx.Response(200, text="not-json"),
    httpx.Response(200, json={"error": "no hits"}),
    httpx.Response(200, json={"hits": [], "nbPages": "many"}),
])
def test_bad_responses_raise_instead_of_becoming_success(api_response):
    with client_for(lambda request: api_response) as client, pytest.raises(collector.CollectionError) as error:
        collector.collect_samples(client, now=NOW)
    assert error.value.summary.status == "error"
    assert error.value.summary.requests == 1
    assert error.value.summary.errors


def test_partial_failure_retains_accurate_read_counts():
    count = 0

    def handle(request):
        nonlocal count
        count += 1
        if count == 1:
            return response([hit()], pages=10)
        raise httpx.ReadTimeout("read timed out", request=request)

    with client_for(handle) as client, pytest.raises(collector.CollectionError) as error:
        collector.collect_samples(client, now=NOW)
    summary = error.value.summary
    assert summary.requests == 2 and summary.collected == summary.fetched == 1
    assert summary.written == 0 and "ReadTimeout" in summary.errors[0]


@pytest.mark.parametrize("arguments", [
    {"limit": 0}, {"limit": 101}, {"days": 0}, {"days": 3651},
    {"max_requests": 0}, {"max_requests": 21}, {"kind": "unknown"},
])
def test_library_rejects_unbounded_arguments(arguments):
    with client_for(lambda request: pytest.fail("must not request")) as client, pytest.raises(ValueError):
        collector.collect_samples(client, **arguments)


def test_cli_writes_only_explicit_array_and_reports_empty(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "samples.json"
    mock_client = client_for(lambda request: response([], pages=0))
    monkeypatch.setattr(collector.httpx, "Client", lambda **kwargs: mock_client)
    assert collector.main(["--output", str(destination)]) == 0
    assert json.loads(destination.read_text()) == []
    assert list(tmp_path.iterdir()) == [destination]
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "empty" and summary["written"] == 0
    assert summary["requests"] == 2 and summary["errors"] == []


def test_cli_network_failure_is_nonzero_and_writes_no_output(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "samples.json"
    mock_client = client_for(lambda request: httpx.Response(503, text="unavailable"))
    monkeypatch.setattr(collector.httpx, "Client", lambda **kwargs: mock_client)
    assert collector.main(["--output", str(destination)]) == 1
    assert not destination.exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "error" and summary["requests"] == 1
    assert summary["written"] == 0 and summary["errors"]


def test_cli_output_path_is_required_and_existing_file_is_preserved(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        collector.main([])
    assert error.value.code == 2
    destination = tmp_path / "keep.json"
    destination.write_text("keep")
    assert collector.main(["--output", str(destination)]) == 1
    assert destination.read_text() == "keep"
    assert json.loads(capsys.readouterr().out)["requests"] == 0


@pytest.mark.parametrize("arguments", [
    ["--limit", "101"], ["--days", "0"], ["--max-requests", "21"], ["--timeout", "31"],
])
def test_cli_rejects_unbounded_inputs(arguments):
    with pytest.raises(SystemExit) as error:
        collector.main([*arguments, "--output", "/tmp/never-hn.json"])
    assert error.value.code == 2


def atom_feed(*, title="有哪些好用的效率工具？", content="&lt;p&gt;每周手工复制报表 &amp;amp; 图表。&lt;/p&gt;", published="2026-11-02T09:00:00Z", updated="2026-11-02T09:00:00Z", url="https://www.v2ex.com/t/1170000#reply0"):
    published_element = f"<published>{published}</published>" if published is not None else ""
    return f'''<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"><title>V2EX 问与答</title>
    <entry><id>tag:www.v2ex.com,2005:topic/1170000</id><title>{title}</title>
    <link rel="alternate" type="text/html" href="{url}"/>
    <author><name>community_user</name></author>{published_element}<updated>{updated}</updated>
    <content type="html">{content}</content></entry></feed>'''.encode()


def test_v2ex_reads_only_allowlisted_feed_and_preserves_source_contract():
    calls = []

    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=atom_feed())

    with client_for(handle) as client:
        items, summary = collector.collect_v2ex_samples(client, limit=4, now=NOW)
    assert calls == ["https://www.v2ex.com/feed/qna.xml"]
    assert len(items) == 1 and items[0]["text"] == "每周手工复制报表 & 图表。"
    item = items[0]
    assert item["subject"] == "有哪些好用的效率工具？"
    assert item["external_url"] == "https://www.v2ex.com/t/1170000#reply0"
    assert item["raw_payload"]["platform"] == "v2ex"
    assert item["raw_payload"]["acquisition_kind"] == "public_feed"
    assert item["raw_payload"]["platform_id"] == "1170000"
    assert item["raw_payload"]["published_at"] == "2026-11-02T09:00:00+00:00"
    assert item["raw_payload"]["updated_at"] == "2026-11-02T09:00:00Z"
    assert item["raw_payload"]["original"]["content_html"] == "<p>每周手工复制报表 &amp; 图表。</p>"
    prepared = _prepare_ingest_data(IngestRequest.model_validate(item))
    assert prepared["context"]["capture_method"] == "crawler"
    assert summary.source == "v2ex" and summary.requests == summary.fetched == summary.collected == 1
    assert summary.stop_reason == "single_feed_exhausted" and "no complete" in summary.coverage_note


@pytest.mark.parametrize("kwargs,reason", [
    ({"query": "does not match"}, "query_mismatch"),
    ({"days": 1, "now": NOW + timedelta(days=2)}, "outside_time_window"),
])
def test_v2ex_filters_only_available_feed_with_accurate_skips(kwargs, reason):
    kwargs.setdefault("now", NOW)
    with client_for(lambda request: httpx.Response(200, content=atom_feed())) as client:
        items, summary = collector.collect_v2ex_samples(client, **kwargs)
    assert items == [] and summary.status == "empty"
    assert summary.fetched == summary.skipped == 1 and summary.skip_reasons == {reason: 1}


@pytest.mark.parametrize("published,reason", [
    (None, "missing_published_at"),
    ("", "missing_published_at"),
    ("   ", "missing_published_at"),
    ("not-a-date", "invalid_published_at"),
    ("2026-11-02T09:00:00", "invalid_published_at"),
])
def test_v2ex_never_substitutes_recent_updated_for_missing_or_invalid_published(published, reason):
    with client_for(lambda request: httpx.Response(200, content=atom_feed(
        published=published, updated="2026-11-03T08:00:00Z",
    ))) as client:
        items, summary = collector.collect_v2ex_samples(client, days=1, now=NOW)
    assert items == []
    assert summary.status == "empty"
    assert summary.fetched == summary.skipped == 1
    assert summary.skip_reasons == {reason: 1}


def test_v2ex_old_publication_is_not_made_recent_by_an_update():
    with client_for(lambda request: httpx.Response(200, content=atom_feed(
        published="2026-08-01T09:00:00Z", updated="2026-11-03T08:00:00Z",
    ))) as client:
        items, summary = collector.collect_v2ex_samples(client, days=30, now=NOW)
    assert items == []
    assert summary.skip_reasons == {"outside_time_window": 1}


@pytest.mark.parametrize("published,expected_count", [
    ("2026-11-01T09:00:00Z", 1),  # exactly the two-day cutoff
    ("2026-11-03T09:00:01Z", 0),  # a future publication, despite a valid update
])
def test_v2ex_publication_window_boundaries(published, expected_count):
    with client_for(lambda request: httpx.Response(200, content=atom_feed(
        published=published, updated="2026-11-02T09:00:00Z",
    ))) as client:
        items, summary = collector.collect_v2ex_samples(client, days=2, now=NOW)
    assert len(items) == expected_count
    assert summary.skip_reasons == ({} if expected_count else {"outside_time_window": 1})


@pytest.mark.parametrize("updated", ["2026-11-03T08:00:00Z", "not-a-date", ""])
def test_v2ex_publication_window_and_update_metadata_have_independent_semantics(updated):
    with client_for(lambda request: httpx.Response(200, content=atom_feed(
        published="2026-11-02T17:00:00+08:00", updated=updated,
    ))) as client:
        items, summary = collector.collect_v2ex_samples(client, days=2, now=NOW)
    assert len(items) == 1
    assert summary.skipped == 0
    payload = items[0]["raw_payload"]
    assert payload["published_at"] == "2026-11-02T09:00:00+00:00"
    assert payload["updated_at"] == (updated or "")
    assert payload["original"]["published"] == "2026-11-02T17:00:00+08:00"
    assert payload["original"]["updated"] == (updated or "")


@pytest.mark.parametrize("feed", [
    b"not-xml", b"<html>blocked</html>", b"x" * 2_000_001,
])
def test_v2ex_rejects_malformed_non_atom_or_oversize_feeds(feed):
    with client_for(lambda request: httpx.Response(200, content=feed)) as client, pytest.raises(collector.CollectionError) as error:
        collector.collect_v2ex_samples(client, now=NOW)
    assert error.value.summary.status == "error" and error.value.summary.requests == 1


def test_v2ex_source_url_is_restricted_and_node_cannot_be_a_url():
    with client_for(lambda request: httpx.Response(200, content=atom_feed(url="https://evil.invalid/t/1170000"))) as client:
        items, summary = collector.collect_v2ex_samples(client, now=NOW)
    assert items == [] and summary.skip_reasons == {"invalid_source_url": 1}
    with client_for(lambda request: pytest.fail("must not request")) as client, pytest.raises(ValueError):
        collector.collect_v2ex_samples(client, node="https://evil.invalid")


def test_v2ex_sample_limit_accounts_for_unselected_feed_entries():
    original = atom_feed()
    duplicate_entry = b"<entry>" + original.split(b"<entry>", 1)[1].split(b"</feed>", 1)[0]
    feed = original.replace(b"</feed>", duplicate_entry + b"</feed>")
    with client_for(lambda request: httpx.Response(200, content=feed)) as client:
        items, summary = collector.collect_v2ex_samples(client, limit=1, now=NOW)
    assert len(items) == 1 and summary.requests == 1
    assert summary.fetched == 2 and summary.skipped == 1
    assert summary.skip_reasons == {"beyond_sample_limit": 1}
    assert summary.stop_reason == "sample_limit"


def test_v2ex_cli_malformed_feed_fails_without_output(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "v2ex.json"
    mock_client = client_for(lambda request: httpx.Response(200, text="<html>blocked</html>"))
    monkeypatch.setattr(collector.httpx, "Client", lambda **kwargs: mock_client)
    assert collector.main(["--source", "v2ex", "--output", str(destination)]) == 1
    assert not destination.exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary["source"] == "v2ex" and summary["written"] == 0
    assert summary["status"] == "error" and "Atom" in summary["errors"][0]


def test_v2ex_cli_exports_array_and_never_calls_hn(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "v2ex.json"
    calls = []

    def handle(request):
        calls.append(str(request.url))
        recent = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        return httpx.Response(200, content=atom_feed(published=recent, updated=recent))

    mock_client = client_for(handle)
    monkeypatch.setattr(collector.httpx, "Client", lambda **kwargs: mock_client)
    assert collector.main(["--source", "v2ex", "--v2ex-node", "ideas", "--output", str(destination)]) == 0
    assert calls == ["https://www.v2ex.com/feed/ideas.xml"]
    data = json.loads(destination.read_text())
    assert len(data) == 1 and data[0]["raw_payload"]["node"] == "ideas"
    summary = json.loads(capsys.readouterr().out)
    assert summary["source"] == "v2ex" and summary["written"] == 1
