"""P13-2-2-1A fix-4: Versioned gate contract — single source of truth.

Declares the EXACT sets of mutation names, readiness invariant names, and
meta‑negative names that MUST be present in every successful gate run.
Orchestrator and both gates must reference this contract.

The contract_sha256 is the SHA‑256 hash of the canonical serialisation of
these five ordered sets, providing tamper‑evident version binding.
"""

from __future__ import annotations

import hashlib
import json

CONTRACT_SCHEMA_VERSION = "contract-1.0.0"

# ── Pack trust mutation gate ──

PACK_TRUST_MUTATIONS: tuple[str, ...] = (
    "dataset_id_mismatch",
    "dataset_manifest_content_changed",
    "dataset_manifest_declared_path_mismatch",
    "dataset_manifest_file_missing",
    "dataset_manifest_omitted",
    "dataset_manifest_path_traversal",
    "dataset_manifest_sha_mismatch",
    "env_development_fixture_test_key_rejected",
    "env_empty_fixture_test_key_rejected",
    "env_production_fixture_test_key_rejected",
    "env_unknown_fixture_test_key_rejected",
    "extra_pack_added",
    "manifest_corrupt_json",
    "manifest_forged_passed_field",
    "pack_content_tampered_sha_stale",
    "pack_removed",
    "pack_replaced_with_another",
    "path_traversal_manifest",
    "schema_version_wrong",
    "signature_missing",
    "signature_truncated",
    "signature_wrong_key",
    "test_env_fixture_no_manifest_rejected",
)

PACK_TRUST_READINESS_INVARIANTS: tuple[str, ...] = (
    "production_no_key_blocked_exit2",
    "test_env_no_injected_key_blocked_exit2",
)

# ── Annotation mutation gate ──

ANNOTATION_MUTATIONS: tuple[str, ...] = (
    "a_reads_b_label",
    "ab_task_packs_missing",
    "all_false_degenerate_kappa",
    "all_true_degenerate_kappa",
    "calibration_policy_missing",
    "calibration_policy_true",
    "calibration_policy_wrong_type",
    "content_hash_tampered",
    "double_annotation_insufficient",
    "evidence_empty",
    "fixture_counted_as_real",
    "fixture_normal_id_false",
    "fixture_uuid_id_false",
    "full_pack_fixture_flip_old_hash",
    "has_signals_false_but_signals_nonempty",
    "invalid_signal_type",
    "llm_suggestion_as_gold_no_action",
    "nonexistent_dataset_id",
    "nonexistent_sample_id",
    "pack_fixture_missing",
    "pack_fixture_wrong_type",
    "pack_task_fixture_conflict",
    "pii_email_leak_in_notes",
    "same_id_different_content_conflict",
    "same_pseudonym_a_and_b",
    "signal_count_mismatch",
    "summary_empty",
    "task_fixture_missing",
    "task_fixture_wrong_type",
    "task_hash_rewritten_both_sides",
    "task_hash_tampered",
    "test_pack_has_model_confidence",
    "unicode_evidence_offset_error",
    "unknown_schema_field",
)

ANNOTATION_READINESS_INVARIANTS: tuple[str, ...] = (
    "zero_real_candidates_blocked_exit2",
)

ANNOTATION_META_NEGATIVES: tuple[str, ...] = (
    "meta_neg_exit1_only_unrelated_false",
    "meta_neg_exit1_target_absent",
    "meta_neg_exit1_target_true",
    "meta_neg_report_corrupt",
    "meta_neg_report_missing",
)

# ── Contract checksum ──

_CONTRACT_PAYLOAD = json.dumps(
    {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "pack_trust_mutations": sorted(PACK_TRUST_MUTATIONS),
        "pack_trust_readiness_invariants": sorted(PACK_TRUST_READINESS_INVARIANTS),
        "annotation_mutations": sorted(ANNOTATION_MUTATIONS),
        "annotation_readiness_invariants": sorted(ANNOTATION_READINESS_INVARIANTS),
        "annotation_meta_negatives": sorted(ANNOTATION_META_NEGATIVES),
    },
    sort_keys=True,
    ensure_ascii=False,
    separators=(",", ":"),
)

CONTRACT_SHA256 = hashlib.sha256(_CONTRACT_PAYLOAD.encode("utf-8")).hexdigest()


# ── Cardinalities (derived, verified by the test suite) ──

PACK_TRUST_MUTATION_COUNT = len(PACK_TRUST_MUTATIONS)
PACK_TRUST_INVARIANT_COUNT = len(PACK_TRUST_READINESS_INVARIANTS)
ANNOTATION_MUTATION_COUNT = len(ANNOTATION_MUTATIONS)
ANNOTATION_INVARIANT_COUNT = len(ANNOTATION_READINESS_INVARIANTS)
ANNOTATION_META_NEGATIVE_COUNT = len(ANNOTATION_META_NEGATIVES)
