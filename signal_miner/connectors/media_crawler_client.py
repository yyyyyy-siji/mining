"""MediaCrawler Client — interface for interacting with the external scraper service.

This module provides a client to communicate with a headless browser scraping
service (like MediaCrawler) via RPC, Redis, or HTTP API.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

class MediaCrawlerClient:
    """Client for interacting with the MediaCrawler external service."""

    def __init__(self, endpoint: str = "http://localhost:8080"):
        self.endpoint = endpoint

    async def fetch_data(self, platform: str, keywords: list[str], limit: int = 100) -> AsyncIterator[dict[str, Any]]:
        """Mock method for fetching data from the crawler service.

        In a real implementation, this would make an HTTP request or subscribe to a queue.
        """
        logger.info(f"Mock fetching data from {platform} for keywords: {keywords}")
        # Simulate network delay
        await asyncio.sleep(1)

        # Mock yielding results
        for i in range(min(limit, 5)):
            yield {
                "id": f"mock_{platform}_{i}",
                "title": f"Mock Title {i} for {keywords[0]}",
                "content": f"Mock detailed content for {platform} regarding {keywords[0]}",
                "author": f"User_{i}",
                "url": f"https://{platform}.com/mock/{i}",
                "created_at": "2024-01-01T12:00:00Z"
            }

    async def validate_cookie(self, platform: str, cookie: str) -> bool:  # noqa: ARG002
        """Mock method to validate if a cookie is still active."""
        # Simple mock logic
        return bool(cookie and len(cookie) > 10)
