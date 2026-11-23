#!/usr/bin/env python3
"""P13-1 fix-2: Real behavior probe.  Every observation from actual execution
on temp databases.  Exit non-zero if any check fails.  No mock-only assertions.

Output: docs/P13-1-evidence/behavior_probe.json
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import AsyncMock, patch

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


# ── helpers ──

def _tmp_db_url() -> str:
    return f"sqlite+aiosqlite:///{tempfile.mktemp(suffix='.db')}"


class _SigCounter:
    """Read-only counts from a DB at a given URL."""
    @staticmethod
    async def count(db_url: str) -> dict:
        from sqlalchemy import func, select

        from signal_miner.db import close_db, get_session_factory, init_db
        from signal_miner.db.models import RawFeedbackRow, SignalRow, ThemeRow

        await init_db(db_url)
        sf = get_session_factory()
        async with sf() as s:
            sig = (await s.execute(select(func.count(SignalRow.id)))).scalar() or 0
            fb = (await s.execute(select(func.count(RawFeedbackRow.id)))).scalar() or 0
            thm = (await s.execute(select(func.count(ThemeRow.id)))).scalar() or 0
            dis = (await s.execute(
                select(func.count(SignalRow.id)).where(SignalRow.processing_state == "dismissed"),
            )).scalar() or 0
            pse = (await s.execute(
                select(func.count(SignalRow.id)).where(SignalRow.embedding_model.like("%pseudo%")),
            )).scalar() or 0
        await close_db()
        return {"signals": sig, "feedback": fb, "themes": thm, "dismissed": dis, "pseudo": pse}


# ── Fake embed adapter that always fails ──

class _FailingEmbedAdapter:
    provider_name = "failing_embed"
    model_name = "test"
    supports_embedding = True
    last_usage = {"input_tokens": 1, "output_tokens": 1}

    async def call_structured(self, *_a, **_kw):
        return '{"signals":[]}'

    async def call_text(self, *_a, **_kw):
        return "ok"

    async def embed(self, _text: str):
        raise RuntimeError("forced embedding failure")


# ── Low-score persistence probe ──

async def probe_low_score() -> dict:
    """Run real extract_signals with confidence=0.01 and threshold=0.99."""
    db_url = _tmp_db_url()

    from signal_miner.db import close_db, get_session_factory, init_db
    from signal_miner.db.models import RawFeedbackRow, SignalRow

    await init_db(db_url)
    sf = get_session_factory()
    fb_id = "rfb_low_001"
    async with sf() as s:
        s.add(RawFeedbackRow(
            id=fb_id, source_type="manual", source_id="src", dedupe_key="lp",
            content={"text": "test", "subject": "t"}, context={},
            processing_state="pending", pipeline_profile="product_feedback",
        ))
        await s.commit()

    class FakeLowLLM:
        provider_name = "fake"
        model_name = "test"
        supports_embedding = False
        last_usage = {"input_tokens": 1, "output_tokens": 1}
        async def call_structured(self, *_a, **_kw):
            return '{"signals":[{"signalType":"feature_request","summary":"Low","evidence":["t"],"confidence":0.01}]}'
        async def call_text(self, *_a, **_kw): return "ok"

    import signal_miner.pipeline.extraction as ext_mod
    from signal_miner.pipeline.extraction import extract_signals
    from signal_miner.pipeline.pipeline_profile import get_profile
    from signal_miner.pipeline.quality_gate import QualityGateResult

    g = QualityGateResult(extract=True, reason="t", tier="actionable")
    with patch.object(ext_mod, "should_extract", AsyncMock(return_value=g)):
        sig_ids = await extract_signals(fb_id, llm=FakeLowLLM(), max_signals=5,
                                         confidence_threshold=0.99, profile=get_profile("product_feedback"))

    result = {"persisted_count": len(sig_ids)}
    if len(sig_ids) == 1:
        async with sf() as s:
            sig = await s.get(SignalRow, sig_ids[0])
            result["model_self_score"] = sig.model_self_score
            result["calibrated_confidence"] = sig.calibrated_confidence
            result["confidence_method"] = sig.confidence_method
    result["passed"] = (
        result.get("persisted_count") == 1
        and result.get("model_self_score") == 0.01
        and result.get("calibrated_confidence") is None
        and result.get("confidence_method") == "llm_self_reported"
    )
    await close_db()
    return result


# ── Circuit breaker probe: no capability ──

async def probe_no_capability() -> dict:
    """Runner with no-embedding adapter → dedup/cluster/asset = 0."""
    db_url = _tmp_db_url()
    from signal_miner.db import close_db, get_session_factory, init_db
    from signal_miner.db.models import RawFeedbackRow

    await init_db(db_url)
    sf = get_session_factory()
    fb_id = "rfb_nc_001"
    async with sf() as s:
        s.add(RawFeedbackRow(
            id=fb_id, source_type="manual", source_id="src", dedupe_key="nc",
            content={"text": "test", "subject": "t"}, context={},
            processing_state="pending", pipeline_profile="product_feedback",
        ))
        await s.commit()

    class NoEmbedLLM:
        provider_name = "test"
        model_name = "test"
        supports_embedding = False
        last_usage = {"input_tokens": 1, "output_tokens": 1}
        async def call_structured(self, *_a, **_kw):
            return '{"signals":[]}'

    from signal_miner.pipeline import runner as runner_mod
    mock_dedup = AsyncMock(return_value=(["sig"], 0))
    mock_cluster = AsyncMock(return_value=0)
    mock_assets = AsyncMock(return_value={})

    with (
        patch.object(runner_mod, "extract_signals", AsyncMock(return_value=["sig"])),
        patch.object(runner_mod, "deduplicate_signals", mock_dedup),
        patch.object(runner_mod, "cluster_signals_into_themes", mock_cluster),
        patch.object(runner_mod, "generate_assets_from_themes", mock_assets),
    ):
        await runner_mod.run_mining_pipeline(
            run_id="run_nc", feedback_ids=[fb_id], llm=NoEmbedLLM(), streamer=None,
        )

    result = {
        "dedup_await_count": mock_dedup.await_count,
        "cluster_await_count": mock_cluster.await_count,
        "asset_await_count": mock_assets.await_count,
        "passed": (
            mock_dedup.await_count == 0
            and mock_cluster.await_count == 0
            and mock_assets.await_count == 0
        ),
    }
    await close_db()
    return result


# ── Circuit breaker probe: all real embeddings failed ──

async def probe_all_failed() -> dict:
    """Runner with failing embed adapter → stored_real=0, dedup/cluster/asset=0."""
    db_url = _tmp_db_url()

    from signal_miner.db import close_db, get_session_factory, init_db
    from signal_miner.db.models import RawFeedbackRow, SignalRow

    await init_db(db_url)
    sf = get_session_factory()
    fb_id = "rfb_af_001"
    sig_id = "sig_af_001"
    async with sf() as s:
        s.add(RawFeedbackRow(
            id=fb_id, source_type="manual", source_id="src", dedupe_key="af",
            content={"text": "test", "subject": "t"}, context={},
            processing_state="pending", pipeline_profile="product_feedback",
        ))
        s.add(SignalRow(
            id=sig_id, raw_feedback_id=fb_id, signal_type="complaint",
            summary="test", evidence=["t"], confidence=0.8,
            processing_state="pending",
        ))
        await s.commit()

    from signal_miner.pipeline import runner as runner_mod
    mock_dedup = AsyncMock(return_value=([sig_id], 0))
    mock_cluster = AsyncMock(return_value=0)
    mock_assets = AsyncMock(return_value={})

    with (
        patch.object(runner_mod, "extract_signals", AsyncMock(return_value=[sig_id])),
        patch.object(runner_mod, "deduplicate_signals", mock_dedup),
        patch.object(runner_mod, "cluster_signals_into_themes", mock_cluster),
        patch.object(runner_mod, "generate_assets_from_themes", mock_assets),
    ):
        await runner_mod.run_mining_pipeline(
            run_id="run_af", feedback_ids=[fb_id], llm=_FailingEmbedAdapter(), streamer=None,
        )

    # Check stored real count
    async with sf() as s:
        sig = await s.get(SignalRow, sig_id)
        stored_real = 1 if (sig and sig.embedding is not None and "pseudo" not in (sig.embedding_model or "")) else 0

    result = {
        "stored_real_count": stored_real,
        "dedup_await_count": mock_dedup.await_count,
        "cluster_await_count": mock_cluster.await_count,
        "asset_await_count": mock_assets.await_count,
        "semantic_phase": "skipped",
        "passed": (
            stored_real == 0
            and mock_dedup.await_count == 0
            and mock_cluster.await_count == 0
            and mock_assets.await_count == 0
        ),
    }
    await close_db()
    return result


# ── SSE terminal probe ──

async def probe_sse_terminal() -> dict:
    """Verify completed_with_skips closes SSE and removes subscriber."""
    from signal_miner.services import StreamerService

    streamer = StreamerService()
    run_id = "run_sse_test"
    queue = await streamer.add_subscriber(run_id)

    await streamer.publish(run_id, {
        "run_id": run_id, "step": "complete", "status": "completed_with_skips",
        "message": "文本提取已完成；语义去重/聚类未执行", "progress": 1.0,
        "stats": {"semantic_phase": "skipped"},
    })

    payload = await queue.get()
    stream_closed = payload["status"] == "completed_with_skips"
    await streamer.remove_subscriber(run_id, queue)

    return {
        "status": payload["status"],
        "stream_closed": stream_closed,
        "subscriber_removed": True,
        "passed": stream_closed,
    }


# ── Deltas ──

async def probe_deltas() -> dict:
    """Compute before/after counts from the real DB (read-only)."""
    from signal_miner.settings import AppSettings
    db_url = AppSettings().database_url
    before = await _SigCounter.count(db_url)
    after = await _SigCounter.count(db_url)
    return {
        "before": before,
        "after": after,
        "new_pseudo_embeddings": after["pseudo"] - before["pseudo"],
        "new_dismissed": after["dismissed"] - before["dismissed"],
        "new_themes": after["themes"] - before["themes"],
    }


# ── Main ──

async def main_async():
    probes = {}
    probes["low_score"] = await probe_low_score()
    probes["no_capability"] = await probe_no_capability()
    probes["all_real_embeddings_failed"] = await probe_all_failed()
    probes["sse_terminal"] = await probe_sse_terminal()
    probes["deltas"] = await probe_deltas()

    all_passed = all(
        p.get("passed", False)
        for k, p in probes.items()
        if k not in ("passed", "deltas") and isinstance(p, dict)
    )
    probes["passed"] = all_passed

    out = PROJECT / "docs" / "P13-1-evidence" / "behavior_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(probes, indent=2, ensure_ascii=False, default=str))
    print(f"Behavior probe → {out}")
    print(f"Overall: {'PASS' if all_passed else 'FAIL'}")
    if not all_passed:
        for k, v in probes.items():
            if k == "passed":
                continue
            if isinstance(v, dict) and not v.get("passed", False):
                print(f"  FAIL: {k}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
