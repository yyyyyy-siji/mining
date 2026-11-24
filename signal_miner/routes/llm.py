"""LLM capability discovery, model settings management, and connectivity test routes."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from signal_miner.llm.embedding_adapter import EMBEDDING_PRESETS
from signal_miner.runtime import rebuild_runtime_models

if TYPE_CHECKING:
    from signal_miner.settings import AppSettings

router = APIRouter()

PRIMARY_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {"label": "DeepSeek", "default_model": "deepseek-flash"},
    "qwen": {"label": "通义千问 Qwen", "default_model": "qwen-max"},
    "minimax": {"label": "MiniMax", "default_model": "MiniMax-M2.7-highspeed"},
    "openai": {"label": "OpenAI / 兼容端点", "default_model": "gpt-4o-mini"},
    "google": {"label": "Google Gemini", "default_model": "gemini-2.0-flash-lite"},
}


async def same_origin(request: Request) -> None:
    """Prevent unrelated local pages from reading or mutating model settings."""
    origin = request.headers.get("origin")
    if origin is not None and (
        origin != str(request.base_url).rstrip("/")
        or request.base_url.hostname not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "cross_origin_forbidden", "message": "模型设置仅接受 MINING 页面同源请求。"},
        )


def _mask_secret(value: str) -> str:
    clean = value.strip()
    if not clean:
        return ""
    if len(clean) <= 8:
        return "*" * len(clean)
    return f"{clean[:4]}****{clean[-4:]}"


def _validate_no_control_chars(value: str) -> str:
    cleaned = value.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cleaned):
        raise ValueError("配置值不能包含换行或控制字符。")
    return cleaned


def _validate_base_url(value: str) -> str:
    cleaned = _validate_no_control_chars(value)
    if not cleaned:
        return ""
    parsed = urlsplit(cleaned)
    if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
        return cleaned
    if (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and not parsed.username
        and not parsed.password
    ):
        return cleaned
    raise ValueError("Base URL 仅支持 https://（或本机 http://127.0.0.1 / localhost），且不能包含账号密码。")


def _env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _persist_env_updates(updates: dict[str, str]) -> None:
    """Atomically update selected keys in .env while preserving unrelated entries."""
    path = _env_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    remaining = dict(updates)
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key, _, _ = line.partition("=")
        k = key.strip()
        if k in remaining:
            val = remaining.pop(k)
            new_lines.append(f"{k}={val}")
        else:
            new_lines.append(line)
    for key, val in remaining.items():
        new_lines.append(f"{key}={val}")
    payload = "\n".join(new_lines).rstrip("\n") + "\n"
    tmp = path.with_suffix(".env.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(payload)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


class ModelCapability(BaseModel):
    provider: str
    model: str
    input_modalities: list[str] = Field(default_factory=list)
    supports_embedding: bool = False
    supports_multimodal: bool = False


class OptionalModelCapability(BaseModel):
    enabled: bool
    provider: str | None = None
    model: str | None = None
    input_modalities: list[str] = Field(default_factory=list)
    supports_embedding: bool = False
    supports_multimodal: bool = False


class LLMCapabilitiesResponse(BaseModel):
    primary: ModelCapability
    multimodal: OptionalModelCapability
    embedding: OptionalModelCapability | None = None


class ModelSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_llm_provider: Literal["deepseek", "qwen", "minimax", "openai", "google"]
    primary_model: str = Field("", max_length=120)
    primary_api_key: str = Field("", max_length=400)
    openai_base_url: str = Field("", max_length=400)
    minimax_group_id: str = Field("", max_length=120)

    multimodal_llm_provider: Literal["", "deepseek", "openai", "google", "disabled"] = ""
    multimodal_model: str = Field("", max_length=120)

    embedding_provider: Literal[
        "auto", "local", "siliconflow", "dashscope", "zhipu", "openai", "custom", "disabled"
    ] = "auto"
    embedding_model: str = Field("", max_length=160)
    embedding_base_url: str = Field("", max_length=400)
    embedding_api_key: str = Field("", max_length=400)

    @field_validator(
        "primary_model", "primary_api_key", "minimax_group_id",
        "multimodal_model", "embedding_model", "embedding_api_key",
    )
    @classmethod
    def _clean_text(cls, value: str) -> str:
        return _validate_no_control_chars(value)

    @field_validator("openai_base_url", "embedding_base_url")
    @classmethod
    def _clean_url(cls, value: str) -> str:
        return _validate_base_url(value)


class ModelTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["primary", "embedding"]


def _capability(adapter) -> dict:
    return {
        "provider": adapter.provider_name,
        "model": adapter.model_name,
        "input_modalities": list(adapter.input_modalities),
        "supports_embedding": adapter.supports_embedding,
        "supports_multimodal": adapter.supports_multimodal,
    }


def _capabilities_payload(runtime) -> dict:
    media_adapter = getattr(runtime, "multimodal_llm", None)
    emb_adapter = getattr(runtime, "embedding_llm", None)
    multimodal = (
        {"enabled": True, **_capability(media_adapter)}
        if media_adapter
        else {"enabled": False}
    )
    embedding = (
        {"enabled": True, **_capability(emb_adapter)}
        if emb_adapter
        else {"enabled": False}
    )
    return {
        "primary": _capability(runtime.llm),
        "multimodal": multimodal,
        "embedding": embedding,
    }


def _settings_payload(runtime) -> dict:
    s: AppSettings = runtime.settings
    key_map = {
        "deepseek": s.deepseek_api_key,
        "qwen": s.qwen_api_key,
        "minimax": s.minimax_api_key,
        "openai": s.openai_api_key,
        "google": s.google_api_key,
    }
    model_map = {
        "deepseek": s.deepseek_model,
        "qwen": s.qwen_model,
        "minimax": s.minimax_model,
        "openai": s.openai_model,
        "google": s.google_model,
    }
    mm_provider = s.multimodal_llm_provider.strip().lower()
    mm_model = {
        "deepseek": s.multimodal_deepseek_model,
        "openai": s.multimodal_openai_model,
        "google": s.multimodal_google_model,
    }.get(mm_provider, "")
    emb_provider = s.embedding_provider.strip().lower() or "auto"
    emb_key = s.embedding_api_key
    return {
        "primary": {
            "provider": s.default_llm_provider,
            "model": model_map.get(s.default_llm_provider, ""),
            "openai_base_url": s.openai_base_url,
            "minimax_group_id": s.minimax_group_id,
            "providers": {
                name: {
                    "model": model_map[name],
                    "api_key_configured": bool(key_map[name]),
                    "api_key_masked": _mask_secret(key_map[name]),
                }
                for name in PRIMARY_PRESETS
            },
        },
        "multimodal": {
            "provider": mm_provider,
            "model": mm_model,
        },
        "embedding": {
            "provider": emb_provider,
            "model": s.local_embedding_model if emb_provider in {"local", "auto"} and not s.embedding_model else s.embedding_model,
            "local_model": s.local_embedding_model,
            "base_url": s.embedding_base_url,
            "api_key_configured": bool(emb_key),
            "api_key_masked": _mask_secret(emb_key),
            "fastembed_available": importlib.util.find_spec("fastembed") is not None,
        },
        "presets": {
            "primary": PRIMARY_PRESETS,
            "embedding": EMBEDDING_PRESETS,
        },
        "capabilities": _capabilities_payload(runtime),
    }


@router.get(
    "/llm/capabilities",
    response_model=LLMCapabilitiesResponse,
    summary="Describe active text, multimodal, and embedding model capabilities",
)
async def llm_capabilities(request: Request) -> dict:
    return _capabilities_payload(request.app.state.runtime)


@router.get(
    "/llm/settings",
    dependencies=[Depends(same_origin)],
    summary="Read masked model settings and presets",
)
async def get_llm_settings(request: Request) -> dict:
    return _settings_payload(request.app.state.runtime)


@router.post(
    "/llm/settings",
    dependencies=[Depends(same_origin)],
    summary="Save model settings to .env and hot-reload runtime adapters",
)
async def update_llm_settings(body: ModelSettingsUpdateRequest, request: Request) -> dict:
    runtime = request.app.state.runtime
    current: AppSettings = runtime.settings

    key_field_map = {
        "deepseek": "deepseek_api_key",
        "qwen": "qwen_api_key",
        "minimax": "minimax_api_key",
        "openai": "openai_api_key",
        "google": "google_api_key",
    }
    model_field_map = {
        "deepseek": "deepseek_model",
        "qwen": "qwen_model",
        "minimax": "minimax_model",
        "openai": "openai_model",
        "google": "google_model",
    }

    updates: dict[str, object] = {
        "default_llm_provider": body.default_llm_provider,
        "openai_base_url": body.openai_base_url,
        "minimax_group_id": body.minimax_group_id,
        "multimodal_llm_provider": body.multimodal_llm_provider,
        "embedding_provider": body.embedding_provider,
        "embedding_base_url": body.embedding_base_url,
    }
    env_updates: dict[str, str] = {
        "DEFAULT_LLM_PROVIDER": body.default_llm_provider,
        "OPENAI_BASE_URL": body.openai_base_url,
        "MINIMAX_GROUP_ID": body.minimax_group_id,
        "MULTIMODAL_LLM_PROVIDER": body.multimodal_llm_provider,
        "EMBEDDING_PROVIDER": body.embedding_provider,
        "EMBEDDING_BASE_URL": body.embedding_base_url,
    }

    chosen_model = body.primary_model or PRIMARY_PRESETS[body.default_llm_provider]["default_model"]
    updates[model_field_map[body.default_llm_provider]] = chosen_model
    env_updates[model_field_map[body.default_llm_provider].upper()] = chosen_model

    if body.primary_api_key:
        kfield = key_field_map[body.default_llm_provider]
        updates[kfield] = body.primary_api_key
        env_updates[kfield.upper()] = body.primary_api_key

    if body.multimodal_model and body.multimodal_llm_provider in {"deepseek", "openai", "google"}:
        mm_field = f"multimodal_{body.multimodal_llm_provider}_model"
        updates[mm_field] = body.multimodal_model
        env_updates[mm_field.upper()] = body.multimodal_model

    if body.embedding_provider == "local":
        local_model = body.embedding_model or current.local_embedding_model
        updates["local_embedding_model"] = local_model
        updates["embedding_model"] = ""
        env_updates["LOCAL_EMBEDDING_MODEL"] = local_model
        env_updates["EMBEDDING_MODEL"] = ""
    else:
        updates["embedding_model"] = body.embedding_model
        env_updates["EMBEDDING_MODEL"] = body.embedding_model

    if body.embedding_api_key:
        updates["embedding_api_key"] = body.embedding_api_key
        env_updates["EMBEDDING_API_KEY"] = body.embedding_api_key

    candidate = current.model_copy(update=updates)
    try:
        rebuild_runtime_models(runtime, candidate)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _persist_env_updates(env_updates)
    return _settings_payload(runtime)


@router.post(
    "/llm/test",
    dependencies=[Depends(same_origin)],
    summary="Test active primary LLM or embedding adapter connectivity",
)
async def test_llm_connection(body: ModelTestRequest, request: Request) -> dict:
    runtime = request.app.state.runtime
    started = time.perf_counter()
    if body.target == "primary":
        adapter = runtime.llm
        try:
            reply = await adapter.call_text("请只回复 OK", temperature=0.0)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return {
                "ok": True,
                "target": "primary",
                "provider": adapter.provider_name,
                "model": adapter.model_name,
                "latency_ms": elapsed_ms,
                "preview": reply[:80],
            }
        except Exception as exc:
            return {
                "ok": False,
                "target": "primary",
                "provider": adapter.provider_name,
                "model": adapter.model_name,
                "error": f"{type(exc).__name__}: {str(exc)[:180]}",
            }

    emb = getattr(runtime, "embedding_llm", None) or runtime.llm
    if not getattr(emb, "supports_embedding", False):
        return {
            "ok": False,
            "target": "embedding",
            "provider": emb.provider_name,
            "model": emb.model_name,
            "error": "当前未启用可用的 Embedding 模型。",
        }
    try:
        vector = await emb.embed("测试中文痛点语义向量化")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "target": "embedding",
            "provider": emb.provider_name,
            "model": emb.model_name,
            "dimensions": len(vector),
            "latency_ms": elapsed_ms,
        }
    except Exception as exc:
        return {
            "ok": False,
            "target": "embedding",
            "provider": emb.provider_name,
            "model": emb.model_name,
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }


__all__ = [
    "LLMCapabilitiesResponse",
    "ModelCapability",
    "OptionalModelCapability",
    "router",
]
