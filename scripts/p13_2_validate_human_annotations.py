#!/usr/bin/env python3
"""P13-2-2-1: Validate human annotations + compute inter-annotator agreement.

Reads:
  - the four human task packs (human_tasks_*.json)
  - the annotation store (human_annotations.json)
  - optional adjudication records

Independently recomputes EVERY check. NEVER trusts a stored "passed" flag.

Output: a metrics JSON with one entry per named check. The overall status is
READY only when ALL of the following hold:
  - annotation_count >= 100 (real annotations, not fixture)
  - test_blind_count >= 25
  - double_annotation_count >= max(20, ceil(n * 0.20))
  - has_signals kappa >= 0.70
  - all disagreements adjudicated
  - fixture/llm/rule/test-tagged annotation count toward real count == 0
  - calibration_allowed == false

Fixture annotations produce FIXTURE_PASS, never READY.

Exit codes:
  0 = fixture pass OR ready
  1 = validation failure (any check false)
  2 = BLOCKED waiting on real data — not a contract violation
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from pydantic import ValidationError  # noqa: E402

from signal_miner.evaluation.human_annotation import (  # noqa: E402
    STATUS_BLOCKED_GUIDELINE_REVISION,
    STATUS_BLOCKED_INSUFFICIENT_DOUBLE,
    STATUS_BLOCKED_PENDING_ADJUDICATION,
    STATUS_BLOCKED_WAITING_AUTHORIZED_DATA,
    STATUS_FIXTURE_PASS,
    STATUS_READY,
    HumanAnnotationV2,
    compute_agreement_metrics,
    required_double_count,
    validate_evidence_offsets,
    validate_signal_types,
)

# Identity patterns that MUST NOT appear in any annotation field (PII leak).
PII_PATTERNS = [
    # email
    __import__("re").compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    # CN mobile
    __import__("re").compile(r"1[3-9]\d{9}"),
]


def _check(name: str, passed: bool, **obs) -> dict:
    return {"name": name, "passed": passed, "observations": obs}


def _load_pack_tasks(task_dir: Path) -> dict[str, dict]:
    """Load all four packs into {sample_id: {slot: task_dict, ...}}."""
    out: dict[str, dict] = defaultdict(dict)
    pack_files = [
        task_dir / "human_tasks_development.json",
        task_dir / "human_tasks_calibration.json",
        task_dir / "human_tasks_test_A.json",
        task_dir / "human_tasks_test_B.json",
    ]
    for pf in pack_files:
        if not pf.exists():
            continue
        pack = json.loads(pf.read_text())
        for task in pack.get("tasks", []):
            out[task["sample_id"]][task["annotator_slot"]] = task
    return out


def _scan_pii(obj) -> list[str]:
    """Recursively find PII patterns in any string field. Returns hit descriptions.

    Skips hash/id-like fields (task_hash, content_hash, annotation_id, etc.)
    because their hex content can spuriously match the CN-mobile regex.
    """
    hits: list[str] = []
    skip_keys = {
        "task_hash", "content_hash", "content_hash_annotation",
        "annotation_id", "dataset_id", "sample_id",
        "annotator_pseudonym", "adjudicator_pseudonym",
        "adjudication_id",
    }

    def _scan(o, path: str = "$"):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in skip_keys:
                    continue
                _scan(v, f"{path}.{k}")
        elif isinstance(o, str):
            for pat in PII_PATTERNS:
                if pat.search(o):
                    hits.append(f"{path}: matches {pat.pattern[:30]}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _scan(v, f"{path}[{i}]")
    _scan(obj)
    return hits


def main() -> int:
    p = argparse.ArgumentParser(description="Validate human annotations")
    p.add_argument("--tasks", default="sample_data/p13_2/human_tasks")
    p.add_argument("--store", default="sample_data/p13_2/human_annotations.json")
    p.add_argument("--adjudications", default="",
                   help="Optional adjudication records JSON")
    p.add_argument("--stage-policy", default="docs/P13-2/stage-policy.json",
                   help="Frozen stage policy JSON (calibration_allowed must be false)")
    p.add_argument("--out", default="docs/P13-2-evidence/human-annotation-contract-metrics.json")
    args = p.parse_args()

    task_dir = Path(args.tasks)
    store_path = Path(args.store)
    adj_path = Path(args.adjudications) if args.adjudications else None
    stage_policy_path = Path(args.stage_policy)

    checks: list[dict] = []

    # --- Files present ---
    packs_exist = all(
        (task_dir / f).exists()
        for f in ("human_tasks_development.json", "human_tasks_calibration.json",
                  "human_tasks_test_A.json", "human_tasks_test_B.json")
    )
    store_exists = store_path.exists()

    # No store at all → genuinely waiting on authorized data + human work.
    # Missing task packs but store EXISTS → task_pack_files_present check will
    # fail below with exit 1 (contract violation, not BLOCKED).
    if not store_exists:
        result = {
            "status": STATUS_BLOCKED_WAITING_AUTHORIZED_DATA,
            "passed": False,
            "checks": {
                "files_present": {"passed": False,
                                  "observations": {"packs": packs_exist,
                                                   "store": store_exists}},
            },
            "fixture_only": True,
        }
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps({"status": result["status"], "passed": False}))
        return 2

    # Store exists — load and run full check suite regardless of pack presence.
    try:
        store_data = json.loads(store_path.read_text())
    except Exception as e:  # noqa: BLE001
        result = {
            "status": "FAIL_STORE_CORRUPT",
            "passed": False,
            "reason": str(e)[:200],
        }
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps({"status": result["status"], "passed": False}))
        return 1

    task_index = _load_pack_tasks(task_dir)

    # --- 0b. task_pack_files_present ---
    pack_names = ("human_tasks_development.json", "human_tasks_calibration.json",
                  "human_tasks_test_A.json", "human_tasks_test_B.json")
    missing_packs = [n for n in pack_names if not (task_dir / n).exists()]
    checks.append(_check("task_pack_files_present", len(missing_packs) == 0,
                         missing=missing_packs))

    # Store entries are {annotation: {...}, content_hash_annotation: "..."}.
    # Unwrap to the annotation dict for validation.
    raw_entries = store_data.get("annotations", [])
    raw_annotations = []
    for entry in raw_entries:
        if isinstance(entry, dict) and "annotation" in entry:
            raw_annotations.append(entry["annotation"])
        else:
            raw_annotations.append(entry)

    # --- 1. schema_strict ---
    parsed: list[HumanAnnotationV2] = []
    schema_errors: list[str] = []
    for raw in raw_annotations:
        try:
            parsed.append(HumanAnnotationV2(**raw))
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                schema_errors.append(f"{raw.get('annotation_id', '?')}.{loc}: {err['msg']}")
    checks.append(_check("schema_strict", len(schema_errors) == 0,
                         error_count=len(schema_errors), errors=schema_errors[:5]))

    # If schema failed, we can't reliably continue, but still emit partial.
    if schema_errors:
        result = {
            "status": "FAIL",
            "passed": False,
            "checks": {c["name"]: {"passed": c["passed"], "observations": c["observations"]}
                       for c in checks},
        }
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps({"status": "FAIL", "passed": False}))
        return 1

    # --- 2. task_identity (sample_id/dataset_id/task_hash/content_hash/slot/mode) ---
    identity_errors: list[str] = []
    for ann in parsed:
        slot_map = task_index.get(ann.sample_id, {})
        task = slot_map.get(ann.annotator_slot)
        if task is None:
            identity_errors.append(
                f"task_not_found: {ann.annotation_id} sample={ann.sample_id} slot={ann.annotator_slot}")
            continue
        if ann.dataset_id != task["dataset_id"]:
            identity_errors.append(f"dataset_id_mismatch: {ann.annotation_id}")
        if ann.task_hash != task["task_hash"]:
            identity_errors.append(f"task_hash_mismatch: {ann.annotation_id}")
        if ann.content_hash != task["content_hash"]:
            identity_errors.append(f"content_hash_mismatch: {ann.annotation_id}")
        if ann.annotation_mode != task["annotation_mode"]:
            identity_errors.append(f"mode_mismatch: {ann.annotation_id}")
    checks.append(_check("task_identity", len(identity_errors) == 0,
                         error_count=len(identity_errors), errors=identity_errors[:5]))

    # --- 3. signal_count_consistency ---
    count_errors = [a.annotation_id for a in parsed if a.signal_count != len(a.signals)]
    checks.append(_check("signal_count_consistency", len(count_errors) == 0,
                         mismatches=count_errors[:5]))

    # --- 4. has_signals_consistency ---
    hs_errors: list[str] = []
    for a in parsed:
        if not a.has_signals and a.signals:
            hs_errors.append(f"{a.annotation_id}: has_signals_false_but_signals_nonempty")
        if a.has_signals and not a.signals:
            hs_errors.append(f"{a.annotation_id}: has_signals_true_but_signals_empty")
    checks.append(_check("has_signals_consistency", len(hs_errors) == 0,
                         errors=hs_errors[:5]))

    # --- 5. evidence_offsets (Unicode safe) ---
    ev_errors: list[str] = []
    for a in parsed:
        task = task_index.get(a.sample_id, {}).get(a.annotator_slot)
        redacted = task.get("redacted_text", "") if task else ""
        if redacted:
            errs = validate_evidence_offsets(redacted, a.signals)
            ev_errors.extend(f"{a.annotation_id}: {e}" for e in errs)
    checks.append(_check("evidence_offsets", len(ev_errors) == 0,
                         error_count=len(ev_errors), errors=ev_errors[:5]))

    # --- 6. summary_and_evidence_nonempty (also catches empty signal_type) ---
    se_errors: list[str] = []
    for a in parsed:
        for i, sig in enumerate(a.signals):
            if not sig.summary or not sig.summary.strip():
                se_errors.append(f"{a.annotation_id}.signal[{i}]: summary_empty")
            if not sig.evidence_spans:
                se_errors.append(f"{a.annotation_id}.signal[{i}]: evidence_empty")
            if not sig.signal_type or not sig.signal_type.strip():
                se_errors.append(f"{a.annotation_id}.signal[{i}]: signal_type_empty")
    checks.append(_check("summary_and_evidence_nonempty", len(se_errors) == 0,
                         error_count=len(se_errors), errors=se_errors[:5]))

    # --- 7. signal_type_whitelist ---
    st_errors: list[str] = []
    for a in parsed:
        task = task_index.get(a.sample_id, {}).get(a.annotator_slot)
        profile = task.get("profile", "") if task else ""
        if profile:
            errs = validate_signal_types(a.signals, profile)
            st_errors.extend(f"{a.annotation_id}: {e}" for e in errs)
    checks.append(_check("signal_type_whitelist", len(st_errors) == 0,
                         error_count=len(st_errors), errors=st_errors[:5]))

    # --- 8. no_self_pairing ---
    pair_map: dict[tuple[str, str], set[str]] = defaultdict(set)
    for a in parsed:
        pair_map[(a.sample_id, a.annotator_pseudonym)].add(a.annotator_slot)
    self_pairs = [f"sample={s} pseudonym={p} slots={sorted(sl)}"
                  for (s, p), sl in pair_map.items() if {"A", "B"}.issubset(sl)]
    checks.append(_check("no_self_pairing", len(self_pairs) == 0,
                         conflicts=self_pairs[:5]))

    # --- 9. assisted_review_action ---
    ar_errors = [a.annotation_id for a in parsed
                 if a.annotation_mode == "assisted_review" and a.review_action is None]
    checks.append(_check("assisted_review_action", len(ar_errors) == 0,
                         missing=ar_errors[:5]))

    # --- 10. no_pii_leak ---
    pii_hits: list[str] = []
    for a in parsed:
        hits = _scan_pii(a.model_dump())
        pii_hits.extend(f"{a.annotation_id}: {h}" for h in hits)
    checks.append(_check("no_pii_leak", len(pii_hits) == 0,
                         hit_count=len(pii_hits), hits=pii_hits[:5]))

    # --- 11. no_blind_leakage_in_tasks (test A/B packs must not carry model/score) ---
    blind_leak = 0
    for pack_file in ("human_tasks_test_A.json", "human_tasks_test_B.json"):
        pf = task_dir / pack_file
        if not pf.exists():
            continue
        pack = json.loads(pf.read_text())
        for task in pack.get("tasks", []):
            if task.get("suggestion") is not None:
                blind_leak += 1
            for forbidden in ("model", "provider", "prompt", "confidence", "score",
                              "prediction", "suggested_signals"):
                if forbidden in task:
                    blind_leak += 1
    checks.append(_check("no_blind_leakage_in_tasks", blind_leak == 0,
                         leak_count=blind_leak))

    # --- 12. real_vs_fixture_count ---
    fixture_count = sum(1 for a in parsed if a.fixture)
    real_count = sum(1 for a in parsed if not a.fixture)
    # Anything tagged as test/mock/sample/fixture in annotation_id does NOT
    # count as real — this catches fixture annotations that were flipped to
    # fixture=false to impersonate real gold.
    suspicious_real = [
        a.annotation_id for a in parsed
        if not a.fixture and any(
            t in a.annotation_id.lower()
            for t in ("test", "mock", "fixture", "sample", "fixann", "demo", "fake")
        )
    ]
    real_count_honest = real_count - len(suspicious_real)
    checks.append(_check("real_vs_fixture_count",
                         len(suspicious_real) == 0,
                         real_count=real_count,
                         real_count_honest=real_count_honest,
                         fixture_count=fixture_count,
                         suspicious_real_ids=suspicious_real[:5]))

    # --- 13. human_verified_count (real annotations, de-duplicated by sample) ---
    real_samples = {a.sample_id for a in parsed if not a.fixture}
    human_verified_count = len(real_samples)
    checks.append(_check("human_verified_count_de-duped",
                         True,  # informational; readiness enforced in 14
                         human_verified_count=human_verified_count))

    # --- 13b. double_annotation_coverage ---
    # Independently of real/fixture, check that double-annotated samples from
    # the manifest actually have BOTH an A and a B annotation in the store.
    manifest_path = Path("sample_data/p13_2/manifest.json")
    declared_double: set[str] = set()
    if manifest_path.exists():
        try:
            mfst = json.loads(manifest_path.read_text())
            declared_double = set(mfst.get("double_annotation_ids", []))
        except Exception:  # noqa: BLE001
            pass
    slot_by_sample_all: dict[str, set[str]] = defaultdict(set)
    for a in parsed:
        if a.annotator_slot in ("A", "B"):
            slot_by_sample_all[a.sample_id].add(a.annotator_slot)
    missing_double = sorted(
        sid for sid in declared_double
        if not {"A", "B"}.issubset(slot_by_sample_all.get(sid, set()))
    )
    checks.append(_check("double_annotation_coverage",
                         len(missing_double) == 0,
                         declared=len(declared_double),
                         missing_both_slots=len(missing_double),
                         missing_samples=missing_double[:5]))

    # --- 14. readiness_thresholds ---
    # Fixture-only runs cannot meet real-data thresholds and that is EXPECTED.
    # The check is reported as informational (passed=true) when fixture_only.
    test_blind_real = sum(1 for a in parsed
                          if not a.fixture and a.annotation_mode == "blind")
    # Double annotation: samples with both an A and a B annotation (real only)
    slot_by_sample: dict[str, set[str]] = defaultdict(set)
    for a in parsed:
        if not a.fixture and a.annotator_slot in ("A", "B"):
            slot_by_sample[a.sample_id].add(a.annotator_slot)
    double_annotated = [s for s, sl in slot_by_sample.items() if {"A", "B"}.issubset(sl)]
    double_count = len(double_annotated)

    min_real = 100
    min_blind = 25
    min_double = required_double_count(max(real_count, 1))

    real_ok = real_count >= min_real
    blind_ok = test_blind_real >= min_blind
    double_ok = double_count >= min_double

    # kappa only meaningful when there are pairs
    pairs = []
    by_pair_key: dict[tuple[str, str], HumanAnnotationV2] = {}
    for a in parsed:
        if not a.fixture and a.annotator_slot in ("A", "B"):
            by_pair_key[(a.sample_id, a.annotator_slot)] = a
    sample_ids_both = sorted({s for s, sl in slot_by_sample.items() if {"A", "B"}.issubset(sl)})
    for sid in sample_ids_both:
        a_ann = by_pair_key.get((sid, "A"))
        b_ann = by_pair_key.get((sid, "B"))
        if a_ann and b_ann:
            pairs.append((a_ann, b_ann))

    agreement = compute_agreement_metrics(pairs)
    kappa = agreement["has_signals_kappa"]
    kappa_degenerate = agreement.get("kappa_degenerate", False)
    # Degenerate kappa (all-true or all-false labels) is NOT acceptable
    # evidence of agreement — it means the annotators never exercised both
    # classes. Treat it as a hard blocker.
    kappa_ok = bool(pairs) and (not kappa_degenerate) and kappa >= 0.70

    readiness_ok = real_ok and blind_ok and double_ok and kappa_ok
    # When the run is fixture-only (no real annotations), readiness_thresholds
    # is informational — it MUST pass so the fixture toolchain reports PASS.
    fixture_only_run = (fixture_count > 0 and real_count == 0)
    checks.append(_check("readiness_thresholds",
                         readiness_ok or fixture_only_run,
                         real_count=real_count, min_real=min_real,
                         test_blind_real=test_blind_real, min_blind=min_blind,
                         double_count=double_count, min_double=min_double,
                         kappa=kappa, kappa_threshold=0.70,
                         fixture_only_run=fixture_only_run))

    # --- 14b. kappa_non_degenerate ---
    # Degenerate kappa (all-true or all-false has_signals labels) means the
    # metric is uncomputable. This is a HARD contract violation even for
    # fixture runs — it proves the annotation set has zero class variation.
    # Only applies when there ARE pairs; zero pairs → check passes (vacuous).
    kappa_nondegen_ok = (not kappa_degenerate) if pairs else True
    checks.append(_check("kappa_non_degenerate", kappa_nondegen_ok,
                         kappa=kappa, degenerate=kappa_degenerate,
                         pair_count=len(pairs)))

    # --- 15. disagreements_adjudicated ---
    disagreement_samples = agreement["disagreement_sample_count"]
    adj_ids: set[str] = set()
    if adj_path and adj_path.exists():
        adj_data = json.loads(adj_path.read_text())
        for rec in adj_data.get("adjudications", []):
            adj_ids.add(rec.get("sample_id", ""))
    unadjudicated = [s for s in sample_ids_both
                     if any(f in {"has_signals", "signal_count", "signal_type_set"}
                            for f in _disagree_fields(by_pair_key, s))
                     and s not in adj_ids] if pairs else []
    checks.append(_check("disagreements_adjudicated",
                         disagreement_samples == 0 or len(unadjudicated) == 0,
                         disagreement_samples=disagreement_samples,
                         unadjudicated=len(unadjudicated)))

    # --- 16. calibration_not_allowed (reads frozen stage policy, NOT a constant) ---
    # The stage policy file is the single source of truth. If it is missing,
    # corrupt, has the wrong type, or says calibration_allowed=true, this check
    # fails. This is NOT a hardcoded false — the mutation gate mutates the file
    # to verify the validator actually reads it.
    cal_errors: list[str] = []
    if not stage_policy_path.exists():
        cal_errors.append("stage_policy_file_missing")
    else:
        try:
            policy = json.loads(stage_policy_path.read_text())
        except Exception as e:  # noqa: BLE001
            cal_errors.append(f"stage_policy_corrupt: {str(e)[:100]}")
            policy = {}
        if isinstance(policy, dict):
            val = policy.get("calibration_allowed")
            if val is None:
                cal_errors.append("calibration_allowed_key_missing")
            elif not isinstance(val, bool):
                cal_errors.append(f"calibration_allowed_wrong_type: {type(val).__name__}")
            elif val is True:
                cal_errors.append("calibration_allowed_is_true")
        else:
            cal_errors.append("stage_policy_not_a_dict")
    checks.append(_check("calibration_not_allowed", len(cal_errors) == 0,
                         errors=cal_errors, policy_path=str(stage_policy_path)))

    # --- Determine status ---
    all_passed = all(c["passed"] for c in checks)

    if not all_passed:
        status = "FAIL"
    elif fixture_count > 0 and real_count == 0:
        # Fixture-only run — tools work but no real gold yet
        status = STATUS_FIXTURE_PASS
    elif not readiness_ok:
        # One of the thresholds not met → pick the most specific blocker
        if not double_ok:
            status = STATUS_BLOCKED_INSUFFICIENT_DOUBLE
        elif not kappa_ok:
            status = STATUS_BLOCKED_GUIDELINE_REVISION
        elif unadjudicated:
            status = STATUS_BLOCKED_PENDING_ADJUDICATION
        else:
            status = STATUS_BLOCKED_WAITING_AUTHORIZED_DATA
    else:
        status = STATUS_READY

    result = {
        "status": status,
        "passed": all_passed and status in (STATUS_READY, STATUS_FIXTURE_PASS),
        "checks": {c["name"]: {"passed": c["passed"], "observations": c["observations"]}
                   for c in checks},
        "annotation_count": len(parsed),
        "real_count": real_count,
        "fixture_count": fixture_count,
        "test_blind_real": test_blind_real,
        "double_annotation_count": double_count,
        "human_verified_count": human_verified_count,
        "human_labels_complete": status == STATUS_READY,
        "calibration_allowed": False,
        "agreement": agreement,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps({"status": status, "passed": result["passed"]}))
    return 0 if result["passed"] else (2 if status.startswith("BLOCKED") else 1)


def _disagree_fields(by_pair_key: dict, sample_id: str) -> list[str]:
    """Helper: return disagree fields for a sample's A/B pair."""
    from signal_miner.evaluation.human_annotation import compute_pair_agreement

    a = by_pair_key.get((sample_id, "A"))
    b = by_pair_key.get((sample_id, "B"))
    if not a or not b:
        return []
    return compute_pair_agreement(a, b)["disagree_fields"]


if __name__ == "__main__":
    sys.exit(main())
