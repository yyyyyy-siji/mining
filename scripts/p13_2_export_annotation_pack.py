#!/usr/bin/env python3
"""P13-2-1 fix-3: Export annotation pack — production signal types, freeze protection.

Exit codes: 0=READY, 1=internal error/freeze conflict, 2=BLOCKED (insufficient data).
Always writes output JSON even when BLOCKED.
Frozen manifest is NEVER modified by a failure path.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from signal_miner.evaluation import (  # noqa: E402
    AUTHORIZED_BASES,
    PROFILES,
    SCHEMA_VERSION,
    FrozenManifest,
    GoldRecord,
    check_blind_pack_leakage,
    compute_ordered_hash,
    has_sensitive,
    is_test_or_mock_record,
    redact_sensitive,
    sha256,
)


def load_feedback() -> list[dict]:
    import asyncio

    from sqlalchemy import select

    from signal_miner.db import close_db, get_session_factory, init_db
    from signal_miner.db.models import RawFeedbackRow
    from signal_miner.settings import AppSettings

    async def _q():
        s = AppSettings()
        await init_db(s.database_url)
        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(select(RawFeedbackRow))
            rows = result.scalars().all()
        await close_db()
        out = []
        for row in rows:
            content = row.content or {}
            text_a = content.get("text", "") or content.get("content", "") or ""
            if isinstance(text_a, str) and text_a.strip():
                out.append({
                    "raw_feedback_id": row.id,
                    "source_platform": getattr(row, "source_platform", "") or "",
                    "capture_method": row.source_type or "",
                    "source_id": row.source_id or "",
                    "profile": getattr(row, "pipeline_profile", "") or "product_feedback",
                    "text": text_a.strip(),
                    "subject": content.get("subject", "") or "",
                    "authorization_basis": getattr(row, "authorization_basis", "") or "",
                })
        return out
    return asyncio.run(_q())


def main() -> int:
    p = argparse.ArgumentParser(description="Export P13-2 annotation pack")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="sample_data/p13_2/positive/candidates.json")
    p.add_argument("--rejects", default="sample_data/p13_2/negative/rejected.json")
    p.add_argument("--manifest", default="sample_data/p13_2/manifest.json")
    p.add_argument("--fixture", default="")
    p.add_argument("--test-packs", action="store_true", help="Export A/B blind packs")
    p.add_argument("--new-dataset-version", action="store_true",
                   help="Allow writing new dataset version (requires new manifest path)")
    p.add_argument("--error-out", default="", help="Write error JSON to this path instead of stdout")
    args = p.parse_args()

    seed = args.seed
    import random
    rng = random.Random(seed)

    # --- Manifest freeze: save original bytes BEFORE any writes ---
    manifest_path = Path(args.manifest)
    original_manifest_bytes = None
    if manifest_path.exists():
        original_manifest_bytes = manifest_path.read_bytes()

    def _safe_error(status: str, **extra) -> int:
        """Write error to stdout or --error-out, NEVER to manifest path."""
        result = {"status": status, "passed": False, **extra}
        if args.error_out:
            Path(args.error_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.error_out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 1

    # --- Load ---
    raw = json.loads(Path(args.fixture).read_text()) if args.fixture else load_feedback()

    # --- Eligibility ---
    eligible: list[dict] = []
    rejected: list[dict] = []

    for fb in raw:
        reasons = []
        if is_test_or_mock_record(fb["raw_feedback_id"], fb.get("text", ""), fb.get("source_id", "")):
            reasons.append("test_or_mock_record")
        auth = fb.get("authorization_basis", "")
        if not auth or auth not in AUTHORIZED_BASES:
            reasons.append("missing_or_invalid_authorization")
        profile = fb.get("profile", "")
        if profile not in PROFILES:
            reasons.append("unsupported_profile")
        src_platform = fb.get("source_platform", "")
        if not src_platform or not src_platform.strip():
            reasons.append("missing_source_platform")
        capture_method = fb.get("capture_method", "")
        if not capture_method or not capture_method.strip():
            reasons.append("missing_capture_method")
        text = fb.get("text", "")
        if has_sensitive(text):
            reasons.append("sensitive_content")
        if not text.strip() or text.strip() in ("N/A", "placeholder", "test"):
            reasons.append("empty_or_placeholder_text")

        if reasons:
            rejected.append({"raw_feedback_id": fb["raw_feedback_id"], "reasons": reasons})
        else:
            eligible.append(fb)

    profile_counts = Counter(fb["profile"] for fb in eligible)
    source_counts = Counter(fb.get("source_platform", "") for fb in eligible)
    capture_counts = Counter(fb.get("capture_method", "") for fb in eligible)

    blocker = ""
    if len(eligible) < 100:
        blocker = "BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES"
    else:
        for prof in PROFILES:
            if profile_counts.get(prof, 0) < 30:
                blocker = f"BLOCKED_INSUFFICIENT_PROFILE_{prof}"
                break
        if not blocker:
            total = len(eligible)
            if total > 0:
                max_pct = max(source_counts.values()) / total
                if max_pct > 0.60:
                    blocker = "BLOCKED_SOURCE_IMBALANCE"

    if blocker:
        result = {
            "status": blocker,
            "passed": False,
            "eligible_count": len(eligible),
            "required_minimum": 100,
            "rejected_count": len(rejected),
            "rejected_by_reason": dict(Counter(r for rj in rejected for r in rj["reasons"])),
            "profile_distribution": dict(profile_counts),
            "source_distribution": dict(source_counts),
            "capture_method_distribution": dict(capture_counts),
        }
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        Path(args.rejects).parent.mkdir(parents=True, exist_ok=True)
        Path(args.rejects).write_text(json.dumps(rejected, indent=2, ensure_ascii=False))
        print(f"BLOCKED: {blocker} ({len(eligible)} eligible)")
        return 2

    # --- Sampling ---
    rng.shuffle(eligible)
    by_profile: dict[str, list] = defaultdict(list)
    for fb in eligible:
        by_profile[fb["profile"]].append(fb)

    selected: list[dict] = []
    for prof in PROFILES:
        selected.extend(by_profile[prof][:45])
    selected_ids = {fb["raw_feedback_id"] for fb in selected}
    remaining = [fb for fb in eligible if fb["raw_feedback_id"] not in selected_ids]
    selected.extend(remaining[:10])
    selected = selected[:100]

    # --- Build records ---
    samples: list[GoldRecord] = []
    for fb in selected:
        redacted, redact_applied = redact_sensitive(fb["text"])
        if redact_applied and has_sensitive(redacted):
            rejected.append({"raw_feedback_id": fb["raw_feedback_id"],
                             "reasons": ["sensitive_content_after_redaction"]})
            continue
        sid = "gs_" + sha256(fb["raw_feedback_id"] + fb["text"][:80])[:12]
        samples.append(GoldRecord(
            schema_version=SCHEMA_VERSION,
            sample_id=sid,
            raw_feedback_id=fb["raw_feedback_id"],
            profile=fb["profile"],
            source_platform=fb.get("source_platform", ""),
            capture_method=fb.get("capture_method", ""),
            authorization_basis=fb["authorization_basis"],
            content_hash=sha256(redacted),
            redacted_text=redacted,
            redaction_applied=redact_applied,
            language="zh",
            split="development",
            split_seed=seed,
            annotation_mode="assisted_review",
            annotation_status="pending",
            annotator_slot="none",
        ))

    samples.sort(key=lambda s: s.content_hash)

    n = len(samples)
    dev_end = int(n * 0.5)
    cal_end = dev_end + int(n * 0.25)
    for i, s in enumerate(samples):
        if i < dev_end:
            s.split = "development"
            s.annotation_mode = "assisted_review"
        elif i < cal_end:
            s.split = "calibration"
            s.annotation_mode = "assisted_review"
        else:
            s.split = "test"
            s.annotation_mode = "blind"
            s.annotator_slot = "none"

    # --- Double annotation ---
    test_samples = [s for s in samples if s.split == "test"]
    double_count = max(20, int(n * 0.2 + 0.999))
    double_ids: list[str] = []
    for s in test_samples:
        if len(double_ids) >= double_count:
            break
        double_ids.append(s.sample_id)
    cal_samples = [s for s in samples if s.split == "calibration"]
    for s in cal_samples:
        if len(double_ids) >= double_count:
            break
        double_ids.append(s.sample_id)

    splits: dict[str, list[str]] = {"development": [], "calibration": [], "test": []}
    for s in samples:
        splits[s.split].append(s.sample_id)

    out_dir = Path(args.out).parent

    # --- A/B blind packs: assign precise annotator_slot per sample ---
    if args.test_packs:
        # A pack: ALL test samples, slot = A
        a_samples = []
        for s in samples:
            if s.split == "test":
                sd = s.model_dump()
                sd["annotator_slot"] = "A"
                a_samples.append(sd)
        # B pack: ONLY double-annotated test samples, slot = B
        double_set = set(double_ids)
        b_samples = []
        for s in samples:
            if s.split == "test" and s.sample_id in double_set:
                sd = s.model_dump()
                sd["annotator_slot"] = "B"
                b_samples.append(sd)
        a_pack = {"schema_version": SCHEMA_VERSION, "split": "test",
                  "annotator_slot": "A", "annotation_mode": "blind",
                  "samples": a_samples}
        b_pack = {"schema_version": SCHEMA_VERSION, "split": "test",
                  "annotator_slot": "B", "annotation_mode": "blind",
                  "samples": b_samples}
        Path(out_dir / "annotation_pack_test_A.json").write_text(
            json.dumps(a_pack, indent=2, ensure_ascii=False))
        Path(out_dir / "annotation_pack_test_B.json").write_text(
            json.dumps(b_pack, indent=2, ensure_ascii=False))

    # --- Manifest ---
    guideline_path = PROJECT / "docs" / "P13-2" / "annotation-guideline-v1.md"
    guideline_hash = sha256(guideline_path.read_text()) if guideline_path.exists() else ""
    ordered_hash = compute_ordered_hash(samples)
    profile_dist = dict(Counter(s.profile for s in samples))
    source_dist = dict(Counter(s.source_platform for s in samples))
    capture_dist = dict(Counter(s.capture_method for s in samples))
    sel_fp = sha256(json.dumps({
        "ids": sorted(s.raw_feedback_id for s in samples),
        "hashes": sorted(s.content_hash for s in samples),
        "seed": seed,
        "schema": SCHEMA_VERSION,
        "rules": "p13_2_1_fix3",
    }, sort_keys=True))

    if args.test_packs:
        a_pack_raw = json.loads(Path(out_dir / "annotation_pack_test_A.json").read_text())
        b_pack_raw = json.loads(Path(out_dir / "annotation_pack_test_B.json").read_text())
        blind_pack_combined = json.dumps(
            {"A": a_pack_raw, "B": b_pack_raw}, sort_keys=True, ensure_ascii=False)
    else:
        test_dump = [s.model_dump() for s in sorted(samples, key=lambda s: s.sample_id) if s.split == "test"]
        blind_pack_combined = json.dumps(test_dump, sort_keys=True, ensure_ascii=False)
    blind_pack_hash = sha256(blind_pack_combined)

    blind_leak = 0
    if args.test_packs:
        blind_leak += check_blind_pack_leakage(a_pack_raw)
        blind_leak += check_blind_pack_leakage(b_pack_raw)

    dataset_id = sha256(ordered_hash)[:16]

    # --- Manifest freeze protection ---
    should_write_manifest = True
    if manifest_path.exists() and original_manifest_bytes is not None:
        try:
            existing = json.loads(original_manifest_bytes)
            existing_id = existing.get("dataset_id", "")
            existing_hash = existing.get("ordered_samples_hash", "")
            if existing_id == dataset_id and existing_hash == ordered_hash:
                should_write_manifest = False
            elif not args.new_dataset_version:
                return _safe_error(
                    "FAIL_FROZEN_MANIFEST_MISMATCH",
                    existing_dataset_id=existing_id,
                    new_dataset_id=dataset_id,
                )
            elif args.new_dataset_version and manifest_path == Path(args.manifest):
                return _safe_error(
                    "FAIL_NEW_VERSION_REQUIRES_NEW_PATH",
                    reason="--new-dataset-version must specify a different manifest path",
                )
        except (json.JSONDecodeError, KeyError):
            # Corrupt manifest — do NOT overwrite, fail
            return _safe_error(
                "FAIL_FROZEN_MANIFEST_CORRUPT",
                reason="existing manifest is corrupt; will not overwrite",
            )

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = FrozenManifest(
        dataset_id=dataset_id,
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        selection_query_fingerprint=sel_fp,
        seed=seed,
        splits=splits,
        double_annotation_ids=double_ids,
        double_annotation_count=len(double_ids),
        double_annotation_ratio=len(double_ids) / n if n else 0,
        annotation_mode_by_split={s: "blind" if s == "test" else "assisted_review" for s in splits},
        sample_count=n,
        profile_distribution=profile_dist,
        source_distribution=source_dist,
        capture_method_distribution=capture_dist,
        blind_pack_hash=blind_pack_hash,
        blind_pack_leakage_count=blind_leak,
        content_hash_list=[s.content_hash for s in samples],
        ordered_samples_hash=ordered_hash,
        guideline_hash=guideline_hash,
        human_labels_complete=False,
        human_verified_count=0,
        calibration_allowed=False,
        passed=(blind_leak == 0),
    )

    # --- Write (manifest only if new or content matches) ---
    out_dir.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps([s.model_dump() for s in samples], indent=2, ensure_ascii=False))
    Path(args.rejects).parent.mkdir(parents=True, exist_ok=True)
    Path(args.rejects).write_text(json.dumps(rejected, indent=2, ensure_ascii=False))
    if should_write_manifest:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.model_dump(), indent=2, ensure_ascii=False))

    # --- Dev/cal assisted-review packs ---
    dev_samples = [s.model_dump() for s in samples if s.split == "development"]
    cal_samples = [s.model_dump() for s in samples if s.split == "calibration"]
    dev_pack = {"schema_version": SCHEMA_VERSION, "split": "development",
                "annotation_mode": "assisted_review", "samples": dev_samples}
    cal_pack = {"schema_version": SCHEMA_VERSION, "split": "calibration",
                "annotation_mode": "assisted_review", "samples": cal_samples}
    Path(out_dir / "annotation_pack_development.json").write_text(
        json.dumps(dev_pack, indent=2, ensure_ascii=False))
    Path(out_dir / "annotation_pack_calibration.json").write_text(
        json.dumps(cal_pack, indent=2, ensure_ascii=False))

    print(f"Exported {n} samples -> {args.out}")
    print(f"  dev={len(splits['development'])} cal={len(splits['calibration'])} test={len(splits['test'])}")
    print(f"  double: {len(double_ids)} ({manifest.double_annotation_ratio:.1%})")
    print(f"  source_platform: {dict(source_dist)}")
    print(f"  capture_method: {dict(capture_dist)}")
    print(f"  passed: {manifest.passed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
