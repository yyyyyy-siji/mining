#!/usr/bin/env python3
"""P13-2-2-1A fix-5: Evidence orchestrator with transaction state machine.

Single source of truth for contract metrics generation. Generates run_id,
runs both gates, validates against the versioned gate contract, atomically
publishes gate evidence and contract metrics.

fix-5 invariants (all mandatory):
  - Evidence transaction state machine: RUNNING → COMMITTED|FAILED
  - RUNNING marker published atomically BEFORE any gate runs
  - Pre-commit re-verification: re-read both published gates after publish,
    verify SHA + run_id + contract_sha + metadata + passed match snapshot
  - Metrics publish failure → exit 1, no PASS, FAILED marker left
  - Malformed input → strict type validation, no uncaught exceptions
  - All errors participate in final exit code (computed AFTER commit)
  - committed-evidence verifier runs as final gate before PASS
  - Test isolation via evidence_dir parameter

Exit codes:
  0 = all gates pass, all checks pass, metrics committed, verifier passes
  1 = any failure -> FAILED marker left, no green metrics
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import uuid

PROJECT = Path(__file__).resolve().parent.parent
PY = sys.executable

PT_GATE = PROJECT / "scripts" / "p13_2_pack_trust_mutation_gate.py"
AN_GATE = PROJECT / "scripts" / "p13_2_annotation_mutation_gate.py"

EVIDENCE_DIR_DEFAULT = PROJECT / "docs" / "P13-2-evidence"
OUT_NAME = "pack-trust-contract-metrics.json"
PT_GATE_NAME = "pack-trust-mutation-gate.json"
AN_GATE_NAME = "human-annotation-mutation-gate.json"
CURRENT_NAME = "current.json"
RUNS_SUBDIR = "runs"

from signal_miner.evaluation.p13_2_gate_contract import (  # noqa: E402
    ANNOTATION_META_NEGATIVES,
    ANNOTATION_MUTATIONS,
    ANNOTATION_READINESS_INVARIANTS,
    CONTRACT_SCHEMA_VERSION,
    CONTRACT_SHA256,
    PACK_TRUST_MUTATIONS,
    PACK_TRUST_READINESS_INVARIANTS,
)

# Strict metadata expectations for each gate
PT_METADATA = {
    "phase": "pack_trust_mutation_gate",
    "command": "pack-trust-mutation-gate",
    "contract_schema_version": CONTRACT_SCHEMA_VERSION,
}
AN_METADATA = {
    "phase": "annotation_mutation_gate",
    "command": "annotation-mutation-gate",
    "contract_schema_version": CONTRACT_SCHEMA_VERSION,
}


# ── Low-level helpers ──

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bool_strictly_true(value) -> bool:
    """Only Python True passes. Rejects 'true' string, 1, etc."""
    return value is True


def _is_str(x) -> bool:
    return isinstance(x, str) and x != ""


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _parse_iso(value):
    """Parse ISO timestamp, return aware datetime or None."""
    if not _is_str(value):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        return None  # naive rejected
    return dt


# ── Atomic publish ──

def _publish_atomic(source_bytes: bytes, dest_path: Path) -> list[str]:
    """Atomically publish bytes to dest_path: temp → fsync → os.replace → readback → SHA verify.

    Returns errors list. On success returns empty list.
    """
    errs: list[str] = []
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    source_sha = _sha256_bytes(source_bytes)
    tmp = dest_path.parent / f".{dest_path.name}.tmp.{uuid.uuid4().hex[:8]}"
    try:
        tmp.write_bytes(source_bytes)
        fd = os.open(str(tmp), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as e:
        errs.append(f"temp-write/fsync for {dest_path.name}: {e}")
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return errs
    try:
        os.replace(str(tmp), str(dest_path))
    except OSError as e:
        errs.append(f"os.replace for {dest_path.name}: {e}")
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return errs
    # Post-publish readback + SHA verify
    if not dest_path.exists():
        errs.append(f"{dest_path.name}: missing after publish")
        return errs
    try:
        dest_bytes = dest_path.read_bytes()
    except OSError as e:
        errs.append(f"{dest_path.name}: readback failed: {e}")
        return errs
    dest_sha = _sha256_bytes(dest_bytes)
    if dest_sha != source_sha:
        errs.append(
            f"{dest_path.name}: SHA mismatch after publish "
            f"(source={source_sha[:16]}... disk={dest_sha[:16]}...)"
        )
    return errs


# ── Strict container validation ──

def _require_dict(data, label: str) -> list[str]:
    if not isinstance(data, dict):
        return [f"{label}: top-level must be dict, got {type(data).__name__}"]
    return []


def _require_list(value, label: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{label}: must be list, got {type(value).__name__}"]
    return []


def _check_row_contract(results: list, label: str) -> list[str]:
    """Per-row strict type + value checks. No bare key access."""
    errs: list[str] = []
    for i, r in enumerate(results):
        if not isinstance(r, dict):
            errs.append(f"{label} row #{i}: must be dict, got {type(r).__name__}")
            continue
        name = r.get("mutation")
        if not _is_str(name):
            errs.append(f"{label} row #{i}: mutation missing or non-string: {name!r}")
            name = f"#{i}"
        ce = r.get("child_exit")
        if not _is_int(ce) or ce != 1:
            errs.append(f"{label} '{name}': child_exit={ce!r} (expected int 1)")
        if not _bool_strictly_true(r.get("detected")):
            errs.append(f"{label} '{name}': detected={r.get('detected')!r} (expected True)")
        if not _bool_strictly_true(r.get("check_exists")):
            errs.append(f"{label} '{name}': check_exists={r.get('check_exists')!r}")
        tp = r.get("target_passed")
        if tp is not False:
            errs.append(f"{label} '{name}': target_passed={tp!r} (expected False)")
    return errs


def _check_exact_set(name: str, expected: tuple[str, ...],
                     actual_names: list[str]) -> list[str]:
    """Verify exact-set match (no missing, no extra, no dupes). Strict typed."""
    errs: list[str] = []
    expected_set = frozenset(expected)
    for i, n in enumerate(actual_names):
        if not _is_str(n):
            errs.append(f"{name} row #{i}: name not a non-empty string: {n!r}")
            return errs  # can't safely compare further
    actual_set = frozenset(actual_names)
    if len(expected) != len(expected_set):
        errs.append(f"{name}: contract has duplicates in definition")
    if len(actual_names) != len(actual_set):
        from collections import Counter
        dupes = [n for n, c in Counter(actual_names).items() if c > 1]
        errs.append(f"{name}: duplicates: {sorted(dupes)}")
    missing = expected_set - actual_set
    extra = actual_set - expected_set
    if missing:
        errs.append(f"{name}: missing {len(missing)}: {sorted(missing)[:5]}")
    if extra:
        errs.append(f"{name}: unknown {len(extra)}: {sorted(extra)[:5]}")
    return errs


def _validate_gate_payload(data, label: str, run_id: str, expected_metadata: dict,
                            started_at: datetime, finished_at: datetime,
                            expected_exit: int) -> list[str]:
    """Full payload validation including strict metadata (P1-1)."""
    errs: list[str] = []
    errs.extend(_require_dict(data, label))
    if errs:
        return errs

    # contract_sha256
    cs = data.get("contract_sha256")
    if not _is_str(cs) or cs != CONTRACT_SHA256:
        errs.append(f"{label}: contract_sha256={cs!r} != expected={CONTRACT_SHA256[:16]}...")

    # run_id
    gr = data.get("run_id")
    if not _is_str(gr) or gr != run_id:
        errs.append(f"{label}: run_id={gr!r} != orchestrator={run_id[:16]}...")

    # generated_at — strict: must be str, parseable, aware, in window
    ga_raw = data.get("generated_at")
    ga = _parse_iso(ga_raw)
    if ga is None:
        errs.append(f"{label}: generated_at missing/naive/unparseable: {ga_raw!r}")
    else:
        if ga < started_at or ga > finished_at:
            errs.append(
                f"{label}: generated_at {ga_raw!r} outside window "
                f"[{started_at.isoformat()} .. {finished_at.isoformat()}]"
            )

    # Strict metadata (P1-1): phase, command, contract_schema_version
    for key, expected_val in expected_metadata.items():
        actual = data.get(key)
        if not _is_str(actual) or actual != expected_val:
            errs.append(f"{label}: {key}={actual!r} != expected={expected_val!r}")

    # exit_code must be int 0 (orchestrator already validated it matches subprocess)
    ec = data.get("exit_code")
    if not _is_int(ec) or ec != expected_exit:
        errs.append(f"{label}: exit_code={ec!r} != expected={expected_exit}")

    return errs


def _check_invariants(expected: tuple[str, ...], items, label: str,
                      check_key: str = "passed") -> list[str]:
    errs: list[str] = []
    errs.extend(_require_list(items, label))
    if errs:
        return errs
    seen: dict = {}
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append(f"{label} item #{i}: must be dict, got {type(it).__name__}")
            continue
        name = it.get("name")
        if not _is_str(name):
            errs.append(f"{label} item #{i}: name missing/non-string: {name!r}")
            continue
        seen[name] = it
    for name in expected:
        if name not in seen:
            errs.append(f"{label}: missing required item '{name}'")
        elif not _bool_strictly_true(seen[name].get(check_key)):
            errs.append(f"{label}: '{name}' {check_key}={seen[name].get(check_key)!r}")
    for name in seen:
        if name not in expected:
            errs.append(f"{label}: unknown item '{name}' not in contract")
    return errs


# ── Gate runner ──

def _run_gate(script: Path, run_id: str, out_path: Path) -> tuple[int, bytes]:
    """Run a mutation gate → (exit_code, raw output bytes snapshot)."""
    env = dict(os.environ)
    env.setdefault("APP_ENVIRONMENT", "test")
    r = subprocess.run(
        [PY, str(script), "--run-id", run_id, "--out", str(out_path)],
        cwd=PROJECT, capture_output=True, text=True, timeout=600, env=env,
    )
    if r.stderr:
        sys.stderr.write(f"[{script.name}] {r.stderr[:500]}\n")
    if not out_path.exists():
        return r.returncode, b""
    return r.returncode, out_path.read_bytes()


# ── Pre-commit re-verification ──

def _reverify_gate_on_disk(dest_path: Path, snapshot_bytes: bytes,
                            snapshot_sha: str, run_id: str,
                            expected_metadata: dict) -> list[str]:
    """Re-read published gate from disk and verify SHA + key fields match snapshot.

    This blocks the P0-1 attack: tamper after publish, before metrics commit.
    """
    errs: list[str] = []
    if not dest_path.exists():
        errs.append(f"{dest_path.name}: re-verify failed, missing on disk")
        return errs
    try:
        disk_bytes = dest_path.read_bytes()
    except OSError as e:
        errs.append(f"{dest_path.name}: re-verify read failed: {e}")
        return errs
    disk_sha = _sha256_bytes(disk_bytes)
    if disk_sha != snapshot_sha:
        errs.append(
            f"{dest_path.name}: re-verify SHA mismatch "
            f"(snapshot={snapshot_sha[:16]}... disk={disk_sha[:16]}...)"
        )
        return errs  # bytes differ → stop
    if disk_bytes != snapshot_bytes:
        errs.append(f"{dest_path.name}: re-verify bytes != snapshot despite SHA match")
        return errs
    # Re-parse and check key fields
    try:
        data = json.loads(disk_bytes.decode("utf-8"))
    except Exception as e:
        errs.append(f"{dest_path.name}: re-verify JSON parse failed: {e}")
        return errs
    if not isinstance(data, dict):
        errs.append(f"{dest_path.name}: re-verify top-level not dict")
        return errs
    if not _is_str(data.get("run_id")) or data.get("run_id") != run_id:
        errs.append(f"{dest_path.name}: re-verify run_id mismatch")
    cs = data.get("contract_sha256")
    if not _is_str(cs) or cs != CONTRACT_SHA256:
        errs.append(f"{dest_path.name}: re-verify contract_sha256 mismatch")
    if not _bool_strictly_true(data.get("passed")):
        errs.append(f"{dest_path.name}: re-verify passed={data.get('passed')!r}")
    for key, expected_val in expected_metadata.items():
        actual = data.get(key)
        if not _is_str(actual) or actual != expected_val:
            errs.append(f"{dest_path.name}: re-verify {key}={actual!r} != {expected_val!r}")
    return errs


# ── Committed-evidence verifier (in-process) ──

def _verify_committed_evidence(evidence_dir: Path) -> list[str]:
    """Independent verifier: read published artifacts and re-check.

    Returns errors list. Empty = OK.
    """
    errs: list[str] = []
    metrics_path = evidence_dir / OUT_NAME
    pt_path = evidence_dir / PT_GATE_NAME
    an_path = evidence_dir / AN_GATE_NAME
    for p, name in [(metrics_path, OUT_NAME), (pt_path, PT_GATE_NAME),
                    (an_path, AN_GATE_NAME)]:
        if not p.exists():
            errs.append(f"verifier: {name} missing")
    if errs:
        return errs

    try:
        metrics_raw = metrics_path.read_bytes()
        pt_raw = pt_path.read_bytes()
        an_raw = an_path.read_bytes()
    except OSError as e:
        errs.append(f"verifier: read failed: {e}")
        return errs

    try:
        metrics = json.loads(metrics_raw.decode("utf-8"))
        pt = json.loads(pt_raw.decode("utf-8"))
        an = json.loads(an_raw.decode("utf-8"))
    except Exception as e:
        errs.append(f"verifier: JSON parse failed: {e}")
        return errs

    if not isinstance(metrics, dict) or not isinstance(pt, dict) or not isinstance(an, dict):
        errs.append("verifier: one or more artifacts not dict")
        return errs

    # SHA consistency: metrics references must match actual artifact SHA
    pt_actual = _sha256_bytes(pt_raw)
    an_actual = _sha256_bytes(an_raw)
    pt_ref = metrics.get("pack_trust_mutation_gate", {}).get("artifact_sha256")
    an_ref = metrics.get("annotation_mutation_gate", {}).get("artifact_sha256")
    if not _is_str(pt_ref) or pt_ref != pt_actual:
        errs.append(f"verifier: pack-trust artifact_sha256 mismatch (metrics={pt_ref!r} actual={pt_actual[:16]}...)")
    if not _is_str(an_ref) or an_ref != an_actual:
        errs.append(f"verifier: annotation artifact_sha256 mismatch (metrics={an_ref!r} actual={an_actual[:16]}...)")

    # run_id consistency across all three
    m_run = metrics.get("run_id")
    if not _is_str(m_run):
        errs.append("verifier: metrics run_id missing/non-string")
    else:
        if pt.get("run_id") != m_run:
            errs.append("verifier: pack-trust run_id != metrics run_id")
        if an.get("run_id") != m_run:
            errs.append("verifier: annotation run_id != metrics run_id")

    # contract_sha256 consistency
    for src, name in [(metrics, "metrics"), (pt, "pack-trust"), (an, "annotation")]:
        if src.get("contract_sha256") != CONTRACT_SHA256:
            errs.append(f"verifier: {name} contract_sha256 mismatch")

    # metrics status must be COMMITTED, passed=true
    if metrics.get("status") != "COMMITTED":
        errs.append(f"verifier: metrics status={metrics.get('status')!r} != COMMITTED")
    if not _bool_strictly_true(metrics.get("passed")):
        errs.append(f"verifier: metrics passed={metrics.get('passed')!r}")

    return errs


# ── Marker helpers (fix-6: MarkerWriteResult contract) ──


@dataclass(frozen=True)
class MarkerWriteResult:
    """Result of an atomic marker publish + readback verification.

    ok=True only when:
      - _publish_atomic returned no errors
      - re-read of the marker file succeeded
      - parsed JSON matches expected run_id / status / passed exactly

    Callers MUST check .ok explicitly. .errors is never empty when ok=False.
    """
    ok: bool
    status: str
    run_id: str
    errors: tuple[str, ...] = field(default_factory=tuple)


def _publish_marker_with_readback(
    evidence_dir: Path, marker: dict,
    expected_status: str, expected_run_id: str,
) -> MarkerWriteResult:
    """Publish marker atomically, then re-read and verify expected fields.

    Returns MarkerWriteResult. Never raises — all failures become ok=False
    with structured errors so callers can branch deterministically.
    """
    out = evidence_dir / OUT_NAME
    errors: list[str] = []
    payload_bytes = b""
    try:
        payload_bytes = json.dumps(
            marker, indent=2, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        errors.append(f"marker serialize failed: {type(e).__name__}: {e}")
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )

    try:
        publish_errs = _publish_atomic(payload_bytes, out)
    except Exception as e:  # noqa: BLE001
        publish_errs = [f"marker _publish_atomic raised: {type(e).__name__}: {e}"]
    if publish_errs:
        errors.extend(publish_errs)
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )

    # Readback + strict field verification
    if not out.exists():
        errors.append("marker missing after publish (readback)")
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )
    try:
        disk_bytes = out.read_bytes()
    except OSError as e:
        errors.append(f"marker readback failed: {e}")
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )
    disk_sha = _sha256_bytes(disk_bytes)
    src_sha = _sha256_bytes(payload_bytes)
    if disk_sha != src_sha:
        errors.append(
            f"marker SHA mismatch after publish "
            f"(source={src_sha[:16]}... disk={disk_sha[:16]}...)"
        )
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )
    try:
        disk_marker = json.loads(disk_bytes.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        errors.append(f"marker readback JSON parse failed: {type(e).__name__}: {e}")
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )
    if not isinstance(disk_marker, dict):
        errors.append(f"marker readback top-level not dict: {type(disk_marker).__name__}")
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )

    # Strict field verification
    d_run = disk_marker.get("run_id")
    if not _is_str(d_run) or d_run != expected_run_id:
        errors.append(
            f"marker readback run_id={d_run!r} != expected {expected_run_id[:16]}..."
        )
    d_status = disk_marker.get("status")
    if not _is_str(d_status) or d_status != expected_status:
        errors.append(f"marker readback status={d_status!r} != expected {expected_status!r}")
    d_passed = disk_marker.get("passed")
    if d_passed is not False:
        errors.append(f"marker readback passed={d_passed!r} != False")

    if errors:
        return MarkerWriteResult(
            ok=False, status=expected_status, run_id=expected_run_id,
            errors=tuple(errors),
        )
    return MarkerWriteResult(
        ok=True, status=expected_status, run_id=expected_run_id,
        errors=(),
    )


def _write_running_marker(evidence_dir: Path, run_id: str,
                          started_at: datetime) -> MarkerWriteResult:
    """Atomically publish RUNNING marker and verify it landed.

    Returns MarkerWriteResult; caller MUST check .ok.
    """
    marker = {
        "run_id": run_id,
        "status": "RUNNING",
        "passed": False,
        "started_at": started_at.isoformat(),
        "generated_at": started_at.isoformat(),
        "phase": "orchestrator",
        "contract_sha256": CONTRACT_SHA256,
    }
    return _publish_marker_with_readback(evidence_dir, marker, "RUNNING", run_id)


def _write_failed_marker(evidence_dir: Path, run_id: str,
                         started_at: datetime, finished_at: datetime,
                         errors: list[str]) -> MarkerWriteResult:
    """Atomically write FAILED marker and verify readback.

    Returns MarkerWriteResult; caller MUST check .ok to decide summary text.
    """
    marker = {
        "run_id": run_id,
        "status": "FAILED",
        "passed": False,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "generated_at": finished_at.isoformat(),
        "phase": "orchestrator",
        "contract_sha256": CONTRACT_SHA256,
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "errors": errors[:50],
        "production_blocked": True,
        "calibration_allowed": False,
        "human_labels_complete": False,
    }
    return _publish_marker_with_readback(evidence_dir, marker, "FAILED", run_id)


# ── Main orchestrator ──

def main(gate_runner=None, evidence_dir: Path | None = None,
         _gate_state: dict | None = None) -> int:
    """Run the full orchestration pipeline.

    gate_runner: if provided (for testing), called as
        gate_runner(script, run_id, out_path) → (exit, bytes).
        Otherwise _run_gate is used.
    evidence_dir: directory for evidence artifacts. Defaults to real
        EVIDENCE_DIR_DEFAULT. Tests pass tmp_path here for isolation.
    _gate_state: optional dict tests use to read {'calls': N}. The wrapper
        that increments it is installed only when this is provided.

    fix-6: RUNNING marker publish is a hard precondition for any gate run.
    If RUNNING write or readback fails, exit 1 immediately, gate_calls=0.
    """
    if gate_runner is None:
        gate_runner = _run_gate
    if evidence_dir is None:
        evidence_dir = EVIDENCE_DIR_DEFAULT

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    # 0. RUNNING marker — hard precondition for any gate.
    # _write_running_marker returns MarkerWriteResult; we MUST check .ok.
    running_result = _write_running_marker(evidence_dir, run_id, started_at)
    if not running_result.ok:
        # RUNNING publish or readback failed → no gates run, exit 1.
        if _gate_state is not None:
            _gate_state["calls"] = 0
            _gate_state["running_ok"] = False
        sys.stderr.write("RUNNING_MARKER_WRITE_FAILED\n")
        for er in running_result.errors:
            sys.stderr.write(f"  ERROR: {er}\n")
        # If a stale COMMITTED file from a previous run is still on disk,
        # it must NOT be interpreted as "this run started". The CLI clearly
        # states the run did not start.
        sys.stderr.write(
            "Orchestrator: FAIL (RUNNING marker not published; "
            "this run did not start; gate_calls=0)\n"
        )
        return 1

    if _gate_state is not None:
        _gate_state["running_ok"] = True
        # Install wrapper that counts gate calls into _gate_state
        original_runner = gate_runner

        def counting_runner(script, run_id_arg, out_path):
            _gate_state["calls"] = _gate_state.get("calls", 0) + 1
            return original_runner(script, run_id_arg, out_path)
        gate_runner = counting_runner

    try:
        return _orchestrate(
            gate_runner=gate_runner,
            evidence_dir=evidence_dir,
            run_id=run_id,
            started_at=started_at,
        )
    except Exception as e:
        # P0-3: any uncaught exception → FAILED marker, exit 1, no stale green
        finished_at = datetime.now(timezone.utc)
        tb_lines = traceback.format_exc().splitlines()
        errors = [f"uncaught exception: {type(e).__name__}: {e}",
                  f"traceback: {' | '.join(tb_lines[-3:])}"]
        failed_result = _write_failed_marker(
            evidence_dir, run_id, started_at, finished_at, errors)
        if failed_result.ok:
            sys.stderr.write("Orchestrator: FAIL (FAILED marker written)\n")
        else:
            sys.stderr.write("FAILED_MARKER_WRITE_FAILED\n")
            for er in failed_result.errors:
                sys.stderr.write(f"  ERROR: {er}\n")
            sys.stderr.write(
                "Orchestrator: FAIL (FAILED marker write failed; "
                "on-disk marker may be from a previous run)\n"
            )
        for er in errors:
            sys.stderr.write(f"  ERROR: {er}\n")
        return 1


def _orchestrate(*, gate_runner, evidence_dir: Path, run_id: str,
                 started_at: datetime) -> int:
    """Inner orchestration. All errors caught by main()'s try/except."""
    errors: list[str] = []

    tmpdir = Path(tempfile.mkdtemp(prefix="p13_metrics_"))

    # Gate output paths — gates write to tmp first, we publish to evidence_dir
    pt_out = tmpdir / "pack-trust-mutation-gate.json"
    an_out = tmpdir / "human-annotation-mutation-gate.json"

    try:
        # 1. Run both gates with the same run_id — immutable bytes snapshots
        pt_exit, pt_bytes = gate_runner(PT_GATE, run_id, pt_out)
        an_exit, an_bytes = gate_runner(AN_GATE, run_id, an_out)
        finished_at = datetime.now(timezone.utc)

        # 2. Strict container validation + parse
        if not pt_bytes:
            errors.append("pack-trust gate produced empty output")
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit)
        if not an_bytes:
            errors.append("annotation gate produced empty output")
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit)

        try:
            ptmg = json.loads(pt_bytes.decode("utf-8"))
        except Exception as e:
            errors.append(f"pack-trust gate JSON parse error: {e}")
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit)
        try:
            amg = json.loads(an_bytes.decode("utf-8"))
        except Exception as e:
            errors.append(f"annotation gate JSON parse error: {e}")
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit)

        # 3. Validate gate payload structure (strict dict)
        errors.extend(_validate_gate_payload(
            ptmg, "pack-trust", run_id, PT_METADATA, started_at, finished_at, pt_exit))
        errors.extend(_validate_gate_payload(
            amg, "annotation", run_id, AN_METADATA, started_at, finished_at, an_exit))

        # 4. Exit code consistency
        if not _is_int(pt_exit):
            errors.append(f"pack-trust: subprocess exit not int: {pt_exit!r}")
        elif pt_exit != 0:
            errors.append(f"pack-trust gate exit={pt_exit} (expected 0)")
        if not _is_int(an_exit):
            errors.append(f"annotation: subprocess exit not int: {an_exit!r}")
        elif an_exit != 0:
            errors.append(f"annotation gate exit={an_exit} (expected 0)")

        # 5. Exact-set match (strict list/dict before key access)
        pt_results_raw = ptmg.get("results")
        errors.extend(_require_list(pt_results_raw, "pack-trust results"))
        an_results_raw = amg.get("results")
        errors.extend(_require_list(an_results_raw, "annotation results"))

        pt_results: list = pt_results_raw if isinstance(pt_results_raw, list) else []
        an_results: list = an_results_raw if isinstance(an_results_raw, list) else []

        pt_names = [r.get("mutation") for r in pt_results if isinstance(r, dict)]
        an_names = [r.get("mutation") for r in an_results if isinstance(r, dict)]
        errors.extend(_check_exact_set("pack-trust-mutations", PACK_TRUST_MUTATIONS, pt_names))
        errors.extend(_check_exact_set("annotation-mutations", ANNOTATION_MUTATIONS, an_names))

        pt_inv_raw = ptmg.get("readiness_invariants")
        an_inv_raw = amg.get("readiness_invariants")
        an_meta_raw = amg.get("meta_negatives")
        errors.extend(_require_list(pt_inv_raw, "pack-trust readiness_invariants"))
        errors.extend(_require_list(an_inv_raw, "annotation readiness_invariants"))
        errors.extend(_require_list(an_meta_raw, "annotation meta_negatives"))

        pt_inv = pt_inv_raw if isinstance(pt_inv_raw, list) else []
        an_inv = an_inv_raw if isinstance(an_inv_raw, list) else []
        an_meta = an_meta_raw if isinstance(an_meta_raw, list) else []

        errors.extend(_check_exact_set(
            "pack-trust-readiness", PACK_TRUST_READINESS_INVARIANTS,
            [r.get("name") for r in pt_inv if isinstance(r, dict)]))
        errors.extend(_check_exact_set(
            "annotation-readiness", ANNOTATION_READINESS_INVARIANTS,
            [r.get("name") for r in an_inv if isinstance(r, dict)]))
        errors.extend(_check_exact_set(
            "annotation-meta-negatives", ANNOTATION_META_NEGATIVES,
            [r.get("name") for r in an_meta if isinstance(r, dict)]))

        # 6. Per-row contract
        errors.extend(_check_row_contract(pt_results, "pack-trust"))
        errors.extend(_check_row_contract(an_results, "annotation"))

        # 7. Gate-level flags
        pt_passed = ptmg.get("passed")
        pt_inv_p = ptmg.get("readiness_invariants_passed")
        an_passed = amg.get("passed")
        an_inv_p = amg.get("readiness_invariants_passed")
        an_meta_p = amg.get("meta_negatives_passed")
        if not _bool_strictly_true(pt_passed):
            errors.append(f"pack-trust passed={pt_passed!r} (expected True)")
        if not _bool_strictly_true(pt_inv_p):
            errors.append(f"pack-trust readiness_invariants_passed={pt_inv_p!r}")
        if not _bool_strictly_true(an_passed):
            errors.append(f"annotation passed={an_passed!r} (expected True)")
        if not _bool_strictly_true(an_inv_p):
            errors.append(f"annotation readiness_invariants_passed={an_inv_p!r}")
        if not _bool_strictly_true(an_meta_p):
            errors.append(f"annotation meta_negatives_passed={an_meta_p!r}")

        # 8. Invariant and meta-negative items
        errors.extend(_check_invariants(
            PACK_TRUST_READINESS_INVARIANTS, pt_inv, "pack-trust-invariant"))
        errors.extend(_check_invariants(
            ANNOTATION_READINESS_INVARIANTS, an_inv, "annotation-invariant"))
        errors.extend(_check_invariants(
            ANNOTATION_META_NEGATIVES, an_meta, "annotation-meta-negative"))

        # 9. Count consistency
        if len(pt_results) != (ptmg.get("total_mutations") if _is_int(ptmg.get("total_mutations")) else -1):
            errors.append(f"pack-trust count drift: declared={ptmg.get('total_mutations')} actual={len(pt_results)}")
        actual_pt_detected = sum(1 for r in pt_results if isinstance(r, dict) and _bool_strictly_true(r.get("detected")))
        if actual_pt_detected != (ptmg.get("detected_count") if _is_int(ptmg.get("detected_count")) else -1):
            errors.append(f"pack-trust detected drift: declared={ptmg.get('detected_count')} actual={actual_pt_detected}")
        if len(an_results) != (amg.get("total_mutations") if _is_int(amg.get("total_mutations")) else -1):
            errors.append(f"annotation count drift: declared={amg.get('total_mutations')} actual={len(an_results)}")
        actual_an_detected = sum(1 for r in an_results if isinstance(r, dict) and _bool_strictly_true(r.get("detected")))
        if actual_an_detected != (amg.get("detected_count") if _is_int(amg.get("detected_count")) else -1):
            errors.append(f"annotation detected drift: declared={amg.get('detected_count')} actual={actual_an_detected}")

        # Business-check final passed (preliminary; final computed AFTER commit)
        business_passed = (
            pt_exit == 0 and an_exit == 0
            and _bool_strictly_true(pt_passed) and _bool_strictly_true(pt_inv_p)
            and _bool_strictly_true(an_passed) and _bool_strictly_true(an_inv_p)
            and _bool_strictly_true(an_meta_p)
            and len(errors) == 0
        )

        if not business_passed:
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at,
                errors + ["business checks failed before publish"],
                pt_exit=pt_exit, an_exit=an_exit,
                pt_count=len(pt_results), an_count=len(an_results),
                pt_passed=pt_passed, an_passed=an_passed, an_meta_p=an_meta_p)

        # 10. Atomic publish gate evidence (still to tmp staging dir for SHA,
        #     then to evidence_dir). Compute SHAs from the snapshot bytes.
        pt_sha = _sha256_bytes(pt_bytes)
        an_sha = _sha256_bytes(an_bytes)
        pt_dest = evidence_dir / PT_GATE_NAME
        an_dest = evidence_dir / AN_GATE_NAME

        errors.extend(_publish_atomic(pt_bytes, pt_dest))
        errors.extend(_publish_atomic(an_bytes, an_dest))
        if errors:
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit,
                pt_count=len(pt_results), an_count=len(an_results),
                pt_passed=pt_passed, an_passed=an_passed, an_meta_p=an_meta_p)

        # 11. Pre-commit re-verification (P0-1): re-read both published gates
        #     from disk and verify they still match the snapshot.
        errors.extend(_reverify_gate_on_disk(pt_dest, pt_bytes, pt_sha, run_id, PT_METADATA))
        errors.extend(_reverify_gate_on_disk(an_dest, an_bytes, an_sha, run_id, AN_METADATA))
        if errors:
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit,
                pt_count=len(pt_results), an_count=len(an_results),
                pt_passed=pt_passed, an_passed=an_passed, an_meta_p=an_meta_p)

        # 12. Build final metrics with status=COMMITTED
        metrics = {
            "run_id": run_id,
            "status": "COMMITTED",
            "passed": True,  # tentative; final after publish + verifier
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "generated_at": finished_at.isoformat(),
            "orchestrator_started_at": started_at.isoformat(),
            "orchestrator_finished_at": finished_at.isoformat(),
            "phase": "orchestrator",
            "contract_sha256": CONTRACT_SHA256,
            "contract_schema_version": CONTRACT_SCHEMA_VERSION,
            "pack_trust_mutation_gate": {
                "exit_code": pt_exit,
                "passed": pt_passed,
                "total_mutations": len(pt_results),
                "detected_count": actual_pt_detected,
                "invariant_count": len(pt_inv),
                "target_check": ptmg.get("target_check", "") if isinstance(ptmg.get("target_check"), str) else "",
                "readiness_invariants_passed": pt_inv_p,
                "artifact_sha256": pt_sha,
            },
            "annotation_mutation_gate": {
                "exit_code": an_exit,
                "passed": an_passed,
                "total_mutations": len(an_results),
                "detected_count": actual_an_detected,
                "readiness_invariants_passed": an_inv_p,
                "meta_negatives_passed": an_meta_p,
                "artifact_sha256": an_sha,
            },
            "fixture_only": True,
            "human_verified_count": 0,
            "human_labels_complete": False,
            "calibration_allowed": False,
            "production_blocked": True,
        }

        # 13. Atomically publish metrics (P0-2: failure must exit 1, no PASS)
        metrics_bytes = json.dumps(metrics, indent=2, ensure_ascii=False).encode("utf-8")
        metrics_path = evidence_dir / OUT_NAME
        errs_metric = _publish_atomic(metrics_bytes, metrics_path)
        errors.extend(errs_metric)
        if errors:
            # Metrics publish failed → FAILED marker, exit 1, NO PASS print
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit,
                pt_count=len(pt_results), an_count=len(an_results),
                pt_passed=pt_passed, an_passed=an_passed, an_meta_p=an_meta_p)

        # 14. Final committed-evidence verifier (catches post-commit tamper
        #     on gates that the orchestrator's own re-verify didn't cover).
        verify_errors = _verify_committed_evidence(evidence_dir)
        errors.extend(verify_errors)
        if errors:
            return _fail_and_summarize(
                evidence_dir, run_id, started_at, finished_at, errors,
                pt_exit=pt_exit, an_exit=an_exit,
                pt_count=len(pt_results), an_count=len(an_results),
                pt_passed=pt_passed, an_passed=an_passed, an_meta_p=an_meta_p)

        # 15. Final passed — computed AFTER all commits + verifier succeed
        final_passed = (
            business_passed
            and len(errors) == 0
            and len(errs_metric) == 0
            and len(verify_errors) == 0
        )

        _print_summary(run_id, pt_exit, an_exit, len(pt_results), len(an_results),
                       pt_passed, an_passed, an_meta_p, final_passed=final_passed)
        return 0 if final_passed else 1
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def _finalize_failed(evidence_dir: Path, run_id: str, started_at: datetime,
                     finished_at: datetime, errors: list[str]) -> MarkerWriteResult:
    """Write FAILED marker, verify it landed, return MarkerWriteResult.

    fix-6: caller decides summary text based on .ok. We never suppress
    publish errors — they go to stderr.
    """
    result = _write_failed_marker(evidence_dir, run_id, started_at,
                                   finished_at, errors)
    if not result.ok:
        sys.stderr.write("FAILED_MARKER_WRITE_FAILED\n")
        for er in result.errors:
            sys.stderr.write(f"  ERROR: {er}\n")
    for e in errors:
        sys.stderr.write(f"  ERROR: {e}\n")
    return result


def _fail_and_summarize(evidence_dir: Path, run_id: str, started_at: datetime,
                        finished_at: datetime, errors: list[str],
                        pt_exit: int = 0, an_exit: int = 0,
                        pt_count: int = 0, an_count: int = 0,
                        pt_passed=None, an_passed=None, an_meta_p=None) -> int:
    """fix-6: finalize FAILED + print summary honoring failed_marker_written.

    Always returns 1. Splitting this out keeps _orchestrate readable while
    guaranteeing the summary text is consistent with on-disk reality.
    """
    result = _finalize_failed(evidence_dir, run_id, started_at,
                               finished_at, errors)
    _print_summary(
        run_id, pt_exit, an_exit, pt_count, an_count,
        pt_passed, an_passed, an_meta_p,
        final_passed=False, failed_marker_written=result.ok,
    )
    return 1


def _print_summary(run_id: str, pt_exit: int, an_exit: int,
                   pt_count: int, an_count: int,
                   pt_passed, an_passed, an_meta_p,
                   final_passed: bool,
                   failed_marker_written: bool | None = None) -> None:
    """Print summary. fix-6: failed_marker_written governs FAILED text.

    final_passed=True  → PASS
    final_passed=False and failed_marker_written=True  → "FAILED (no green metrics left)"
    final_passed=False and failed_marker_written=False → "FAILED_MARKER_WRITE_FAILED"
    final_passed=False and failed_marker_written=None  → generic FAIL (no marker claim)
    """
    if final_passed:
        print("Orchestrator: PASS")
    else:
        print("Orchestrator: FAIL")
    print(f"  run_id:        {run_id}")
    print(f"  contract_sha:  {CONTRACT_SHA256[:16]}...")
    print(f"  pack-trust:    {pt_count} mutations, exit={pt_exit}, passed={pt_passed!r}")
    print(f"  annotation:    {an_count} mutations, exit={an_exit}, passed={an_passed!r}")
    print(f"  meta-neg:      {an_meta_p!r}")
    if not final_passed:
        if failed_marker_written is True:
            print("  status:        FAILED (no green metrics left)")
        elif failed_marker_written is False:
            print("  status:        FAILED_MARKER_WRITE_FAILED")
            print("  note:          on-disk marker may be from a previous run")
        else:
            print("  status:        FAILED")


if __name__ == "__main__":
    sys.exit(main())
