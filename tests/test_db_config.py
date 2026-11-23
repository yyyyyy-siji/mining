"""Tests for the database configuration and pgvector support."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestDatabaseConfig:
    """Test database engine configuration for different backends."""

    @pytest.mark.asyncio
    async def test_sqlite_connect_args(self):
        """SQLite URL includes check_same_thread=False."""
        from signal_miner.db import init_db

        with (
            patch("signal_miner.db.create_async_engine") as mock_create,
            patch("signal_miner.db.async_sessionmaker"),
            patch("signal_miner.db.models.Base"),
        ):
            await init_db("sqlite+aiosqlite:///./test.db")

        kwargs = mock_create.call_args[1]
        assert kwargs["connect_args"]["check_same_thread"] is False

    @pytest.mark.asyncio
    async def test_postgresql_pool_config(self):
        """PostgreSQL URL sets pool_size and max_overflow."""
        from signal_miner.db import init_db

        with (
            patch("signal_miner.db.create_async_engine") as mock_create,
            patch("signal_miner.db.async_sessionmaker"),
            patch("signal_miner.db.models.Base"),
        ):
            await init_db("postgresql+asyncpg://user:pass@localhost/db")

        kwargs = mock_create.call_args[1]
        assert kwargs["pool_size"] == 5
        assert kwargs["max_overflow"] == 10


class TestPgvectorFlag:
    """Test the HAS_PGVECTOR flag reflects the import state."""

    def test_pgvector_import_flag_exists(self):
        """HAS_PGVECTOR is a boolean flag in db.models."""
        from signal_miner.db.models import HAS_PGVECTOR

        assert isinstance(HAS_PGVECTOR, bool)

    def test_embedding_column_function_returns_valid_column(self):
        """_embedding_column() returns a valid mapped_column."""
        from signal_miner.db.models import _embedding_column

        col = _embedding_column()
        assert col is not None
