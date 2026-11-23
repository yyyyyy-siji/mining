"""P13-1: Deterministic evidence validation against source text.

Checks whether LLM-returned evidence quotes actually appear in the original
feedback text.  Uses Unicode normalization + whitespace normalization only
— deliberately strict (no fuzzy/semantic matching) so that a paraphrase
is never mistaken for the original text.

Status values:
  - ``verified``: every quote is found in source text
  - ``partial``: some quotes found, some not
  - ``invalid``: no quotes found (or quotes list is empty)
  - ``not_checked``: validation not performed
"""

from __future__ import annotations

import unicodedata


def _normalize(text: str) -> str:
    """NFC-normalize and collapse whitespace for comparison."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    return " ".join(normalized.split())


def check_evidence_in_source(
    evidence_quotes: list[str],
    source_text: str,
) -> str:
    """Determine whether evidence quotes appear verbatim in source text.

    Returns one of: ``verified``, ``partial``, ``invalid``.
    """
    if not evidence_quotes:
        return "invalid"

    normalized_source = _normalize(source_text)
    if not normalized_source:
        return "invalid"

    matched = 0
    for quote in evidence_quotes:
        normalized_quote = _normalize(quote)
        if not normalized_quote:
            continue
        if normalized_quote in normalized_source:
            matched += 1

    if matched == len(evidence_quotes):
        return "verified"
    if matched > 0:
        return "partial"
    return "invalid"


__all__ = ["check_evidence_in_source"]
