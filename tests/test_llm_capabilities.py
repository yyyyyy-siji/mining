"""Contracts for separate primary and multimodal LLM resources."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from signal_miner.llm.types import MultimodalInput
from signal_miner.routes.llm import router


class _FakeAdapter:
    def __init__(
        self,
        provider: str,
        model: str,
        modalities: tuple[str, ...],
        *,
        embedding: bool,
    ) -> None:
        self.provider_name = provider
        self.model_name = model
        self.input_modalities = modalities
        self.supports_embedding = embedding
        self.supports_multimodal = any(item != "text" for item in modalities)


def _client(multimodal=None) -> TestClient:
    app = FastAPI()
    app.state.runtime = SimpleNamespace(
        llm=_FakeAdapter("deepseek", "deepseek-chat", ("text",), embedding=False),
        multimodal_llm=multimodal,
    )
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_capabilities_show_text_only_primary_and_disabled_multimodal():
    response = _client().get("/api/v1/llm/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["primary"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "input_modalities": ["text"],
        "supports_embedding": False,
        "supports_multimodal": False,
    }
    assert payload["multimodal"]["enabled"] is False


def test_capabilities_show_independent_multimodal_model():
    media = _FakeAdapter(
        "google",
        "gemini-test",
        ("text", "image", "audio", "video"),
        embedding=True,
    )
    payload = _client(media).get("/api/v1/llm/capabilities").json()
    assert payload["primary"]["provider"] == "deepseek"
    assert payload["multimodal"]["enabled"] is True
    assert payload["multimodal"]["input_modalities"] == ["text", "image", "audio", "video"]


def test_multimodal_input_requires_exactly_one_transport():
    with pytest.raises(ValueError, match="exactly one"):
        MultimodalInput(mime_type="image/png")
    with pytest.raises(ValueError, match="exactly one"):
        MultimodalInput(mime_type="image/png", url="https://a.test/x", data_base64="AA==")


def test_multimodal_input_reports_mime_modality():
    item = MultimodalInput(mime_type="video/mp4", url="https://a.test/video.mp4")
    assert item.modality == "video"
