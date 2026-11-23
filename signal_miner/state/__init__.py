"""State store protocol and in-memory implementation.

Design reference: agentic-prd-generation/backend/state/
"""

from __future__ import annotations

from typing import Any, Protocol


class StateStore(Protocol):
    """Protocol for a key-value state store."""

    backend_name: str

    async def save(self, key: str, value: dict[str, Any]) -> None: ...
    async def get(self, key: str) -> dict[str, Any] | None: ...
    async def delete(self, key: str) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class InMemoryStore:
    """Simple in-memory state store for development."""

    backend_name: str = "memory"

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def save(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = value

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()
