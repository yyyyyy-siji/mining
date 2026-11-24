"""Database engine and session management.

Uses SQLAlchemy async engine with SQLite (dev) or PostgreSQL (prod).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import structlog

logger = structlog.get_logger(__name__)

# Module-level engine — initialized by init_db()
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str) -> None:
    """Initialize the async database engine and create tables."""
    global _engine, _session_factory

    connect_args: dict = {}
    pool_kwargs: dict = {}

    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False
    elif "postgresql" in database_url:
        pool_kwargs["pool_size"] = 5
        pool_kwargs["max_overflow"] = 10

    _engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
        **pool_kwargs,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Create all tables
    from signal_miner.db.models import Base

    async with _engine.begin() as conn:
        # Enable pgvector extension for PostgreSQL
        if "postgresql" in database_url:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_version_schema(conn, database_url)

    logger.info("database_initialized", url=database_url.split("@")[-1])


_VERSIONED_TABLES = (
    "raw_feedback_items",
    "feedback_signals",
    "themes",
    "pain_points",
    "opportunities",
    "requirement_assets",
    "pipeline_runs",
)


async def _ensure_version_schema(conn, database_url: str) -> None:
    """Idempotently add version_id columns, upgrade dedupe index, and seed default version."""
    from sqlalchemy.ext.asyncio import AsyncConnection

    if not isinstance(conn, AsyncConnection):
        return
    is_sqlite = "sqlite" in database_url
    table_cols: dict[str, set[str]] = {}
    for table in _VERSIONED_TABLES:
        if is_sqlite:
            cols = {
                row[1]
                for row in (await conn.execute(text(f"PRAGMA table_info({table})"))).fetchall()
            }
            if "version_id" not in cols:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN version_id VARCHAR(40) NOT NULL DEFAULT 'default'")
                )
                cols.add("version_id")
            table_cols[table] = cols
            await conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS ix_{table}_version_id ON {table} (version_id)")
            )
        else:
            await conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS version_id VARCHAR(40) NOT NULL DEFAULT 'default'")
            )
            await conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS ix_{table}_version_id ON {table} (version_id)")
            )

    # Composite indexes for hot profile+version+state queries on existing databases
    if not is_sqlite or {"version_id", "pipeline_profile", "processing_state"} <= table_cols.get("raw_feedback_items", set()):
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS raw_feedback_ver_profile_state_idx "
                "ON raw_feedback_items (version_id, pipeline_profile, processing_state)"
            )
        )
    if not is_sqlite or {"version_id", "pipeline_profile"} <= table_cols.get("themes", set()):
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS themes_ver_profile_idx "
                "ON themes (version_id, pipeline_profile)"
            )
        )

    if is_sqlite:
        idx_cols = [
            row[2]
            for row in (await conn.execute(text("PRAGMA index_info('raw_feedback_dedupe_idx')"))).fetchall()
        ]
        if idx_cols and "version_id" not in idx_cols:
            await conn.execute(text("DROP INDEX IF EXISTS raw_feedback_dedupe_idx"))
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS raw_feedback_dedupe_idx "
                    "ON raw_feedback_items (version_id, source_id, dedupe_key)"
                )
            )
        await conn.execute(
            text(
                "INSERT OR IGNORE INTO dataset_versions (id, name, description, status) "
                "VALUES ('default', '默认版本（历史数据）', '系统内置默认版本，归档未指定版本的历史数据。', 'active')"
            )
        )
    else:
        await conn.execute(
            text(
                "INSERT INTO dataset_versions (id, name, description, status) "
                "VALUES ('default', '默认版本（历史数据）', '系统内置默认版本，归档未指定版本的历史数据。', 'active') "
                "ON CONFLICT (id) DO NOTHING"
            )
        )


async def close_db() -> None:
    """Dispose of the database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_closed")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the async session factory. Raises if DB not initialized."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory
