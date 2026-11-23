"""Main FastAPI application entry point.

Design reference: agentic-prd-generation/backend/main.py
  - App factory pattern
  - Lifespan context manager for resource lifecycle
  - CORS middleware
  - CLI entry point
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from signal_miner.auth import get_api_key_dependency
from signal_miner.connectors.existing_chrome import ExistingChromeCollector
from signal_miner.connectors.mediacrawler_runner import MediaCrawlerRunner
from signal_miner.routes.assets import router as assets_router
from signal_miner.routes.connectors import router as connectors_router
from signal_miner.routes.existing_chrome import router as existing_chrome_router
from signal_miner.routes.feedback import router as feedback_router
from signal_miner.routes.health import router as health_router
from signal_miner.routes.llm import router as llm_router
from signal_miner.routes.mediacrawler import router as mediacrawler_router
from signal_miner.routes.pipeline import router as pipeline_router
from signal_miner.routes.signals import router as signals_router
from signal_miner.routes.versions import router as versions_router
from signal_miner.runtime import build_runtime, close_runtime
from signal_miner.settings import AppSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create a configured FastAPI application."""
    app_settings = settings or AppSettings()
    api_key_dep = get_api_key_dependency(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = await build_runtime(app_settings)
        app.state.runtime = runtime
        app.state.mediacrawler = MediaCrawlerRunner(app_settings.mediacrawler_runtime_dir)
        app.state.existing_chrome = ExistingChromeCollector()
        try:
            yield
        finally:
            await app.state.existing_chrome.close()
            await app.state.mediacrawler.close()
            await close_runtime(runtime)

    app = FastAPI(
        title=app_settings.app_name,
        description=(
            "AI-powered agent that mines multi-source user signals "
            "into traceable product requirement assets."
        ),
        version=app_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routes (health + static = no auth; API routes = auth when configured)
    api_auth = [Depends(api_key_dep)] if app_settings.api_key else []
    app.include_router(health_router, prefix="", tags=["health"])
    app.include_router(feedback_router, prefix="/api/v1", tags=["feedback"], dependencies=api_auth)
    app.include_router(pipeline_router, prefix="/api/v1", tags=["pipeline"], dependencies=api_auth)
    app.include_router(signals_router, prefix="/api/v1", tags=["signals"], dependencies=api_auth)
    app.include_router(assets_router, prefix="/api/v1", tags=["assets"], dependencies=api_auth)
    app.include_router(connectors_router, prefix="/api/v1", tags=["connectors"], dependencies=api_auth)
    app.include_router(llm_router, prefix="/api/v1", tags=["llm"], dependencies=api_auth)
    app.include_router(mediacrawler_router, prefix="/api/v1", tags=["mediacrawler"], dependencies=api_auth)
    app.include_router(existing_chrome_router, prefix="/api/v1", tags=["existing-chrome"], dependencies=api_auth)
    app.include_router(versions_router, prefix="/api/v1", tags=["versions"], dependencies=api_auth)

    # Mount static frontend (after all API routes)
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).resolve().parent.parent / "frontend" / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# Default instance for uvicorn
DEFAULT_SETTINGS = AppSettings()
app = create_app(DEFAULT_SETTINGS)


def cli(argv: list[str] | None = None) -> int:
    """Run the API server from the installed console script."""
    parser = argparse.ArgumentParser(description="Run the SignalMiner API server.")
    parser.add_argument("--host", default=DEFAULT_SETTINGS.api_host)
    parser.add_argument("--port", type=int, default=DEFAULT_SETTINGS.api_port)
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_SETTINGS.environment == "development",
    )
    args = parser.parse_args(argv)
    uvicorn.run(
        "signal_miner.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
