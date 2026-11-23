"""Application settings loaded from environment variables and .env file."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Central configuration for the SignalMiner application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "SignalMiner"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])

    # --- LLM Providers ---
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash-lite"

    # --- Chinese LLM Providers ---
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-flash"

    qwen_api_key: str = ""
    qwen_model: str = "qwen-max"

    minimax_api_key: str = ""
    minimax_group_id: str = ""
    minimax_model: str = "MiniMax-M2.7-highspeed"

    default_llm_provider: str = "deepseek"  # "openai" | "google" | "deepseek" | "qwen" | "minimax"

    # --- Optional multimodal LLM ---
    # Can inherit a multimodal primary model (e.g. deepseek-flash) when empty,
    # or explicitly select "deepseek" | "openai" | "google" | "disabled".
    multimodal_llm_provider: str = ""
    multimodal_deepseek_model: str = "deepseek-flash"
    multimodal_openai_model: str = "gpt-4o-mini"
    multimodal_google_model: str = "gemini-2.0-flash-lite"

    # --- Decoupled Embedding LLM ---
    # Supports: "auto" (use local fastembed if installed or primary embedding),
    # "local" (fastembed BAAI/bge-small-zh-v1.5), "siliconflow", "dashscope",
    # "zhipu", "openai", "custom", or "disabled".
    embedding_provider: str = "auto"
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    local_embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./signal_miner.db"

    # --- State Store ---
    state_backend: str = "auto"  # "auto" | "redis" | "memory"
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_seconds: int = 86400

    # --- Pipeline ---
    extraction_confidence_threshold: float = 0.5
    max_signals_per_feedback: int = 5
    similarity_vote_threshold: float = 0.8
    similarity_min_threshold: float = 0.55
    quality_gate_bypass_sources: list[str] = Field(
        default=[],
        description="Source types that bypass the quality gate (e.g. ['manual', 'zendesk'])",
    )

    # --- Authentication ---
    api_key: str = ""  # Empty = no auth (development mode)

    # --- Connectors ---
    github_token: str = ""
    webhook_secret: str = ""
    mediacrawler_runtime_dir: str = ""  # Empty: validate only this project's managed runtime.
    zhihu_access_secret: SecretStr = Field(default=SecretStr(""), repr=False)
