#!/usr/bin/env python3
"""P13-2-1 fix-3: Independent validator — production whitelist, pack field consistency.

Reads: candidates, manifest, dev/cal/test packs, preannotations, guideline.
All checks independently recomputed. NEVER trusts manifest.passed.

Key fix-3 additions:
- suggestion_signal_types: validates against production get_profile().signal_types
- source_platform_contract: non-empty per-candidate check
- pack_contract: per-field consistency with candidate canonical map
- suggestion_contract: fixture flag, model name, label status
- manifest_hash_valid: compares capture_method_distribution
- blind_pack_leakage: enhanced field scan (model/provider/prompt/score)
"""

from __future__ import annotations

from collections import Counter
import contextlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from signal_miner.evaluation import (  # noqa: E402
    AUTHORIZED_BASES,
    PROFILES,
    SCHEMA_VERSION,
    EvidenceSpan,
    FrozenManifest,
    GoldRecord,
    check_blind_pack_leakage,
    compute_ordered_hash,
    has_sensitive,
    sha256,
    validate_evidence,
)
from signal_miner.pipeline.pipeline_profile import get_profile  # noqa: E402

# Fields that must match exactly between candidate and pack samples
CANONICAL_FIELDS = [
    "schema_version", "sample_id", "raw_feedback_id", "profile",
    "source_platform", "capture_method", "authorization_basis",
    "content_hash", "redacted_text", "redaction_applied",
    "language", "hard_case_tags", "split", "split_seed",
    "annotation_mode", "annotation_status",
]


def _check(name: str, passed: bool, **obs) -> dict:
    return {"name": name, "passed": passed, "observations": obs}


def _build_canonical_map(samples: list[GoldRecord]) -> dict[str, dict]:
    """Build canonical field map from candidate samples."""
    return {s.sample_id: {f: getattr(s, f) for f in CANONICAL_FIELDS} for s in samples}


def _verify_pack_samples(pack_samples: list[dict], canonical: dict[str, dict],
                         expected_slot: str | None = None) -> list[str]:
    """Verify each pack sample matches candidate canonical fields.

    Args:
        pack_samples: list of sample dicts from a pack
        canonical: sample_id -> canonical field dict
        expected_slot: if set, annotator_slot must be exactly this value

    Returns: list of error strings
    """
    errors = []
    for ps in pack_samples:
        sid = ps.get("sample_id", "")
        canon = canonical.get(sid)
        if not canon:
            errors.append(f"unknown_sample_in_pack: {sid}")
            continue
        # Check annotator_slot
        if expected_slot is not None:
            actual_slot = ps.get("annotator_slot", "")
            if actual_slot != expected_slot:
                errors.append(f"slot_mismatch: {sid} expected={expected_slot} actual={actual_slot}")
        # Check all canonical fields
        for field in CANONICAL_FIELDS:
            if field == "annotator_slot":
                continue  # slot is allowed to differ
            expected_val = canon[field]
            actual_val = ps.get(field)
            if actual_val != expected_val:
                errors.append(
                    f"field_mismatch: {sid}.{field} "
                    f"expected={str(expected_val)[:30]} actual={str(actual_val)[:30]}"
                )
    return errors


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Validate P13-2 gold-set")
    p.add_argument("--candidates", default="sample_data/p13_2/positive/candidates.json")
    p.add_argument("--manifest", default="sample_data/p13_2/manifest.json")
    p.add_argument("--preannotations", default="sample_data/p13_2/positive/preannotations.json")
    p.add_argument("--test-pack-a", default="sample_data/p13_2/positive/annotation_pack_test_A.json")
    p.add_argument("--test-pack-b", default="sample_data/p13_2/positive/annotation_pack_test_B.json")
    p.add_argument("--dev-pack", default="sample_data/p13_2/positive/annotation_pack_development.json")
    p.add_argument("--cal-pack", default="sample_data/p13_2/positive/annotation_pack_calibration.json")
    p.add_argument("--guideline", default="docs/P13-2/annotation-guideline-v1.md")
    p.add_argument("--out", default="docs/P13-2-evidence/goldset-contract-metrics.json")
    args = p.parse_args()

    cp = Path(args.candidates)
    mp = Path(args.manifest)
    pp = Path(args.preannotations)
    pa = Path(args.test_pack_a)
    pb = Path(args.test_pack_b)
    pd = Path(args.dev_pack)
    pc = Path(args.cal_pack)
    gp = Path(args.guideline)

    required_files = {
        "candidates": cp, "manifest": mp, "preannotations": pp,
        "test_pack_a": pa, "test_pack_b": pb,
        "dev_pack": pd, "cal_pack": pc, "guideline": gp,
    }
    missing = {k: str(v) for k, v in required_files.items() if not v.exists()}

    def _emit(checks, status, passed):
        result = {
            "status": status,
            "passed": passed,
            "checks": {c["name"]: {"passed": c["passed"], "observations": c["observations"]} for c in checks},
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps({"status": result["status"], "passed": result["passed"]}))
        return 0 if passed else 1

    if missing:
        checks = [_check("files_exist", False, missing=missing)]
        return _emit(checks, "FAIL", False)

    samples_raw = json.loads(cp.read_text())
    if isinstance(samples_raw, dict) and samples_raw.get("status", "").startswith("BLOCKED"):
        checks = [_check("files_exist", False, reason="candidates BLOCKED")]
        return _emit(checks, samples_raw["status"], False)

    try:
        samples = [GoldRecord(**s) for s in samples_raw]
    except Exception as e:
        checks = [_check("schema_validation", False, error=str(e)[:200])]
        return _emit(checks, "FAIL", False)

    try:
        manifest = FrozenManifest(**json.loads(mp.read_text()))
    except Exception as e:
        checks = [_check("schema_validation", False, error=f"manifest: {str(e)[:200]}")]
        return _emit(checks, "FAIL", False)

    n = len(samples)
    checks: list[dict] = []

    # --- 1. schema_validation ---
    schema_ok = (all(s.schema_version == SCHEMA_VERSION for s in samples) and
                 manifest.schema_version == SCHEMA_VERSION)
    checks.append(_check("schema_validation", schema_ok, expected=SCHEMA_VERSION))

    # --- 2. files_exist ---
    checks.append(_check("files_exist", True, count=len(required_files)))

    # --- 3. sample_count ---
    checks.append(_check("sample_count", n >= 100, count=n))

    # --- 4. profile_minimum ---
    profile_dist = dict(Counter(s.profile for s in samples))
    invalid_profiles = [p for p in profile_dist if p not in PROFILES]
    pf_ok = (all(profile_dist.get(p, 0) >= 30 for p in PROFILES) and
             len(invalid_profiles) == 0)
    checks.append(_check("profile_minimum", pf_ok, distribution=profile_dist))

    # --- 5. source_balance ---
    source_dist = dict(Counter(s.source_platform for s in samples))
    max_pct = max(source_dist.values()) / n if n else 0
    src_ok = max_pct <= 0.60
    checks.append(_check("source_balance", src_ok, max_pct=round(max_pct, 4)))

    # --- 5b. source_platform_contract — non-empty per candidate ---
    empty_sources = [s.sample_id for s in samples if not s.source_platform or not s.source_platform.strip()]
    checks.append(_check("source_platform_contract", len(empty_sources) == 0,
                         empty_count=len(empty_sources), samples=empty_sources[:5]))

    # --- 6. capture_method_contract ---
    capture_dist = dict(Counter(s.capture_method for s in samples))
    cm_ok = all(cm in ("api", "manual", "import", "crawl") for cm in capture_dist)
    checks.append(_check("capture_method_contract", cm_ok, distribution=capture_dist))

    # --- 7. splits_valid ---
    splits: dict[str, list[str]] = {"development": [], "calibration": [], "test": []}
    for s in samples:
        splits[s.split].append(s.sample_id)
    split_ok = (len(splits["development"]) == 50 and
                len(splits["calibration"]) == 25 and
                len(splits["test"]) == 25)
    checks.append(_check("splits_valid", split_ok,
                         split_counts={k: len(v) for k, v in splits.items()}))

    # --- 8. annotation_modes ---
    mode_by_split = {}
    for s in samples:
        mode_by_split.setdefault(s.split, set()).add(s.annotation_mode)
    modes_ok = (
        mode_by_split.get("test") == {"blind"} and
        mode_by_split.get("development") == {"assisted_review"} and
        mode_by_split.get("calibration") == {"assisted_review"}
    )
    checks.append(_check("annotation_modes", modes_ok, modes={k: sorted(v) for k, v in mode_by_split.items()}))

    # --- 9. authorization ---
    auth_missing = [s.sample_id for s in samples if s.authorization_basis not in AUTHORIZED_BASES]
    checks.append(_check("authorization", len(auth_missing) == 0, missing_count=len(auth_missing)))

    # --- 10. no_test_records ---
    test_tagged = [s.sample_id for s in samples if any(
        t in (s.sample_id + (s.raw_feedback_id or "")).lower()
        for t in ("test", "mock", "fixture", "sample")
    )]
    checks.append(_check("no_test_records", len(test_tagged) == 0, count=len(test_tagged)))

    # --- 11. sensitive_content — has_sensitive alone fails ---
    sens_found = [s.sample_id for s in samples if has_sensitive(s.redacted_text)]
    checks.append(_check("sensitive_content", len(sens_found) == 0, count=len(sens_found)))

    # --- 12. no_cross_split_leak ---
    seen_hashes: dict[str, str] = {}
    cross_leak = 0
    for s in samples:
        if s.content_hash in seen_hashes and seen_hashes[s.content_hash] != s.split:
            cross_leak += 1
        seen_hashes[s.content_hash] = s.split
    checks.append(_check("no_cross_split_leak", cross_leak == 0, count=cross_leak))

    # --- 13. double_annotation ---
    double_ids = manifest.double_annotation_ids
    double_count = len(double_ids)
    min_double = max(20, int(n * 0.2 + 0.999))
    double_ids_set = set(double_ids)
    all_ids = {s.sample_id for s in samples}
    double_exists = double_ids_set.issubset(all_ids)
    double_unique = len(double_ids_set) == len(double_ids)
    double_ratio_ok = abs(manifest.double_annotation_ratio - (double_count / n if n else 0)) < 1e-9
    double_ok = double_count >= min_double and double_exists and double_unique and double_ratio_ok
    checks.append(_check("double_annotation", double_ok,
                         count=double_count, required=min_double,
                         all_exist=double_exists, all_unique=double_unique,
                         ratio_consistent=double_ratio_ok))

    # --- 14. pack_contract — per-field consistency with canonical map ---
    canonical = _build_canonical_map(samples)
    pack_errors = []
    with contextlib.suppress(Exception):
        a_pack = json.loads(pa.read_text())
        b_pack = json.loads(pb.read_text())
        dev_pack = json.loads(pd.read_text())
        cal_pack = json.loads(pc.read_text())
    try:
        a_pack = json.loads(pa.read_text())
        b_pack = json.loads(pb.read_text())
        dev_pack = json.loads(pd.read_text())
        cal_pack = json.loads(pc.read_text())
    except Exception as e:
        pack_errors.append(f"pack_parse_error: {e}")
        a_pack = b_pack = dev_pack = cal_pack = {}

    if a_pack:
        if a_pack.get("annotator_slot") != "A":
            pack_errors.append("A_pack_header_slot_not_A")
        a_ids = {s["sample_id"] for s in a_pack.get("samples", [])}
        if a_ids != set(splits["test"]):
            pack_errors.append("A_pack_sample_set_mismatch")
        pack_errors.extend(_verify_pack_samples(a_pack.get("samples", []), canonical, expected_slot="A"))

    if b_pack:
        if b_pack.get("annotator_slot") != "B":
            pack_errors.append("B_pack_header_slot_not_B")
        b_ids = {s["sample_id"] for s in b_pack.get("samples", [])}
        expected_b = set(double_ids) & set(splits["test"])
        if b_ids != expected_b:
            pack_errors.append("B_pack_sample_set_mismatch")
        pack_errors.extend(_verify_pack_samples(b_pack.get("samples", []), canonical, expected_slot="B"))

    if dev_pack:
        dev_ids = {s["sample_id"] for s in dev_pack.get("samples", [])}
        if dev_ids != set(splits["development"]):
            pack_errors.append("dev_pack_set_mismatch")
        if dev_pack.get("annotation_mode") != "assisted_review":
            pack_errors.append("dev_pack_wrong_mode")
        pack_errors.extend(_verify_pack_samples(dev_pack.get("samples", []), canonical, expected_slot=None))
        dev_leak = check_blind_pack_leakage(dev_pack)
        if dev_leak > 0:
            pack_errors.append(f"dev_pack_has_leak_fields: {dev_leak}")

    if cal_pack:
        cal_ids = {s["sample_id"] for s in cal_pack.get("samples", [])}
        if cal_ids != set(splits["calibration"]):
            pack_errors.append("cal_pack_set_mismatch")
        if cal_pack.get("annotation_mode") != "assisted_review":
            pack_errors.append("cal_pack_wrong_mode")
        pack_errors.extend(_verify_pack_samples(cal_pack.get("samples", []), canonical, expected_slot=None))
        cal_leak = check_blind_pack_leakage(cal_pack)
        if cal_leak > 0:
            pack_errors.append(f"cal_pack_has_leak_fields: {cal_leak}")

    checks.append(_check("pack_contract", len(pack_errors) == 0, errors=pack_errors[:10]))

    # --- 15. blind_pack_leakage ---
    blind_leak = 0
    for pack in [a_pack, b_pack]:
        if pack:
            blind_leak += check_blind_pack_leakage(pack)
    checks.append(_check("blind_pack_leakage", blind_leak == 0, count=blind_leak))

    # --- 16. suggestion_contract + fixture/live isolation ---
    preann_data = {}
    with contextlib.suppress(Exception):
        preann_data = json.loads(pp.read_text())
    test_ids_set = set(splits["test"])
    dev_cal_ids_set = set(splits["development"]) | set(splits["calibration"])
    sug_errors = []

    # Check fixture flag consistency
    top_fixture = preann_data.get("fixture_only", None)
    for sg in preann_data.get("suggestions", []):
        sid_raw = sg.get("suggestion_id", "")
        sid = sid_raw.replace("sg_", "") if sid_raw.startswith("sg_") else sid_raw
        if sid in test_ids_set:
            sug_errors.append(f"suggestion_references_test: {sid}")
        elif sid not in dev_cal_ids_set:
            sug_errors.append(f"suggestion_unknown_sample: {sid}")

        # Fixture/live isolation
        sg_fixture = sg.get("fixture_only", None)
        sg_model = sg.get("suggestion_model", "")
        sg_label = sg.get("label_status", "")
        sg_human = sg.get("counts_as_human_verified", None)

        # Fixture/live isolation: model name, version and fixture flag must be consistent
        sg_version = sg.get("suggestion_model_version", "")
        sg_prompt_ver = sg.get("suggestion_prompt_version", "")
        if sg_fixture is True and sg_model != "fixture":
            sug_errors.append(f"fixture_flag_true_but_model_not_fixture: {sid} model={sg_model}")
        if sg_fixture is False and sg_model == "fixture":
            sug_errors.append(f"fixture_flag_false_but_model_is_fixture: {sid}")
        # Detect fixture artifacts disguised as live (version/prompt still say fixture)
        if "fixture" in sg_version.lower() and sg_model != "fixture":
            sug_errors.append(f"fixture_version_but_non_fixture_model: {sid} model={sg_model}")
        if "fixture" in sg_prompt_ver.lower() and sg_model != "fixture":
            sug_errors.append(f"fixture_prompt_but_non_fixture_model: {sid} model={sg_model}")
        if top_fixture is True:
            if sg_fixture is not True:
                sug_errors.append(f"suggestion_not_fixture: {sid}")
            if sg_model != "fixture":
                sug_errors.append(f"suggestion_model_not_fixture: {sid} model={sg_model}")
        if top_fixture is False:
            # Live mode: must not have fixture model, must have real provider
            if sg_model == "fixture":
                sug_errors.append(f"live_mode_has_fixture_model: {sid}")
            if not sg_model or sg_model == "":
                sug_errors.append(f"live_mode_empty_model: {sid}")
        if sg_label != "suggestion_only":
            sug_errors.append(f"label_status_not_suggestion_only: {sid}")
        if sg_human is not False:
            sug_errors.append(f"counts_as_human_verified_not_false: {sid}")

    dev_suggestion_count = sum(1 for sg in preann_data.get("suggestions", [])
                               if (sg.get("suggestion_id", "").replace("sg_", "")
                                   if sg.get("suggestion_id", "").startswith("sg_")
                                   else sg.get("suggestion_id", "")) in set(splits["development"]))
    cal_suggestion_count = sum(1 for sg in preann_data.get("suggestions", [])
                               if (sg.get("suggestion_id", "").replace("sg_", "")
                                   if sg.get("suggestion_id", "").startswith("sg_")
                                   else sg.get("suggestion_id", "")) in set(splits["calibration"]))
    if dev_suggestion_count != len(splits["development"]):
        sug_errors.append(f"dev_suggestion_count={dev_suggestion_count}_expected={len(splits['development'])}")
    if cal_suggestion_count != len(splits["calibration"]):
        sug_errors.append(f"cal_suggestion_count={cal_suggestion_count}_expected={len(splits['calibration'])}")

    checks.append(_check("suggestion_contract", len(sug_errors) == 0,
                         errors=sug_errors[:10],
                         dev_count=dev_suggestion_count, cal_count=cal_suggestion_count))

    # --- 16b. suggestion_signal_types — production whitelist ---
    sig_type_errors = []
    sample_profile_map = {s.sample_id: s.profile for s in samples}
    for sg in preann_data.get("suggestions", []):
        sid_raw = sg.get("suggestion_id", "")
        sid = sid_raw.replace("sg_", "") if sid_raw.startswith("sg_") else sid_raw
        profile = sample_profile_map.get(sid, "")
        if not profile:
            continue
        try:
            allowed = get_profile(profile).signal_types
        except KeyError:
            allowed = []
        for sig in sg.get("suggested_signals", []):
            stype = sig.get("signal_type", "")
            if stype not in allowed:
                sig_type_errors.append(f"invalid_signal_type: {sid} type={stype} profile={profile}")
    checks.append(_check("suggestion_signal_types", len(sig_type_errors) == 0,
                         errors=sig_type_errors[:10]))

    # --- 17. evidence_offsets ---
    offset_mismatches = 0
    sample_map = {s.sample_id: s for s in samples}
    for sg in preann_data.get("suggestions", []):
        sid_raw = sg.get("suggestion_id", "")
        sid = sid_raw.replace("sg_", "") if sid_raw.startswith("sg_") else sid_raw
        s = sample_map.get(sid)
        if s and s.split != "test":
            for sig in sg.get("suggested_signals", []):
                for span_dict in sig.get("evidence_spans", []):
                    try:
                        span = EvidenceSpan(**span_dict)
                        mismatches = validate_evidence(s.redacted_text, [span])
                        offset_mismatches += len(mismatches)
                    except Exception:
                        offset_mismatches += 1
    checks.append(_check("evidence_offsets", offset_mismatches == 0, mismatch_count=offset_mismatches))

    # --- 18. manifest_hash_valid — includes capture_method_distribution ---
    recomputed_ordered_hash = compute_ordered_hash(samples)
    guideline_hash = sha256(gp.read_text()) if gp.exists() else ""
    recomputed_selection_fp = sha256(json.dumps({
        "ids": sorted(s.raw_feedback_id for s in samples),
        "hashes": sorted(s.content_hash for s in samples),
        "seed": manifest.seed,
        "schema": SCHEMA_VERSION,
        "rules": "p13_2_1_fix3",
    }, sort_keys=True))
    recomputed_dataset_id = sha256(recomputed_ordered_hash)[:16]

    with contextlib.suppress(Exception):
        a_pack_raw = json.loads(pa.read_text())
        b_pack_raw = json.loads(pb.read_text())
        blind_combined = json.dumps({"A": a_pack_raw, "B": b_pack_raw}, sort_keys=True, ensure_ascii=False)
        recomputed_blind_hash = sha256(blind_combined)
    try:
        a_pack_raw = json.loads(pa.read_text())
        b_pack_raw = json.loads(pb.read_text())
        blind_combined = json.dumps({"A": a_pack_raw, "B": b_pack_raw}, sort_keys=True, ensure_ascii=False)
        recomputed_blind_hash = sha256(blind_combined)
    except Exception:
        recomputed_blind_hash = ""

    manifest_hash_ok = (
        recomputed_ordered_hash == manifest.ordered_samples_hash and
        guideline_hash == manifest.guideline_hash and
        recomputed_selection_fp == manifest.selection_query_fingerprint and
        manifest.content_hash_list == [s.content_hash for s in samples] and
        manifest.sample_count == n and
        manifest.double_annotation_count == double_count and
        manifest.profile_distribution == profile_dist and
        manifest.source_distribution == source_dist and
        manifest.capture_method_distribution == capture_dist and
        manifest.splits == splits and
        recomputed_blind_hash == manifest.blind_pack_hash
    )
    checks.append(_check("manifest_hash_valid", manifest_hash_ok,
                         ordered_ok=(recomputed_ordered_hash == manifest.ordered_samples_hash),
                         blind_hash_ok=(recomputed_blind_hash == manifest.blind_pack_hash)))

    # --- 19. manifest_identity ---
    identity_ok = (recomputed_dataset_id == manifest.dataset_id)
    checks.append(_check("manifest_identity", identity_ok,
                         recomputed=recomputed_dataset_id, stored=manifest.dataset_id))

    # --- 20. labels_not_complete ---
    labels_ok = (not manifest.human_labels_complete) and (manifest.human_verified_count == 0)
    checks.append(_check("labels_not_complete", labels_ok,
                         human_labels_complete=manifest.human_labels_complete,
                         human_verified_count=manifest.human_verified_count))

    # --- 21. calibration_not_allowed ---
    cal_ok = not manifest.calibration_allowed
    checks.append(_check("calibration_not_allowed", cal_ok,
                         calibration_allowed=manifest.calibration_allowed))

    # Overall
    all_passed = all(c["passed"] for c in checks)
    result = {
        "status": "READY" if all_passed else "FAIL",
        "passed": all_passed,
        "checks": {c["name"]: {"passed": c["passed"], "observations": c["observations"]} for c in checks},
        "sample_count": n,
        "profile_distribution": profile_dist,
        "source_distribution": source_dist,
        "capture_method_distribution": capture_dist,
        "double_annotation_count": double_count,
        "double_annotation_ratio": double_count / n if n else 0,
        "split_counts": {k: len(v) for k, v in splits.items()},
        "human_labels_complete": manifest.human_labels_complete,
        "human_verified_count": manifest.human_verified_count,
        "calibration_allowed": manifest.calibration_allowed,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps({"status": result["status"], "passed": result["passed"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
