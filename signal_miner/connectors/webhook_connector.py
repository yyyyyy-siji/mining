"""Webhook connector — ingest feedback from generic HTTP webhook payloads.

This is a push-based connector. It does not implement ``fetch()``.
Instead it provides ``verify_signature()`` and ``parse_payload()`` for
use inside a FastAPI route that receives incoming webhook requests.
"""

from __future__ import annotations

import hashlib
import hmac

from signal_miner.models.feedback import FeedbackAuthor, FeedbackContent, RawFeedback


class WebhookConnector:
    """Accept and validate generic webhook payloads.

    Security: supports HMAC-SHA256 signature verification via ``secret``.
    Payload parsing uses loose field mapping — similar to CSVConnector's
    ``_first_nonempty`` pattern — to accommodate various webhook formats.
    """

    source_type: str = "webhook"

    def __init__(
        self,
        source_id: str = "webhook_default",
        secret: str | None = None,
    ) -> None:
        self._source_id = source_id
        self._secret = secret

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature on the webhook payload.

        If no secret is configured, always returns ``True`` (pass-through
        without verification).

        Args:
            payload: Raw bytes of the webhook request body.
            signature: Value of the ``X-Hub-Signature-256`` or
                       ``X-Signature`` header (including ``sha256=`` prefix).

        Returns:
            ``True`` if the signature is valid or no secret is configured.
        """
        if not self._secret:
            return True

        # Strip the "sha256=" prefix if present
        sig_value = signature
        if sig_value.startswith("sha256="):
            sig_value = sig_value[7:]

        expected = hmac.new(
            self._secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, sig_value)

    def parse_payload(self, payload: dict) -> RawFeedback:
        """Convert a generic webhook JSON payload into a RawFeedback.

        Uses loose field mapping:
          - ``text`` / ``content`` / ``body`` / ``message`` / ``feedback`` → content.text
          - ``title`` / ``subject`` / ``summary`` → content.subject
          - ``author`` / ``user`` / ``sender`` / ``name`` → author.name
          - ``email`` → author.email

        The ``dedupe_key`` is derived from a SHA-256 hash of the text.

        Raises:
            ValueError: If no text field can be found in the payload.
        """
        text = self._first_nonempty(payload, ["text", "content", "body", "message", "feedback"])
        if not text:
            raise ValueError(
                f"Webhook payload missing a recognised text field. "
                f"Available keys: {list(payload.keys())}"
            )

        subject = self._first_nonempty(payload, ["title", "subject", "summary"])
        author_name = self._first_nonempty(payload, ["author", "user", "sender", "name"])
        author_email = payload.get("email", "")

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        return RawFeedback(
            source_type=self.source_type,
            source_id=self._source_id,
            dedupe_key=f"webhook_{self._source_id}_{content_hash}",
            external_id=str(payload.get("id") or ""),
            external_url=payload.get("url"),
            author=FeedbackAuthor(
                name=author_name,
                email=str(author_email) if author_email else None,
            ),
            content=FeedbackContent(subject=subject, text=text),
            context={k: v for k, v in payload.items() if k not in {
                "id", "url", "text", "content", "body", "message", "feedback",
                "title", "subject", "summary", "author", "user", "sender",
                "name", "email",
            }},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _first_nonempty(data: dict, keys: list[str]) -> str | None:
        for key in keys:
            val = data.get(key)
            if val and str(val).strip():
                return str(val).strip()
        return None
