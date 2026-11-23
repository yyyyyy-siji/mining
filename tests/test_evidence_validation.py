"""P13-1: Evidence validation tests.

Verifies the deterministic source-text matching for LLM-returned evidence:
  - All quotes found → verified
  - Some quotes found → partial
  - No quotes found → invalid
  - Empty evidence → invalid
  - Unicode normalization works (NFC)
"""

from __future__ import annotations

from signal_miner.pipeline.evidence_validation import check_evidence_in_source


class TestEvidenceValidation:
    """Verify deterministic evidence-in-source checking."""

    def test_all_quotes_match(self):
        """All evidence quotes found in source → verified."""
        source = "The export feature is broken and crashes every time I use it."
        quotes = ["export feature is broken", "crashes every time"]
        assert check_evidence_in_source(quotes, source) == "verified"

    def test_partial_match(self):
        """One real quote + one fake quote → partial."""
        source = "The export feature is broken and crashes every time I use it."
        quotes = ["export feature is broken", "this quote does not exist in the text"]
        assert check_evidence_in_source(quotes, source) == "partial"

    def test_no_match(self):
        """None of the quotes appear in source → invalid."""
        source = "The export feature is broken."
        quotes = ["completely fabricated quote", "another made up text"]
        assert check_evidence_in_source(quotes, source) == "invalid"

    def test_empty_evidence(self):
        """Empty evidence list → invalid."""
        source = "Some source text here."
        assert check_evidence_in_source([], source) == "invalid"

    def test_empty_source(self):
        """Empty source text → invalid."""
        assert check_evidence_in_source(["some quote"], "") == "invalid"

    def test_unicode_normalization(self):
        """NFC normalization: precomposed and decomposed forms match."""
        # 'é' (U+00E9) vs 'e' + combining accent (U+0065 U+0301)
        source = "Caf\u00e9 quality is great"
        quote = "Caf\u0065\u0301 quality"  # Same text, decomposed
        assert check_evidence_in_source([quote], source) == "verified"

    def test_whitespace_normalization(self):
        """Extra whitespace in quote still matches."""
        source = "The  feature   is    broken"
        quote = "The feature is broken"
        assert check_evidence_in_source([quote], source) == "verified"

    def test_no_fuzzy_match(self):
        """Paraphrase must NOT be considered a match."""
        source = "The export functionality is not working correctly."
        quote = "the export is broken"  # Paraphrase, not verbatim
        assert check_evidence_in_source([quote], source) == "invalid"
