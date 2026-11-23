"""P13-1: Confidence contract tests.

Verifies the structured confidence semantics:
  - Low-score signals (0.01) persist even with high legacy threshold (0.99)
  - calibrated_confidence remains null
  - Product profile rejects viral_hook via real extraction path
  - Product/video prompt versions recorded correctly
"""

from __future__ import annotations

import pytest

from signal_miner.models.feedback import ExtractedSignal, Signal

# ---------------------------------------------------------------------------
# Confidence contract — model-level tests
# ---------------------------------------------------------------------------

class TestConfidenceContract:
    """Verify LLM self-reported scores are separated from calibrated value."""

    def test_llm_confidence_099(self):
        """LLM returns confidence=0.99 — field exists."""
        extracted = ExtractedSignal(
            signalType="feature_request",
            summary="Test",
            evidence=["test"],
            confidence=0.99,
        )
        assert extracted.confidence == 0.99
        assert hasattr(extracted, "confidence")

    def test_signal_has_confidence_fields(self):
        """Signal model has all P13-1 confidence contract fields."""
        sig = Signal(
            raw_feedback_id="rfb_test",
            signal_type="feature_request",
            summary="Test signal",
            confidence=0.85,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        assert sig.model_self_score is None
        assert sig.calibrated_confidence is None
        assert sig.confidence_method is None
        assert sig.confidence_model_version is None
        assert sig.evidence_validation_status is None

    def test_calibrated_confidence_default_none(self):
        """calibrated_confidence must be null by default."""
        sig = Signal(
            raw_feedback_id="rfb_test",
            signal_type="feature_request",
            summary="Test",
            confidence=0.5,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            model_self_score=0.5,
            confidence_method="llm_self_reported",
        )
        assert sig.calibrated_confidence is None

    def test_extracted_signal_has_evidence_validation_default(self):
        """ExtractedSignal starts with evidence_validation_status=not_checked."""
        extracted = ExtractedSignal(
            signalType="bug_report",
            summary="Test",
            confidence=0.7,
        )
        assert extracted.evidence_validation_status == "not_checked"


# ---------------------------------------------------------------------------
# Behavioural extraction tests — real pipeline path
# ---------------------------------------------------------------------------

class FakeLowScoreLLM:
    """LLM adapter that returns a low-confidence signal."""
    provider_name = "test_fake"
    model_name = "test-model"
    supports_embedding = False
    last_usage = {"input_tokens": 10, "output_tokens": 20}

    async def call_structured(self, prompt, *, temperature=0.1, max_tokens=2000):
        return '{"signals":[{"signalType":"feature_request","summary":"Low-score test","evidence":["test"],"confidence":0.01}]}'

    async def call_text(self, prompt, *, temperature=0.3):
        return "ok"


class FakeViralHookLLM:
    """LLM adapter that returns viral_hook (invalid for product profile)."""
    provider_name = "test_fake"
    model_name = "test-model"
    supports_embedding = False
    last_usage = {"input_tokens": 10, "output_tokens": 20}

    async def call_structured(self, prompt, *, temperature=0.1, max_tokens=2000):
        return '{"signals":[{"signalType":"viral_hook","summary":"Viral test","evidence":["test"],"confidence":0.8}]}'

    async def call_text(self, prompt, *, temperature=0.3):
        return "ok"


class FakeAIGCVideoLLM:
    """LLM that returns a valid video signal type for video profile."""
    provider_name = "test_fake"
    model_name = "test-model"
    supports_embedding = False
    last_usage = {"input_tokens": 10, "output_tokens": 20}

    async def call_structured(self, prompt, *, temperature=0.1, max_tokens=2000):
        return '{"signals":[{"signalType":"viral_hook","summary":"Viral test","evidence":["test"],"confidence":0.8}]}'

    async def call_text(self, prompt, *, temperature=0.3):
        return "ok"


@pytest.mark.asyncio
class TestLowScoreSignalPersists:
    """Verify low-confidence signals are NOT dropped by confidence_threshold."""

    async def test_low_score_signal_persists_with_high_threshold(self):
        """0.01 score, threshold=0.99 → signal still persisted, calibrated=null."""
        import os
        import tempfile

        from signal_miner.db import close_db, get_session_factory, init_db
        from signal_miner.db.models import RawFeedbackRow, SignalRow
        from signal_miner.pipeline.quality_gate import QualityGateResult

        # --- Setup temp DB ---
        tmpdb = tempfile.mktemp(suffix='.db')
        db_url = f'sqlite+aiosqlite:///{tmpdb}'
        await init_db(db_url)

        try:
            sf = get_session_factory()
            # Insert raw feedback
            fb_id = "rfb_lowscore_test_001"
            async with sf() as session:
                row = RawFeedbackRow(
                    id=fb_id,
                    source_type="manual",
                    source_id="test_src",
                    dedupe_key="low_score_test",
                    content={"text": "The UI is slow and needs improvement.", "subject": "Performance"},
                    context={},
                    processing_state="pending",
                    pipeline_profile="product_feedback",
                )
                session.add(row)
                await session.commit()

            # Mock quality gate to always pass
            from unittest.mock import AsyncMock, patch

            import signal_miner.pipeline.extraction as ext_mod

            mock_gate = QualityGateResult(extract=True, reason="test", tier="actionable")

            with patch.object(ext_mod, "should_extract", AsyncMock(return_value=mock_gate)):
                # Call extract_signals with high legacy threshold
                from signal_miner.pipeline.pipeline_profile import get_profile
                profile = get_profile("product_feedback")
                llm = FakeLowScoreLLM()
                sig_ids = await ext_mod.extract_signals(
                    fb_id,
                    llm=llm,
                    max_signals=5,
                    confidence_threshold=0.99,  # Legacy, should NOT affect persistence
                    profile=profile,
                )

            assert len(sig_ids) == 1, f"Expected 1 signal, got {len(sig_ids)}"

            # Verify persisted fields
            async with sf() as session:
                sig = await session.get(SignalRow, sig_ids[0])
                assert sig is not None
                assert sig.model_self_score == 0.01
                assert sig.calibrated_confidence is None
                assert sig.confidence_method == "llm_self_reported"
                assert sig.signal_type == "feature_request"

        finally:
            await close_db()
            os.unlink(tmpdb)

    async def test_viral_hook_rejected_in_product_profile(self):
        """viral_hook from LLM is rejected in product_feedback profile."""
        import os
        import tempfile
        from unittest.mock import AsyncMock, patch

        from signal_miner.db import close_db, get_session_factory, init_db
        from signal_miner.db.models import RawFeedbackRow
        from signal_miner.pipeline.quality_gate import QualityGateResult

        tmpdb = tempfile.mktemp(suffix='.db')
        db_url = f'sqlite+aiosqlite:///{tmpdb}'
        await init_db(db_url)

        try:
            sf = get_session_factory()
            fb_id = "rfb_viralhook_test_001"
            async with sf() as session:
                row = RawFeedbackRow(
                    id=fb_id,
                    source_type="manual",
                    source_id="test_src",
                    dedupe_key="viral_hook_test",
                    content={"text": "Amazing viral technique discovered.", "subject": "Test"},
                    context={},
                    processing_state="pending",
                    pipeline_profile="product_feedback",
                )
                session.add(row)
                await session.commit()

            mock_gate = QualityGateResult(extract=True, reason="test", tier="actionable")

            import signal_miner.pipeline.extraction as ext_mod
            with patch.object(ext_mod, "should_extract", AsyncMock(return_value=mock_gate)):
                from signal_miner.pipeline.pipeline_profile import get_profile
                profile = get_profile("product_feedback")
                llm = FakeViralHookLLM()
                sig_ids = await ext_mod.extract_signals(
                    fb_id,
                    llm=llm,
                    max_signals=5,
                    confidence_threshold=0.5,
                    profile=profile,
                )

            # viral_hook not in product profile whitelist → rejected
            assert len(sig_ids) == 0, f"Expected 0 signals, got {len(sig_ids)}"

        finally:
            await close_db()
            os.unlink(tmpdb)


# ---------------------------------------------------------------------------
# SignalType whitelist isolation
# ---------------------------------------------------------------------------

class TestSignalTypeWhitelist:
    """Verify that product and video signal types are isolated."""

    def test_product_types_not_in_video(self):
        """Product feedback types must not appear in AIGC video profile."""
        from signal_miner.pipeline.pipeline_profile import (
            AIGC_VIDEO_PROFILE,
            PRODUCT_FEEDBACK_PROFILE,
        )
        product_set = set(PRODUCT_FEEDBACK_PROFILE.signal_types)
        video_set = set(AIGC_VIDEO_PROFILE.signal_types)
        assert product_set.isdisjoint(video_set)

    def test_viral_hook_not_in_product(self):
        """viral_hook must not be in product feedback whitelist."""
        from signal_miner.pipeline.pipeline_profile import PRODUCT_FEEDBACK_PROFILE
        assert "viral_hook" not in PRODUCT_FEEDBACK_PROFILE.signal_types

    def test_feature_request_not_in_video(self):
        """feature_request must not be in AIGC video whitelist."""
        from signal_miner.pipeline.pipeline_profile import AIGC_VIDEO_PROFILE
        assert "feature_request" not in AIGC_VIDEO_PROFILE.signal_types

    def test_product_profile_uses_v1_prompt(self):
        """product_feedback prompt_version is v1."""
        from signal_miner.pipeline.extraction import (
            EXTRACTION_PROMPT_VERSION,
            VIDEO_EXTRACTION_PROMPT_VERSION,
        )
        assert EXTRACTION_PROMPT_VERSION == "v1"
        assert VIDEO_EXTRACTION_PROMPT_VERSION == "v1-video"
        assert EXTRACTION_PROMPT_VERSION != VIDEO_EXTRACTION_PROMPT_VERSION
