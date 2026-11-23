"""CSV/JSON file connector for batch feedback import.

Supports importing feedback from structured files — the simplest
way to get started without external integrations.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from signal_miner.models.feedback import FeedbackAuthor, FeedbackContent, RawFeedback

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class CSVConnector:
    """Import raw feedback from CSV or JSON files."""

    source_type: str = "csv"

    def __init__(self, file_path: str, source_id: str = "csv_import") -> None:
        self._file_path = Path(file_path)
        self._source_id = source_id

    async def fetch(self) -> AsyncIterator[RawFeedback]:
        """Parse and yield feedback items from the file."""
        suffix = self._file_path.suffix.lower()
        if suffix == ".json":
            items = self._load_json()
        elif suffix in (".csv", ".tsv"):
            items = self._load_csv()
        else:
            raise ValueError(f"Unsupported file type: {suffix}. Use .csv, .tsv, or .json")

        for item in items:
            yield item

    def _load_json(self) -> list[RawFeedback]:
        """Load feedback from a JSON file (array of objects)."""
        with open(self._file_path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = [data]

        results = []
        for idx, row in enumerate(data):
            text = row.get("text", row.get("content", row.get("body", row.get("feedback", ""))))
            subject = row.get("subject", row.get("title", row.get("summary", None)))

            feedback = RawFeedback(
                source_type=self.source_type,
                source_id=self._source_id,
                dedupe_key=self._make_dedupe_key(text, idx),
                external_id=str(row.get("id", idx)),
                author=FeedbackAuthor(
                    name=row.get("author", row.get("user", row.get("name", None))),
                    email=row.get("email", None),
                    company=row.get("company", None),
                    segment=row.get("segment", None),
                ),
                content=FeedbackContent(subject=subject, text=text),
                context=_extract_context(row),
            )
            results.append(feedback)

        return results

    def _load_csv(self) -> list[RawFeedback]:
        """Load feedback from a CSV/TSV file."""
        delimiter = "\t" if self._file_path.suffix.lower() == ".tsv" else ","
        with open(self._file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            results = []
            for idx, row in enumerate(reader):
                text = _first_nonempty(row, ["text", "content", "body", "feedback", "description"])
                subject = _first_nonempty(row, ["subject", "title", "summary"])

                feedback = RawFeedback(
                    source_type=self.source_type,
                    source_id=self._source_id,
                    dedupe_key=self._make_dedupe_key(text, idx),
                    external_id=str(row.get("id", idx)),
                    author=FeedbackAuthor(
                        name=_first_nonempty(row, ["author", "user", "name"]),
                        email=row.get("email"),
                        company=row.get("company"),
                        segment=row.get("segment"),
                    ),
                    content=FeedbackContent(subject=subject, text=text),
                    context=_extract_context(row),
                )
                results.append(feedback)

            return results

    @staticmethod
    def _make_dedupe_key(text: str, index: int) -> str:
        """Generate a stable dedup key from content hash."""
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"csv_{index}_{content_hash}"


class ManualConnector:
    """Create a single feedback item from manual text input."""

    source_type: str = "manual"

    def __init__(self, source_id: str = "manual_input") -> None:
        self._source_id = source_id

    async def from_text(
        self,
        text: str,
        *,
        subject: str | None = None,
        author_name: str | None = None,
        author_email: str | None = None,
        segment: str | None = None,
    ) -> RawFeedback:
        """Create a RawFeedback from manual text input."""
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return RawFeedback(
            source_type=self.source_type,
            source_id=self._source_id,
            dedupe_key=f"manual_{content_hash}",
            author=FeedbackAuthor(
                name=author_name,
                email=author_email,
                segment=segment,
            ),
            content=FeedbackContent(subject=subject, text=text),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_nonempty(row: dict, keys: list[str]) -> str | None:
    """Return the first non-empty value from a dict for the given keys."""
    for key in keys:
        val = row.get(key, "")
        if val and str(val).strip():
            return str(val).strip()
    return None


def _extract_context(row: dict[str, Any]) -> dict:
    """Extract non-core fields as context metadata."""
    core_keys = {
        "id", "text", "content", "body", "feedback", "description",
        "subject", "title", "summary", "author", "user", "name",
        "email", "company", "segment",
    }
    return {k: v for k, v in row.items() if k not in core_keys and v}
