"""P13-1: Embedding safety tests.

Verifies that:
  1. When the LLM adapter does NOT support embeddings, no pseudo vectors
     are generated, and the status returned is ``skipped_no_real_embedding``.
  2. When ``find_similar_signals`` encounters a pseudo-embedding target,
     it returns empty results.
  3. Deduplication does not perform destructive dismiss.
"""

from __future__ import annotations

import os

import pytest


class FakeNoEmbeddingAdapter:
    """LLM adapter that does NOT support embeddings."""

    provider_name = "test_no_embed"
    model_name = "test-model"
    input_modalities = ("text",)
    supports_multimodal = False
    supports_embedding = False
    last_usage = {"input_tokens": 10, "output_tokens": 20}

    async def call_text(self, prompt, *, temperature=0.3):
        return "ok"

    async def call_structured(self, prompt, *, temperature=0.1, max_tokens=2000):
        return "{}"

    async def embed(self, text):
        raise NotImplementedError("No embedding support")


class TestEmbeddingSafety:
    """Verify pseudo-embeddings are blocked in production."""

    @pytest.mark.asyncio
    async def test_no_pseudo_embedding_in_production(self):
        """When adapter lacks embedding support, semantic_ready=False."""
        from signal_miner.pipeline.embedding import generate_embeddings_for_signals

        old_val = os.environ.pop("ALLOW_TEST_PSEUDO_EMBEDDING", None)
        try:
            adapter = FakeNoEmbeddingAdapter()
            result = await generate_embeddings_for_signals(["fake_id"], adapter)
            assert result.semantic_ready is False
            assert result.status == "skipped_no_real_embedding_capability"
        finally:
            if old_val is not None:
                os.environ["ALLOW_TEST_PSEUDO_EMBEDDING"] = old_val

    def test_pseudo_embedding_model_detection(self):
        """_is_pseudo_embedding_model correctly identifies pseudo models."""
        from signal_miner.pipeline.deduplication import _is_pseudo_embedding_model

        assert _is_pseudo_embedding_model("deepseek_pseudo_embedding") is True
        assert _is_pseudo_embedding_model("openai_test_only_pseudo") is True
        assert _is_pseudo_embedding_model(None) is True
        assert _is_pseudo_embedding_model("") is True
        assert _is_pseudo_embedding_model("openai_embedding") is False

    def test_pseudo_filter_in_clustering(self):
        """_is_pseudo_embedding_model in clustering correctly filters."""
        from signal_miner.pipeline.clustering import _is_pseudo_embedding_model

        assert _is_pseudo_embedding_model("deepseek_pseudo_embedding") is True
        assert _is_pseudo_embedding_model("openai_embedding") is False

    @pytest.mark.asyncio
    async def test_production_env_blocks_pseudo_even_with_flag(self):
        """ALLOW_TEST_PSEUDO_EMBEDDING=1 in development → still blocked."""
        from signal_miner.pipeline.embedding import generate_embeddings_for_signals

        old_flag = os.environ.pop("ALLOW_TEST_PSEUDO_EMBEDDING", None)
        old_env = os.environ.pop("APP_ENVIRONMENT", None)
        try:
            os.environ["ALLOW_TEST_PSEUDO_EMBEDDING"] = "1"
            os.environ["APP_ENVIRONMENT"] = "development"
            adapter = FakeNoEmbeddingAdapter()
            result = await generate_embeddings_for_signals(["fake_id"], adapter)
            assert result.semantic_ready is False
            assert result.status == "skipped_no_real_embedding_capability"
        finally:
            if old_flag is not None:
                os.environ["ALLOW_TEST_PSEUDO_EMBEDDING"] = old_flag
            else:
                os.environ.pop("ALLOW_TEST_PSEUDO_EMBEDDING", None)
            if old_env is not None:
                os.environ["APP_ENVIRONMENT"] = old_env
            else:
                os.environ.pop("APP_ENVIRONMENT", None)


class TestDeduplicationSafety:
    """Verify deduplication does not make destructive dismiss decisions."""

    @pytest.mark.asyncio
    async def test_dedup_no_destructive_dismiss(self):
        """Deduplication must NOT dismiss signals based on uncalibrated confidence."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from signal_miner.pipeline import deduplication as dedup_mod

        # Mock the session factory so no real DB access occurs
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No signals with embeddings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(dedup_mod, "get_session_factory", return_value=mock_factory):
            surviving, removed = await dedup_mod.deduplicate_signals(["fake_1", "fake_2"])

        assert removed == 0  # No destructive dismiss
        assert len(surviving) == 2  # All survive


# ---------------------------------------------------------------------------
# P13-1 fix-1: Runner control-flow — circuit breaker tests
# ---------------------------------------------------------------------------

class TestRunnerCircuitBreaker:
    """When embedding returns skipped/blocked, runner MUST NOT call
    dedup, cluster, or asset generation."""

    @pytest.mark.asyncio
    async def test_no_real_embedding_circuit_breaker(self):
        """skipped_no_real_embedding → dedup/cluster/asset await_count == 0."""
        import os
        import tempfile
        from unittest.mock import AsyncMock, patch

        from signal_miner.db import close_db, get_session_factory, init_db
        from signal_miner.db.models import RawFeedbackRow

        # --- Setup temp DB ---
        tmpdb = tempfile.mktemp(suffix='.db')
        db_url = f'sqlite+aiosqlite:///{tmpdb}'
        await init_db(db_url)

        try:
            sf = get_session_factory()
            fb_id = "rfb_breaker_test_001"
            async with sf() as session:
                row = RawFeedbackRow(
                    id=fb_id,
                    source_type="manual",
                    source_id="test_src",
                    dedupe_key="breaker_test",
                    content={"text": "Test feedback for circuit breaker.", "subject": "Test"},
                    context={},
                    processing_state="pending",
                    pipeline_profile="product_feedback",
                )
                session.add(row)
                await session.commit()

            # Prepare mock pipeline functions — EmbeddingResult with semantic_ready=False
            from signal_miner.pipeline.embedding import EmbeddingResult
            mock_embed = AsyncMock(return_value=EmbeddingResult(
                status="skipped_no_real_embedding_capability",
                semantic_ready=False,
                reason="Test: no embedding capability",
                requested_count=1,
            ))
            mock_dedup = AsyncMock(return_value=(["sig_001"], 0))
            mock_cluster = AsyncMock(return_value=0)
            mock_assets = AsyncMock(return_value={})

            from signal_miner.pipeline import runner as runner_mod

            # Mock the LLM for extraction
            class MockLLM:
                provider_name = "test"
                model_name = "test"
                last_usage = {"input_tokens": 1, "output_tokens": 1}

                async def call_structured(self, prompt, *, temperature=0.1, max_tokens=2000):
                    return '{"signals":[]}'

            llm = MockLLM()

            # Run the real runner with mocked pipeline steps
            with (
                patch.object(runner_mod, "extract_signals", AsyncMock(return_value=["sig_001"])),
                patch.object(runner_mod, "generate_embeddings_for_signals", mock_embed),
                patch.object(runner_mod, "deduplicate_signals", mock_dedup),
                patch.object(runner_mod, "cluster_signals_into_themes", mock_cluster),
                patch.object(runner_mod, "generate_assets_from_themes", mock_assets),
            ):
                await runner_mod.run_mining_pipeline(
                    run_id="run_breaker_test",
                    feedback_ids=[fb_id],
                    llm=llm,
                    streamer=None,
                )

            # Assert: circuit breaker fired — none of the semantic phases were called
            assert mock_dedup.await_count == 0, (
                f"Expected dedup await_count=0, got {mock_dedup.await_count}"
            )
            assert mock_cluster.await_count == 0, (
                f"Expected cluster await_count=0, got {mock_cluster.await_count}"
            )
            assert mock_assets.await_count == 0, (
                f"Expected asset await_count=0, got {mock_assets.await_count}"
            )

        finally:
            await close_db()
            os.unlink(tmpdb)
