"""Tests for the Webhook connector."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from signal_miner.connectors.webhook_connector import WebhookConnector

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def connector_with_secret():
    return WebhookConnector(secret="my-secret-key")


@pytest.fixture
def connector_without_secret():
    return WebhookConnector()


# ---------------------------------------------------------------------------
# Signature verification tests
# ---------------------------------------------------------------------------

def test_verify_signature_valid(connector_with_secret):
    """Correct signature → True."""
    payload = b'{"text":"hello"}'
    expected_sig = hmac.new(
        b"my-secret-key", payload, hashlib.sha256
    ).hexdigest()
    sig_header = f"sha256={expected_sig}"

    assert connector_with_secret.verify_signature(payload, sig_header) is True


def test_verify_signature_invalid(connector_with_secret):
    """Wrong signature → False."""
    payload = b'{"text":"hello"}'
    bad_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    assert connector_with_secret.verify_signature(payload, bad_sig) is False


def test_verify_signature_no_secret(connector_without_secret):
    """No secret configured → always True (pass-through)."""
    payload = b'{"text":"no-secret"}'
    assert connector_without_secret.verify_signature(payload, "anything") is True
    assert connector_without_secret.verify_signature(payload, "") is True


def test_verify_signature_without_prefix(connector_with_secret):
    """Signature without 'sha256=' prefix also works."""
    payload = b'{"text":"test"}'
    sig = hmac.new(b"my-secret-key", payload, hashlib.sha256).hexdigest()
    assert connector_with_secret.verify_signature(payload, sig) is True


# ---------------------------------------------------------------------------
# Payload parsing tests
# ---------------------------------------------------------------------------

def test_parse_payload_standard():
    """Standard payload with text + author → valid RawFeedback."""
    connector = WebhookConnector()
    payload = {
        "text": "This feature is broken.",
        "title": "Bug Report",
        "author": "Alice",
        "email": "alice@example.com",
    }
    feedback = connector.parse_payload(payload)

    assert feedback.source_type == "webhook"
    assert feedback.content.text == "This feature is broken."
    assert feedback.content.subject == "Bug Report"
    assert feedback.author.name == "Alice"
    assert feedback.author.email == "alice@example.com"
    assert feedback.dedupe_key.startswith("webhook_webhook_default_")


def test_parse_payload_alternative_keys():
    """Alternative field names (body, sender) map correctly."""
    connector = WebhookConnector()
    payload = {
        "body": "The dashboard loads too slowly.",
        "sender": "Bob",
    }
    feedback = connector.parse_payload(payload)

    assert feedback.content.text == "The dashboard loads too slowly."
    assert feedback.author.name == "Bob"
    assert feedback.content.subject is None


def test_parse_payload_message_key():
    """'message' key maps to content.text."""
    connector = WebhookConnector()
    payload = {"message": "Please add dark mode."}
    feedback = connector.parse_payload(payload)

    assert feedback.content.text == "Please add dark mode."


def test_parse_payload_feedback_key():
    """'feedback' key (least priority) maps to content.text."""
    connector = WebhookConnector()
    payload = {"feedback": "Great app overall."}
    feedback = connector.parse_payload(payload)

    assert feedback.content.text == "Great app overall."


def test_parse_payload_missing_text():
    """Missing all text fields → ValueError."""
    connector = WebhookConnector()
    payload = {"timestamp": "2026-01-01", "source": "unknown"}

    with pytest.raises(ValueError, match="missing a recognised text field"):
        connector.parse_payload(payload)


def test_parse_payload_text_priority():
    """'text' takes priority over other keys."""
    connector = WebhookConnector()
    payload = {
        "text": "priority text",
        "body": "fallback body",
        "message": "other message",
    }
    feedback = connector.parse_payload(payload)
    assert feedback.content.text == "priority text"


def test_parse_payload_dedupe_key_stability():
    """Same text produces same dedupe_key."""
    connector = WebhookConnector()
    payload1 = {"text": "Stable text", "author": "Alice"}
    payload2 = {"text": "Stable text", "author": "Bob"}

    fb1 = connector.parse_payload(payload1)
    fb2 = connector.parse_payload(payload2)

    assert fb1.dedupe_key == fb2.dedupe_key
