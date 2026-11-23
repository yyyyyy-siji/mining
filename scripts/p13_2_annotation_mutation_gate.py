#!/usr/bin/env python3
"""P13-2-2-1: Annotation mutation gate — adversarial mutations.

Hard contract (applies to BOTH validator-targeted and importer-targeted
mutations):

  detected := (
      child_exit == 1                       # process reported failure
      AND target check EXISTS in the report # not fabricated
      AND target.passed IS False            # the SPECIFIC rule failed
  )

The importer mutation runner reads the SAME-RUN `import_report.json`
produced by the importer's `--out` flag. It NEVER fabricates
check_exists or derives target_passed from the exit code. If the report
is missing/corrupt, the target check is absent, or the target still
passed, the mutation is NOT detected — the gate FAILS. This is enforced
by the four meta-negative invariants at the end of the run.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parent.parent
VALIDATE = PROJECT / "scripts" / "p13_2_validate_human_annotations.py"
IMPORT = PROJECT / "scripts" / "p13_2_import_human_annotations.py"
PREPARE = PROJECT / "scripts" / "p13_2_prepare_human_tasks.py"
GENFIX = PROJECT / "scripts" / "p13_2_generate_fixture_annotations.py"
SIGN = PROJECT / "scripts" / "p13_2_sign_human_task_pack.py"
PY = sys.executable

# Source artifacts
POS_DIR = PROJECT / "sample_data" / "p13_2" / "positive"
TASKS_DIR = PROJECT / "sample_data" / "p13_2" / "human_tasks"
FIXTURE_ANN = PROJECT / "sample_data" / "p13_2" / "annotations" / "fixture_annotations.json"
DATASET_MANIFEST = PROJECT / "sample_data" / "p13_2" / "manifest.json"

# Test key injected per-run; never hardcoded in production code
TEST_KEY = "test-key-for-ci-pipeline"


def _setup(tmpdir: str) -> None:
    """Copy fixture task packs + fixture annotations + sign manifest to temp dir."""
    for src in TASKS_DIR.glob("human_tasks_*.json"):
        shutil.copy(src, f"{tmpdir}/{src.name}")
    shutil.copy(FIXTURE_ANN, f"{tmpdir}/fixture_annotations.json")
    shutil.copy(str(DATASET_MANIFEST), f"{tmpdir}/dataset_manifest.json")

    _re_sign(tmpdir)


def _re_sign(tmpdir: str) -> None:
    """Re-sign manifest for the tasks in tmpdir (test env + injected key)."""
    sign_env = {
        "APP_ENVIRONMENT": "test",
        "ANNOTATION_PACK_TEST_SIGNING_KEY": TEST_KEY,
        "PATH": os.environ.get("PATH", ""),
    }
    r = subprocess.run(
        [PY, str(SIGN),
         "--tasks", tmpdir,
         "--dataset-manifest", f"{tmpdir}/dataset_manifest.json",
         "--fixture",
         "--manifest-out", f"{tmpdir}/human-task-pack-manifest.json",
         "--out", f"{tmpdir}/sign_report.json"],
        cwd=PROJECT, capture_output=True, text=True, timeout=30, env=sign_env,
    )
    assert r.returncode == 0, f"re-sign failed: {r.stderr[:200]}"


def _run_validate(tmpdir: str, metrics_path: str,
                  stage_policy: str = "") -> subprocess.CompletedProcess:
    """Run the validator with explicit --store and --out in tmpdir."""
    cmd = [PY, str(VALIDATE),
           "--tasks", tmpdir,
           "--store", f"{tmpdir}/store.json",
           "--out", metrics_path]
    if stage_policy:
        cmd.extend(["--stage-policy", stage_policy])
    return subprocess.run(
        cmd, cwd=PROJECT, capture_output=True, text=True, timeout=30,
    )


def _run_import(tmpdir: str, input_path: str, report_path: str) -> subprocess.CompletedProcess:
    """Run the importer with signed manifest + dataset manifest + test env."""
    env = {
        "APP_ENVIRONMENT": "test",
        "ANNOTATION_PACK_TEST_SIGNING_KEY": TEST_KEY,
        "PATH": os.environ.get("PATH", ""),
    }
    return subprocess.run(
        [PY, str(IMPORT),
         "--input", input_path,
         "--tasks", tmpdir,
         "--store", f"{tmpdir}/store.json",
         "--out", report_path,
         "--manifest", f"{tmpdir}/human-task-pack-manifest.json",
         "--dataset-manifest", f"{tmpdir}/dataset_manifest.json",
         "--fixture"],
        cwd=PROJECT, capture_output=True, text=True, timeout=30, env=env,
    )


def _seed_store(tmpdir: str) -> None:
    """Import the clean fixture annotations to seed a valid store."""
    r = _run_import(tmpdir, f"{tmpdir}/fixture_annotations.json",
                    f"{tmpdir}/seed_report.json")
    assert r.returncode == 0, f"seed import failed: {r.stderr[:200]}"


def _read_report_checks(report_path: str) -> dict[str, dict] | None:
    """Read a report JSON and return its `checks` dict, or None on any error.

    Returns None when the file is missing, not JSON, or has no `checks` key.
    The mutation runner treats None as "target absent → not detected".
    """
    p = Path(report_path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None
    checks = data.get("checks")
    if not isinstance(checks, dict):
        return None
    return checks


def _evaluate_detection(child_exit: int, report_path: str,
                        target_check: str) -> tuple[bool, bool, object]:
    """Apply the hard detection contract uniformly.

    Returns (detected, check_exists, target_passed).
    detected is True iff child_exit==1 AND the target check exists in the
    SAME-RUN report AND target.passed is strictly False.
    """
    checks = _read_report_checks(report_path)
    check_exists = checks is not None and target_check in checks
    target_passed = (
        checks.get(target_check, {}).get("passed") if check_exists else None
    )
    detected = (
        child_exit == 1
        and check_exists
        and target_passed is False
    )
    return detected, check_exists, target_passed


def run_validator_mutation(name: str, target_check: str, mutate_fn) -> dict:
    """Mutation that targets the validator (needs a seeded store)."""
    tmpdir = tempfile.mkdtemp(prefix="p13_ann_mut_")
    metrics_path = f"{tmpdir}/metrics.json"
    try:
        _setup(tmpdir)
        _seed_store(tmpdir)
        mutate_fn(tmpdir)
        # Re-sign: pack files may have been modified by the mutation
        _re_sign(tmpdir)
        r = _run_validate(tmpdir, metrics_path)
        detected, check_exists, target_passed = _evaluate_detection(
            r.returncode, metrics_path, target_check)
        return {
            "mutation": name,
            "target_check": target_check,
            "child_exit": r.returncode,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "detected": detected,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "mutation": name,
            "target_check": target_check,
            "child_exit": -1,
            "error": str(e),
            "check_exists": False,
            "target_passed": None,
            "detected": False,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_importer_mutation(name: str, target_check: str, mutate_fn) -> dict:
    """Mutation that targets the importer.

    Hard contract identical to the validator runner: detected requires
    child_exit==1 AND target_check present in the SAME-RUN import_report.json
    AND target.passed is False. The report is read from the importer's --out
    output, never fabricated from the exit code.

    Re-signs the manifest after mutate_fn so that pack_trust passes and the
    target_check (not pack_trust) is the one that catches the mutation.
    """
    tmpdir = tempfile.mkdtemp(prefix="p13_ann_imp_")
    report_path = f"{tmpdir}/import_report.json"
    try:
        _setup(tmpdir)
        _seed_store(tmpdir)
        input_path = f"{tmpdir}/malicious_input.json"
        mutate_fn(tmpdir, input_path)
        # Re-sign: pack files may have been modified by the mutation.
        # For annotation-only mutations, re-signing produces the same manifest
        # (SHA unchanged) — it's a safe no-op in that case.
        _re_sign(tmpdir)
        r = _run_import(tmpdir, input_path, report_path)
        detected, check_exists, target_passed = _evaluate_detection(
            r.returncode, report_path, target_check)
        return {
            "mutation": name,
            "target_check": target_check,
            "child_exit": r.returncode,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "detected": detected,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "mutation": name,
            "target_check": target_check,
            "child_exit": -1,
            "error": str(e),
            "check_exists": False,
            "target_passed": None,
            "detected": False,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run_policy_mutation(name: str, target_check: str, mutate_policy_fn) -> dict:
    """Mutation that mutates the stage policy file and runs the validator."""
    tmpdir = tempfile.mkdtemp(prefix="p13_ann_pol_")
    metrics_path = f"{tmpdir}/metrics.json"
    try:
        _setup(tmpdir)
        _seed_store(tmpdir)
        policy_copy = Path(tmpdir) / "stage-policy.json"
        src_policy = PROJECT / "docs" / "P13-2" / "stage-policy.json"
        if src_policy.exists():
            shutil.copy(src_policy, policy_copy)
        mutate_policy_fn(policy_copy)
        r = _run_validate(tmpdir, metrics_path, stage_policy=str(policy_copy))
        detected, check_exists, target_passed = _evaluate_detection(
            r.returncode, metrics_path, target_check)
        return {
            "mutation": name,
            "target_check": target_check,
            "child_exit": r.returncode,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "detected": detected,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "mutation": name,
            "target_check": target_check,
            "child_exit": -1,
            "error": str(e),
            "check_exists": False,
            "target_passed": None,
            "detected": False,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run_zero_candidate_invariant() -> dict:
    """Readiness invariant: zero real candidates must produce BLOCKED/exit 2.

    NOT a mutation — verifies correct BLOCKED behavior; does not count toward
    the mutation detected_count.
    """
    d = tempfile.mkdtemp(prefix="p13_ann_blocked_")
    try:
        blocked = {"status": "BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES",
                   "eligible_count": 0}
        _save(f"{d}/blocked_candidates.json", blocked)
        r = subprocess.run(
            [PY, str(PREPARE),
             "--candidates", f"{d}/blocked_candidates.json",
             "--manifest", str(PROJECT / "sample_data" / "p13_2" / "manifest.json"),
             "--out-dir", f"{d}/blocked_tasks",
             "--out", f"{d}/blocked_readiness.json"],
            cwd=PROJECT, capture_output=True, text=True, timeout=30,
        )
        return {
            "name": "zero_real_candidates_blocked_exit2",
            "child_exit": r.returncode,
            "expected_exit": 2,
            "passed": r.returncode == 2,
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _run_importer_meta_negatives() -> list[dict]:
    """Four meta-negatives proving the importer runner cannot be fooled.

    Each MUST report detected=False. They construct importer reports that
    would have falsely passed under the old (exit-code-deriving) runner:
      1. exit 1 + target check = true   → must NOT detect
      2. exit 1 + target check absent   → must NOT detect
      3. exit 1 + only an unrelated check false → must NOT detect
      4. report missing/corrupt         → must NOT detect

    These are implemented by writing a synthetic import_report.json directly
    and feeding it to _evaluate_detection (the SAME function the real runner
    uses), so they verify the contract logic itself.
    """
    tmpdir = tempfile.mkdtemp(prefix="p13_ann_meta_")
    results: list[dict] = []
    try:
        # MN1: exit 1, target check present but passed=true
        r1 = f"{tmpdir}/r1.json"
        _save(r1, {
            "status": "FAIL_VALIDATION", "passed": False,
            "checks": {
                "schema_strict": {"passed": True,
                                  "observations": {"error_codes": [], "error_count": 0}},
            },
        })
        detected, check_exists, target_passed = _evaluate_detection(
            1, r1, "schema_strict")
        results.append({
            "name": "meta_neg_exit1_target_true",
            "expected_detected": False,
            "actual_detected": detected,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "passed": detected is False,
        })

        # MN2: exit 1, target check absent (only unrelated checks present)
        r2 = f"{tmpdir}/r2.json"
        _save(r2, {
            "status": "FAIL_VALIDATION", "passed": False,
            "checks": {
                "schema_strict": {"passed": False,
                                  "observations": {"error_codes": ["x"], "error_count": 1}},
            },
        })
        detected, check_exists, target_passed = _evaluate_detection(
            1, r2, "fixture_provenance")  # target NOT in report
        results.append({
            "name": "meta_neg_exit1_target_absent",
            "expected_detected": False,
            "actual_detected": detected,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "passed": detected is False,
        })

        # MN3: exit 1, only an unrelated check is false (target check true)
        r3 = f"{tmpdir}/r3.json"
        _save(r3, {
            "status": "FAIL_VALIDATION", "passed": False,
            "checks": {
                "fixture_provenance": {"passed": True,
                                       "observations": {"error_codes": [], "error_count": 0}},
                "schema_strict": {"passed": False,
                                  "observations": {"error_codes": ["y"], "error_count": 1}},
            },
        })
        detected, check_exists, target_passed = _evaluate_detection(
            1, r3, "fixture_provenance")
        results.append({
            "name": "meta_neg_exit1_only_unrelated_false",
            "expected_detected": False,
            "actual_detected": detected,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "passed": detected is False,
        })

        # MN4: report missing / corrupt
        detected, check_exists, target_passed = _evaluate_detection(
            1, f"{tmpdir}/does_not_exist.json", "schema_strict")
        results.append({
            "name": "meta_neg_report_missing",
            "expected_detected": False,
            "actual_detected": detected,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "passed": detected is False,
        })

        # MN4b: report corrupt (not valid JSON)
        corrupt = f"{tmpdir}/corrupt.json"
        Path(corrupt).write_text("{not valid json")
        detected, check_exists, target_passed = _evaluate_detection(
            1, corrupt, "schema_strict")
        results.append({
            "name": "meta_neg_report_corrupt",
            "expected_detected": False,
            "actual_detected": detected,
            "check_exists": check_exists,
            "target_passed": target_passed,
            "passed": detected is False,
        })

        return results
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _load(path: str) -> dict | list:
    return json.loads(Path(path).read_text())


def _save(path: str, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _load_store(tmpdir: str) -> dict:
    return _load(f"{tmpdir}/store.json")


def _save_store(tmpdir: str, data) -> None:
    _save(f"{tmpdir}/store.json", data)


def _load_fixture_anns(tmpdir: str) -> list:
    return _load(f"{tmpdir}/fixture_annotations.json")["annotations"]


def main() -> int:
    p = argparse.ArgumentParser(
        description="Annotation mutation gate",
    )
    p.add_argument("--run-id", default="",
                   help="Shared run ID from orchestrator (injected for evidence chain)")
    p.add_argument("--out", default="",
                   help="Override output JSON path")
    args = p.parse_args()

    if not FIXTURE_ANN.exists():
        print("ERROR: fixture_annotations.json not found. Run generate first.")
        return 1

    results = []

    # ─── Validator-targeted mutations (1-15c) ───

    # 1. fixture 标签计入真实人工数量 — flip fixture=false on all annotations
    def m1(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            entry["annotation"]["fixture"] = False
        _save_store(d, store)
    results.append(run_validator_mutation(
        "fixture_counted_as_real", "real_vs_fixture_count", m1))

    # 2. LLM suggestion 直接复制为 gold 且无人工 action — assisted annotation
    #    without review_action, fixture=false (mimics LLM copy)
    def m2(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["annotation_mode"] == "assisted_review":
                ann["review_action"] = None
                ann["fixture"] = False
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "llm_suggestion_as_gold_no_action", "assisted_review_action", m2))

    # 3. test 包含 prediction/model/confidence — inject into test A task pack
    def m3(d):
        pack = _load(f"{d}/human_tasks_test_A.json")
        for task in pack.get("tasks", []):
            task["model"] = "deepseek"
            task["confidence"] = 0.95
            break
        _save(f"{d}/human_tasks_test_A.json", pack)
    results.append(run_validator_mutation(
        "test_pack_has_model_confidence", "no_blind_leakage_in_tasks", m3))

    # 4. A 能读取 B 标签 — copy B's annotation into A pack's task
    def m4(d):
        store = _load_store(d)
        b_entry = None
        a_ann_id = None
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["annotator_slot"] == "B":
                b_entry = ann
            if ann["annotator_slot"] == "A" and a_ann_id is None:
                a_ann_id = ann["annotation_id"]
        if b_entry and a_ann_id:
            for entry in store.get("annotations", []):
                if entry["annotation"]["annotation_id"] == a_ann_id:
                    entry["annotation"]["cross_ref_b_label"] = json.dumps(
                        b_entry["signals"], ensure_ascii=False)
                    break
            _save_store(d, store)
    results.append(run_validator_mutation(
        "a_reads_b_label", "schema_strict", m4))

    # 5. 同一 pseudonym 同时标 A 和 B
    def m5(d):
        store = _load_store(d)
        by_sample: dict[str, dict] = {}
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["annotator_slot"] in ("A", "B"):
                by_sample.setdefault(ann["sample_id"], {})[ann["annotator_slot"]] = ann
        for _sid, slots in by_sample.items():
            if "A" in slots and "B" in slots:
                slots["B"]["annotator_pseudonym"] = slots["A"]["annotator_pseudonym"]
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "same_pseudonym_a_and_b", "no_self_pairing", m5))

    # 6. task hash 篡改
    def m6(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            entry["annotation"]["task_hash"] = "a" * 64
            break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "task_hash_tampered", "task_identity", m6))

    # 7. content hash 篡改
    def m7(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            entry["annotation"]["content_hash"] = "b" * 64
            break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "content_hash_tampered", "task_identity", m7))

    # 8. signal count 与 signals 长度不一致
    def m8(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["signals"]:
                ann["signal_count"] = ann["signal_count"] + 1
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "signal_count_mismatch", "signal_count_consistency", m8))

    # 9. has_signals=false 但 signals 非空
    def m9(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["signals"]:
                ann["has_signals"] = False
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "has_signals_false_but_signals_nonempty", "has_signals_consistency", m9))

    # 10. 非法 signal type
    def m10(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["signals"]:
                ann["signals"][0]["signal_type"] = "totally_invalid_type"
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "invalid_signal_type", "signal_type_whitelist", m10))

    # 11. 中文 Unicode evidence offset 错误
    def m11(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["signals"] and ann["signals"][0]["evidence_spans"]:
                span = ann["signals"][0]["evidence_spans"][0]
                span["text"] = span["text"] + "额外字符"
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "unicode_evidence_offset_error", "evidence_offsets", m11))

    # 12. evidence 为空
    def m12(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["signals"]:
                ann["signals"][0]["evidence_spans"] = []
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "evidence_empty", "summary_and_evidence_nonempty", m12))

    # 13. summary 为空
    def m13(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["signals"]:
                ann["signals"][0]["summary"] = ""
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "summary_empty", "summary_and_evidence_nonempty", m13))

    # 14. PII leak via a LEGITIMATE signal-level field (notes)
    def m14(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["signals"]:
                ann["signals"][0]["notes"] = "contact annotator at leaked@company.com or 13800138000"
                break
        _save_store(d, store)
    results.append(run_validator_mutation(
        "pii_email_leak_in_notes", "no_pii_leak", m14))

    # 15. calibration policy=true — mutate the FROZEN STAGE POLICY FILE
    results.append(_run_policy_mutation(
        "calibration_policy_true", "calibration_not_allowed",
        lambda p: _save(str(p), json.dumps({"stage": "P13-2-2-1",
                                            "calibration_allowed": True}))))

    # 15b. calibration policy missing
    results.append(_run_policy_mutation(
        "calibration_policy_missing", "calibration_not_allowed",
        lambda p: p.unlink(missing_ok=True) if p.exists() else None))

    # 15c. calibration policy wrong type (string instead of bool)
    results.append(_run_policy_mutation(
        "calibration_policy_wrong_type", "calibration_not_allowed",
        lambda p: _save(str(p), json.dumps({"stage": "P13-2-2-1",
                                            "calibration_allowed": "yes"}))))

    # ─── Importer-targeted mutations (16-20) ───
    # These now assert against the importer's SAME-RUN structured `checks`
    # report. The target_check must be a real importer check name. Each
    # mutation produces a violation that makes ONLY (or primarily) the
    # target check fail.

    # 16. 同 annotation ID 不同内容重复导入 — change started_at so the content
    #     hash differs while every per-item check still passes, then the
    #     annotation_id_conflict check fires against the seeded store.
    def m16(d, input_path):
        anns = _load_fixture_anns(d)
        first = dict(anns[0])
        # Same id, different content (started_at is part of the hash but not
        # validated against the task pack). Every other field stays valid.
        first["started_at"] = "2020-01-01T00:00:00+00:00"
        first["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [first]})
    results.append(run_importer_mutation(
        "same_id_different_content_conflict", "annotation_id_conflict", m16))

    # 17. dataset ID mismatch — keep sample_id/slot valid so the task lookup
    #     succeeds, but corrupt dataset_id so dataset_identity fails.
    def m17(d, input_path):
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["dataset_id"] = "nonexistent_dataset_0"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "nonexistent_dataset_id", "dataset_identity", m17))

    # 18. sample ID 不存在 — task_exists fails (no task for the sample/slot).
    def m18(d, input_path):
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["sample_id"] = "gs_nonexistent_sample"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "nonexistent_sample_id", "task_exists", m18))

    # 19. 未知 schema 字段 — schema_strict fails (extra="forbid").
    def m19(d, input_path):
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["totally_unknown_field"] = "surprise"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "unknown_schema_field", "schema_strict", m19))

    # 20a. fixture task + 普通 annotation ID + fixture=false
    #       (Commander 发现的真实绕过路径，fix-3 后必须阻断)
    def m20a(d, input_path):
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_human_20260713_0001"
        ann["fixture"] = False
        # Change started_at so content hash differs and idempotent skip
        # does not suppress the check.
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "fixture_normal_id_false", "fixture_provenance", m20a))

    # 20b. fixture task + 随机 UUID + fixture=false
    def m20b(d, input_path):
        import uuid as _uuid
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = str(_uuid.uuid4())
        ann["fixture"] = False
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "fixture_uuid_id_false", "fixture_provenance", m20b))

    # 20c. task fixture 字段缺失 — importer 应在 fixture_provenance 报
    #       task_fixture_missing
    def m20c(d, input_path):
        pack = _load(f"{d}/human_tasks_development.json")
        # Remove fixture from first task, keep hash unchanged
        for t in pack.get("tasks", []):
            if "fixture" in t:
                del t["fixture"]
                break
        _save(f"{d}/human_tasks_development.json", pack)
        # Write a clean annotation (with correct fixture=true) that
        # maps to the corrupted task.
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_fix3_task_fixture_missing"
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "task_fixture_missing", "fixture_provenance", m20c))

    # 20d. task fixture 为非 bool 类型（字符串 "yes"）
    def m20d(d, input_path):
        pack = _load(f"{d}/human_tasks_development.json")
        for t in pack.get("tasks", []):
            if "fixture" in t:
                t["fixture"] = "yes"
                break
        _save(f"{d}/human_tasks_development.json", pack)
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_fix3_task_fixture_str"
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "task_fixture_wrong_type", "fixture_provenance", m20d))

    # 20e. task pack 顶层 fixture 与逐条 task fixture 冲突
    def m20e(d, input_path):
        pack = _load(f"{d}/human_tasks_development.json")
        # Flip pack-level fixture but leave task fixture unchanged
        pack["fixture"] = False
        _save(f"{d}/human_tasks_development.json", pack)
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_fix3_pack_task_conflict"
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "pack_task_fixture_conflict", "fixture_provenance", m20e))

    # 20f. P13-2-2-1 fix-4: 整包 fixture 翻 false，保留旧 task hash
    #      → importer 独立重算 hash ≠ 存储 hash → dataset_identity false
    def m20f(d, input_path):
        pack = _load(f"{d}/human_tasks_development.json")
        pack["fixture"] = False
        for t in pack.get("tasks", []):
            t["fixture"] = False
        _save(f"{d}/human_tasks_development.json", pack)
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_fix4_full_pack_flip"
        ann["fixture"] = False
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "full_pack_fixture_flip_old_hash", "dataset_identity", m20f))

    # 20g. 任意改写 task.hash + annotation.task_hash 同步为同一错误值
    #      → 独立重算不匹配 → dataset_identity false
    def m20g(d, input_path):
        pack = _load(f"{d}/human_tasks_development.json")
        fake_hash = "b" * 64
        for t in pack.get("tasks", []):
            t["task_hash"] = fake_hash
            break
        _save(f"{d}/human_tasks_development.json", pack)
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_fix4_fake_hash"
        ann["task_hash"] = fake_hash
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "task_hash_rewritten_both_sides", "dataset_identity", m20g))

    # 20h. pack 顶层 fixture 缺失 → fixture_provenance false
    def m20h(d, input_path):
        pack = _load(f"{d}/human_tasks_development.json")
        del pack["fixture"]
        _save(f"{d}/human_tasks_development.json", pack)
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_fix4_pack_fixture_missing"
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "pack_fixture_missing", "fixture_provenance", m20h))

    # 20i. pack 顶层 fixture 为字符串 → fixture_provenance false
    def m20i(d, input_path):
        pack = _load(f"{d}/human_tasks_development.json")
        pack["fixture"] = "yes"
        _save(f"{d}/human_tasks_development.json", pack)
        anns = _load_fixture_anns(d)
        ann = dict(anns[0])
        ann["annotation_id"] = "ann_fix4_pack_fixture_str"
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        _save(input_path, {"annotations": [ann]})
    results.append(run_importer_mutation(
        "pack_fixture_wrong_type", "pack_trust", m20i))

    # ─── More validator mutations (22-26, was 21-25) ───

    # 21. A/B packs missing — validator should fail files_present equivalent
    def m21(d):
        Path(f"{d}/human_tasks_test_A.json").unlink(missing_ok=True)
        Path(f"{d}/human_tasks_test_B.json").unlink(missing_ok=True)
    results.append(run_validator_mutation(
        "ab_task_packs_missing", "task_pack_files_present", m21))

    # 22. 双标比例不足 — remove all B annotations
    def m22(d):
        store = _load_store(d)
        store["annotations"] = [
            entry for entry in store.get("annotations", [])
            if entry["annotation"]["annotator_slot"] != "B"
        ]
        _save_store(d, store)
    results.append(run_validator_mutation(
        "double_annotation_insufficient", "double_annotation_coverage", m22))

    # 23. A/B 全 true has_signals — degenerate kappa
    def m23(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["annotator_slot"] in ("A", "B"):
                ann["has_signals"] = True
                ann["fixture"] = False
                if not ann["signals"]:
                    ann["signals"] = [{
                        "signal_type": "feature_request",
                        "summary": "[degenerate kappa test] forced signal",
                        "evidence_spans": [{"start": 0, "end": 5,
                                            "text": "hello"[:5]}],
                        "implicit_need": None,
                        "implicit_need_has_basis": False,
                        "hallucination": False,
                        "notes": None,
                    }]
                    ann["signal_count"] = 1
        _save_store(d, store)
    results.append(run_validator_mutation(
        "all_true_degenerate_kappa", "kappa_non_degenerate", m23))

    # 24. A/B 全 false has_signals — degenerate kappa
    def m24(d):
        store = _load_store(d)
        for entry in store.get("annotations", []):
            ann = entry["annotation"]
            if ann["annotator_slot"] in ("A", "B"):
                ann["has_signals"] = False
                ann["signals"] = []
                ann["signal_count"] = 0
                ann["fixture"] = False
        _save_store(d, store)
    results.append(run_validator_mutation(
        "all_false_degenerate_kappa", "kappa_non_degenerate", m24))

    # ─── Readiness invariants (NOT counted as mutations) ───
    readiness_invariants = []
    readiness_invariants.append(_run_zero_candidate_invariant())

    # ─── Meta-negative invariants (NOT counted as mutations) ───
    # Prove the importer runner cannot be fooled by exit-code-only failures.
    meta_negatives = _run_importer_meta_negatives()

    # ─── Summary ───
    all_detected = all(r["detected"] for r in results)
    detected_count = sum(1 for r in results if r["detected"])

    all_invariants_ok = all(r["passed"] for r in readiness_invariants)
    all_meta_neg_ok = all(r["passed"] for r in meta_negatives)

    gate_passed = all_detected and all_invariants_ok and all_meta_neg_ok

    run_id = args.run_id or ""
    import signal_miner.evaluation.p13_2_gate_contract as gc  # noqa: E402
    my_exit = 0 if gate_passed else 1
    out_path = (Path(args.out) if args.out else
                PROJECT / "docs" / "P13-2-evidence" / "human-annotation-mutation-gate.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "annotation_mutation_gate",
        "contract_sha256": gc.CONTRACT_SHA256,
        "contract_schema_version": gc.CONTRACT_SCHEMA_VERSION,
        "exit_code": my_exit,
        "command": "annotation-mutation-gate",
        "passed": gate_passed,
        "total_mutations": len(results),
        "detected_count": detected_count,
        "results": results,
        "readiness_invariants": readiness_invariants,
        "readiness_invariants_passed": all_invariants_ok,
        "meta_negatives": meta_negatives,
        "meta_negatives_passed": all_meta_neg_ok,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return my_exit

    print(f"Annotation mutation gate: {'PASS' if gate_passed else 'FAIL'} "
          f"({detected_count}/{len(results)} mutations, "
          f"{sum(1 for r in readiness_invariants if r['passed'])}/"
          f"{len(readiness_invariants)} invariants, "
          f"{sum(1 for r in meta_negatives if r['passed'])}/"
          f"{len(meta_negatives)} meta-negatives)")
    if not all_detected:
        for r in results:
            if not r["detected"]:
                print(f"  MUTATION FAIL: {r['mutation']} (exit={r['child_exit']}, "
                      f"check_exists={r.get('check_exists')}, "
                      f"target_passed={r.get('target_passed')})")
    if not all_invariants_ok:
        for r in readiness_invariants:
            if not r["passed"]:
                print(f"  INVARIANT FAIL: {r['name']} (exit={r['child_exit']})")
    if not all_meta_neg_ok:
        for r in meta_negatives:
            if not r["passed"]:
                print(f"  META-NEG FAIL: {r['name']} "
                      f"(detected={r['actual_detected']})")
    return my_exit


if __name__ == "__main__":
    sys.exit(main())
