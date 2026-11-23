"""Simple API key authentication.

When API_KEY is configured in settings, all API routes require
the X-API-Key header to match. Health and static routes are exempt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

if TYPE_CHECKING:
    from signal_miner.settings import AppSettings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key_dependency(settings: AppSettings):
    """Create an API key verification dependency.

    If settings.api_key is empty, returns a no-op dependency
    (all requests pass through without authentication).
    """
    required_key = settings.api_key

    async def verify_api_key(
        api_key: str | None = Security(_api_key_header),
    ) -> str | None:
        if not required_key:
            return None  # No auth configured — pass through
        if api_key != required_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key.",
            )
        return api_key

    return verify_api_key
