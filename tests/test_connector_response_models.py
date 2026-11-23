"""Route-level contract tests for P9-4 / P9-5 connector response models.

Uses ASGI TestClient with a mocked GitHubConnector — zero real network access.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from signal_miner.routes.connectors import (
    ConnectorListResponse,
    GitHubFetchRequest,
    GitHubFetchResponse,
    router,
)

# ---------------------------------------------------------------------------
# Response model unit tests (no HTTP needed)
# ---------------------------------------------------------------------------


def test_connector_list_response_model_shape():
    """ConnectorListResponse must serialise to ``{"connectors": [...]}``."""
    model = ConnectorListResponse(connectors=["github", "webhook"])
    data = model.model_dump()
    assert data == {"connectors": ["github", "webhook"]}


def test_github_fetch_response_model_shape():
    """GitHubFetchResponse must serialise with ingested_count (not ingested)."""
    model = GitHubFetchResponse(repo="test/repo", ingested_count=5, source_type="github")
    data = model.model_dump()
    assert data == {"repo": "test/repo", "ingested_count": 5, "source_type": "github"}
    # Must NOT have 'ingested'
    assert "ingested" not in data


def test_github_fetch_response_has_ingested_count_not_ingested_field():
    """GitHubFetchResponse field names are ingested_count, never ingested."""
    fields = GitHubFetchResponse.model_fields
    assert "ingested_count" in fields
    assert "ingested" not in fields


# ---------------------------------------------------------------------------
# Request model validation (no HTTP needed)
# ---------------------------------------------------------------------------


def test_repo_pattern_valid():
    """Valid owner/repo must parse."""
    req = GitHubFetchRequest(repo="owner/repo")
    assert req.repo == "owner/repo"


def test_repo_pattern_invalid():
    """Invalid repo format must raise validation error."""
    with pytest.raises(Exception) as exc_info:  # noqa: B017 (Pydantic ValidationError)
        GitHubFetchRequest(repo="invalid-repo")
    assert "repo" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()


def test_defaults():
    """Default state and include_comments must be correct."""
    req = GitHubFetchRequest(repo="test/repo")
    assert req.state == "all"
    assert req.include_comments is True


# ---------------------------------------------------------------------------
# Integration smoke: GET /connectors (no mocks needed)
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_connectors_list_route(client: TestClient) -> None:
    """GET /connectors must return 200 with a connectors list."""
    resp = client.get("/api/v1/connectors")
    assert resp.status_code == 200
    body = resp.json()
    assert "connectors" in body
    assert isinstance(body["connectors"], list)


def test_github_fetch_validates_repo(client: TestClient) -> None:
    """Invalid repo → 422 before any DB / connector code runs."""
    resp = client.post(
        "/api/v1/connectors/github/fetch",
        json={"repo": "no-slash"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# P9-5: Full route → response_model → JSON success path (mocked)
# ---------------------------------------------------------------------------


def _make_mock_route_app() -> TestClient:
    """Build a FastAPI app with mocked runtime + router for connector route tests."""
    app = FastAPI()

    runtime = MagicMock()
    runtime.settings.github_token = None
    app.state.runtime = runtime
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _make_mock_session_ctx():
    """Return (mock_get_session_factory_value, mock_session) for DB mocking.

    Models the real ``async_sessionmaker`` / ``AsyncSession`` shape so the
    route handler can ``async with session_factory() as session:``.
    """

    class _FakeAsyncSessionCtx:
        """Async context manager that yields *session*."""

        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, *args):
            pass

    class _FakeSessionFactory:
        """Callable that returns an async context manager (like async_sessionmaker)."""

        def __init__(self, session):
            self._session = session

        def __call__(self):
            return _FakeAsyncSessionCtx(self._session)

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    return _FakeSessionFactory(mock_session), mock_session


def test_github_fetch_success_route_returns_response_model_fields():
    """Full route → response_model → JSON path with mocked connector + DB.

    Verifies that a valid POST to /connectors/github/fetch:
    - returns 200
    - returns exactly ``{"repo", "ingested_count", "source_type"}``
    - does NOT leak ``ingested`` (which belongs to a different endpoint)
    - does not touch a real database or GitHub network
    """
    client = _make_mock_route_app()
    fake_sf, _mock_session = _make_mock_session_ctx()

    # Mock connector: yields nothing → ingested_count = 0
    mock_connector = MagicMock()
    mock_connector.source_type = "github"

    async def _empty_fetch():
        if False:
            yield  # never yields — pragma: no cover

    mock_connector.fetch.return_value = _empty_fetch()

    with (
        patch(
            "signal_miner.routes.connectors.get_session_factory",
            return_value=fake_sf,
        ),
        patch(
            "signal_miner.connectors.github_connector.GitHubConnector",
            return_value=mock_connector,
        ),
    ):
        resp = client.post(
            "/api/v1/connectors/github/fetch",
            json={"repo": "owner/repo", "state": "all"},
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body == {
        "repo": "owner/repo",
        "ingested_count": 0,
        "source_type": "github",
    }
    assert "ingested" not in body


def test_github_fetch_success_route_counts_ingested():
    """When the mocked connector yields items, ingested_count must match."""
    from signal_miner.models.feedback import FeedbackAuthor, FeedbackContent, RawFeedback

    fb = RawFeedback(
        id="rfb_test_p9_5_001",
        source_type="github",
        source_id="gh_test_repo",
        dedupe_key="gh_test_repo_1",
        external_id="1",
        external_url="https://github.com/test/repo/issues/1",
        author=FeedbackAuthor(name="tester"),
        content=FeedbackContent(subject="test", text="body"),
        context={},
    )

    client = _make_mock_route_app()
    fake_sf, mock_session = _make_mock_session_ctx()

    mock_connector = MagicMock()
    mock_connector.source_type = "github"

    async def _one_item_fetch():
        yield fb

    mock_connector.fetch.return_value = _one_item_fetch()

    with (
        patch(
            "signal_miner.routes.connectors.get_session_factory",
            return_value=fake_sf,
        ),
        patch(
            "signal_miner.connectors.github_connector.GitHubConnector",
            return_value=mock_connector,
        ),
    ):
        resp = client.post(
            "/api/v1/connectors/github/fetch",
            json={"repo": "test/repo"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested_count"] == 1
    assert body["repo"] == "test/repo"
    assert body["source_type"] == "github"
    assert "ingested" not in body

    # Verify session.add and session.commit were called
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
