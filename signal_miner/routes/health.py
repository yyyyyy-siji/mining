"""Health check routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Health check")
async def health() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok", "service": "signal-miner"}


@router.get("/ready", summary="Readiness check")
async def ready() -> dict:
    """Check if the service is ready to accept requests."""
    from signal_miner.db import get_session_factory
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        return {"status": "not_ready", "database": str(exc)}
