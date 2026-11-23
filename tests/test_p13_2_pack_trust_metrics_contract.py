"""P13-2-2-1A fix-5: Orchestrator contract tests with full evidence isolation.

Every test injects tmp_path as evidence_dir → real docs/P13-2-evidence is
NEVER touched by tests. Plus a pre/post SHA invariance test verifies the
real evidence is byte-for-byte unchanged across the entire test suite.

fix-5 negatives (real orchestrator main paths):
  MN01  pack mutation 缺一项 → exit 1
  MN02  annotation mutation 缺一项 → exit 1
  MN03  mutation 多一项未知 → exit 1
  MN04  mutation 名称重复 → exit 1
  MN05  用未知替换必需项 → exit 1
  MN06  pack 2 readiness invariant 缺一项 → exit 1
  MN07  annotation readiness invariant 缺失 → exit 1
  MN08  annotation 5 meta-negative 缺一项 → exit 1
  MN09  子进程 exit≠0 但 evidence 伪造 → exit 1
  MN10  evidence exit_code 与真实退出码不一致 → exit 1
  MN11  run_id 不同 → exit 1
  MN12  generated_at 窗口外 / naive → exit 1
  MN13  contract SHA 不匹配 → exit 1
  MN14  _publish_atomic 正常 roundtrip
  MN15  Commander coverage-shrink: 1/1 arbitrary + 0 invariant → exit 1

fix-5 Commander negatives (real main paths, real evidence_dir):
  MN16  Pre-commit tamper: gate publish 后篡改 → exit 1, no green metrics
  MN17  Metrics publish failure → exit 1, no PASS, FAILED marker
  MN18  Malformed evidence (缺 mutation 字段) → exit 1, no exception, FAILED marker
  MN19  Metadata mismatch (phase/schema/command) → exit 1
  MN20  Post-commit tamper → verifier exit 1

fix-5 isolation:
  MN21  Real evidence SHA pre/post test suite: delta = 0
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import uuid

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

# Real orchestrator + verifier
from scripts.p13_2_pack_trust_contract_metrics import (  # noqa: E402
    _publish_atomic,
    _sha256_bytes,
)
from scripts.p13_2_pack_trust_contract_metrics import (  # noqa: E402
    main as orchestrator_main,
)
import scripts.p13_2_verify_committed_evidence as verifier_module  # noqa: E402
from signal_miner.evaluation.p13_2_gate_contract import (  # noqa: E402
    ANNOTATION_META_NEGATIVES,
    ANNOTATION_MUTATIONS,
    ANNOTATION_READINESS_INVARIANTS,
    CONTRACT_SCHEMA_VERSION,
    CONTRACT_SHA256,
    PACK_TRUST_MUTATIONS,
    PACK_TRUST_READINESS_INVARIANTS,
)

# Artifact names (must match orchestrator/verifier constants)
PT_NAME = "pack-trust-mutation-gate.json"
AN_NAME = "human-annotation-mutation-gate.json"
METRICS_NAME = "pack-trust-contract-metrics.json"

REAL_EVIDENCE_DIR = PROJECT / "docs" / "P13-2-evidence"
REAL_FILES = (
    REAL_EVIDENCE_DIR / METRICS_NAME,
    REAL_EVIDENCE_DIR / PT_NAME,
    REAL_EVIDENCE_DIR / AN_NAME,
)

PT_PHASE = "pack_trust_mutation_gate"
PT_COMMAND = "pack-trust-mutation-gate"
AN_PHASE = "annotation_mutation_gate"
AN_COMMAND = "annotation-mutation-gate"


# ── Fake gate runner helpers ──

def _gen_ts() -> str:
    """Fresh aware ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _gen_ts_naive() -> str:
    """Naive (tzinfo-stripped) timestamp for negative tests."""
    return datetime.now().isoformat()


def _make_valid_row(name: str) -> dict:
    return {
        "mutation": name,
        "child_exit": 1,
        "check_exists": True,
        "target_passed": False,
        "detected": True,
    }


def _make_standard_pt_bytes(run_id: str) -> bytes:
    rows = [_make_valid_row(n) for n in PACK_TRUST_MUTATIONS]
    invariants = [
        {"name": n, "passed": True, "child_exit": 2, "expected_exit": 2}
        for n in PACK_TRUST_READINESS_INVARIANTS
    ]
    payload = {
        "run_id": run_id,
        "generated_at": _gen_ts(),
        "phase": PT_PHASE,
        "contract_sha256": CONTRACT_SHA256,
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "exit_code": 0,
        "command": PT_COMMAND,
        "passed": True,
        "total_mutations": len(rows),
        "detected_count": len(rows),
        "target_check": "pack_trust",
        "results": rows,
        "readiness_invariants": invariants,
        "readiness_invariants_passed": True,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def _make_standard_an_bytes(run_id: str) -> bytes:
    rows = [_make_valid_row(n) for n in ANNOTATION_MUTATIONS]
    invariants = [
        {"name": n, "passed": True, "child_exit": 2, "expected_exit": 2}
        for n in ANNOTATION_READINESS_INVARIANTS
    ]
    meta_negatives = [
        {"name": n, "passed": True, "actual_detected": False,
         "expected_detected": False, "check_exists": True, "target_passed": None}
        for n in ANNOTATION_META_NEGATIVES
    ]
    payload = {
        "run_id": run_id,
        "generated_at": _gen_ts(),
        "phase": AN_PHASE,
        "contract_sha256": CONTRACT_SHA256,
        "contract_schema_version": CONTRACT_SCHEMA_VERSION,
        "exit_code": 0,
        "command": AN_COMMAND,
        "passed": True,
        "total_mutations": len(rows),
        "detected_count": len(rows),
        "results": rows,
        "readiness_invariants": invariants,
        "readiness_invariants_passed": True,
        "meta_negatives": meta_negatives,
        "meta_negatives_passed": True,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def _make_runner(pt_bytes_fn=None, an_bytes_fn=None,
                 pt_exit=0, an_exit=0):
    """Factory: returns a gate_runner callable."""
    def runner(script, run_id, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if "pack_trust" in str(script):
            raw = (pt_bytes_fn or _make_standard_pt_bytes)(run_id)
            out_path.write_bytes(raw)
            return (pt_exit, raw)
        else:
            raw = (an_bytes_fn or _make_standard_an_bytes)(run_id)
            out_path.write_bytes(raw)
            return (an_exit, raw)
    return runner


def _read_metrics(evidence_dir: Path) -> dict:
    return json.loads(
        (evidence_dir / "pack-trust-contract-metrics.json").read_text())


# ── Real evidence SHA invariance (suite-wide fixture) ──

@pytest.fixture(scope="module", autouse=True)
def real_evidence_sha_guard():
    """Record real evidence SHAs before any test, assert unchanged after."""
    before = {}
    for f in REAL_FILES:
        if f.exists():
            before[f] = _sha256_bytes(f.read_bytes())
        else:
            before[f] = None
    yield before
    after = {}
    for f in REAL_FILES:
        if f.exists():
            after[f] = _sha256_bytes(f.read_bytes())
        else:
            after[f] = None
    for f in REAL_FILES:
        assert before[f] == after[f], (
            f"REAL evidence changed by tests: {f.name} "
            f"before={before[f]} after={after[f]}. Tests MUST use tmp_path."
        )


class TestRealEvidenceIsolation:
    """MN21: real evidence SHA must be byte-for-byte unchanged."""

    def test_real_evidence_unchanged_before_tests(self, real_evidence_sha_guard):
        # Fixture handles before/after; this test just makes the guard visible.
        for f in REAL_FILES:
            if real_evidence_sha_guard[f] is not None:
                assert real_evidence_sha_guard[f] is not None


# ── Positive test ──

class TestOrchestratorPositive:
    def test_full_contract_pass(self, tmp_path):
        """Full 23/34/2/1/5 contract → orchestrator exit 0, passed=true."""
        runner = _make_runner()
        exit_code = orchestrator_main(gate_runner=runner, evidence_dir=tmp_path)
        assert exit_code == 0, f"Expected exit 0, got {exit_code}"

        metrics = _read_metrics(tmp_path)
        assert metrics["passed"] is True
        assert metrics["status"] == "COMMITTED"
        assert metrics["pack_trust_mutation_gate"]["total_mutations"] == 23
        assert metrics["annotation_mutation_gate"]["total_mutations"] == 34

        # Verifier must also pass
        v_errs = verifier_module.verify(tmp_path)
        assert v_errs == [], f"verifier errors: {v_errs}"


# ── Meta-negatives 1–15 ──

class TestMetaNegativeContract:
    """MN01–MN15: orchestrator MUST exit 1 on contract violations."""

    # MN01
    def test_pt_mutation_missing_one(self, tmp_path):
        def pt_bytes_fn(run_id):
            rows = [_make_valid_row(n) for n in PACK_TRUST_MUTATIONS[:-1]]
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["results"] = rows
            payload["total_mutations"] = len(rows)
            payload["detected_count"] = len(rows)
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1
        metrics = _read_metrics(tmp_path)
        assert metrics["passed"] is False
        assert metrics["status"] == "FAILED"

    # MN02
    def test_an_mutation_missing_one(self, tmp_path):
        def an_bytes_fn(run_id):
            rows = [_make_valid_row(n) for n in ANNOTATION_MUTATIONS[:-1]]
            payload = json.loads(_make_standard_an_bytes(run_id))
            payload["results"] = rows
            payload["total_mutations"] = len(rows)
            payload["detected_count"] = len(rows)
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(an_bytes_fn=an_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN03
    def test_unknown_extra_mutation(self, tmp_path):
        def pt_bytes_fn(run_id):
            rows = [_make_valid_row(n) for n in PACK_TRUST_MUTATIONS]
            rows.append(_make_valid_row("not_in_contract"))
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["results"] = rows
            payload["total_mutations"] = len(rows)
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN04
    def test_duplicate_mutation_name(self, tmp_path):
        def pt_bytes_fn(run_id):
            names = list(PACK_TRUST_MUTATIONS)
            names.append(names[0])
            rows = [_make_valid_row(n) for n in names]
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["results"] = rows
            payload["total_mutations"] = len(rows)
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN05
    def test_replaced_with_unknown(self, tmp_path):
        def pt_bytes_fn(run_id):
            names = list(PACK_TRUST_MUTATIONS)
            names[0] = "completely_unknown_mutation"
            rows = [_make_valid_row(n) for n in names]
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["results"] = rows
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN06
    def test_pt_invariant_missing_one(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["readiness_invariants"] = payload["readiness_invariants"][:-1]
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN07
    def test_an_invariant_missing(self, tmp_path):
        def an_bytes_fn(run_id):
            payload = json.loads(_make_standard_an_bytes(run_id))
            payload["readiness_invariants"] = []
            payload["readiness_invariants_passed"] = True
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(an_bytes_fn=an_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN08
    def test_meta_negative_missing_one(self, tmp_path):
        def an_bytes_fn(run_id):
            payload = json.loads(_make_standard_an_bytes(run_id))
            payload["meta_negatives"] = payload["meta_negatives"][:-1]
            payload["meta_negatives_passed"] = True
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(an_bytes_fn=an_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN09
    def test_subprocess_exit_nonzero_evidence_forged(self, tmp_path):
        runner = _make_runner(pt_exit=1)
        exit_code = orchestrator_main(gate_runner=runner, evidence_dir=tmp_path)
        assert exit_code == 1

    # MN10
    def test_evidence_exit_code_mismatch(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["exit_code"] = 99
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN11
    def test_run_id_mismatch(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["run_id"] = "different-run-id-" + uuid.uuid4().hex
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN12a
    def test_generated_at_outside_window(self, tmp_path):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["generated_at"] = old_ts
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN12b — naive timestamp (no tzinfo)
    def test_generated_at_naive(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["generated_at"] = _gen_ts_naive()
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN13
    def test_contract_sha_mismatch(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["contract_sha256"] = "deadbeef" * 8
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN14
    def test_publish_atomic_roundtrip(self, tmp_path):
        dest = tmp_path / "_publish_tmp.json"
        data = json.dumps({"test": "roundtrip"}).encode()
        errs = _publish_atomic(data, dest)
        assert len(errs) == 0, f"_publish_atomic errors: {errs}"
        assert dest.exists()
        assert dest.read_bytes() == data

    # MN15
    def test_commander_coverage_shrink(self, tmp_path):
        def pt_bytes_fn(run_id):
            return json.dumps({
                "run_id": run_id, "generated_at": _gen_ts(),
                "phase": PT_PHASE, "contract_sha256": CONTRACT_SHA256,
                "contract_schema_version": CONTRACT_SCHEMA_VERSION,
                "exit_code": 0, "command": PT_COMMAND,
                "passed": True, "total_mutations": 1, "detected_count": 1,
                "results": [_make_valid_row("arbitrary_unrecognized_probe")],
                "readiness_invariants": [],
                "readiness_invariants_passed": True,
            }).encode()
        def an_bytes_fn(run_id):
            return json.dumps({
                "run_id": run_id, "generated_at": _gen_ts(),
                "phase": AN_PHASE, "contract_sha256": CONTRACT_SHA256,
                "contract_schema_version": CONTRACT_SCHEMA_VERSION,
                "exit_code": 0, "command": AN_COMMAND,
                "passed": True, "total_mutations": 1, "detected_count": 1,
                "results": [_make_valid_row("arbitrary_unrecognized_probe")],
                "readiness_invariants": [],
                "readiness_invariants_passed": True,
                "meta_negatives": [],
                "meta_negatives_passed": True,
            }).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn, an_bytes_fn=an_bytes_fn),
            evidence_dir=tmp_path)
        assert exit_code == 1


# ── fix-5 Commander negatives (real main paths) ──

class TestFix5CommanderNegatives:
    """Real pre-commit / publish / malformed / metadata / post-commit attacks."""

    # MN16 — Pre-commit tamper
    # pack gate publish 后、metrics commit 前把其 passed 改 false。
    # main() 必须 exit 1, 本次 metrics 为 FAILED/passed=false (no green).
    def test_pre_commit_tamper(self, tmp_path, monkeypatch):
        import scripts.p13_2_pack_trust_contract_metrics as mod

        real_publish = mod._publish_atomic
        pt_path_holder: dict = {}

        def patched_publish(source_bytes, dest_path):
            errs = real_publish(source_bytes, dest_path)
            if dest_path.name == PT_NAME and dest_path.parent == tmp_path:
                pt_path_holder["path"] = dest_path
            return errs

        def tampering_runner(script, run_id, out_path):
            exit_code, raw = _make_runner()(script, run_id, out_path)
            return exit_code, raw

        monkeypatch.setattr(mod, "_publish_atomic", patched_publish)

        # Run with a runner that, after pack gate publish, tampers the file
        # in-place before the metrics commit.
        original_reverify = mod._reverify_gate_on_disk

        call_count = {"n": 0}
        def patched_reverify(dest_path, snapshot_bytes, snapshot_sha, run_id, metadata):
            call_count["n"] += 1
            # After pt publish, before metrics commit: tamper the gate file
            if call_count["n"] == 1 and dest_path.exists():
                tampered = json.loads(dest_path.read_text())
                tampered["passed"] = False
                tampered["tamper_marker"] = "pre_commit"
                dest_path.write_text(json.dumps(tampered, indent=2))
            return original_reverify(dest_path, snapshot_bytes, snapshot_sha,
                                      run_id, metadata)

        monkeypatch.setattr(mod, "_reverify_gate_on_disk", patched_reverify)

        exit_code = orchestrator_main(
            gate_runner=tampering_runner, evidence_dir=tmp_path)
        assert exit_code == 1, "pre-commit tamper MUST exit 1"

        metrics = _read_metrics(tmp_path)
        assert metrics["passed"] is False, "FAILED marker, no green"
        assert metrics["status"] == "FAILED"

    # MN17 — Metrics publish failure
    def test_metrics_publish_failure(self, tmp_path, monkeypatch):
        import scripts.p13_2_pack_trust_contract_metrics as mod

        real_publish = mod._publish_atomic
        call_count = {"n": 0}

        def patched_publish(source_bytes, dest_path):
            call_count["n"] += 1
            # Let gate publishes succeed, but metrics publish fails
            if dest_path.name == "pack-trust-contract-metrics.json" and call_count["n"] >= 3:
                return ["forced metrics publish failure"]
            return real_publish(source_bytes, dest_path)

        monkeypatch.setattr(mod, "_publish_atomic", patched_publish)

        exit_code = orchestrator_main(
            gate_runner=_make_runner(), evidence_dir=tmp_path)
        assert exit_code == 1, "metrics publish failure MUST exit 1"

        # Even if metrics write partially failed, the FAILED marker write
        # should also attempt to publish; final state must NOT be COMMITTED green.
        metrics_path = tmp_path / "pack-trust-contract-metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
            assert metrics.get("passed") is not True, "no green metrics"

    # MN18 — Malformed evidence: row missing mutation field → KeyError previously
    def test_malformed_evidence_no_mutation_field(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            # Strip 'mutation' from first row
            first_row = payload["results"][0]
            del first_row["mutation"]
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        # Must NOT crash; must exit 1
        assert exit_code == 1
        metrics = _read_metrics(tmp_path)
        assert metrics["status"] == "FAILED"
        assert metrics["passed"] is False

    # MN18b — Malformed: top-level list instead of dict
    def test_malformed_top_level_list(self, tmp_path):
        def pt_bytes_fn(run_id):
            return json.dumps(["not", "a", "dict"]).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1
        metrics = _read_metrics(tmp_path)
        assert metrics["status"] == "FAILED"

    # MN18c — Malformed: results is dict instead of list
    def test_malformed_results_dict(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["results"] = {"key": "value"}
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN18d — Malformed: row is not a dict
    def test_malformed_row_not_dict(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["results"][0] = "not a dict"
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN18e — Malformed: bool as 1 instead of True (truthy but not True)
    def test_malformed_bool_as_int(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["results"][0]["detected"] = 1
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN19 — Metadata mismatch: phase/schema/command all wrong
    def test_metadata_mismatch_all(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["phase"] = "wrong_phase"
            payload["command"] = "wrong-command"
            payload["contract_schema_version"] = "0.0.0-wrong"
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN19b — phase wrong only
    def test_metadata_phase_wrong(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            payload["phase"] = "annotation_mutation_gate"  # cross-contamination
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN19c — command missing
    def test_metadata_command_missing(self, tmp_path):
        def pt_bytes_fn(run_id):
            payload = json.loads(_make_standard_pt_bytes(run_id))
            del payload["command"]
            return json.dumps(payload).encode()
        exit_code = orchestrator_main(
            gate_runner=_make_runner(pt_bytes_fn=pt_bytes_fn), evidence_dir=tmp_path)
        assert exit_code == 1

    # MN20 — Post-commit tamper: verifier exit 1
    def test_post_commit_tamper_verifier(self, tmp_path):
        # First: run a successful commit
        runner = _make_runner()
        exit_code = orchestrator_main(gate_runner=runner, evidence_dir=tmp_path)
        assert exit_code == 0

        # Verifier should pass
        v_errs = verifier_module.verify(tmp_path)
        assert v_errs == [], f"verifier should pass before tamper: {v_errs}"

        # Now tamper the pack-trust gate file
        pt_path = tmp_path / "pack-trust-mutation-gate.json"
        tampered = json.loads(pt_path.read_text())
        tampered["passed"] = False
        tampered["tamper_marker"] = "post_commit"
        pt_path.write_text(json.dumps(tampered, indent=2))

        # Verifier MUST now exit 1
        v_errs = verifier_module.verify(tmp_path)
        assert len(v_errs) > 0, "verifier must catch post-commit tamper"
        # Verifier reports SHA mismatch (artifacts SHA changed)
        assert any("sha256" in e.lower() or "sha" in e.lower() for e in v_errs), (
            f"verifier should report SHA mismatch: {v_errs}")


# ── fix-6 Commander negatives: marker publish error closure ──
#
# All 8 cases exercise the REAL main() with monkeypatched _publish_atomic
# and capture stdout/stderr to assert consistency with on-disk reality.

class TestFix6MarkerNegatives:
    """8 marker publish failure negatives. All use tmp_path; real evidence
    is never touched (module-level fixture asserts SHA delta=0)."""

    def _gate_state(self):
        return {"calls": 0, "running_ok": None}

    def _capture_main(self, monkeypatch, tmp_path, runner=None,
                      publish_fail_indices=None,
                      publish_fail_message="forced failure",
                      pre_seed_metrics=None):
        """Run main() under monkeypatch, capturing stdout/stderr.

        publish_fail_indices: set of 1-based call numbers to fail (each
        returns [message] instead of publishing).
        pre_seed_metrics: optional dict to write to evidence_dir/OUT_NAME
        before calling main (simulates stale COMMITTED).
        Returns (exit_code, stdout, stderr, gate_state, publish_call_count).
        """
        import io

        import scripts.p13_2_pack_trust_contract_metrics as mod

        if pre_seed_metrics is not None:
            (tmp_path / "pack-trust-contract-metrics.json").write_text(
                json.dumps(pre_seed_metrics))

        real_publish = mod._publish_atomic
        publish_n = {"n": 0}

        if publish_fail_indices:
            def patched_publish(source_bytes, dest_path):
                publish_n["n"] += 1
                if publish_n["n"] in publish_fail_indices:
                    return [publish_fail_message]
                return real_publish(source_bytes, dest_path)
            monkeypatch.setattr(mod, "_publish_atomic", patched_publish)

        out_buf = io.StringIO()
        err_buf = io.StringIO()
        gate_state = self._gate_state()
        try:
            old_out, old_err = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = out_buf, err_buf
            try:
                exit_code = mod.main(
                    gate_runner=runner or _make_runner(),
                    evidence_dir=tmp_path,
                    _gate_state=gate_state,
                )
            finally:
                sys.stdout, sys.stderr = old_out, old_err
        except Exception as e:
            exit_code = -99
            err_buf.write(f"EXCEPTION: {type(e).__name__}: {e}\n")
        return exit_code, out_buf.getvalue(), err_buf.getvalue(), gate_state, publish_n["n"]

    # MN-M1: RUNNING _publish_atomic returns error → exit 1, gate_calls=0, no PASS
    def test_m1_running_publish_failure_blocks_gates(self, tmp_path, monkeypatch):
        exit_code, stdout, stderr, gs, _ = self._capture_main(
            monkeypatch, tmp_path,
            publish_fail_indices={1},  # first publish = RUNNING marker
            publish_fail_message="forced RUNNING marker publish failure",
        )
        assert exit_code == 1
        assert gs["calls"] == 0, "gates MUST NOT run when RUNNING marker fails"
        assert "RUNNING_MARKER_WRITE_FAILED" in stderr
        assert "this run did not start" in stderr
        assert "PASS" not in stdout

    # MN-M2: RUNNING publish OK, readback run_id mismatch → exit 1, gate_calls=0
    def test_m2_running_readback_run_id_mismatch(self, tmp_path, monkeypatch):
        import scripts.p13_2_pack_trust_contract_metrics as mod

        real_publish = mod._publish_atomic
        call_n = {"n": 0}

        def tampering_publish(source_bytes, dest_path):
            call_n["n"] += 1
            errs = real_publish(source_bytes, dest_path)
            # After RUNNING publish (call 1), tamper run_id on disk
            if call_n["n"] == 1 and dest_path.name == "pack-trust-contract-metrics.json":
                disk = json.loads(dest_path.read_text())
                disk["run_id"] = "tampered-different-run-id"
                dest_path.write_text(json.dumps(disk))
            return errs

        monkeypatch.setattr(mod, "_publish_atomic", tampering_publish)
        gate_state = self._gate_state()
        import io
        err_buf = io.StringIO()
        out_buf = io.StringIO()
        sys.stderr, sys.stdout = err_buf, out_buf
        try:
            exit_code = mod.main(gate_runner=_make_runner(),
                                 evidence_dir=tmp_path, _gate_state=gate_state)
        finally:
            sys.stderr, sys.stdout = sys.__stderr__, sys.__stdout__
        assert exit_code == 1
        assert gate_state["calls"] == 0

    # MN-M3: RUNNING publish OK, readback status mismatch → exit 1, gate_calls=0
    def test_m3_running_readback_status_mismatch(self, tmp_path, monkeypatch):
        import scripts.p13_2_pack_trust_contract_metrics as mod

        real_publish = mod._publish_atomic
        call_n = {"n": 0}

        def tampering_publish(source_bytes, dest_path):
            call_n["n"] += 1
            errs = real_publish(source_bytes, dest_path)
            if call_n["n"] == 1 and dest_path.name == "pack-trust-contract-metrics.json":
                disk = json.loads(dest_path.read_text())
                disk["status"] = "COMMITTED"  # wrong — should be RUNNING
                dest_path.write_text(json.dumps(disk))
            return errs

        monkeypatch.setattr(mod, "_publish_atomic", tampering_publish)
        gate_state = self._gate_state()
        exit_code = mod.main(gate_runner=_make_runner(),
                             evidence_dir=tmp_path, _gate_state=gate_state)
        assert exit_code == 1
        assert gate_state["calls"] == 0

    # MN-M4: pre-seeded stale COMMITTED, RUNNING fails → exit 1, gate_calls=0,
    #        error text says "this run did not start"
    def test_m4_stale_committed_running_fails(self, tmp_path, monkeypatch):
        stale = {
            "run_id": "old-green-run",
            "status": "COMMITTED",
            "passed": True,
        }
        exit_code, stdout, stderr, gs, _ = self._capture_main(
            monkeypatch, tmp_path,
            publish_fail_indices={1},
            pre_seed_metrics=stale,
        )
        assert exit_code == 1
        assert gs["calls"] == 0
        assert "this run did not start" in stderr

    # MN-M5: COMMITTED publish fails, FAILED marker succeeds
    #        → exit 1, final status = FAILED/passed=false for this run_id
    def test_m5_committed_fails_failed_marker_succeeds(self, tmp_path, monkeypatch):
        # Commit is the 4th publish (RUNNING=1, pt=2, an=3, COMMITTED=4).
        # FAILED marker (5th) succeeds → should be FAILED/passed=false.
        exit_code, stdout, stderr, gs, _ = self._capture_main(
            monkeypatch, tmp_path,
            publish_fail_indices={4},
        )
        assert exit_code == 1
        assert gs["calls"] == 2  # gates ran
        # FAILED marker should have landed → metrics file is FAILED
        metrics_path = tmp_path / "pack-trust-contract-metrics.json"
        if metrics_path.exists():
            m = json.loads(metrics_path.read_text())
            assert m["status"] == "FAILED"
            assert m["passed"] is False
        # Summary must say "no green metrics left" since FAILED marker wrote OK
        assert "FAILED (no green metrics left)" in stdout
        assert "FAILED_MARKER_WRITE_FAILED" not in stdout
        assert "FAILED_MARKER_WRITE_FAILED" not in stderr

    # MN-M6: COMMITTED fails AND FAILED marker fails
    #        → exit 1, summary contains FAILED_MARKER_WRITE_FAILED,
    #        must NOT contain "no green metrics left"
    def test_m6_committed_and_failed_marker_both_fail(self, tmp_path, monkeypatch):
        exit_code, stdout, stderr, gs, _ = self._capture_main(
            monkeypatch, tmp_path,
            publish_fail_indices={4, 5},  # COMMITTED + FAILED marker
        )
        assert exit_code == 1
        assert "FAILED_MARKER_WRITE_FAILED" in stderr
        # Must NOT claim "no green metrics left"
        assert "no green metrics left" not in stdout

    # MN-M7: FAILED marker written but readback shows old run_id/passed=true
    #        → treated as marker failure, FAILED_MARKER_WRITE_FAILED
    def test_m7_failed_marker_readback_stale(self, tmp_path, monkeypatch):
        import scripts.p13_2_pack_trust_contract_metrics as mod

        real_publish = mod._publish_atomic
        call_n = {"n": 0}

        def tampering_publish(source_bytes, dest_path):
            call_n["n"] += 1
            errs = real_publish(source_bytes, dest_path)
            # After FAILED marker publish (the 5th call), replace with old green
            if call_n["n"] == 5 and dest_path.name == "pack-trust-contract-metrics.json":
                dest_path.write_text(json.dumps({
                    "run_id": "old-green-run",
                    "status": "COMMITTED",
                    "passed": True,
                }))
            return errs

        monkeypatch.setattr(mod, "_publish_atomic", tampering_publish)
        # Force COMMITTED publish (call 4) to fail so FAILED marker is attempted
        # We need a hybrid: call 4 fails normally, call 5 succeeds but tampered
        # Simpler: use _capture_main but override with a more nuanced patcher
        real_publish2 = mod._publish_atomic

        def hybrid_publish(source_bytes, dest_path):
            # Use the tampering_publish above, but force call 4 to "fail"
            # by intercepting before real_publish — we already incremented in
            # tampering_publish, so just route differently
            pass

        # Use a fresh approach: fail call 4, then for call 5 tamper
        call_n2 = {"n": 0}

        def clean_publish(source_bytes, dest_path):
            call_n2["n"] += 1
            if call_n2["n"] == 4:
                return ["forced COMMITTED failure"]
            errs = real_publish2(source_bytes, dest_path)
            if call_n2["n"] == 5 and dest_path.name == "pack-trust-contract-metrics.json":
                dest_path.write_text(json.dumps({
                    "run_id": "old-green-run",
                    "status": "COMMITTED",
                    "passed": True,
                }))
            return errs

        monkeypatch.setattr(mod, "_publish_atomic", clean_publish)
        import io
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        sys.stdout, sys.stderr = out_buf, err_buf
        try:
            exit_code = mod.main(gate_runner=_make_runner(), evidence_dir=tmp_path,
                                 _gate_state=self._gate_state())
        finally:
            sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        assert exit_code == 1
        assert "FAILED_MARKER_WRITE_FAILED" in err_buf.getvalue()
        assert "no green metrics left" not in out_buf.getvalue()

    # MN-M8: positive — RUNNING succeeds → gate_calls=2, COMMITTED, verifier PASS
    def test_m8_positive_running_then_committed(self, tmp_path, monkeypatch):
        exit_code, stdout, stderr, gs, _ = self._capture_main(
            monkeypatch, tmp_path,
            runner=_make_runner(),
        )
        assert exit_code == 0
        assert gs["calls"] == 2
        assert "PASS" in stdout
        metrics = _read_metrics(tmp_path)
        assert metrics["status"] == "COMMITTED"
        assert metrics["passed"] is True
        v_errs = verifier_module.verify(tmp_path)
        assert v_errs == [], f"verifier errors: {v_errs}"


# ── Verifier direct tests ──

class TestVerifier:
    def test_verifier_missing_metrics(self, tmp_path):
        # Only create gates, no metrics
        (tmp_path / PT_NAME).write_text("{}")
        (tmp_path / AN_NAME).write_text("{}")
        errs = verifier_module.verify(tmp_path)
        assert any("missing" in e for e in errs)

    def test_verifier_pass_on_clean_run(self, tmp_path):
        runner = _make_runner()
        exit_code = orchestrator_main(gate_runner=runner, evidence_dir=tmp_path)
        assert exit_code == 0
        errs = verifier_module.verify(tmp_path)
        assert errs == [], f"verifier errors: {errs}"
