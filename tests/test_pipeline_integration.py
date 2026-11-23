"""Integration tests for Phase 1 pipeline features.

Tests retry mechanism, run history persistence, quality gate bypass,
and the strip_code_fences utility function.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from signal_miner.pipeline.quality_gate import should_extract
from signal_miner.pipeline.utils import strip_code_fences

# ---------------------------------------------------------------------------
# Helpers: Mock LLM adapter
# ---------------------------------------------------------------------------

def _make_mock_llm(
    *,
    call_structured_side_effect=None,
    call_structured_return=None,
    provider_name: str = "mock",
):
    """Create a mock LLM adapter that conforms to BaseLLMAdapter Protocol."""
    llm = AsyncMock()
    llm.provider_name = provider_name
    llm.supports_embedding = False
    type(llm).last_usage = PropertyMock(
        return_value={"input_tokens": 10, "output_tokens": 20}
    )

    if call_structured_side_effect is not None:
        llm.call_structured = AsyncMock(side_effect=call_structured_side_effect)
    elif call_structured_return is not None:
        llm.call_structured = AsyncMock(return_value=call_structured_return)
    else:
        llm.call_structured = AsyncMock(return_value='{"extract": true, "reason": "ok", "tier": "signal"}')

    return llm


# ===========================================================================
# Test: strip_code_fences utility
# ===========================================================================

class TestStripCodeFencesUtility:
    """Verify strip_code_fences handles various inputs correctly."""

    def test_with_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_with_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_no_fence(self):
        text = '{"key": "value"}'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_empty_string(self):
        assert strip_code_fences("") == ""

    def test_whitespace_around_fences(self):
        text = '  ```json\n{"key": "value"}\n```  '
        result = strip_code_fences(text)
        assert result == '{"key": "value"}'

    def test_multiline_content(self):
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        result = strip_code_fences(text)
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}


# ===========================================================================
# Test: Quality Gate bypass
# ===========================================================================

class TestQualityGateBypass:
    """Verify quality gate bypass mechanism."""

    @pytest.mark.asyncio
    async def test_bypass_gate_skips_llm(self):
        """When bypass_gate=True, the LLM should NOT be called."""
        llm = _make_mock_llm()

        result = await should_extract(
            source_type="manual",
            text="Some feedback text here for testing",
            raw_feedback_id="rfb_test_001",
            llm=llm,
            bypass_gate=True,
        )

        assert result.extract is True
        assert result.tier == "bypassed"
        assert result.reason == "Gate bypassed"
        # LLM should NOT have been called
        llm.call_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_gate_calls_llm(self):
        """When bypass_gate=False (default), the LLM IS called."""
        gate_response = json.dumps({"extract": True, "reason": "has signal", "tier": "signal"})
        llm = _make_mock_llm(call_structured_return=gate_response)

        result = await should_extract(
            source_type="csv",
            text="I really need dark mode support in the editor",
            raw_feedback_id="rfb_test_002",
            llm=llm,
            bypass_gate=False,
        )

        assert result.extract is True
        llm.call_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_short_text_rejected_even_with_bypass_false(self):
        """Short texts are rejected before bypass logic is even checked."""
        llm = _make_mock_llm()

        result = await should_extract(
            source_type="manual",
            text="hi",
            raw_feedback_id="rfb_test_003",
            llm=llm,
            bypass_gate=False,
        )

        assert result.extract is False
        assert result.tier == "noise"

    @pytest.mark.asyncio
    async def test_bypass_overrides_short_text_check(self):
        """bypass_gate=True should return True even for short text."""
        llm = _make_mock_llm()

        result = await should_extract(
            source_type="manual",
            text="hi",
            raw_feedback_id="rfb_test_004",
            llm=llm,
            bypass_gate=True,
        )

        assert result.extract is True
        assert result.tier == "bypassed"


# ===========================================================================
# Test: Pipeline retry mechanism
# ===========================================================================

class TestPipelineRetry:
    """Verify the retry logic in extract_signals invocation within the runner."""

    @pytest.mark.asyncio
    async def test_retry_on_extraction_failure(self):
        """Simulate extract_signals failing twice then succeeding on the 3rd attempt.

        We test the retry logic at the runner level by patching extract_signals.
        """
        call_count = 0

        async def mock_extract_signals(fb_id, *, llm, max_signals=5, confidence_threshold=0.5, bypass_quality_gate=False, profile=None):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError(f"Simulated failure #{call_count}")
            return ["sig_001"]

        with patch("signal_miner.pipeline.runner.extract_signals", side_effect=mock_extract_signals):  # noqa: SIM117
            with patch("signal_miner.pipeline.runner.get_session_factory") as mock_sf:
                # Mock session factory for PipelineRunRow
                mock_session = AsyncMock()
                mock_session.get = AsyncMock(return_value=None)
                mock_session.add = MagicMock()
                mock_session.commit = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=False)
                mock_sf.return_value = MagicMock(return_value=mock_session)

                with patch("signal_miner.pipeline.runner.generate_embeddings_for_signals", new_callable=AsyncMock):  # noqa: SIM117
                    with patch("signal_miner.pipeline.runner.deduplicate_signals", new_callable=AsyncMock, return_value=(["sig_001"], 0)):  # noqa: SIM117
                        with patch("signal_miner.pipeline.runner.cluster_signals_into_themes", new_callable=AsyncMock, return_value=0):
                            with patch("signal_miner.pipeline.runner.log_pipeline_event", new_callable=AsyncMock):
                                from signal_miner.pipeline.runner import run_mining_pipeline

                                llm = _make_mock_llm()
                                result = await run_mining_pipeline(
                                    run_id="run_test_retry",
                                    feedback_ids=["fb_001"],
                                    llm=llm,
                                )

        assert result == "run_test_retry"
        # extract_signals should have been called 3 times (2 failures + 1 success)
        assert call_count == 3


# ===========================================================================
# Test: PipelineRunRow persistence
# ===========================================================================

class TestPipelineRunHistory:
    """Verify that PipelineRunRow is created and updated during pipeline runs."""

    @pytest.mark.asyncio
    async def test_pipeline_records_run_history(self):
        """Verify the pipeline creates a PipelineRunRow with status=running,
        then updates it to completed."""
        created_rows = []

        original_run_row = None

        class MockPipelineRunRow:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        async def mock_extract_signals(fb_id, *, llm, max_signals=5, confidence_threshold=0.5, bypass_quality_gate=False, profile=None):
            return ["sig_001"]

        mock_session = AsyncMock()

        async def mock_get(model_class, row_id):
            nonlocal original_run_row
            if original_run_row and row_id == original_run_row.id:
                return original_run_row
            return None

        def mock_add(row):
            nonlocal original_run_row
            created_rows.append(row)
            if hasattr(row, 'status') and hasattr(row, 'feedback_count'):
                original_run_row = row

        mock_session.get = mock_get
        mock_session.add = mock_add
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_sf = MagicMock(return_value=mock_session)

        with patch("signal_miner.pipeline.runner.extract_signals", side_effect=mock_extract_signals):  # noqa: SIM117
            with patch("signal_miner.pipeline.runner.get_session_factory", return_value=mock_sf):  # noqa: SIM117
                with patch("signal_miner.pipeline.runner.generate_embeddings_for_signals", new_callable=AsyncMock):
                    with patch("signal_miner.pipeline.runner.deduplicate_signals", new_callable=AsyncMock, return_value=(["sig_001"], 0)):
                        with patch("signal_miner.pipeline.runner.cluster_signals_into_themes", new_callable=AsyncMock, return_value=0):
                            with patch("signal_miner.pipeline.runner.log_pipeline_event", new_callable=AsyncMock):
                                from signal_miner.pipeline.runner import run_mining_pipeline

                                llm = _make_mock_llm()
                                result = await run_mining_pipeline(
                                    run_id="run_test_history",
                                    feedback_ids=["fb_001"],
                                    llm=llm,
                                )

        assert result == "run_test_history"
        # A PipelineRunRow should have been created
        assert len(created_rows) >= 1
        run_row = created_rows[0]
        assert run_row.id == "run_test_history"
        assert run_row.feedback_count == 1
        # After completion, the row should be updated. P13-1 fix-1: may be
        # "completed" or "completed_with_skips" depending on embedding status.
        assert run_row.status in ("completed", "completed_with_skips"), (
            f"Expected 'completed' or 'completed_with_skips', got {run_row.status}"
        )
