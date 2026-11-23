"""Shared types for text and multimodal LLM adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MultimodalInput:
    """One media input supplied to a multimodal model.

    Exactly one of ``url`` and ``data_base64`` must be supplied.  Keeping the
    transport neutral lets provider adapters decide whether to use a remote
    URI or inline bytes without coupling the mining pipeline to one vendor.
    """

    mime_type: str
    url: str | None = None
    data_base64: str | None = None

    def __post_init__(self) -> None:
        if not self.mime_type or "/" not in self.mime_type:
            raise ValueError("mime_type must be a non-empty media MIME type")
        if bool(self.url) == bool(self.data_base64):
            raise ValueError("exactly one of url or data_base64 must be provided")

    @property
    def modality(self) -> str:
        """Return the top-level MIME type used for capability checks."""
        return self.mime_type.split("/", 1)[0].lower()


__all__ = ["MultimodalInput"]
