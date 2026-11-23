"""Tests for the API key authentication module."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import HTTPException
import pytest

from signal_miner.auth import get_api_key_dependency

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_settings(api_key: str = ""):
    """Create a mock settings object with the given api_key."""
    settings = MagicMock()
    settings.api_key = api_key
    return settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_api_key_configured_allows_all():
    """When API_KEY is empty, all requests pass without auth."""
    dep = get_api_key_dependency(make_settings(""))
    result = await dep(api_key=None)
    assert result is None  # No auth required


@pytest.mark.asyncio
async def test_no_api_key_configured_ignores_wrong_key():
    """When API_KEY is empty, wrong keys are also ignored."""
    dep = get_api_key_dependency(make_settings(""))
    result = await dep(api_key="wrong_key")
    assert result is None


@pytest.mark.asyncio
async def test_api_key_required_missing_header():
    """When API_KEY is set, missing header raises 401."""
    dep = get_api_key_dependency(make_settings("secret"))
    with pytest.raises(HTTPException) as exc:
        await dep(api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_api_key_required_wrong_key():
    """When API_KEY is set, wrong key raises 401."""
    dep = get_api_key_dependency(make_settings("secret"))
    with pytest.raises(HTTPException) as exc:
        await dep(api_key="wrong-secret")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_api_key_required_correct_key():
    """When API_KEY is set, correct key passes."""
    dep = get_api_key_dependency(make_settings("secret"))
    result = await dep(api_key="secret")
    assert result == "secret"
