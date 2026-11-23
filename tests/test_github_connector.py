"""Tests for the GitHub Issues connector."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signal_miner.connectors.github_connector import GitHubConnector

# ---------------------------------------------------------------------------
# Fake GitHub API fixtures
# ---------------------------------------------------------------------------

def fake_issue(number: int, title: str, body: str, user: str, labels: list[str],
               state: str = "open", is_pr: bool = False) -> dict:
    """Build a fake GitHub API issue response."""
    item: dict = {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "user": {"login": user},
        "labels": [{"name": lb} for lb in labels],
        "html_url": f"https://github.com/owner/repo/issues/{number}",
        "created_at": "2026-05-01T12:00:00Z",
        "reactions": {"total_count": 3},
    }
    if is_pr:
        item["pull_request"] = {"url": f"https://api.github.com/repos/owner/repo/pulls/{number}"}
    return item


def fake_comment(comment_id: int, body: str, user: str) -> dict:
    """Build a fake GitHub API comment response."""
    return {
        "id": comment_id,
        "body": body,
        "user": {"login": user},
        "html_url": f"https://github.com/owner/repo/issues/1#issuecomment-{comment_id}",
        "created_at": "2026-05-02T10:00:00Z",
    }


def mock_rate_limit_headers(remaining: int = 5000) -> dict:
    """Build mock rate limit headers."""
    return {
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": "9999999999",
    }


# ---------------------------------------------------------------------------
# Unit tests: __init__
# ---------------------------------------------------------------------------

def test_init_default():
    """Verify default parameter initialisation."""
    connector = GitHubConnector("owner/repo")
    assert connector.source_type == "github"
    assert connector._repo == "owner/repo"
    assert connector._source_id == "github_owner_repo"
    assert connector._state == "all"
    assert connector._include_comments is True
    assert connector._labels == []


def test_init_custom_params():
    """Verify custom label / state / since / source_id parameters."""
    connector = GitHubConnector(
        "owner/repo",
        labels=["bug", "feature"],
        state="open",
        since="2026-01-01T00:00:00Z",
        source_id="custom_source",
        include_comments=False,
    )
    assert connector._labels == ["bug", "feature"]
    assert connector._state == "open"
    assert connector._since == "2026-01-01T00:00:00Z"
    assert connector._source_id == "custom_source"
    assert connector._include_comments is False


# ---------------------------------------------------------------------------
# Unit tests: field mapping
# ---------------------------------------------------------------------------

def test_field_mapping():
    """Verify GitHub API issue fields map correctly to RawFeedback."""
    issue = fake_issue(1, "Bug: export broken", "The export button doesn't work.", "alice", ["bug"])
    connector = GitHubConnector("owner/repo")
    feedback = connector._issue_to_feedback(issue)

    assert feedback.source_type == "github"
    assert feedback.external_id == "1"
    assert feedback.external_url == "https://github.com/owner/repo/issues/1"
    assert feedback.content.subject == "Bug: export broken"
    assert feedback.content.text == "The export button doesn't work."
    assert feedback.author.name == "alice"
    assert feedback.context["labels"] == ["bug"]
    assert feedback.context["state"] == "open"
    assert feedback.source_created_at is not None


def test_dedupe_key_stability():
    """Verify dedupe_key is stable for the same issue."""
    issue = fake_issue(42, "title", "body", "user", [])
    connector = GitHubConnector("owner/repo")

    feedback1 = connector._issue_to_feedback(issue)
    feedback2 = connector._issue_to_feedback(issue)

    assert feedback1.dedupe_key == feedback2.dedupe_key
    assert "github_owner_repo_42" in feedback1.dedupe_key


# ---------------------------------------------------------------------------
# Integration tests: fetch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_issues_basic():
    """Mock GitHub API returning 2 issues → 2 RawFeedback items."""
    issues = [
        fake_issue(1, "Issue 1", "Body 1", "alice", ["bug"]),
        fake_issue(2, "Issue 2", "Body 2", "bob", ["feature"]),
    ]

    mock_response = MagicMock()
    mock_response.headers = mock_rate_limit_headers()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = issues

    mock_empty_response = MagicMock()
    mock_empty_response.headers = mock_rate_limit_headers()
    mock_empty_response.raise_for_status = MagicMock()
    mock_empty_response.json.return_value = []

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = [mock_response, mock_empty_response]

    with patch("httpx.AsyncClient", return_value=mock_client):
        connector = GitHubConnector("owner/repo", include_comments=False)
        results = [fb async for fb in connector.fetch()]

    assert len(results) == 2
    assert results[0].content.subject == "Issue 1"
    assert results[1].content.subject == "Issue 2"


@pytest.mark.asyncio
async def test_fetch_skips_pull_requests():
    """Verify PRs (with 'pull_request' key) are filtered out."""
    issues = [
        fake_issue(1, "Issue", "Body", "alice", []),
        fake_issue(2, "PR title", "PR body", "bob", [], is_pr=True),
    ]

    mock_response = MagicMock()
    mock_response.headers = mock_rate_limit_headers()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = issues

    mock_empty_response = MagicMock()
    mock_empty_response.headers = mock_rate_limit_headers()
    mock_empty_response.raise_for_status = MagicMock()
    mock_empty_response.json.return_value = []

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = [mock_response, mock_empty_response]

    with patch("httpx.AsyncClient", return_value=mock_client):
        connector = GitHubConnector("owner/repo", include_comments=False)
        results = [fb async for fb in connector.fetch()]

    assert len(results) == 1
    assert results[0].content.subject == "Issue"


@pytest.mark.asyncio
async def test_fetch_with_comments():
    """Verify include_comments=True yields issue + comments."""
    issues = [fake_issue(1, "Issue with comments", "Issue body", "alice", [])]

    comments = [
        fake_comment(100, "Comment 1 body", "bob"),
        fake_comment(101, "Comment 2 body", "charlie"),
    ]

    # First call returns issues, second call returns comments, third returns empty
    call_count = 0

    def side_effect_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        response = MagicMock()
        response.headers = mock_rate_limit_headers()
        response.raise_for_status = MagicMock()
        if "comments" in url:
            # Return comments on first comments call, empty on second (pagination)
            if call_count == 2:
                response.json.return_value = comments
            else:
                response.json.return_value = []
        else:
            if call_count == 1:
                response.json.return_value = issues
            else:
                response.json.return_value = []
        return response

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(side_effect=side_effect_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        connector = GitHubConnector("owner/repo", include_comments=True)
        results = [fb async for fb in connector.fetch()]

    assert len(results) == 3  # 1 issue + 2 comments
    assert results[0].content.subject == "Issue with comments"
    assert results[1].content.text == "Comment 1 body"
    assert results[2].content.text == "Comment 2 body"
    # Verify comment dedupe keys
    assert "comment_100" in results[1].dedupe_key
    assert "comment_101" in results[2].dedupe_key


@pytest.mark.asyncio
async def test_fetch_without_comments():
    """Verify include_comments=False only yields issue bodies."""
    issues = [fake_issue(1, "Issue only", "Body only", "alice", [])]

    mock_response = MagicMock()
    mock_response.headers = mock_rate_limit_headers()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = issues

    mock_empty_response = MagicMock()
    mock_empty_response.headers = mock_rate_limit_headers()
    mock_empty_response.raise_for_status = MagicMock()
    mock_empty_response.json.return_value = []

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = [mock_response, mock_empty_response]

    with patch("httpx.AsyncClient", return_value=mock_client):
        connector = GitHubConnector("owner/repo", include_comments=False)
        results = [fb async for fb in connector.fetch()]

    assert len(results) == 1
    assert results[0].content.subject == "Issue only"


@pytest.mark.asyncio
async def test_fetch_pagination():
    """Verify the connector paginates through multiple pages."""
    page1 = [fake_issue(1, "Issue 1", "B1", "alice", [])]
    page2 = [fake_issue(2, "Issue 2", "B2", "bob", [])]
    empty: list = []

    call_count = 0

    def side_effect_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        response = MagicMock()
        response.headers = mock_rate_limit_headers()
        response.raise_for_status = MagicMock()
        if call_count == 1:
            response.json.return_value = page1
        elif call_count == 2:
            response.json.return_value = page2
        else:
            response.json.return_value = empty
        return response

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(side_effect=side_effect_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        connector = GitHubConnector("owner/repo", include_comments=False)
        results = [fb async for fb in connector.fetch()]

    assert len(results) == 2
