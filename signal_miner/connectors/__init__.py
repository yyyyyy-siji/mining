"""Data source connectors — base protocol and implementations.

Design reference: Quackback's integrations framework pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from signal_miner.models.feedback import RawFeedback


class BaseConnector(Protocol):
    """Protocol for data source connectors."""

    source_type: str

    async def fetch(self) -> AsyncIterator[RawFeedback]:
        """Yield raw feedback items from this source."""
        ...


class BrowserBaseConnector(BaseConnector, Protocol):
    """Protocol for connectors that rely on browser automation or external scraping services (e.g., MediaCrawler)."""

    requires_credentials: bool = True

    async def validate_credentials(self) -> bool:
        """Check if the current session/cookie is valid."""
        ...


# ---------------------------------------------------------------------------
# Connector Registry
# ---------------------------------------------------------------------------

CONNECTOR_REGISTRY: dict[str, type] = {}


def register_connector(name: str, connector_class: type) -> None:
    """Register a connector type."""
    CONNECTOR_REGISTRY[name] = connector_class


def get_connector(name: str) -> type:
    """Get a registered connector type by name.

    Raises:
        ValueError: If the name is not found in the registry.
    """
    if name not in CONNECTOR_REGISTRY:
        raise ValueError(
            f"Unknown connector type: '{name}'. "
            f"Available: {list(CONNECTOR_REGISTRY.keys())}"
        )
    return CONNECTOR_REGISTRY[name]


def list_connectors() -> list[str]:
    """List all registered connector type names."""
    return list(CONNECTOR_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Auto-register all available connectors
# ---------------------------------------------------------------------------

from signal_miner.connectors.csv_connector import CSVConnector, ManualConnector  # noqa: E402
from signal_miner.connectors.github_connector import GitHubConnector  # noqa: E402
from signal_miner.connectors.webhook_connector import WebhookConnector  # noqa: E402

register_connector("csv", CSVConnector)
register_connector("manual", ManualConnector)
register_connector("github", GitHubConnector)
register_connector("webhook", WebhookConnector)
