#!/usr/bin/env python3
"""P13-2-2-1: Import human annotations into a local annotation store.

The "store" is a JSON file (default sample_data/p13_2/human_annotations.json)
that accumulates annotations keyed by annotation_id. It is independent from
the production DB: this tool NEVER writes to signal_miner.db.

Integrity rules enforced on every import (each maps to a named structured
check in the --out report so adversarial mutation gates can target a specific
rule rather than inferring pass/fail from the exit code):

  0. pack_trust              — P13-2-2-1A: HMAC-signed manifest (external
                              trust root). Verifies schema, file-level SHA/
                              bytes/count, and HMAC-SHA256 signature BEFORE
                              any annotation is processed. Production mode
                              requires ANNOTATION_PACK_SIGNING_KEY env var.
  1. schema_strict          — Pydantic strict schema (extra="forbid").
  2. task_exists            — (sample_id, annotator_slot) must map to a
                              frozen task pack entry.
  3. dataset_identity       — dataset_id / task_hash / content_hash /
                              annotation_mode must match the frozen task.
  4. signal_count_consistency — signal_count == len(signals).
  5. has_signals_consistency — has_signals ⇔ signals emptiness agreement.
  6. evidence_offsets       — every evidence span satisfies
                              redacted_text[start:end] == text (Unicode-safe).
  7. summary_and_evidence_nonempty — summary non-empty, evidence_spans
                              non-empty per signal.
  8. signal_type_whitelist  — signal_type ∈ production profile.signal_types.
  9. assisted_review_action — review_action required for assisted_review.
 10. no_self_pairing        — a single annotator_pseudonym cannot annotate
                              BOTH A and B of the same sample.
 11. annotation_id_conflict — re-importing the same annotation_id with
                              DIFFERENT content → FAIL (not idempotent).
 12. fixture_provenance     — annotation.fixture MUST exactly match the
                              frozen task's fixture field. The task pack is
                              the single source of truth. No ID-based
                              heuristic is used.

Idempotent re-import of identical content (same content hash) is a silent
no-op (exit 0, adds nothing).

Exit codes:
  0 = imported successfully (or idempotent no-op)
  1 = validation failure / conflict (store unchanged)
  2 = input file missing / unreadable OR BLOCKED (no production signing key)
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
    HumanAnnotationV2,
    compute_annotation_hash,
    compute_task_hash,
    validate_evidence_offsets,
    validate_signal_types,
)
from signal_miner.evaluation.pack_trust import (  # noqa: E402
    FIXTURE_KEY_ID,
    verify_manifest_file,
)

# Ordered list of all importer checks. The order here defines the canonical
# ordering of the `checks` dict in the --out report and MUST stay in sync with
# the mutation gate's target_check names.
IMPORTER_CHECKS: tuple[str, ...] = (
    "pack_trust",
    "schema_strict",
    "task_exists",
    "dataset_identity",
    "signal_count_consistency",
    "has_signals_consistency",
    "evidence_offsets",
    "summary_and_evidence_nonempty",
    "signal_type_whitelist",
    "assisted_review_action",
    "no_self_pairing",
    "annotation_id_conflict",
    "fixture_provenance",
)

# Substrings in annotation_id that betray a fixture/test/mock origin. If
# fixture=false but any of these appear, the annotation is rejected.
# P13-2-2-1 fix-3: fixture/real identity is determined solely by the frozen
# task pack's structured `fixture` field, NOT by annotation_id keywords.
# ID-based heuristics (e.g. "fixann", "test", "mock") are not a security
# boundary and MUST NOT be used for provenance decisions.


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text())


# ── P13-2-2-1A: Pack trust (manifest verification) ──

# No built-in test key. Test key must be injected via env var
# ANNOTATION_PACK_TEST_SIGNING_KEY under APP_ENVIRONMENT=test.


def _verify_pack_trust(
    manifest_path: str | None,
    task_dir: Path,
    is_fixture: bool,
    dataset_manifest_path: Path | None,
) -> tuple[list[str], str | None]:
    """Verify pack manifest (external trust root) before importing.

    P13-2-2-1A fix-2: manifest + dataset_manifest are MANDATORY for all
    imports. Test key requires APP_ENVIRONMENT=test + --fixture +
    ANNOTATION_PACK_TEST_SIGNING_KEY explicitly injected.

    Returns (errors, error_kind).
      errors: list of error code strings (empty = trust established)
      error_kind: None on success, one of:
        - "test_key_environment_boundary" (test key in non-test env)
        - "FAIL_MISSING_PACK_MANIFEST" (fixture, no --manifest)
        - "BLOCKED_MISSING_MANIFEST" (production, no --manifest)
        - "FAIL_MISSING_DATASET_MANIFEST" (no --dataset-manifest or file missing)
        - "BLOCKED_MISSING_TEST_KEY" (test env but no injected key)
        - "BLOCKED_MISSING_PACK_SIGNING_KEY" (production, no key)
        - "FAIL_MANIFEST_VERIFICATION" (schema/SHA/signature failure)
    """
    errors: list[str] = []

    # Manifest is MANDATORY for all imports
    if manifest_path is None:
        if is_fixture:
            return (
                ["FAIL_MISSING_PACK_MANIFEST: --manifest is required for all imports"],
                "FAIL_MISSING_PACK_MANIFEST",
            )
        return (
            ["BLOCKED: --manifest is required for production imports"],
            "BLOCKED_MISSING_MANIFEST",
        )

    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        if is_fixture:
            return (
                [f"FAIL_MISSING_PACK_MANIFEST: manifest file not found: {manifest_path}"],
                "FAIL_MISSING_PACK_MANIFEST",
            )
        return (
            [f"BLOCKED: manifest file not found: {manifest_path}"],
            "BLOCKED_MISSING_MANIFEST",
        )

    # Dataset manifest is MANDATORY for all imports
    if dataset_manifest_path is None:
        return (
            ["FAIL_MISSING_DATASET_MANIFEST: --dataset-manifest is required for all imports"],
            "FAIL_MISSING_DATASET_MANIFEST",
        )
    if not dataset_manifest_path.exists():
        return (
            [f"FAIL_MISSING_DATASET_MANIFEST: dataset manifest not found: {dataset_manifest_path}"],
            "FAIL_MISSING_DATASET_MANIFEST",
        )

    # Resolve verification key (same four-condition rule as signer)
    from signal_miner.evaluation.pack_trust import (
        resolve_signing_key as _resolve,
    )
    key, key_error, key_error_kind = _resolve(is_fixture)
    if key is None:
        # test_key_environment_boundary → FAIL exit 1
        # BLOCKED → exit 2
        errors.append(key_error or "key resolution failed")
        return errors, key_error_kind

    expected_key_id = FIXTURE_KEY_ID if is_fixture else None

    # Run full verification: schema + file-level + dataset-manifest + signature
    result = verify_manifest_file(
        manifest_path=manifest_file,
        task_dir=task_dir,
        key=key,
        expected_key_id=expected_key_id,
        dataset_manifest_path=dataset_manifest_path,
    )

    if not result["valid"]:
        errors.extend(result["errors"])

    # Additional: verify manifest fixture flag matches import context
    manifest = result.get("manifest")
    if manifest and isinstance(manifest, dict):
        manifest_fixture = manifest.get("fixture")
        if manifest_fixture is not True and is_fixture:
            errors.append(
                "manifest_fixture_mismatch: expected fixture=true for fixture import"
            )
        if manifest_fixture is not False and not is_fixture:
            errors.append(
                "manifest_fixture_mismatch: expected fixture=false for production import"
            )
        # Verify manifest dataset_id matches pack dataset_id
        manifest_dataset = manifest.get("dataset_id", "")
        for name in ("human_tasks_development.json", "human_tasks_test_A.json"):
            pf = task_dir / name
            if pf.exists():
                pack = _load_json(pf)
                pack_dataset = pack.get("dataset_id", "")
                if pack_dataset and manifest_dataset and pack_dataset != manifest_dataset:
                    errors.append(
                        f"dataset_id_mismatch: manifest={manifest_dataset} pack={pack_dataset}"
                    )
                break

    error_kind = "FAIL_MANIFEST_VERIFICATION" if errors else None
    return errors, error_kind


def _build_task_index(task_dir: Path) -> tuple[dict[tuple[str, str], dict], list[str]]:
    """Returns (task_index, pack_fixture_errors).

    P13-2-2-1 fix-3/4: validates pack-level `fixture` schema (must exist
    and be bool), per-task `fixture` schema (must exist and be bool), and
    pack/task fixture consistency. Errors feed into fixture_provenance.
    """
    index: dict[tuple[str, str], dict] = {}
    pack_fixture_errors: list[str] = []
    pack_files = [
        task_dir / "human_tasks_development.json",
        task_dir / "human_tasks_calibration.json",
        task_dir / "human_tasks_test_A.json",
        task_dir / "human_tasks_test_B.json",
    ]
    for pf in pack_files:
        if not pf.exists():
            continue
        pack = _load_json(pf)
        pack_fixture = pack.get("fixture")

        # P13-2-2-1 fix-4: pack-level fixture must exist and be bool
        if pack_fixture is None:
            pack_fixture_errors.append(
                f"{pf.name}: pack_fixture_missing"
            )
        elif not isinstance(pack_fixture, bool):
            pack_fixture_errors.append(
                f"{pf.name}: pack_fixture_not_bool ({type(pack_fixture).__name__})"
            )

        for task in pack.get("tasks", []):
            key = (task["sample_id"], task["annotator_slot"])
            index[key] = task

            task_fixture = task.get("fixture")
            # fix-4: per-task fixture must exist and be bool
            if task_fixture is None:
                pack_fixture_errors.append(
                    f"{pf.name}: sample={task['sample_id']} task_fixture_missing"
                )
            elif not isinstance(task_fixture, bool):
                pack_fixture_errors.append(
                    f"{pf.name}: sample={task['sample_id']} "
                    f"task_fixture_not_bool ({type(task_fixture).__name__})"
                )
            elif (isinstance(pack_fixture, bool)
                  and pack_fixture != task_fixture):
                pack_fixture_errors.append(
                    f"{pf.name}: sample={task['sample_id']} "
                    f"pack_fixture={pack_fixture} task_fixture={task_fixture}"
                )
    return index, pack_fixture_errors


def _new_check_buckets() -> dict[str, list[str]]:
    """Fresh per-batch error buckets, one list per named check."""
    return {name: [] for name in IMPORTER_CHECKS}


def _validate_one(raw: dict, task_index: dict[tuple[str, str], dict],
                  _existing: dict[str, dict],
                  buckets: dict[str, list[str]]) -> tuple[HumanAnnotationV2 | None,
                                                           str | None]:
    """Validate a single raw annotation dict.

    Appends error codes into the shared `buckets` dict keyed by check name.
    Returns (parsed_model, content_hash). parsed_model is None on any error.
    """
    aid_raw = raw.get("annotation_id", "<unknown>")

    # 1. schema_strict
    try:
        ann = HumanAnnotationV2(**raw)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            buckets["schema_strict"].append(f"{aid_raw}.{loc}: {err['msg']}")
        return None, None

    content_hash = compute_annotation_hash(ann)
    aid = ann.annotation_id

    # 2. task_exists
    key = (ann.sample_id, ann.annotator_slot)
    task = task_index.get(key)
    if task is None:
        buckets["task_exists"].append(
            f"{aid}: task_not_found sample={ann.sample_id} slot={ann.annotator_slot}"
        )

    # 3. dataset_identity
    if task is not None:
        if ann.dataset_id != task["dataset_id"]:
            buckets["dataset_identity"].append(
                f"{aid}: dataset_id_mismatch ann={ann.dataset_id} task={task['dataset_id']}"
            )
        if ann.task_hash != task["task_hash"]:
            buckets["dataset_identity"].append(
                f"{aid}: task_hash_mismatch ann={ann.task_hash} task={task['task_hash']}"
            )
        # P13-2-2-1 fix-4: independently recompute the expected task hash
        # from the task's canonical fields. This closes the integrity loop:
        # if a task pack's fixture is flipped but the hash is not updated,
        # the recomputed hash will differ from both task.task_hash and
        # ann.task_hash.
        expected_hash = compute_task_hash(
            task["dataset_id"],
            task["sample_id"],
            task["annotator_slot"],
            task["content_hash"],
            fixture=task.get("fixture", True),
        )
        if task["task_hash"] != expected_hash:
            buckets["dataset_identity"].append(
                f"{aid}: task_hash_recompute_mismatch task_hash={task['task_hash']} "
                f"expected={expected_hash}"
            )
        if ann.task_hash != expected_hash:
            buckets["dataset_identity"].append(
                f"{aid}: task_hash_recompute_mismatch ann_hash={ann.task_hash} "
                f"expected={expected_hash}"
            )
        if ann.content_hash != task["content_hash"]:
            buckets["dataset_identity"].append(
                f"{aid}: content_hash_mismatch ann={ann.content_hash} task={task['content_hash']}"
            )
        if ann.annotation_mode != task["annotation_mode"]:
            buckets["dataset_identity"].append(
                f"{aid}: annotation_mode_mismatch ann={ann.annotation_mode} task={task['annotation_mode']}"
            )

    # 4. signal_count_consistency
    if ann.signal_count != len(ann.signals):
        buckets["signal_count_consistency"].append(
            f"{aid}: signal_count_mismatch stated={ann.signal_count} actual={len(ann.signals)}"
        )

    # 5. has_signals_consistency
    if not ann.has_signals and ann.signals:
        buckets["has_signals_consistency"].append(
            f"{aid}: has_signals_false_but_signals_nonempty"
        )
    if ann.has_signals and len(ann.signals) == 0:
        buckets["has_signals_consistency"].append(
            f"{aid}: has_signals_true_but_signals_empty"
        )

    # 6 & 7. evidence_offsets + summary_and_evidence_nonempty
    for i, sig in enumerate(ann.signals):
        if not sig.summary or not sig.summary.strip():
            buckets["summary_and_evidence_nonempty"].append(
                f"{aid}.signal[{i}]: summary_empty"
            )
        if not sig.evidence_spans:
            buckets["summary_and_evidence_nonempty"].append(
                f"{aid}.signal[{i}]: evidence_empty"
            )
    profile = task.get("profile", "") if task else ""
    redacted = task.get("redacted_text", "") if task else ""
    if redacted:
        ev_errors = validate_evidence_offsets(redacted, ann.signals)
        for e in ev_errors:
            buckets["evidence_offsets"].append(f"{aid}: {e}")

    # 8. signal_type_whitelist
    if profile:
        stype_errors = validate_signal_types(ann.signals, profile)
        for e in stype_errors:
            buckets["signal_type_whitelist"].append(f"{aid}: {e}")

    # 9. assisted_review_action
    if ann.annotation_mode == "assisted_review" and ann.review_action is None:
        buckets["assisted_review_action"].append(
            f"{aid}: assisted_review_missing_review_action"
        )

    # 10. no_self_pairing is a cross-annotation check handled in _validate_batch.

    # 12. fixture_provenance — annotation.fixture MUST equal the frozen
    #     task's fixture field. The task pack is the single source of truth.
    #     ID-based heuristics are NOT used (fix-3).
    if task is not None:
        task_fixture = task.get("fixture")
        if task_fixture is None:
            # Task fixture field missing entirely — pack is corrupt.
            buckets["fixture_provenance"].append(
                f"{aid}: task_fixture_missing"
            )
        elif not isinstance(task_fixture, bool):
            # Non-boolean fixture is a schema violation on the task side.
            buckets["fixture_provenance"].append(
                f"{aid}: task_fixture_not_bool ({type(task_fixture).__name__})"
            )
        elif ann.fixture is not task_fixture:
            buckets["fixture_provenance"].append(
                f"{aid}: fixture_mismatch annotation={ann.fixture} task={task_fixture}"
            )
    else:
        # task not found (task_exists already failed). Since we can't
        # verify the fixture status, flag it as unverifiable provenance.
        buckets["fixture_provenance"].append(
            f"{aid}: task_not_found_cannot_verify_fixture"
        )

    return ann, content_hash


def _validate_batch(raws: list[dict], task_index: dict[tuple[str, str], dict],
                    existing: dict[str, dict]
                    ) -> tuple[list[HumanAnnotationV2], dict[str, list[str]],
                               dict[str, str]]:
    """Validate a batch.

    Returns (valid_models, check_buckets, content_hashes_by_id).
    `check_buckets` maps each importer check name to its list of error codes;
    a check passes iff its list is empty.
    """
    buckets = _new_check_buckets()
    content_hashes: dict[str, str] = {}

    # First pass: per-annotation checks. Collect annotations that pass all
    # per-item checks; annotations with any per-item error are excluded from
    # the candidate set but their error codes are already recorded.
    candidates: list[tuple[int, HumanAnnotationV2]] = []
    for idx, raw in enumerate(raws):
        ann, ch = _validate_one(raw, task_index, existing, buckets)
        if ann is None:
            continue
        # If this annotation produced ANY per-item error it cannot be imported.
        aid = ann.annotation_id
        has_item_error = any(
            any(line.startswith(f"{aid}:") or line.startswith(f"{aid}.")
                for line in errs)
            for errs in buckets.values()
            if errs
        )
        if has_item_error:
            continue
        content_hashes[aid] = ch or ""
        candidates.append((idx, ann))

    # 10. no_self_pairing within the incoming batch + existing store.
    slot_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for ex in existing.values():
        ex_ann = ex.get("annotation", ex)
        ex_pair = (ex_ann.get("sample_id", ""), ex_ann.get("annotator_pseudonym", ""))
        slot_by_pair[ex_pair].add(ex_ann.get("annotator_slot", ""))
    for _, ann in candidates:
        pair = (ann.sample_id, ann.annotator_pseudonym)
        slot_by_pair[pair].add(ann.annotator_slot)

    implicated_pairs: set[tuple[str, str]] = set()
    for (sid, pseud), slots in slot_by_pair.items():
        if {"A", "B"}.issubset(slots):
            implicated_pairs.add((sid, pseud))
            buckets["no_self_pairing"].append(
                f"self_pairing: sample={sid} pseudonym={pseud} holds both A and B"
            )

    kept: list[HumanAnnotationV2] = []
    for _, ann in candidates:
        if (ann.sample_id, ann.annotator_pseudonym) in implicated_pairs:
            continue
        kept.append(ann)

    # 11. annotation_id_conflict vs idempotent re-import.
    final: list[HumanAnnotationV2] = []
    for ann in kept:
        existing_entry = existing.get(ann.annotation_id)
        if existing_entry is not None:
            existing_hash = existing_entry.get("content_hash_annotation", "")
            incoming_hash = content_hashes.get(ann.annotation_id, "")
            if existing_hash == incoming_hash:
                continue  # idempotent
            buckets["annotation_id_conflict"].append(
                f"{ann.annotation_id}: conflict_same_id_different_content "
                f"existing={existing_hash} incoming={incoming_hash}"
            )
            continue
        final.append(ann)

    return final, buckets, content_hashes


def _build_checks_report(buckets: dict[str, list[str]]) -> dict[str, dict]:
    """Build the structured `checks` object from error buckets.

    Each check: {"passed": bool, "observations": {"error_codes": [...], "error_count": N}}.
    """
    checks: dict[str, dict] = {}
    for name in IMPORTER_CHECKS:
        errs = buckets.get(name, [])
        checks[name] = {
            "passed": len(errs) == 0,
            "observations": {
                "error_codes": errs[:50],
                "error_count": len(errs),
            },
        }
    return checks


def _write_report(out_path: str, status: str, passed: bool,
                  checks: dict[str, dict] | None = None,
                  **extra) -> None:
    """Write the structured --out report JSON."""
    result: dict = {"status": status, "passed": passed}
    if checks is not None:
        result["checks"] = checks
        # Top-level passed is the recomputation across all checks; it MUST
        # agree with the `passed` argument. This is asserted defensively.
        recomputed = all(c["passed"] for c in checks.values())
        # If there are no checks (e.g. input missing), fall back to the arg.
        result["passed"] = passed and recomputed if checks else passed
    result.update(extra)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> int:
    p = argparse.ArgumentParser(description="Import human annotations")
    p.add_argument("--input", required=True, help="JSON file with annotations to import")
    p.add_argument("--tasks", default="sample_data/p13_2/human_tasks",
                   help="Directory containing the four human_tasks_*.json packs")
    p.add_argument("--store", default="sample_data/p13_2/human_annotations.json",
                   help="Annotation store JSON (created if missing)")
    p.add_argument("--out", default="",
                   help="Optional import report JSON path (for mutation gate plumbing)")
    p.add_argument("--manifest", default="",
                   help="Path to signed pack manifest JSON (MANDATORY trust root)")
    p.add_argument("--dataset-manifest", default="",
                   help="Path to frozen dataset manifest JSON (MANDATORY SHA-256 binding)")
    p.add_argument("--fixture", action="store_true",
                   help="Fixture/test mode: requires APP_ENVIRONMENT=test + injected test key")
    args = p.parse_args()

    input_path = Path(args.input)
    task_dir = Path(args.tasks)
    store_path = Path(args.store)
    manifest_path = args.manifest if args.manifest else None
    dataset_manifest_str = args.dataset_manifest if args.dataset_manifest else ""
    dataset_manifest_path = Path(dataset_manifest_str) if dataset_manifest_str else None
    is_fixture = args.fixture

    # --- Input missing → exit 2, structured report with no checks ---
    if not input_path.exists():
        if args.out:
            _write_report(args.out, "FAIL_INPUT_MISSING", passed=False)
        print(json.dumps({"status": "FAIL_INPUT_MISSING", "passed": False},
                         ensure_ascii=False))
        return 2

    raw_input = json.loads(input_path.read_text())
    if isinstance(raw_input, dict):
        raws = raw_input.get("annotations", [])
    elif isinstance(raw_input, list):
        raws = raw_input
    else:
        if args.out:
            _write_report(args.out, "FAIL_INPUT_SHAPE", passed=False)
        print(json.dumps({"status": "FAIL_INPUT_SHAPE", "passed": False},
                         ensure_ascii=False))
        return 1

    # Load existing store (if any)
    existing: dict[str, dict] = {}
    if store_path.exists():
        store_data = json.loads(store_path.read_text())
        for entry in store_data.get("annotations", []):
            ann = entry.get("annotation", entry)
            existing[ann["annotation_id"]] = {
                "annotation": ann,
                "content_hash_annotation": entry.get("content_hash_annotation", ""),
            }

    # P13-2-2-1A fix: Verify pack manifest (external trust root) BEFORE
    # building the task index or processing any annotation. Manifest is
    # MANDATORY for all imports. Test key requires APP_ENVIRONMENT=test.
    buckets = _new_check_buckets()
    trust_errors, trust_error_kind = _verify_pack_trust(
        manifest_path, task_dir, is_fixture, dataset_manifest_path,
    )
    if trust_errors:
        buckets["pack_trust"].extend(trust_errors)

    # Handle error kinds:
    #   test_key_environment_boundary → FAIL exit 1
    #   FAIL_MISSING_PACK_MANIFEST → exit 1 (fixture contract violation)
    #   FAIL_MISSING_DATASET_MANIFEST → exit 1 (dataset binding violation)
    #   BLOCKED_MISSING_MANIFEST / BLOCKED_MISSING_*_KEY → exit 2
    #   FAIL_MANIFEST_VERIFICATION → exit 1
    fail_exit1_kinds = {
        "test_key_environment_boundary",
        "FAIL_MISSING_PACK_MANIFEST",
        "FAIL_MISSING_DATASET_MANIFEST",
        "FAIL_MANIFEST_VERIFICATION",
    }

    if trust_error_kind in fail_exit1_kinds:
        status_map = {
            "test_key_environment_boundary": "FAIL_TEST_KEY_ENVIRONMENT_BOUNDARY",
            "FAIL_MISSING_PACK_MANIFEST": "FAIL_MISSING_PACK_MANIFEST",
            "FAIL_MISSING_DATASET_MANIFEST": "FAIL_MISSING_DATASET_MANIFEST",
            "FAIL_MANIFEST_VERIFICATION": "FAIL_VALIDATION",
        }
        status = status_map.get(trust_error_kind, "FAIL_VALIDATION")
        checks = _build_checks_report(buckets)
        if args.out:
            _write_report(args.out, status,
                          passed=False, checks=checks)
        print(json.dumps({
            "status": status, "passed": False,
        }, ensure_ascii=False))
        return 1

    if trust_error_kind and trust_error_kind.startswith("BLOCKED"):
        status_map = {
            "BLOCKED_MISSING_MANIFEST": "BLOCKED_MISSING_MANIFEST",
            "BLOCKED_MISSING_TEST_KEY": "BLOCKED_MISSING_TEST_KEY",
            "BLOCKED_MISSING_PACK_SIGNING_KEY": "BLOCKED_MISSING_PACK_SIGNING_KEY",
        }
        status = status_map.get(trust_error_kind, "BLOCKED")
        checks = _build_checks_report(buckets)
        if args.out:
            _write_report(args.out, status, passed=False, checks=checks)
        print(json.dumps({"status": status, "passed": False},
                         ensure_ascii=False))
        return 2

    task_index, pack_fixture_errors = _build_task_index(task_dir)

    valid, item_buckets, content_hashes = _validate_batch(raws, task_index, existing)

    # Merge per-annotation buckets into our unified buckets (pack_trust already filled)
    for name in IMPORTER_CHECKS:
        if name == "pack_trust":
            continue
        buckets[name].extend(item_buckets.get(name, []))

    # P13-2-2-1 fix-3: pack-level fixture consistency errors go into
    # fixture_provenance. These are detected at task-index build time before
    # any annotation is processed.
    if pack_fixture_errors:
        buckets["fixture_provenance"].extend(pack_fixture_errors)

    checks = _build_checks_report(buckets)
    all_checks_passed = all(c["passed"] for c in checks.values())

    # --- Validation failure → exit 1, structured checks report ---
    if not all_checks_passed:
        total_errors = sum(c["observations"]["error_count"] for c in checks.values())
        if args.out:
            _write_report(args.out, "FAIL_VALIDATION", passed=False,
                          checks=checks, error_count=total_errors)
        print(json.dumps({
            "status": "FAIL_VALIDATION", "passed": False,
            "error_count": total_errors,
        }, ensure_ascii=False))
        return 1

    # --- All checks passed: merge valid into store ---
    store_data = {"annotations": []}
    if store_path.exists():
        store_data = json.loads(store_path.read_text())

    existing_ids = {a["annotation"]["annotation_id"]
                    for a in store_data.get("annotations", [])}
    added = 0
    for ann in valid:
        if ann.annotation_id in existing_ids:
            continue  # idempotent
        entry = {
            "annotation": ann.model_dump(),
            "content_hash_annotation": content_hashes.get(ann.annotation_id, ""),
        }
        store_data.setdefault("annotations", []).append(entry)
        added += 1

    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store_data, indent=2, ensure_ascii=False))

    if args.out:
        _write_report(args.out, "IMPORTED", passed=True,
                      checks=checks, added=added,
                      skipped_idempotent=len(valid) - added,
                      total_in_store=len(store_data.get("annotations", [])))
    print(json.dumps({
        "status": "IMPORTED", "passed": True,
        "added": added, "total": len(store_data.get("annotations", [])),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
