"""Application runtime resources and lifecycle helpers.

Design reference: agentic-prd-generation/backend/runtime.py
  - Builds shared resources (LLM, state store, streamer)
  - Manages lifecycle (init/close)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from signal_miner.services import StreamerService
from signal_miner.state import InMemoryStore, StateStore

if TYPE_CHECKING:
    from signal_miner.llm import BaseLLMAdapter
    from signal_miner.settings import AppSettings

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class AppRuntime:
    """Shared application resources available throughout the request lifecycle."""

    settings: AppSettings
    llm: BaseLLMAdapter
    state_store: StateStore
    streamer: StreamerService
    multimodal_llm: BaseLLMAdapter | None = None
    embedding_llm: BaseLLMAdapter | None = None


async def build_runtime(settings: AppSettings) -> AppRuntime:
    """Create shared process-level resources.

    - Initializes the database
    - Selects and configures the LLM adapter
    - Sets up the state store (Redis with memory fallback)
    - Creates the SSE streamer service
    """
    # Production mode overrides and warnings
    if settings.environment == "production":
        if settings.debug:
            logger.warning("production_debug_override", msg="Forcing debug=False in production")
            settings.debug = False
        if "sqlite" in settings.database_url:
            logger.warning("production_sqlite_warning", msg="SQLite is not recommended for production")
        if not settings.api_key:
            logger.warning("production_no_auth", msg="No API_KEY set — API is unauthenticated")

    _configure_logging(settings.debug)

    # Initialize database
    from signal_miner.db import init_db
    await init_db(settings.database_url)

    # Build LLM adapter
    llm = _build_llm_adapter(settings)
    multimodal_llm = _build_multimodal_llm_adapter(settings, primary_llm=llm)
    embedding_llm = _build_embedding_adapter(settings, primary_llm=llm)

    # Build state store
    state_store = await _build_state_store(settings)

    # Create streamer
    streamer = StreamerService()

    logger.info(
        "runtime_initialized",
        environment=settings.environment,
        llm_provider=llm.provider_name,
        multimodal_provider=(multimodal_llm.provider_name if multimodal_llm else "disabled"),
        embedding_provider=(embedding_llm.provider_name if embedding_llm else "disabled"),
        state_backend=state_store.backend_name,
    )

    return AppRuntime(
        settings=settings,
        llm=llm,
        state_store=state_store,
        streamer=streamer,
        multimodal_llm=multimodal_llm,
        embedding_llm=embedding_llm,
    )


async def close_runtime(runtime: AppRuntime) -> None:
    """Release shared resources on shutdown."""
    await runtime.state_store.close()

    from signal_miner.db import close_db
    await close_db()

    logger.info("runtime_closed")


def _build_llm_adapter(settings: AppSettings) -> BaseLLMAdapter:
    """Select and configure the LLM adapter based on settings."""
    provider = settings.default_llm_provider

    if provider == "openai" and settings.openai_api_key:
        from signal_miner.llm.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            embedding_model=settings.openai_embedding_model,
            base_url=settings.openai_base_url or None,
        )

    if provider == "google" and settings.google_api_key:
        from signal_miner.llm.google_adapter import GoogleAdapter
        return GoogleAdapter(
            api_key=settings.google_api_key,
            model=settings.google_model,
        )

    if provider == "deepseek" and settings.deepseek_api_key:
        from signal_miner.llm.deepseek_adapter import DeepSeekAdapter
        return DeepSeekAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
        )

    if provider == "qwen" and settings.qwen_api_key:
        from signal_miner.llm.qwen_adapter import QwenAdapter
        return QwenAdapter(
            api_key=settings.qwen_api_key,
            model=settings.qwen_model,
        )

    if provider == "minimax" and settings.minimax_api_key:
        from signal_miner.llm.minimax_adapter import MinimaxAdapter
        return MinimaxAdapter(
            api_key=settings.minimax_api_key,
            group_id=settings.minimax_group_id,
            model=settings.minimax_model,
        )

    # Fallback: try whichever key is available
    if settings.deepseek_api_key:
        from signal_miner.llm.deepseek_adapter import DeepSeekAdapter
        logger.warning("llm_fallback", requested=provider, actual="deepseek")
        return DeepSeekAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
        )

    if settings.qwen_api_key:
        from signal_miner.llm.qwen_adapter import QwenAdapter
        logger.warning("llm_fallback", requested=provider, actual="qwen")
        return QwenAdapter(
            api_key=settings.qwen_api_key,
            model=settings.qwen_model,
        )

    if settings.minimax_api_key:
        from signal_miner.llm.minimax_adapter import MinimaxAdapter
        logger.warning("llm_fallback", requested=provider, actual="minimax")
        return MinimaxAdapter(
            api_key=settings.minimax_api_key,
            group_id=settings.minimax_group_id,
            model=settings.minimax_model,
        )

    if settings.openai_api_key:
        from signal_miner.llm.openai_adapter import OpenAIAdapter
        logger.warning("llm_fallback", requested=provider, actual="openai")
        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            embedding_model=settings.openai_embedding_model,
            base_url=settings.openai_base_url or None,
        )

    if settings.google_api_key:
        from signal_miner.llm.google_adapter import GoogleAdapter
        logger.warning("llm_fallback", requested=provider, actual="google")
        return GoogleAdapter(
            api_key=settings.google_api_key,
            model=settings.google_model,
        )

    raise RuntimeError(
        "No LLM API key configured. Set DEEPSEEK_API_KEY, QWEN_API_KEY, MINIMAX_API_KEY, OPENAI_API_KEY or GOOGLE_API_KEY in .env"
    )


def _build_multimodal_llm_adapter(
    settings: AppSettings,
    *,
    primary_llm: BaseLLMAdapter | None = None,
) -> BaseLLMAdapter | None:
    """Build or reuse the multimodal model without forcing text-only replacement."""
    provider = settings.multimodal_llm_provider.strip().lower()
    if provider in {"disabled", "none", "off"}:
        return None
    if not provider:
        if primary_llm is not None and primary_llm.supports_multimodal:
            return primary_llm
        return None

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            logger.warning("multimodal_llm_disabled", provider=provider, reason="missing API key")
            return None
        from signal_miner.llm.deepseek_adapter import DeepSeekAdapter

        return DeepSeekAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.multimodal_deepseek_model,
            input_modalities=("text", "image"),
        )

    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning("multimodal_llm_disabled", provider=provider, reason="missing API key")
            return None
        from signal_miner.llm.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.multimodal_openai_model,
            embedding_model=settings.openai_embedding_model,
            base_url=settings.openai_base_url or None,
            input_modalities=("text", "image"),
        )

    if provider == "google":
        if not settings.google_api_key:
            logger.warning("multimodal_llm_disabled", provider=provider, reason="missing API key")
            return None
        from signal_miner.llm.google_adapter import GoogleAdapter

        return GoogleAdapter(
            api_key=settings.google_api_key,
            model=settings.multimodal_google_model,
            input_modalities=("text", "image", "audio", "video"),
        )

    logger.warning("multimodal_llm_disabled", provider=provider, reason="unsupported provider")
    return None


def _build_embedding_adapter(
    settings: AppSettings,
    *,
    primary_llm: BaseLLMAdapter | None = None,
) -> BaseLLMAdapter | None:
    """Build or reuse a decoupled embedding adapter without replacing primary LLM."""
    from signal_miner.llm.embedding_adapter import (
        EMBEDDING_PRESETS,
        LocalFastEmbedAdapter,
        OpenAICompatibleEmbeddingAdapter,
    )

    provider = settings.embedding_provider.strip().lower() or "auto"
    if provider in {"disabled", "none", "off"}:
        return None

    if provider in {"local", "fastembed"}:
        adapter = LocalFastEmbedAdapter(model=settings.local_embedding_model)
        if not adapter.supports_embedding:
            logger.warning("embedding_disabled", provider=provider, reason="fastembed not installed")
            return None
        return adapter

    if provider in {"siliconflow", "dashscope", "zhipu", "openai", "custom"}:
        preset = EMBEDDING_PRESETS[provider]
        api_key = settings.embedding_api_key.strip()
        if not api_key and provider == "dashscope":
            api_key = settings.qwen_api_key.strip()
        if not api_key and provider == "openai":
            api_key = settings.openai_api_key.strip()
        if not api_key:
            logger.warning("embedding_disabled", provider=provider, reason="missing API key")
            return None
        base_url = settings.embedding_base_url.strip() or preset["base_url"] or (
            settings.openai_base_url.strip() if provider == "openai" else ""
        )
        model = settings.embedding_model.strip() or (
            settings.openai_embedding_model if provider == "openai" else preset["default_model"]
        )
        if not model:
            logger.warning("embedding_disabled", provider=provider, reason="missing model")
            return None
        return OpenAICompatibleEmbeddingAdapter(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url or None,
        )

    if provider == "auto":
        if primary_llm is not None and primary_llm.supports_embedding:
            return primary_llm
        local = LocalFastEmbedAdapter(model=settings.local_embedding_model)
        if local.supports_embedding:
            return local
        return None

    logger.warning("embedding_disabled", provider=provider, reason="unsupported provider")
    return None


def rebuild_runtime_models(runtime: AppRuntime, settings: AppSettings) -> None:
    """Hot-reload LLM, multimodal, and embedding adapters after settings save."""
    llm = _build_llm_adapter(settings)
    multimodal_llm = _build_multimodal_llm_adapter(settings, primary_llm=llm)
    embedding_llm = _build_embedding_adapter(settings, primary_llm=llm)
    runtime.settings = settings
    runtime.llm = llm
    runtime.multimodal_llm = multimodal_llm
    runtime.embedding_llm = embedding_llm


async def _build_state_store(settings: AppSettings) -> StateStore:
    """Select a concrete state store based on configuration and availability."""
    if settings.state_backend == "memory":
        return InMemoryStore()

    if settings.state_backend in ("auto", "redis"):
        try:
            from signal_miner.state.redis_store import RedisStore
            store = RedisStore(redis_url=settings.redis_url, ttl_seconds=settings.redis_ttl_seconds)
            if await store.ping():
                return store
            await store.close()
        except Exception:
            pass

        if settings.state_backend == "redis":
            raise RuntimeError("Redis was selected explicitly but is not reachable.")

    logger.warning("state_store_fallback", requested=settings.state_backend, actual="memory")
    return InMemoryStore()


def _configure_logging(debug: bool) -> None:
    """Configure structlog for the application."""
    import logging

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
