"""Bilibili Connector.

Fetches videos, descriptions, and comments using the MediaCrawler client.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import structlog

from signal_miner.connectors import BrowserBaseConnector
from signal_miner.connectors.media_crawler_client import MediaCrawlerClient
from signal_miner.models.feedback import FeedbackAuthor, FeedbackContent, RawFeedback

logger = structlog.get_logger(__name__)

class BilibiliConnector(BrowserBaseConnector):
    """Pull Bilibili content as RawFeedback items."""

    source_type: str = "bilibili"
    requires_credentials: bool = True

    def __init__(
        self,
        keywords: list[str],
        limit: int = 100,
        source_id: str | None = None,
    ) -> None:
        self._keywords = keywords
        self._limit = limit
        self._source_id = source_id or f"bili_{'_'.join(keywords)[:20]}"
        self._client = MediaCrawlerClient()

    async def fetch(self) -> AsyncIterator[RawFeedback]:
        logger.info("Starting Bilibili fetch", keywords=self._keywords)

        async for data in self._client.fetch_data("bilibili", self._keywords, self._limit):
            yield self._data_to_feedback(data)

    async def validate_credentials(self) -> bool:
        return True

    def _data_to_feedback(self, data: dict[str, Any]) -> RawFeedback:
        item_id = data.get("id", "")
        title = data.get("title", "")
        content = data.get("content", "")

        created_at: datetime | None = None
        raw_created = data.get("created_at")
        if raw_created:
            with suppress(ValueError, TypeError):
                created_at = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))

        return RawFeedback(
            source_type=self.source_type,
            source_id=self._source_id,
            dedupe_key=f"bili_{item_id}",
            external_id=str(item_id),
            external_url=data.get("url"),
            author=FeedbackAuthor(
                name=data.get("author"),
            ),
            content=FeedbackContent(subject=title, text=content),
            context={
                "platform": "bilibili",
                "keywords": self._keywords
            },
            source_created_at=created_at,
        )
