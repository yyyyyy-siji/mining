"""Tests for the CSV connector."""

import json

import pytest

from signal_miner.connectors.csv_connector import CSVConnector, ManualConnector


class TestCSVConnector:
    @pytest.mark.asyncio
    async def test_load_json(self, tmp_path):
        """Test loading feedback from a JSON file."""
        data = [
            {"text": "I want dark mode", "author": "Alice", "title": "Dark mode request"},
            {"text": "The app crashes on startup", "author": "Bob"},
            {"feedback": "Love the product!", "user": "Charlie"},
        ]
        json_file = tmp_path / "feedback.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")

        connector = CSVConnector(str(json_file), source_id="test_json")
        items = [item async for item in connector.fetch()]

        assert len(items) == 3
        assert items[0].content.text == "I want dark mode"
        assert items[0].content.subject == "Dark mode request"
        assert items[0].author.name == "Alice"
        assert items[0].source_type == "csv"
        assert items[2].content.text == "Love the product!"

    @pytest.mark.asyncio
    async def test_load_csv(self, tmp_path):
        """Test loading feedback from a CSV file."""
        csv_content = "title,text,author,company\nBug,App crashes,Alice,Acme\nFeature,Need API,Bob,\n"
        csv_file = tmp_path / "feedback.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        connector = CSVConnector(str(csv_file))
        items = [item async for item in connector.fetch()]

        assert len(items) == 2
        assert items[0].content.subject == "Bug"
        assert items[0].content.text == "App crashes"
        assert items[0].author.name == "Alice"
        assert items[0].author.company == "Acme"

    @pytest.mark.asyncio
    async def test_dedupe_keys_unique(self, tmp_path):
        """Test that different items get different dedupe keys."""
        data = [
            {"text": "feedback one"},
            {"text": "feedback two"},
        ]
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")

        connector = CSVConnector(str(json_file))
        items = [item async for item in connector.fetch()]

        assert items[0].dedupe_key != items[1].dedupe_key


class TestManualConnector:
    @pytest.mark.asyncio
    async def test_from_text(self):
        """Test creating feedback from manual text input."""
        connector = ManualConnector()
        feedback = await connector.from_text(
            "I need better search functionality",
            subject="Search improvement",
            author_name="Test User",
        )

        assert feedback.content.text == "I need better search functionality"
        assert feedback.content.subject == "Search improvement"
        assert feedback.source_type == "manual"
        assert feedback.author.name == "Test User"

    @pytest.mark.asyncio
    async def test_deterministic_dedupe(self):
        """Test that same text produces same dedupe key."""
        connector = ManualConnector()
        fb1 = await connector.from_text("same text")
        fb2 = await connector.from_text("same text")
        assert fb1.dedupe_key == fb2.dedupe_key


# ---------------------------------------------------------------------------
# Connector Registry tests
# ---------------------------------------------------------------------------

class TestConnectorRegistry:
    def test_list_connectors(self):
        """list_connectors() returns at least 4 registered connector types."""
        from signal_miner.connectors import list_connectors

        names = list_connectors()
        assert "csv" in names
        assert "manual" in names
        assert "github" in names
        assert "webhook" in names

    def test_get_connector_github(self):
        """get_connector('github') returns GitHubConnector class."""
        from signal_miner.connectors import get_connector
        from signal_miner.connectors.github_connector import GitHubConnector

        cls = get_connector("github")
        assert cls is GitHubConnector

    def test_get_connector_unknown(self):
        """get_connector('unknown') raises ValueError."""
        from signal_miner.connectors import get_connector

        with pytest.raises(ValueError, match="Unknown connector type"):
            get_connector("unknown")

    def test_register_custom(self):
        """A custom connector class can be registered and retrieved."""
        from signal_miner.connectors import (
            CONNECTOR_REGISTRY,
            get_connector,
            register_connector,
        )

        class CustomConnector:
            source_type = "custom"

        register_connector("custom", CustomConnector)
        try:
            cls = get_connector("custom")
            assert cls is CustomConnector
        finally:
            # Clean up to avoid polluting the global registry
            CONNECTOR_REGISTRY.pop("custom", None)
