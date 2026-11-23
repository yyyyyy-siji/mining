"""GitHub Issues connector — pull issues and comments via GitHub REST API v3.

Design reference: CSVConnector pattern + Quackback's source-source connectors.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from signal_miner.models.feedback import FeedbackAuthor, FeedbackContent, RawFeedback

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubConnector:
    """Pull GitHub Issues (and optionally comments) as RawFeedback items.

    Uses the GitHub REST API v3 with automatic pagination and rate-limit
    handling. Pull Requests are automatically filtered out.
    """

    source_type: str = "github"

    def __init__(
        self,
        repo: str,
        token: str | None = None,
        labels: list[str] | None = None,
        state: str = "all",
        since: str | None = None,
        source_id: str | None = None,
        include_comments: bool = True,
    ) -> None:
        """Initialise a GitHub connector.

        Args:
            repo: Repo identifier in "owner/repo" format.
            token: GitHub Personal Access Token (optional; raises rate limit).
            labels: Optional label names to filter issues by.
            state: "open" | "closed" | "all".
            since: ISO-8601 datetime filter for issues updated after this time.
            source_id: Override the auto-generated source_id.
            include_comments: Whether to yield issue comments as separate items.
        """
        self._repo = repo
        self._token = token
        self._labels = labels or []
        self._state = state
        self._since = since
        self._source_id = source_id or f"github_{repo.replace('/', '_')}"
        self._include_comments = include_comments

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch(self) -> AsyncIterator[RawFeedback]:
        """Fetch issues (and optionally comments) from the GitHub repository."""
        headers = self._build_headers()
        issues_url = f"{GITHUB_API_BASE}/repos/{self._repo}/issues"
        params: dict[str, Any] = {
            "state": self._state,
            "per_page": 100,
        }
        if self._labels:
            params["labels"] = ",".join(self._labels)
        if self._since:
            params["since"] = self._since

        page = 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params["page"] = page
                response = await client.get(issues_url, headers=headers, params=params)
                await self._check_rate_limit(response)
                response.raise_for_status()
                issues: list[dict] = response.json()

                if not issues:
                    break

                for issue in issues:
                    # Skip Pull Requests
                    if "pull_request" in issue:
                        continue

                    feedback = self._issue_to_feedback(issue)
                    yield feedback

                    # Fetch comments for this issue
                    if self._include_comments:
                        async for comment_feedback in self._fetch_comments(
                            client, headers, issue["number"]
                        ):
                            yield comment_feedback

                logger.info(
                    "github_page_fetched",
                    repo=self._repo,
                    page=page,
                    issue_count=len(issues),
                )
                page += 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Construct HTTP headers including optional auth."""
        headers: dict[str, str] = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "signal-miner",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _check_rate_limit(self, response: httpx.Response) -> None:
        """Sleep if rate limit is about to be exhausted."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) <= 5:
            reset_epoch = response.headers.get("X-RateLimit-Reset")
            if reset_epoch:
                reset_time = datetime.fromtimestamp(int(reset_epoch), tz=timezone.utc)
                wait_seconds = max(
                    (reset_time - datetime.now(timezone.utc)).total_seconds(), 1
                )
                logger.warning(
                    "github_rate_limit_near",
                    remaining=remaining,
                    wait_seconds=wait_seconds,
                    reset=reset_epoch,
                )
                await asyncio.sleep(wait_seconds)

    def _issue_to_feedback(self, issue: dict) -> RawFeedback:
        """Map a GitHub Issue JSON object to a RawFeedback model."""
        issue_number = issue["number"]
        title = issue.get("title") or ""
        body = issue.get("body") or ""

        labels_list = [lb["name"] for lb in issue.get("labels", []) if isinstance(lb, dict)]

        created_at: datetime | None = None
        raw_created = issue.get("created_at")
        if raw_created:
            with suppress(ValueError, TypeError):
                created_at = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))

        return RawFeedback(
            source_type=self.source_type,
            source_id=self._source_id,
            dedupe_key=f"github_{self._repo.replace('/', '_')}_{issue_number}",
            external_id=str(issue_number),
            external_url=issue.get("html_url"),
            author=FeedbackAuthor(
                name=issue.get("user", {}).get("login") if isinstance(issue.get("user"), dict) else None,
            ),
            content=FeedbackContent(subject=title, text=body),
            context={
                "labels": labels_list,
                "state": issue.get("state"),
                "issue_number": issue_number,
                "reactions": issue.get("reactions", {}),
            },
            source_created_at=created_at,
        )

    async def _fetch_comments(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        issue_number: int,
    ) -> AsyncIterator[RawFeedback]:
        """Fetch comments for a single issue and yield as RawFeedback items."""
        url = f"{GITHUB_API_BASE}/repos/{self._repo}/issues/{issue_number}/comments"
        params: dict[str, Any] = {"per_page": 100}

        page = 1
        while True:
            params["page"] = page
            response = await client.get(url, headers=headers, params=params)
            await self._check_rate_limit(response)

            if response.status_code == 404:
                break
            response.raise_for_status()

            comments: list[dict] = response.json()
            if not comments:
                break

            for comment in comments:
                comment_id = comment["id"]
                body = comment.get("body") or ""

                created_at: datetime | None = None
                raw_created = comment.get("created_at")
                if raw_created:
                    with suppress(ValueError, TypeError):
                        created_at = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))

                yield RawFeedback(
                    source_type=self.source_type,
                    source_id=self._source_id,
                    dedupe_key=f"github_{self._repo.replace('/', '_')}_{issue_number}_comment_{comment_id}",
                    external_id=str(comment_id),
                    external_url=comment.get("html_url"),
                    author=FeedbackAuthor(
                        name=comment.get("user", {}).get("login") if isinstance(comment.get("user"), dict) else None,
                    ),
                    content=FeedbackContent(
                        subject=f"Comment on #{issue_number}",
                        text=body,
                    ),
                    context={
                        "issue_number": issue_number,
                        "comment_id": comment_id,
                        "is_comment": True,
                    },
                    source_created_at=created_at,
                )

            page += 1
