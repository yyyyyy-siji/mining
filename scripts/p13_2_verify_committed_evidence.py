#!/usr/bin/env python3
"""P13-2-2-1A fix-5: Standalone committed-evidence verifier.

Independently reads the published evidence artifacts in
``docs/P13-2-evidence`` and re-checks SHA / run_id / contract_sha / status /
metadata consistency. Designed to be run AFTER the orchestrator has committed
green metrics — any post-commit tampering of gate artifacts makes this
verifier exit 1.

Exit codes:
  0 = all evidence files consistent and COMMITTED
  1 = any inconsistency (post-commit tamper detected)

Usage:
  python scripts/p13_2_verify_committed_evidence.py
  python scripts/p13_2_verify_committed_evidence.py --evidence-dir path/to/ev
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent

from signal_miner.evaluation.p13_2_gate_contract import (  # noqa: E402
    ANNOTATION_META_NEGATIVES,
    ANNOTATION_MUTATIONS,
    ANNOTATION_READINESS_INVARIANTS,
    CONTRACT_SCHEMA_VERSION,
    CONTRACT_SHA256,
    PACK_TRUST_MUTATIONS,
    PACK_TRUST_READINESS_INVARIANTS,
)

EVIDENCE_DIR_DEFAULT = PROJECT / "docs" / "P13-2-evidence"
METRICS_NAME = "pack-trust-contract-metrics.json"
PT_NAME = "pack-trust-mutation-gate.json"
AN_NAME = "human-annotation-mutation-gate.json"

PT_PHASE = "pack_trust_mutation_gate"
PT_COMMAND = "pack-trust-mutation-gate"
AN_PHASE = "annotation_mutation_gate"
AN_COMMAND = "annotation-mutation-gate"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bool_strictly_true(x) -> bool:
    return x is True


def _is_str(x) -> bool:
    return isinstance(x, str) and x != ""


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def verify(evidence_dir: Path) -> list[str]:
    """Return errors list. Empty = OK."""
    errs: list[str] = []

    metrics_path = evidence_dir / METRICS_NAME
    pt_path = evidence_dir / PT_NAME
    an_path = evidence_dir / AN_NAME

    for p, name in [(metrics_path, METRICS_NAME), (pt_path, PT_NAME),
                    (an_path, AN_NAME)]:
        if not p.exists():
            errs.append(f"{name}: file missing")
    if errs:
        return errs

    try:
        metrics_raw = metrics_path.read_bytes()
        pt_raw = pt_path.read_bytes()
        an_raw = an_path.read_bytes()
    except OSError as e:
        errs.append(f"read failed: {e}")
        return errs

    try:
        metrics = json.loads(metrics_raw.decode("utf-8"))
        pt = json.loads(pt_raw.decode("utf-8"))
        an = json.loads(an_raw.decode("utf-8"))
    except Exception as e:
        errs.append(f"JSON parse failed: {e}")
        return errs

    if not isinstance(metrics, dict):
        errs.append(f"{METRICS_NAME}: top-level not dict")
        return errs
    if not isinstance(pt, dict):
        errs.append(f"{PT_NAME}: top-level not dict")
        return errs
    if not isinstance(an, dict):
        errs.append(f"{AN_NAME}: top-level not dict")
        return errs

    # ── Metrics status + passed ──
    if metrics.get("status") != "COMMITTED":
        errs.append(f"{METRICS_NAME}: status={metrics.get('status')!r} != COMMITTED")
    if not _bool_strictly_true(metrics.get("passed")):
        errs.append(f"{METRICS_NAME}: passed={metrics.get('passed')!r} != True")

    # ── contract_sha256 consistency across all three ──
    for src, name in [(metrics, METRICS_NAME), (pt, PT_NAME), (an, AN_NAME)]:
        cs = src.get("contract_sha256")
        if not _is_str(cs) or cs != CONTRACT_SHA256:
            errs.append(f"{name}: contract_sha256={cs!r} != expected")

    # ── contract_schema_version in metrics ──
    csv = metrics.get("contract_schema_version")
    if not _is_str(csv) or csv != CONTRACT_SCHEMA_VERSION:
        errs.append(f"{METRICS_NAME}: contract_schema_version={csv!r} != expected")

    # ── run_id consistency ──
    m_run = metrics.get("run_id")
    if not _is_str(m_run):
        errs.append(f"{METRICS_NAME}: run_id missing/non-string")
    else:
        for src, name in [(pt, PT_NAME), (an, AN_NAME)]:
            if src.get("run_id") != m_run:
                errs.append(f"{name}: run_id={src.get('run_id')!r} != metrics {m_run[:16]}...")

    # ── SHA: metrics reference must match actual artifact SHA on disk ──
    pt_actual = _sha256_bytes(pt_raw)
    an_actual = _sha256_bytes(an_raw)
    pt_ref = metrics.get("pack_trust_mutation_gate", {}).get("artifact_sha256")
    an_ref = metrics.get("annotation_mutation_gate", {}).get("artifact_sha256")
    if not _is_str(pt_ref) or pt_ref != pt_actual:
        errs.append(
            f"{METRICS_NAME}: pack-trust artifact_sha256={pt_ref!r} "
            f"!= disk={pt_actual[:16]}..."
        )
    if not _is_str(an_ref) or an_ref != an_actual:
        errs.append(
            f"{METRICS_NAME}: annotation artifact_sha256={an_ref!r} "
            f"!= disk={an_actual[:16]}..."
        )

    # ── Gate metadata: phase / command / exit_code ──
    for src, name, phase, command in [(pt, PT_NAME, PT_PHASE, PT_COMMAND),
                                       (an, AN_NAME, AN_PHASE, AN_COMMAND)]:
        if src.get("phase") != phase:
            errs.append(f"{name}: phase={src.get('phase')!r} != {phase!r}")
        if src.get("command") != command:
            errs.append(f"{name}: command={src.get('command')!r} != {command!r}")
        if not _is_int(src.get("exit_code")) or src.get("exit_code") != 0:
            errs.append(f"{name}: exit_code={src.get('exit_code')!r} != 0")
        if src.get("contract_schema_version") != CONTRACT_SCHEMA_VERSION:
            errs.append(
                f"{name}: contract_schema_version={src.get('contract_schema_version')!r}"
            )
        if not _bool_strictly_true(src.get("passed")):
            errs.append(f"{name}: passed={src.get('passed')!r} != True")

    # ── Cardinalities: counts must match contract ──
    pt_results = pt.get("results", [])
    an_results = an.get("results", [])
    if isinstance(pt_results, list) and len(pt_results) != len(PACK_TRUST_MUTATIONS):
        errs.append(
            f"{PT_NAME}: pack-trust mutation count={len(pt_results)} "
            f"!= contract {len(PACK_TRUST_MUTATIONS)}"
        )
    if isinstance(an_results, list) and len(an_results) != len(ANNOTATION_MUTATIONS):
        errs.append(
            f"{AN_NAME}: annotation mutation count={len(an_results)} "
            f"!= contract {len(ANNOTATION_MUTATIONS)}"
        )
    pt_inv = pt.get("readiness_invariants", [])
    if isinstance(pt_inv, list) and len(pt_inv) != len(PACK_TRUST_READINESS_INVARIANTS):
        errs.append(
            f"{PT_NAME}: pack-trust invariant count={len(pt_inv)} "
            f"!= contract {len(PACK_TRUST_READINESS_INVARIANTS)}"
        )
    an_inv = an.get("readiness_invariants", [])
    if isinstance(an_inv, list) and len(an_inv) != len(ANNOTATION_READINESS_INVARIANTS):
        errs.append(
            f"{AN_NAME}: annotation invariant count={len(an_inv)} "
            f"!= contract {len(ANNOTATION_READINESS_INVARIANTS)}"
        )
    an_meta = an.get("meta_negatives", [])
    if isinstance(an_meta, list) and len(an_meta) != len(ANNOTATION_META_NEGATIVES):
        errs.append(
            f"{AN_NAME}: meta-negative count={len(an_meta)} "
            f"!= contract {len(ANNOTATION_META_NEGATIVES)}"
        )

    return errs


def main() -> int:
    p = argparse.ArgumentParser(
        description="P13-2 committed-evidence verifier — exit 1 if any post-commit tampering detected")
    p.add_argument("--evidence-dir", default=str(EVIDENCE_DIR_DEFAULT),
                   help="Directory containing the three evidence JSON files")
    args = p.parse_args()

    evidence_dir = Path(args.evidence_dir)
    errs = verify(evidence_dir)
    if errs:
        print(f"committed-evidence verifier: FAIL ({len(errs)} errors)")
        for e in errs:
            print(f"  ERROR: {e}")
        return 1
    print("committed-evidence verifier: PASS")
    print(f"  evidence_dir: {evidence_dir}")
    print(f"  checked_at:   {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
