"""SSE streaming service for pipeline progress updates.

Design reference: agentic-prd-generation/backend/services/streamer.py
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class StreamerService:
    """Manages SSE connections, broadcasts progress, and caches recent run states."""

    def __init__(self) -> None:
        self._queues: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._latest: dict[str, dict[str, Any]] = {}
        self._steps: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def add_subscriber(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Create a subscriber queue and replay any cached steps for reconnects."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._queues[run_id].add(queue)
            steps = list(self._steps.get(run_id, {}).values())
            latest = self._latest.get(run_id)
        for event in steps:
            await queue.put(event)
        if latest and (not steps or latest is not steps[-1]):
            await queue.put(latest)
        return queue

    async def remove_subscriber(
        self, run_id: str, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        """Remove a subscriber queue for a pipeline run."""
        async with self._lock:
            subscribers = self._queues.get(run_id)
            if not subscribers:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._queues.pop(run_id, None)

    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        """Return latest event and per-step snapshots for status recovery."""
        latest = self._latest.get(run_id)
        steps = self._steps.get(run_id)
        if not latest and not steps:
            return None
        return {
            "latest": dict(latest) if latest else None,
            "steps": {k: dict(v) for k, v in (steps or {}).items()},
        }

    def recent_runs(self) -> list[dict[str, Any]]:
        """Return latest cached payloads in newest-first order."""
        return [dict(v) for v in reversed(list(self._latest.values()))]

    async def publish(self, run_id: str, data: dict[str, Any]) -> None:
        """Broadcast a payload to all subscribers for a pipeline run."""
        async with self._lock:
            self._latest[run_id] = dict(data)
            step_key = data.get("step")
            if isinstance(step_key, str) and step_key:
                self._steps.setdefault(run_id, {})[step_key] = dict(data)
            for old in list(self._latest)[:-50]:
                self._latest.pop(old, None)
                self._steps.pop(old, None)
            subscribers = list(self._queues.get(run_id, set()))
        for queue in subscribers:
            await queue.put(data)
