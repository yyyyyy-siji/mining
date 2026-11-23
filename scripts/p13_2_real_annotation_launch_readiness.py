#!/usr/bin/env python3
"""P13-2-2-2A fix-2: Real annotation launch readiness with trust chain.

Single source of truth for whether real human annotation can safely start.

State classification:
  - BLOCKED_INPUT_REQUIRED / exit 2 : key external inputs missing
  - FAILED_INVALID_INPUT / exit 1   : inputs provided but invalid
  - READY_FOR_HUMAN_ANNOTATION / 0  : all real inputs and gates pass

Production CLI accepts --launch-config JSON referencing real files:
  real_candidate_path, real_rejections_path,
  dataset_manifest_path, pack_manifest_path, task_dir,
  roles_config_path, splits_config_path, governance_config_path

Independent evidence verifier:
  --verify-evidence : read-only SHA sidecar check, exit 0 match, exit 1 mismatch

Hard invariants (constant until P13-2-2-2B):
  human_verified_count = 0, human_labels_complete = False,
  calibration_allowed = False, kappa = 0.0
"""

from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

EVIDENCE_DIR_DEFAULT = PROJECT / "docs" / "P13-2-evidence"
OUT_NAME = "real-annotation-launch-readiness.json"
SIDECAR_SUFFIX = ".sha256"

MIN_AUTHORIZED_CANDIDATES = 100
MIN_DEVELOPMENT = 50
MIN_CALIBRATION = 25
MIN_TEST_BLIND = 25
MIN_DOUBLE_LABEL = 20
DOUBLE_LABEL_RATIO = 0.20
KAPPA_THRESHOLD = 0.70

ENV_VAR_ENVIRONMENT = "APP_ENVIRONMENT"
ENV_VAR_PROD_KEY = "ANNOTATION_PACK_SIGNING_KEY"
ENV_VAR_TEST_KEY = "ANNOTATION_PACK_TEST_SIGNING_KEY"
ALLOWED_TEST_ENVIRONMENTS = ("test",)

AUTHORIZATION_FIELD_SPECS: tuple[tuple[str, str], ...] = (
    ("dataset_id", "str"),
    ("sample_id", "str"),
    ("raw_feedback_id", "str"),
    ("source_url", "url"),
    ("source_adapter", "str"),
    ("source_version", "str"),
    ("captured_at", "iso8601"),
    ("content_sha256", "sha256"),
    ("authorization_basis", "str"),
    ("authorization_record_ref", "str"),
    ("permitted_use", "str_list"),
    ("pii_scanned", "bool_true"),
    ("pii_redacted", "bool_true"),
    ("raw_text_sha256", "sha256"),
    ("redacted_text_sha256", "sha256"),
    ("profile", "str"),
    ("language", "str"),
    ("source_tier", "str"),
)

AUTHORIZATION_REQUIRED_FIELDS = tuple(n for n, _ in AUTHORIZATION_FIELD_SPECS)

TEST_BLIND_FORBIDDEN_FIELDS = (
    "prediction", "model", "model_score", "confidence",
    "preannotation", "suggestion", "prompt", "self_score",
    "machine_label", "llm_label", "rule_label",
)

SUBSTITUTE_KEY_PATTERNS = (
    re.compile(r"fixture", re.IGNORECASE),
    re.compile(r"^test[-_]", re.IGNORECASE),
    re.compile(r"example", re.IGNORECASE),
    re.compile(r"dummy", re.IGNORECASE),
)

PII_PATTERNS = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b\d{15,18}[Xx]?\b"),
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URL_SCHEME_RE = re.compile(r"^https?://")
APPROVED_URL_HOSTS = None  # None = accept all; set for policy enforcement

PACK_NAMES = (
    "human_tasks_development.json",
    "human_tasks_calibration.json",
    "human_tasks_test_A.json",
    "human_tasks_test_B.json",
)


# ── Error classification ──

class InputError:
    __slots__ = ("kind", "check", "message")

    def __init__(self, kind: str, check: str, message: str) -> None:
        assert kind in ("missing", "invalid"), f"bad kind: {kind}"
        self.kind = kind
        self.check = check
        self.message = message

    def __repr__(self) -> str:
        return f"InputError({self.kind!r}, {self.check!r}, {self.message!r})"


# ── Type helpers ──

def _bool_strictly_true(x: Any) -> bool:
    return x is True


def _is_str(x: Any) -> bool:
    return isinstance(x, str) and x != ""


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_list(x: Any) -> bool:
    return isinstance(x, list)


def _is_dict(x: Any) -> bool:
    return isinstance(x, dict)


def _is_sha256(x: Any) -> bool:
    return _is_str(x) and bool(SHA256_RE.match(x))


def _is_url(x: Any) -> bool:
    if not _is_str(x):
        return False
    if not URL_SCHEME_RE.match(x):
        return False
    if APPROVED_URL_HOSTS is not None:
        from urllib.parse import urlparse
        host = urlparse(x).hostname
        if not host or host not in APPROVED_URL_HOSTS:
            return False
    return True


def _is_iso8601(x: Any) -> bool:
    if not _is_str(x):
        return False
    try:
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S",
        ):
            dt = datetime.strptime(x.replace("+00:00", "Z"), fmt if "Z" in fmt else "%Y-%m-%dT%H:%M:%S")
            break
        else:
            dt = datetime.fromisoformat(x)
        return isinstance(dt, datetime)
    except (ValueError, TypeError):
        return False


def _is_str_list(x: Any) -> bool:
    if not _is_list(x) or len(x) == 0:
        return False
    return all(_is_str(item) for item in x)


def _validate_field(val: Any, kind: str) -> bool:
    if kind == "str":
        return _is_str(val)
    elif kind == "bool_true":
        return _bool_strictly_true(val)
    elif kind == "str_list":
        return _is_str_list(val)
    elif kind == "sha256":
        return _is_sha256(val)
    elif kind == "url":
        return _is_url(val)
    elif kind == "iso8601":
        return _is_iso8601(val)
    return False


def _validate_candidate_row(idx: int, cand: Any) -> tuple[bool, list[str]]:
    if not _is_dict(cand):
        return False, [f"candidate[{idx}]: not dict"]
    bad: list[str] = []
    for field, kind in AUTHORIZATION_FIELD_SPECS:
        val = cand.get(field)
        if not _validate_field(val, kind):
            bad.append(
                f"candidate[{idx}].{field}: invalid type/value "
                f"(expected {kind}, got {type(val).__name__})"
            )
    return (len(bad) == 0), bad


# ── Real candidates ──

def _check_real_candidates(
    real_candidate_path: Path,
    real_rejections_path: Path,
    dataset_id: str | None = None,
) -> tuple[dict[str, Any], list[InputError]]:
    obs: dict[str, Any] = {
        "declared_eligible_count": None,
        "row_count": 0,
        "authorized_count": 0,
        "incomplete_count": 0,
        "duplicate_sample_ids": [],
        "duplicate_content_hashes": [],
        "fixture_contamination": [],
        "per_row_errors": [],
        "rejected_count": 0,
        "rejected_count_declared": None,
        "rejection_reasons": {},
        "rejection_reasons_declared": {},
        "rejection_count_match": False,
        "count_recompute_match": False,
        "dataset_id_match": False,
    }
    errs: list[InputError] = []

    if not real_candidate_path.exists():
        errs.append(InputError("missing", "real_candidates",
            f"real candidate export missing: {real_candidate_path}"))
        return obs, errs
    if not real_rejections_path.exists():
        errs.append(InputError("missing", "real_candidates",
            f"real rejections file missing: {real_rejections_path}"))
        return obs, errs

    try:
        data = json.loads(real_candidate_path.read_text())
    except Exception as e:
        errs.append(InputError("invalid", "real_candidates",
            f"real-candidate-export.json: JSON parse failed: {e}"))
        return obs, errs
    if not _is_dict(data):
        errs.append(InputError("invalid", "real_candidates",
            "real-candidate-export.json: top-level not dict"))
        return obs, errs

    declared = data.get("eligible_count")
    if not _is_int(declared):
        errs.append(InputError("invalid", "real_candidates",
            f"declared eligible_count={declared!r} not int"))
        declared = 0
    obs["declared_eligible_count"] = declared

    candidates = data.get("candidates") or data.get("eligible_candidates") or []
    if not _is_list(candidates):
        errs.append(InputError("invalid", "real_candidates",
            "candidates field missing or not a list"))
        return obs, errs

    row_count = len(candidates)
    obs["row_count"] = row_count
    authorized = 0
    incomplete = 0
    fixture_hits: list[str] = []
    per_row_errors: list[dict[str, Any]] = []
    seen_sids: dict[str, int] = {}
    seen_chs: dict[str, int] = {}
    dup_sample: list[str] = []
    dup_content: list[str] = []

    # Per-row dataset_id validation — collect all, verify uniqueness and manifest match
    row_dataset_ids: set[str] = set()
    has_row_without_dsid = False
    candidate_index: dict[str, dict[str, Any]] = {}
    obs["_candidate_index"] = candidate_index  # consumed downstream

    for idx, cand in enumerate(candidates):
        ok, bad_fields = _validate_candidate_row(idx, cand)
        if ok:
            authorized += 1
        else:
            incomplete += 1
            per_row_errors.append({"index": idx, "errors": bad_fields[:5]})

        if _is_dict(cand):
            sid = cand.get("sample_id")
            if _is_str(sid):
                if sid in seen_sids:
                    dup_sample.append(sid)
                else:
                    seen_sids[sid] = idx
                    # Build candidate index entry
                    entry = {
                        "dataset_id": cand.get("dataset_id"),
                        "content_sha256": cand.get("content_sha256"),
                        "source_adapter": cand.get("source_adapter"),
                        "source_version": cand.get("source_version"),
                        "captured_at": cand.get("captured_at"),
                        "authorization_basis": cand.get("authorization_basis"),
                        "pii_scanned": cand.get("pii_scanned"),
                        "pii_redacted": cand.get("pii_redacted"),
                        "profile": cand.get("profile"),
                        "language": cand.get("language"),
                        "source_tier": cand.get("source_tier"),
                        "permitted_use": cand.get("permitted_use"),
                        # Group metadata fields for cross-split isolation
                        "session_id": cand.get("session_id"),
                        "conversation_id": cand.get("conversation_id"),
                        "near_duplicate_group_id": cand.get("near_duplicate_group_id"),
                        "has_near_duplicate_group_id": "near_duplicate_group_id" in cand,
                    }
                    candidate_index[sid] = entry
                    # Collect per-row dataset_id
                    dsid = cand.get("dataset_id")
                    if _is_str(dsid):
                        row_dataset_ids.add(dsid)
                    else:
                        has_row_without_dsid = True
            ch = cand.get("content_sha256")
            if _is_str(ch):
                if ch in seen_chs:
                    dup_content.append(ch)
                else:
                    seen_chs[ch] = idx
            sid_str = str(sid or cand.get("raw_feedback_id") or "")
            if any(p.search(sid_str) for p in SUBSTITUTE_KEY_PATTERNS) or \
               _bool_strictly_true(cand.get("fixture")):
                fixture_hits.append(sid_str)

    obs["authorized_count"] = authorized
    obs["incomplete_count"] = incomplete
    obs["duplicate_sample_ids"] = dup_sample[:20]
    obs["duplicate_content_hashes"] = dup_content[:20]
    obs["fixture_contamination"] = fixture_hits[:20]
    obs["per_row_errors"] = per_row_errors[:20]
    obs["count_recompute_match"] = (declared == authorized)

    # Per-row dataset_id consistency validation
    if row_count == 0:
        # No candidate rows → no per-row validation possible
        obs["dataset_id_match"] = False
    elif has_row_without_dsid:
        errs.append(InputError("invalid", "real_candidates",
            "one or more candidate rows missing dataset_id"))
    elif len(row_dataset_ids) == 0:
        errs.append(InputError("invalid", "real_candidates",
            "no candidate rows have a valid dataset_id"))
    elif len(row_dataset_ids) > 1:
        errs.append(InputError("invalid", "real_candidates",
            f"candidate rows have inconsistent dataset_ids: {sorted(row_dataset_ids)}"))
    elif dataset_id and _is_str(dataset_id):
        actual_row_dsid = next(iter(row_dataset_ids))
        obs["dataset_id_match"] = (actual_row_dsid == dataset_id)
        if not obs["dataset_id_match"]:
            errs.append(InputError("invalid", "real_candidates",
                f"per-row dataset_id={actual_row_dsid!r} != "
                f"dataset_manifest dataset_id={dataset_id!r}"))
    else:
        obs["dataset_id_match"] = False

    # ── Real rejections: count from actual file ──
    try:
        rej_data = json.loads(real_rejections_path.read_text())
    except Exception:
        rej_data = None
    if _is_list(rej_data):
        obs["rejected_count"] = len(rej_data)
    elif _is_dict(rej_data) and _is_int(rej_data.get("count")):
        obs["rejected_count"] = rej_data["count"]
    else:
        obs["rejected_count"] = 0
    declared_rej = data.get("rejected_count")
    if _is_int(declared_rej):
        obs["rejected_count_declared"] = declared_rej
        obs["rejection_count_match"] = (declared_rej == obs["rejected_count"])
    declared_reasons = data.get("rejected_by_reason")
    if _is_dict(declared_reasons):
        obs["rejection_reasons_declared"] = dict(declared_reasons)
    if _is_list(rej_data):
        reason_counts: dict[str, int] = {}
        for r in rej_data:
            if _is_dict(r):
                for reason in r.get("reasons", []):
                    if _is_str(reason):
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        obs["rejection_reasons"] = reason_counts

    # ── Generate errors ──
    if declared != authorized:
        errs.append(InputError("invalid", "real_candidates",
            f"COUNT_RECOMPUTE_MISMATCH: declared={declared} != authorized={authorized}"))
    if incomplete > 0:
        errs.append(InputError("invalid", "real_candidates",
            f"authorization_incomplete_rows={incomplete} > 0"))
    if dup_sample:
        errs.append(InputError("invalid", "real_candidates",
            f"duplicate_sample_ids: {len(dup_sample)}"))
    if dup_content:
        errs.append(InputError("invalid", "real_candidates",
            f"duplicate_content_hashes: {len(dup_content)}"))
    if fixture_hits:
        errs.append(InputError("invalid", "real_candidates",
            f"fixture_contamination: {len(fixture_hits)} rows"))

    if obs.get("rejection_count_match") is False:
        errs.append(InputError("invalid", "real_candidates",
            f"rejection_count_mismatch: declared={declared_rej} "
            f"!= actual={obs['rejected_count']}"))

    if authorized < MIN_AUTHORIZED_CANDIDATES:
        if row_count == 0 and declared == 0:
            errs.append(InputError("missing", "real_candidates",
                f"no real authorized candidates: authorized={authorized} < {MIN_AUTHORIZED_CANDIDATES}"))
        else:
            errs.append(InputError("invalid", "real_candidates",
                f"insufficient authorized: {authorized} < {MIN_AUTHORIZED_CANDIDATES}"))

    return obs, errs


# ── Production signing key ──

def _check_production_signing_key(
    environment: str | None = None,
    env_override: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[InputError]]:
    env = env_override or os.environ
    obs: dict[str, Any] = {
        "environment": environment or env.get(ENV_VAR_ENVIRONMENT, "") or "",
        "prod_key_present": False, "key_id": None,
        "key_algorithm": "HMAC-SHA256",
        "substitute_detected": False, "substitute_reason": None,
    }
    errs: list[InputError] = []
    prod_key = env.get(ENV_VAR_PROD_KEY)
    test_key = env.get(ENV_VAR_TEST_KEY)
    if not _is_str(prod_key):
        errs.append(InputError("missing", "production_signing_key",
            f"{ENV_VAR_PROD_KEY} not set"))
        return obs, errs
    obs["prod_key_present"] = True
    if any(p.search(prod_key) for p in SUBSTITUTE_KEY_PATTERNS):
        obs["substitute_detected"] = True
        obs["substitute_reason"] = "matches fixture/test/example/dummy pattern"
        errs.append(InputError("invalid", "production_signing_key",
            "production key matches substitute pattern"))
    elif _is_str(test_key) and test_key == prod_key:
        obs["substitute_detected"] = True
        obs["substitute_reason"] = "production key == test key"
        errs.append(InputError("invalid", "production_signing_key",
            "production key identical to test key"))
    elif environment in ALLOWED_TEST_ENVIRONMENTS:
        obs["substitute_detected"] = True
        obs["substitute_reason"] = "production key in test environment"
        errs.append(InputError("invalid", "production_signing_key",
            "production key present in test environment"))
    else:
        obs["key_id"] = "production-key"
    return obs, errs


# ── Human roles ──

def _check_human_roles(
    roles: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[InputError]]:
    obs: dict[str, Any] = {
        "annotator_a_ready": False, "annotator_b_ready": False,
        "adjudicator_ready": False,
        "annotator_a_pseudonym": None, "annotator_b_pseudonym": None,
        "adjudicator_pseudonym": None,
        "roles_distinct": False, "access_boundary_ok": False,
        "double_label_plan_count": 0, "double_label_ratio": 0.0,
        "meets_double_label_minimum": False,
    }
    errs: list[InputError] = []
    if roles is None:
        errs.append(InputError("missing", "human_roles", "roles config not provided"))
        return obs, errs
    if not _is_dict(roles):
        errs.append(InputError("invalid", "human_roles", "roles config not a dict"))
        return obs, errs

    a = roles.get("annotator_a_pseudonym")
    b = roles.get("annotator_b_pseudonym")
    adj = roles.get("adjudicator_pseudonym")
    obs["annotator_a_ready"] = _is_str(a)
    obs["annotator_b_ready"] = _is_str(b)
    obs["adjudicator_ready"] = _is_str(adj)
    if _is_str(a):
        obs["annotator_a_pseudonym"] = a
    if _is_str(b):
        obs["annotator_b_pseudonym"] = b
    if _is_str(adj):
        obs["adjudicator_pseudonym"] = adj

    missing = [n for n in ("annotator_a_pseudonym", "annotator_b_pseudonym",
                             "adjudicator_pseudonym") if not _is_str(roles.get(n))]
    if missing:
        errs.append(InputError("invalid", "human_roles",
            f"missing pseudonyms: {missing}"))

    if _is_str(a) and _is_str(b) and _is_str(adj):
        distinct = len({a, b, adj}) == 3
        obs["roles_distinct"] = distinct
        if not distinct:
            errs.append(InputError("invalid", "human_roles",
                "roles not distinct: A/B/adjudicator pseudonyms collide"))

    a_b_isolation = roles.get("a_b_access_isolation")
    if _bool_strictly_true(a_b_isolation):
        obs["access_boundary_ok"] = True
    else:
        errs.append(InputError("invalid", "human_roles",
            "a_b_access_isolation not set true"))

    plan = roles.get("double_label_plan_count")
    total = roles.get("total_candidate_count") or 0
    if _is_int(plan):
        obs["double_label_plan_count"] = plan
        if _is_int(total) and total > 0:
            ratio = plan / total
            obs["double_label_ratio"] = round(ratio, 4)
            required = max(MIN_DOUBLE_LABEL, int(total * DOUBLE_LABEL_RATIO + 0.999))
            obs["meets_double_label_minimum"] = plan >= required
            if plan < required:
                errs.append(InputError("invalid", "human_roles",
                    f"double-label plan {plan} < required {required}"))
        elif plan < MIN_DOUBLE_LABEL:
            errs.append(InputError("invalid", "human_roles",
                f"double-label plan {plan} < minimum {MIN_DOUBLE_LABEL}"))
    else:
        errs.append(InputError("invalid", "human_roles",
            "double_label_plan_count missing or not int"))
    return obs, errs


# ── Test blind leakage ──

def _check_test_blind_leakage(
    test_packs: list[dict[str, Any]] | None,
    test_tasks: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[InputError]]:
    obs: dict[str, Any] = {
        "test_blind_count": 0, "leakage_count": 0,
        "leaked_fields": [], "leaked_samples": [],
        "test_unique_task_count": 0,
    }
    errs: list[InputError] = []
    if test_packs is None:
        errs.append(InputError("missing", "test_blind_leakage",
            "test packs not provided"))
        return obs, errs
    if not _is_list(test_packs):
        errs.append(InputError("invalid", "test_blind_leakage",
            "test packs not a list"))
        return obs, errs

    obs["test_blind_count"] = len(test_packs)
    leaked_fields: set[str] = set()
    leaked_samples: list[str] = []
    all_test_samples: set[str] = set()

    for idx, pack in enumerate(test_packs):
        if not _is_dict(pack):
            continue
        # Check pack-level
        for field in TEST_BLIND_FORBIDDEN_FIELDS:
            if field in pack:
                leaked_fields.add(field)
                leaked_samples.append(f"pack[{idx}].{field}")
        # Check tasks
        tasks = pack.get("tasks") or pack.get("samples") or []
        if _is_list(tasks):
            for s_idx, task in enumerate(tasks):
                if not _is_dict(task):
                    continue
                sid = task.get("sample_id")
                if _is_str(sid):
                    all_test_samples.add(sid)
                for field in TEST_BLIND_FORBIDDEN_FIELDS:
                    if field in task:
                        leaked_fields.add(field)
                        leaked_samples.append(f"pack[{idx}].task[{s_idx}].{field}")

    obs["test_unique_task_count"] = len(all_test_samples)
    obs["leakage_count"] = len(leaked_samples)
    obs["leaked_fields"] = sorted(leaked_fields)
    obs["leaked_samples"] = leaked_samples[:20]

    if obs["test_unique_task_count"] < MIN_TEST_BLIND:
        errs.append(InputError("invalid", "test_blind_leakage",
            f"test_unique_task_count={obs['test_unique_task_count']} < {MIN_TEST_BLIND}"))
    if leaked_samples:
        errs.append(InputError("invalid", "test_blind_leakage",
            f"test blind leakage: {len(leaked_samples)} forbidden fields: {sorted(leaked_fields)}"))

    if test_tasks:
        for idx, task in enumerate(test_tasks):
            if not _is_dict(task):
                continue
            for field in TEST_BLIND_FORBIDDEN_FIELDS:
                if field in task:
                    leaked_fields.add(field)
                    leaked_samples.append(f"test_task[{idx}].{field}")
        obs["leakage_count"] = len(leaked_samples)
        if leaked_samples:
            errs.append(InputError("invalid", "test_blind_leakage",
                f"test blind leakage: {len(leaked_samples)} forbidden fields"))

    return obs, errs


# ── PII scan ──

def _check_pii_scan(
    candidates: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], list[InputError]]:
    obs: dict[str, Any] = {"scanned_count": 0, "pii_hit_count": 0, "pii_patterns_hit": []}
    errs: list[InputError] = []
    if candidates is None:
        errs.append(InputError("missing", "pii_scan", "candidates not provided for PII scan"))
        return obs, errs
    if not _is_list(candidates):
        errs.append(InputError("invalid", "pii_scan", "candidates not a list"))
        return obs, errs
    obs["scanned_count"] = len(candidates)
    pattern_hits: set[str] = set()
    total = 0
    for cand in candidates:
        if not _is_dict(cand):
            continue
        for f in ("raw_text", "redacted_text", "feedback_text", "content"):
            t = cand.get(f)
            if not _is_str(t):
                continue
            for p in PII_PATTERNS:
                if p.search(t):
                    pattern_hits.add(p.pattern)
                    total += 1
    obs["pii_hit_count"] = total
    obs["pii_patterns_hit"] = sorted(pattern_hits)
    if total > 0:
        errs.append(InputError("invalid", "pii_scan", f"PII scan: {total} potential matches"))
    return obs, errs


# ── Split isolation ──

def _check_split_isolation(
    splits: dict[str, list[str]] | None,
    all_candidate_ids: set[str] | None = None,
    content_hash_by_sample: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[InputError]]:
    obs: dict[str, Any] = {
        "development_count": 0, "calibration_count": 0, "test_count": 0,
        "cross_split_overlap": [], "minimums_met": False,
        "candidate_coverage_match": False,
    }
    errs: list[InputError] = []
    if splits is None:
        errs.append(InputError("missing", "split_isolation", "splits not provided"))
        return obs, errs
    if not _is_dict(splits):
        errs.append(InputError("invalid", "split_isolation", "splits not a dict"))
        return obs, errs
    dev = splits.get("development") or []
    cal = splits.get("calibration") or []
    tst = splits.get("test") or []
    if not (_is_list(dev) and _is_list(cal) and _is_list(tst)):
        errs.append(InputError("invalid", "split_isolation", "splits must be lists"))
        return obs, errs

    obs["development_count"] = len(dev)
    obs["calibration_count"] = len(cal)
    obs["test_count"] = len(tst)

    dev_s, cal_s, tst_s = set(dev), set(cal), set(tst)
    overlaps: list[str] = []
    dc, dt, ct = dev_s & cal_s, dev_s & tst_s, cal_s & tst_s
    if dc:
        overlaps.append(f"dev∩cal:{len(dc)}")
    if dt:
        overlaps.append(f"dev∩test:{len(dt)}")
    if ct:
        overlaps.append(f"cal∩test:{len(ct)}")
    obs["cross_split_overlap"] = overlaps
    if overlaps:
        errs.append(InputError("invalid", "split_isolation",
            f"cross-split overlap: {';'.join(overlaps)}"))

    # Content-hash-based overlap: same content sha must not appear in different splits
    if content_hash_by_sample:
        ch_dev = {content_hash_by_sample.get(sid) for sid in dev if content_hash_by_sample.get(sid)}
        ch_cal = {content_hash_by_sample.get(sid) for sid in cal if content_hash_by_sample.get(sid)}
        ch_tst = {content_hash_by_sample.get(sid) for sid in tst if content_hash_by_sample.get(sid)}
        ch_overlaps = []
        if ch_dev & ch_cal:
            ch_overlaps.append("dev∩cal(content_hash)")
        if ch_dev & ch_tst:
            ch_overlaps.append("dev∩test(content_hash)")
        if ch_cal & ch_tst:
            ch_overlaps.append("cal∩test(content_hash)")
        if ch_overlaps:
            errs.append(InputError("invalid", "split_isolation",
                f"content-hash cross-split: {';'.join(ch_overlaps)}"))

    # Candidate coverage: split ids union must match authorized candidate ids exactly
    if all_candidate_ids:
        split_union = dev_s | cal_s | tst_s
        obs["candidate_coverage_match"] = (split_union == all_candidate_ids)
        if not obs["candidate_coverage_match"]:
            missing_from_splits = all_candidate_ids - split_union
            extra_in_splits = split_union - all_candidate_ids
            parts = []
            if missing_from_splits:
                parts.append(f"missing_from_splits:{len(missing_from_splits)}")
            if extra_in_splits:
                parts.append(f"extra_in_splits:{len(extra_in_splits)}")
            errs.append(InputError("invalid", "split_isolation",
                f"split-candidate mismatch: {';'.join(parts)}"))

    obs["minimums_met"] = (
        len(dev) >= MIN_DEVELOPMENT and len(cal) >= MIN_CALIBRATION
        and len(tst) >= MIN_TEST_BLIND)
    if not obs["minimums_met"]:
        errs.append(InputError("invalid", "split_isolation",
            f"minimums not met: dev={len(dev)}/{MIN_DEVELOPMENT} "
            f"cal={len(cal)}/{MIN_CALIBRATION} test={len(tst)}/{MIN_TEST_BLIND}"))
    return obs, errs


# ── Annotation governance ──

def _check_annotation_governance(
    governance: dict[str, Any] | None,
    a_role: str | None = None,
    b_role: str | None = None,
    adj_role: str | None = None,
) -> tuple[dict[str, Any], list[InputError]]:
    obs: dict[str, Any] = {
        "annotation_window_start": None, "annotation_window_end": None,
        "retention_until": None, "allowed_access_role_ids": [],
        "window_valid": False, "retention_valid": False,
        "access_list_valid": False, "access_covers_roles": False,
    }
    errs: list[InputError] = []
    if governance is None:
        errs.append(InputError("missing", "annotation_governance",
            "governance config not provided"))
        return obs, errs
    if not _is_dict(governance):
        errs.append(InputError("invalid", "annotation_governance",
            "governance config not a dict"))
        return obs, errs

    start = governance.get("annotation_window_start")
    end = governance.get("annotation_window_end")
    retention = governance.get("retention_until")
    access = governance.get("allowed_access_role_ids")

    obs["annotation_window_start"] = start if _is_str(start) else None
    obs["annotation_window_end"] = end if _is_str(end) else None
    obs["retention_until"] = retention if _is_str(retention) else None
    obs["allowed_access_role_ids"] = access if _is_list(access) else []

    # Parse as datetime for proper comparison — must be timezone-aware
    start_dt = None
    end_dt = None
    ret_dt = None
    try:
        if _is_str(start):
            start_dt = datetime.fromisoformat(start)
        if _is_str(end):
            end_dt = datetime.fromisoformat(end)
        if _is_str(retention):
            ret_dt = datetime.fromisoformat(retention)
    except (ValueError, TypeError):
        errs.append(InputError("invalid", "annotation_governance",
            "dates must be valid ISO 8601"))
        return obs, errs

    # Reject naive datetimes (no timezone) — must NOT continue to comparison
    naive_errors = 0
    if start_dt and start_dt.tzinfo is None:
        errs.append(InputError("invalid", "annotation_governance",
            f"annotation_window_start must be timezone-aware: {start}"))
        naive_errors += 1
    if end_dt and end_dt.tzinfo is None:
        errs.append(InputError("invalid", "annotation_governance",
            f"annotation_window_end must be timezone-aware: {end}"))
        naive_errors += 1
    if ret_dt and ret_dt.tzinfo is None:
        errs.append(InputError("invalid", "annotation_governance",
            f"retention_until must be timezone-aware: {retention}"))
        naive_errors += 1

    # Only compare if all datetimes are timezone-aware (avoid TypeError)
    if naive_errors > 0:
        return obs, errs

    if not (start_dt and end_dt):
        errs.append(InputError("invalid", "annotation_governance",
            "annotation_window_start/end must be ISO 8601"))
    elif start_dt >= end_dt:
        errs.append(InputError("invalid", "annotation_governance",
            f"window_start >= window_end: {start} >= {end}"))
    else:
        obs["window_valid"] = True

    if not ret_dt:
        errs.append(InputError("invalid", "annotation_governance",
            "retention_until must be ISO 8601"))
    elif end_dt and ret_dt <= end_dt:
        errs.append(InputError("invalid", "annotation_governance",
            f"retention_until <= window_end: {retention} <= {end}"))
    else:
        obs["retention_valid"] = True

    if not _is_str_list(access):
        errs.append(InputError("invalid", "annotation_governance",
            "allowed_access_role_ids must be non-empty str list"))
    else:
        obs["access_list_valid"] = True
        # Access must cover all three roles
        if a_role and b_role and adj_role:
            access_set = set(access)
            uncovered = []
            for role_name, role_val in [("A", a_role), ("B", b_role), ("adj", adj_role)]:
                if role_val not in access_set:
                    uncovered.append(f"{role_name}:{role_val}")
            if uncovered:
                errs.append(InputError("invalid", "annotation_governance",
                    f"access list does not cover roles: {uncovered}"))
            else:
                obs["access_covers_roles"] = True
        else:
            obs["access_covers_roles"] = True  # no roles to check

    return obs, errs


# ── Pack trust verification (reuse 1A verifier) ──

def _check_pack_trust(
    manifest_path: Path | None,
    task_dir: Path | None,
    key: str | None,
    expected_key_id: str | None,
    dataset_manifest_path: Path | None,
) -> tuple[dict[str, Any], list[InputError]]:
    """Verify pack manifest using P13-2-2-1A verifier."""
    from signal_miner.evaluation.pack_trust import verify_manifest_file

    obs: dict[str, Any] = {
        "manifest_path": str(manifest_path) if manifest_path else None,
        "task_dir": str(task_dir) if task_dir else None,
        "dataset_manifest_path": str(dataset_manifest_path) if dataset_manifest_path else None,
        "valid": False, "errors": [],
    }
    errs: list[InputError] = []

    if manifest_path is None:
        errs.append(InputError("missing", "pack_trust", "pack manifest not provided"))
        return obs, errs
    if dataset_manifest_path is None:
        errs.append(InputError("missing", "pack_trust", "dataset manifest not provided"))
        return obs, errs
    if task_dir is None:
        errs.append(InputError("missing", "pack_trust", "task_dir not provided"))
        return obs, errs

    if not manifest_path.exists():
        errs.append(InputError("missing", "pack_trust",
            f"pack manifest not found: {manifest_path}"))
        return obs, errs

    result = verify_manifest_file(
        manifest_path=manifest_path,
        task_dir=task_dir,
        key=key,
        expected_key_id=expected_key_id,
        dataset_manifest_path=dataset_manifest_path,
    )
    obs["valid"] = result.get("valid", False) is True
    obs["errors"] = result.get("errors", [])
    if not obs["valid"]:
        errs.append(InputError("invalid", "pack_trust",
            f"manifest verification failed: {len(obs['errors'])} errors"))
    return obs, errs


# ── Task identity verification (reuse 1A compute_task_hash) ──

def _check_task_identity(
    task_dir: Path | None,
) -> tuple[dict[str, Any], list[InputError]]:
    """Verify task hashes by recomputing compute_task_hash() per task."""
    from signal_miner.evaluation.human_annotation import compute_task_hash

    obs: dict[str, Any] = {
        "tasks_scanned": 0, "hash_mismatches": [],
        "empty_packs": [], "development_tasks": 0,
        "calibration_tasks": 0, "test_a_tasks": 0, "test_b_tasks": 0,
    }
    errs: list[InputError] = []

    if task_dir is None:
        errs.append(InputError("missing", "task_identity", "task_dir not provided"))
        return obs, errs

    if not task_dir.exists() or not task_dir.is_dir():
        errs.append(InputError("invalid", "task_identity",
            f"task_dir not found or not a directory: {task_dir}"))
        return obs, errs

    for pack_name in PACK_NAMES:
        pf = task_dir / pack_name
        if not pf.exists():
            errs.append(InputError("missing", "task_identity",
                f"pack file missing: {pack_name}"))
            continue
        try:
            pack = json.loads(pf.read_text())
        except Exception as e:
            errs.append(InputError("invalid", "task_identity",
                f"{pack_name}: JSON parse error: {e}"))
            continue
        if not _is_dict(pack):
            errs.append(InputError("invalid", "task_identity",
                f"{pack_name}: not a dict"))
            continue
        tasks = pack.get("tasks", [])
        if not _is_list(tasks):
            errs.append(InputError("invalid", "task_identity",
                f"{pack_name}: tasks not a list"))
            continue
        if len(tasks) == 0:
            obs["empty_packs"].append(pack_name)

        if "development" in pack_name:
            obs["development_tasks"] = len(tasks)
        elif "calibration" in pack_name:
            obs["calibration_tasks"] = len(tasks)
        elif "test_A" in pack_name:
            obs["test_a_tasks"] = len(tasks)
        elif "test_B" in pack_name:
            obs["test_b_tasks"] = len(tasks)

        for idx, task in enumerate(tasks):
            if not _is_dict(task):
                continue
            obs["tasks_scanned"] += 1
            dsid = task.get("dataset_id")
            sid = task.get("sample_id")
            slot = task.get("annotator_slot")
            ch = task.get("content_hash")
            declared_th = task.get("task_hash")
            fixture = _bool_strictly_true(task.get("fixture", False))
            if not all(_is_str(x) for x in (dsid, sid, slot, ch, declared_th)):
                obs["hash_mismatches"].append(
                    f"{pack_name}.task[{idx}]: missing required fields")
                continue
            expected_th = compute_task_hash(dsid, sid, slot, ch, fixture)
            if expected_th != declared_th:
                obs["hash_mismatches"].append(
                    f"{pack_name}.task[{idx}]({sid}): "
                    f"declared={declared_th[:16]}... expected={expected_th[:16]}...")

    if obs["empty_packs"]:
        errs.append(InputError("invalid", "task_identity",
            f"empty packs: {obs['empty_packs']}"))
    if obs["hash_mismatches"]:
        errs.append(InputError("invalid", "task_identity",
            f"task hash mismatches: {len(obs['hash_mismatches'])}"))
    if obs["test_a_tasks"] + obs["test_b_tasks"] < MIN_TEST_BLIND:
        errs.append(InputError("invalid", "task_identity",
            f"total test tasks {obs['test_a_tasks']+obs['test_b_tasks']} < {MIN_TEST_BLIND}"))

    return obs, errs


# ── Recompute double-label from actual task packs ──

def _recompute_double_label_from_packs(
    task_dir: Path | None,
    authorized_candidate_count: int = 0,
) -> tuple[dict[str, Any], list[InputError]]:
    """Read test_A and test_B packs, find shared sample_ids → double-label count.

    Also verify A/B slot isolation: A pack must only contain slot 'A' tasks,
    B pack must only contain slot 'B' tasks. No cross-reading of labels.
    """
    obs: dict[str, Any] = {
        "double_label_actual_count": 0,
        "double_label_sample_ids": [],
        "slot_isolation_ok": True,
        "slot_violations": [],
    }
    errs: list[InputError] = []

    if task_dir is None:
        return obs, errs

    a_path = task_dir / "human_tasks_test_A.json"
    b_path = task_dir / "human_tasks_test_B.json"

    a_samples: set[str] = set()
    b_samples: set[str] = set()
    slot_violations: list[str] = []

    for path, expected_slot, samples_set in [
        (a_path, "A", a_samples),
        (b_path, "B", b_samples),
    ]:
        if not path.exists():
            continue
        try:
            pack = json.loads(path.read_text())
        except Exception:
            continue
        if not _is_dict(pack):
            continue
        tasks = pack.get("tasks", [])
        if not _is_list(tasks):
            continue
        for idx, task in enumerate(tasks):
            if not _is_dict(task):
                continue
            sid = task.get("sample_id")
            slot = task.get("annotator_slot")
            if _is_str(sid):
                samples_set.add(sid)
            if _is_str(slot) and slot != expected_slot:
                slot_violations.append(
                    f"{path.name}.task[{idx}]: slot={slot} != expected {expected_slot}"
                )
        # Also check for B label presence in A pack, and vice versa
        for field in ("label", "annotation", "human_label", "b_label", "a_label"):
            for idx, task in enumerate(tasks):
                if not _is_dict(task):
                    continue
                if field in task:
                    slot_violations.append(
                        f"{path.name}.task[{idx}]: contains cross-slot field '{field}'"
                    )

    double = a_samples & b_samples
    obs["double_label_actual_count"] = len(double)
    obs["double_label_sample_ids"] = sorted(double)[:20]
    obs["slot_violations"] = slot_violations[:20]
    obs["slot_isolation_ok"] = len(slot_violations) == 0

    if not obs["slot_isolation_ok"]:
        errs.append(InputError("invalid", "task_identity",
            f"A/B slot isolation violated: {len(slot_violations)} issues"))

    # Double-label threshold: max(20, ceil(authorized_candidate_count * 0.2))
    req_base = authorized_candidate_count if authorized_candidate_count > 0 else len(a_samples | b_samples)
    required = max(MIN_DOUBLE_LABEL, int(req_base * DOUBLE_LABEL_RATIO + 0.999))
    if len(double) < required:
        errs.append(InputError("invalid", "task_identity",
            f"double-label actual={len(double)} < required={required} "
            f"(authorized_candidates={authorized_candidate_count})"))
    obs["required_double_label"] = required

    return obs, errs


# ── Task-candidate-split binding ──

def _check_task_candidate_binding(
    task_dir: Path | None,
    candidate_index: dict[str, dict[str, Any]],
    splits: dict[str, list[str]] | None,
    dataset_id: str | None,
) -> tuple[dict[str, Any], list[InputError]]:
    """Verify each task binds to authorized candidate + correct split."""
    obs: dict[str, Any] = {
        "tasks_checked": 0,
        "binding_errors": [],
        "a_b_content_hash_mismatches": [],
    }
    errs: list[InputError] = []

    if task_dir is None:
        errs.append(InputError("missing", "task_candidate_binding",
            "task_dir not provided"))
        return obs, errs

    if not candidate_index:
        errs.append(InputError("invalid", "task_candidate_binding",
            "candidate_index is empty"))
        return obs, errs

    # Build reverse index: sample_id → split name
    sample_to_split: dict[str, str] = {}
    if splits and _is_dict(splits):
        for split_name in ("development", "calibration", "test"):
            ids = splits.get(split_name, [])
            if _is_list(ids):
                for sid in ids:
                    if _is_str(sid):
                        sample_to_split[sid] = split_name

    # A/B content_hash consistency tracker
    a_content_hashes: dict[str, str] = {}

    for pack_name in PACK_NAMES:
        pf = task_dir / pack_name
        if not pf.exists():
            continue
        try:
            pack = json.loads(pf.read_text())
        except Exception:
            continue
        if not _is_dict(pack):
            continue
        tasks = pack.get("tasks", [])
        if not _is_list(tasks):
            continue
        for idx, task in enumerate(tasks):
            if not _is_dict(task):
                continue
            obs["tasks_checked"] += 1
            task_dsid = task.get("dataset_id")
            task_sid = task.get("sample_id")
            task_ch = task.get("content_hash")
            task_split = task.get("split")
            task_slot = task.get("annotator_slot")

            # Check dataset_id match
            if (_is_str(task_dsid) and dataset_id and _is_str(dataset_id)
                    and task_dsid != dataset_id):
                obs["binding_errors"].append(
                        f"{pack_name}.task[{idx}]({task_sid}): "
                        f"dataset_id={task_dsid!r} != expected {dataset_id!r}")

            # Check sample_id in candidate_index
            if _is_str(task_sid):
                ci = candidate_index.get(task_sid)
                if ci is None:
                    obs["binding_errors"].append(
                        f"{pack_name}.task[{idx}]({task_sid}): "
                        "sample_id not in authorized candidates")
                else:
                    # Check content_hash matches candidate
                    expected_ch = ci.get("content_sha256")
                    if (_is_str(task_ch) and _is_str(expected_ch)
                            and task_ch != expected_ch):
                        obs["binding_errors"].append(
                                f"{pack_name}.task[{idx}]({task_sid}): "
                                f"content_hash mismatch "
                                f"task={task_ch[:16]}... vs "
                                f"candidate={expected_ch[:16]}...")
                    # Check split matches frozen assignment
                    expected_split = sample_to_split.get(task_sid)
                    if _is_str(expected_split) and _is_str(task_split):
                        if task_split != expected_split:
                            obs["binding_errors"].append(
                                f"{pack_name}.task[{idx}]({task_sid}): "
                                f"split={task_split!r} != "
                                f"frozen split={expected_split!r}")
                    elif _is_str(expected_split) and not _is_str(task_split):
                        obs["binding_errors"].append(
                            f"{pack_name}.task[{idx}]({task_sid}): "
                            "missing split field")

                    # A/B content_hash consistency
                    if _is_str(task_slot) and task_slot == "A":
                        if _is_str(task_ch):
                            a_content_hashes[task_sid] = task_ch
                    elif _is_str(task_slot) and task_slot == "B":
                        a_ch = a_content_hashes.get(task_sid)
                        if _is_str(a_ch) and _is_str(task_ch) and a_ch != task_ch:
                            obs["a_b_content_hash_mismatches"].append(task_sid)

    if obs["binding_errors"]:
        errs.append(InputError("invalid", "task_candidate_binding",
            f"binding errors: {len(obs['binding_errors'])}"))
    if obs["a_b_content_hash_mismatches"]:
        errs.append(InputError("invalid", "task_candidate_binding",
            f"A/B content_hash mismatches: "
            f"{len(obs['a_b_content_hash_mismatches'])} samples"))

    return obs, errs


# ── Group isolation ──

GROUP_METADATA_FIELDS = ("session_id", "conversation_id", "near_duplicate_group_id")


def _check_group_isolation(
    candidate_index: dict[str, dict[str, Any]],
    splits: dict[str, list[str]] | None,
) -> tuple[dict[str, Any], list[InputError]]:
    """Check per-candidate group metadata + cross-split group isolation.

    Every candidate must have non-empty session_id and conversation_id.
    near_duplicate_group_id may be None (explicit absence), but the field
    must exist in the candidate row.
    """
    obs: dict[str, Any] = {
        "groups_checked": 0,
        "cross_split_groups": [],
        "missing_group_metadata": False,
        "missing_group_rows": [],
    }
    errs: list[InputError] = []

    if splits is None:
        return obs, errs

    # Build sample_id → split mapping
    sample_to_split: dict[str, str] = {}
    for split_name in ("development", "calibration", "test"):
        ids = splits.get(split_name, [])
        if _is_list(ids):
            for sid in ids:
                if _is_str(sid):
                    sample_to_split[sid] = split_name

    # Per-row validation: every candidate must have required group metadata
    missing_rows: list[str] = []
    for sid, ci in candidate_index.items():
        session = ci.get("session_id")
        conv = ci.get("conversation_id")
        has_ndg = ci.get("has_near_duplicate_group_id", False)
        if not _is_str(session) or not _is_str(conv) or not has_ndg:
            missing_rows.append(sid)

    obs["missing_group_rows"] = missing_rows[:20]
    if missing_rows:
        obs["missing_group_metadata"] = True
        errs.append(InputError("invalid", "group_isolation",
            f"{len(missing_rows)} candidate rows missing required group metadata "
            f"(session_id, conversation_id, near_duplicate_group_id): "
            f"{missing_rows[:5]}"))

    # Cross-split group leakage check
    if not missing_rows:
        for group_field in GROUP_METADATA_FIELDS:
            group_to_splits: dict[str, set[str]] = {}
            for sid, ci in candidate_index.items():
                gv = ci.get(group_field)
                # For near_duplicate_group_id: only group if non-null non-empty string
                if group_field == "near_duplicate_group_id":
                    has_ndg = ci.get("has_near_duplicate_group_id", False)
                    # ndg is None or empty → no near-duplicate, skip grouping
                    if not has_ndg or not _is_str(gv):
                        continue
                if not _is_str(gv):
                    continue
                split = sample_to_split.get(sid)
                if not _is_str(split):
                    continue
                if gv not in group_to_splits:
                    group_to_splits[gv] = set()
                group_to_splits[gv].add(split)
            obs["groups_checked"] += 1
            for gv, splits_in_group in group_to_splits.items():
                if len(splits_in_group) > 1:
                    obs["cross_split_groups"].append(
                        f"{group_field}={gv} in {sorted(splits_in_group)}")
    else:
        obs["missing_group_metadata"] = True

    if obs["cross_split_groups"]:
        errs.append(InputError("invalid", "group_isolation",
            f"cross-split group leakage: {obs['cross_split_groups']}"))

    return obs, errs

def assess_readiness(
    *,
    real_candidate_path: Path,
    real_rejections_path: Path,
    dataset_manifest_path: Path | None = None,
    pack_manifest_path: Path | None = None,
    task_dir: Path | None = None,
    roles: dict[str, Any] | None = None,
    splits: dict[str, list[str]] | None = None,
    governance: dict[str, Any] | None = None,
    roles_config_path: Path | None = None,
    splits_config_path: Path | None = None,
    governance_config_path: Path | None = None,
    environment: str | None = None,
    env_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    all_errs: list[InputError] = []
    checks: dict[str, Any] = {}

    # Dataset_id from dataset manifest
    dataset_id: str | None = None
    if dataset_manifest_path and dataset_manifest_path.exists():
        try:
            dm = json.loads(dataset_manifest_path.read_text())
            if _is_dict(dm):
                dataset_id = dm.get("dataset_id")
        except Exception:
            pass

    # 1. Candidates
    c_obs, c_errs = _check_real_candidates(
        real_candidate_path, real_rejections_path, dataset_id)
    checks["real_candidates"] = c_obs
    all_errs.extend(c_errs)

    # 2. Signing key
    k_obs, k_errs = _check_production_signing_key(environment, env_override)
    checks["production_signing_key"] = k_obs
    all_errs.extend(k_errs)

    # 3. Human roles
    r_obs, r_errs = _check_human_roles(roles)
    checks["human_roles"] = r_obs
    all_errs.extend(r_errs)

    # 4. Pack trust (1A verifier)
    key = (env_override or os.environ).get(ENV_VAR_PROD_KEY)
    pt_obs, pt_errs = _check_pack_trust(
        pack_manifest_path, task_dir, key if _is_str(key) else None,
        None, dataset_manifest_path)
    checks["pack_trust"] = pt_obs
    all_errs.extend(pt_errs)

    # 5. Task identity (1A compute_task_hash)
    ti_obs, ti_errs = _check_task_identity(task_dir)
    checks["task_identity"] = ti_obs
    all_errs.extend(ti_errs)

    # 6. Double-label from actual packs (using authorized count)
    authorized_count = c_obs.get("authorized_count", 0)
    dl_obs, dl_errs = _recompute_double_label_from_packs(task_dir, authorized_count)
    checks["double_label_recomputed"] = dl_obs
    all_errs.extend(dl_errs)

    # 7. Task-candidate-split binding
    candidate_index: dict[str, dict[str, Any]] = c_obs.get("_candidate_index", {})
    tc_obs, tc_errs = _check_task_candidate_binding(
        task_dir, candidate_index, splits, dataset_id)
    checks["task_candidate_binding"] = tc_obs
    all_errs.extend(tc_errs)

    # 8. Group isolation
    gi_obs, gi_errs = _check_group_isolation(candidate_index, splits)
    checks["group_isolation"] = gi_obs
    all_errs.extend(gi_errs)

    # 9. Test blind leakage (from packs)
    test_packs: list[dict[str, Any]] | None = None
    if task_dir and task_dir.exists():
        test_packs = []
        for name in ("human_tasks_test_A.json", "human_tasks_test_B.json"):
            pf = task_dir / name
            if pf.exists():
                with contextlib.suppress(Exception):
                    test_packs.append(json.loads(pf.read_text()))
    tb_obs, tb_errs = _check_test_blind_leakage(test_packs)
    checks["test_blind_leakage"] = tb_obs
    all_errs.extend(tb_errs)

    # 10. Split isolation (with candidate binding)
    auth_ids: set[str] = set(candidate_index.keys())
    content_ch_by_sample: dict[str, str] = {
        sid: ci.get("content_sha256", "") for sid, ci in candidate_index.items()
        if _is_str(ci.get("content_sha256"))
    }
    s_obs, s_errs = _check_split_isolation(splits, auth_ids, content_ch_by_sample)
    checks["split_isolation"] = s_obs
    all_errs.extend(s_errs)

    # 11. PII scan
    candidates_for_pii: list[dict[str, Any]] | None = None
    try:
        rc_data2 = json.loads(real_candidate_path.read_text()) if real_candidate_path.exists() else {}
    except Exception:
        rc_data2 = {}
    if _is_dict(rc_data2):
        cs = rc_data2.get("candidates") or []
        if _is_list(cs):
            candidates_for_pii = cs
    p_obs, p_errs = _check_pii_scan(candidates_for_pii)
    checks["pii_scan"] = p_obs
    all_errs.extend(p_errs)

    # 12. Governance
    g_obs, g_errs = _check_annotation_governance(
        governance,
        r_obs.get("annotator_a_pseudonym"),
        r_obs.get("annotator_b_pseudonym"),
        r_obs.get("adjudicator_pseudonym"),
    )
    checks["annotation_governance"] = g_obs
    all_errs.extend(g_errs)

    # ── Classify ──
    missing_errs = [e for e in all_errs if e.kind == "missing"]
    invalid_errs = [e for e in all_errs if e.kind == "invalid"]

    if not all_errs:
        status = "READY_FOR_HUMAN_ANNOTATION"
        passed = True
        exit_code = 0
        blockers: list[str] = []
    elif invalid_errs:
        status = "FAILED_INVALID_INPUT"
        passed = False
        exit_code = 1
        blockers = sorted({e.check for e in invalid_errs})
    else:
        status = "BLOCKED_INPUT_REQUIRED"
        passed = False
        exit_code = 2
        blockers = sorted({e.check for e in missing_errs})

    error_messages = [f"[{e.kind}] {e.check}: {e.message}" for e in all_errs]

    check_passed: dict[str, bool] = {}
    for cn in ("real_candidates", "production_signing_key", "human_roles",
               "pack_trust", "task_identity", "task_candidate_binding",
               "group_isolation", "test_blind_leakage",
               "split_isolation", "pii_scan", "annotation_governance"):
        check_passed[cn] = not any(e for e in all_errs if e.check == cn)

    # Derive all input SHAs for batch_id
    def _file_sha(p: Path | None) -> str | None:
        if p and p.exists():
            return hashlib.sha256(p.read_bytes()).hexdigest()
        return None

    # Deterministic batch_id: sha256 of all 7 input component SHAs (sorted by name)
    batch_id_components: dict[str, str | None] = {}
    batch_id = None
    if passed:
        component_pairs: list[tuple[str, str]] = []
        for comp_name, comp_path in [
            ("dataset_manifest", dataset_manifest_path),
            ("pack_manifest", pack_manifest_path),
            ("real_candidate_export", real_candidate_path),
            ("real_rejections", real_rejections_path),
            ("roles_config", roles_config_path),
            ("splits_config", splits_config_path),
            ("governance_config", governance_config_path),
        ]:
            sha = _file_sha(comp_path)
            batch_id_components[comp_name] = sha
            if sha:
                component_pairs.append((comp_name, sha))
        if component_pairs:
            component_pairs.sort(key=lambda x: x[0])
            raw = "\n".join(f"{name}:{sha}" for name, sha in component_pairs)
            batch_id = "annbatch_" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    dm_sha = batch_id_components.get("dataset_manifest")
    pm_sha = batch_id_components.get("pack_manifest")

    return {
        "status": status, "passed": passed, "exit_code": exit_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "readiness-2.1.0",
        "blockers": blockers, "errors": error_messages,
        "checks": checks, "check_passed": check_passed,
        "dataset_id": dataset_id, "batch_id": batch_id,
        "batch_id_components": batch_id_components,
        "dataset_manifest_sha256": dm_sha,
        "pack_manifest_sha256": pm_sha,
        "human_verified_count": 0, "human_labels_complete": False,
        "calibration_allowed": False, "kappa": 0.0,
        "kappa_threshold": KAPPA_THRESHOLD,
        "disagreement_adjudicated": True,
        "fixture_substitute_detected": k_obs.get("substitute_detected", False),
        "minimums": {
            "authorized_candidates": MIN_AUTHORIZED_CANDIDATES,
            "development": MIN_DEVELOPMENT, "calibration": MIN_CALIBRATION,
            "test_blind": MIN_TEST_BLIND, "double_label": MIN_DOUBLE_LABEL,
            "double_label_ratio": DOUBLE_LABEL_RATIO,
        },
    }


# ── Publish with sidecar ──

def _publish_with_sidecar(json_path: Path, payload: dict[str, Any]) -> tuple[str, str]:
    raw = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    tmp = json_path.with_suffix(json_path.suffix + ".tmp")
    tmp.write_bytes(raw)
    with open(tmp, "rb") as f:
        os.fsync(f.fileno())
    os.replace(tmp, json_path)

    final_raw = json_path.read_bytes()
    final_sha = hashlib.sha256(final_raw).hexdigest()

    sidecar_path = json_path.with_suffix(json_path.suffix + SIDECAR_SUFFIX)
    sidecar_content = f"{final_sha}  {json_path.name}\n"
    tmp2 = sidecar_path.with_suffix(sidecar_path.suffix + ".tmp")
    tmp2.write_bytes(sidecar_content.encode("utf-8"))
    with open(tmp2, "rb") as f:
        os.fsync(f.fileno())
    os.replace(tmp2, sidecar_path)

    readback = sidecar_path.read_text().strip()
    expected = f"{final_sha}  {json_path.name}"
    if readback != expected:
        raise RuntimeError(f"sidecar mismatch: {readback!r} != {expected!r}")

    recheck = hashlib.sha256(json_path.read_bytes()).hexdigest()
    if recheck != final_sha:
        raise RuntimeError(f"re-read SHA mismatch: {final_sha} != {recheck}")
    return final_sha, final_sha


# ── Load helpers ──

def _load_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _load_launch_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"launch config not found: {path}")
    data = json.loads(path.read_text())
    if not _is_dict(data):
        raise ValueError("launch config not a JSON object")
    base = path.parent
    for key in ("real_candidate_path", "real_rejections_path",
                "dataset_manifest_path", "pack_manifest_path",
                "task_dir", "roles_config_path", "splits_config_path",
                "governance_config_path"):
        v = data.get(key)
        if _is_str(v) and not Path(v).is_absolute():
            data[key] = str(base / v)
    return data


# ── Verify evidence (independent read-only) ──

def verify_evidence(evidence_dir: Path) -> tuple[bool, list[str]]:
    """Read-only verification: JSON + sidecar must match. Returns (ok, errors)."""
    errs: list[str] = []
    json_path = evidence_dir / OUT_NAME
    sidecar_path = evidence_dir / (OUT_NAME + SIDECAR_SUFFIX)

    if not json_path.exists():
        errs.append(f"JSON file not found: {json_path}")
        return False, errs
    if not sidecar_path.exists():
        errs.append(f"sidecar file not found: {sidecar_path}")
        return False, errs

    try:
        json.loads(json_path.read_text())
    except Exception as e:
        errs.append(f"JSON parse error: {e}")
        return False, errs

    sidecar_text = sidecar_path.read_text().strip()
    actual_sha = hashlib.sha256(json_path.read_bytes()).hexdigest()
    expected_sidecar = f"{actual_sha}  {OUT_NAME}"

    if sidecar_text != expected_sidecar:
        errs.append(f"SHA mismatch: sidecar={sidecar_text[:64]}... actual={actual_sha[:16]}...")
        return False, errs

    return True, []


# ── CLI ──

def main(
    *,
    evidence_dir: Path | None = None,
    real_candidate_path: Path | None = None,
    real_rejections_path: Path | None = None,
    dataset_manifest_path: Path | None = None,
    pack_manifest_path: Path | None = None,
    task_dir: Path | None = None,
    launch_config_path: Path | None = None,
    roles_config_path: Path | None = None,
    splits_config_path: Path | None = None,
    governance_config_path: Path | None = None,
    environment: str | None = None,
    env_override: dict[str, str] | None = None,
    publish: bool = True,
    _test_mode: bool = False,
) -> tuple[int, dict[str, Any]]:
    e_dir = evidence_dir or EVIDENCE_DIR_DEFAULT

    # ── Load launch config ──
    cfg: dict[str, Any] = {}
    if launch_config_path is not None:
        try:
            cfg = _load_launch_config(launch_config_path)
        except Exception as e:
            report = _error_report("FAILED_INVALID_INPUT", 1,
                [f"[invalid] launch_config: {type(e).__name__}: {e}"])
            if publish:
                _publish_with_sidecar(e_dir / OUT_NAME, report)
            return 1, report

    # Resolve paths
    rc_path = real_candidate_path or (Path(cfg["real_candidate_path"]) if "real_candidate_path" in cfg else None) or (EVIDENCE_DIR_DEFAULT / "real-candidate-export.json")
    rr_path = real_rejections_path or (Path(cfg["real_rejections_path"]) if "real_rejections_path" in cfg else None) or (EVIDENCE_DIR_DEFAULT / "real-rejections.json")
    dm_path = dataset_manifest_path or (Path(cfg["dataset_manifest_path"]) if "dataset_manifest_path" in cfg else None)
    pm_path = pack_manifest_path or (Path(cfg["pack_manifest_path"]) if "pack_manifest_path" in cfg else None)
    td_path = task_dir or (Path(cfg["task_dir"]) if "task_dir" in cfg else None)
    rl_path = roles_config_path or (Path(cfg["roles_config_path"]) if "roles_config_path" in cfg else None)
    sp_path = splits_config_path or (Path(cfg["splits_config_path"]) if "splits_config_path" in cfg else None)
    gv_path = governance_config_path or (Path(cfg["governance_config_path"]) if "governance_config_path" in cfg else None)

    # Load config files
    roles = _load_json_if_exists(rl_path) if rl_path else None
    splits = _load_json_if_exists(sp_path) if sp_path else None
    governance = _load_json_if_exists(gv_path) if gv_path else None

    try:
        report = assess_readiness(
            real_candidate_path=rc_path,
            real_rejections_path=rr_path,
            dataset_manifest_path=dm_path,
            pack_manifest_path=pm_path,
            task_dir=td_path,
            roles=roles,
            splits=splits,
            governance=governance,
            roles_config_path=rl_path,
            splits_config_path=sp_path,
            governance_config_path=gv_path,
            environment=environment,
            env_override=env_override,
        )
    except Exception as e:
        report = _error_report("FAILED_INVALID_INPUT", 1,
            [f"[invalid] unexpected: {type(e).__name__}: {e}"])

    if publish:
        out_path = e_dir / OUT_NAME
        final_sha, _ = _publish_with_sidecar(out_path, report)
        report["_final_artifact_sha256"] = final_sha
        report["_final_artifact_path"] = str(out_path)

    exit_code_val = report.get("exit_code", 2)
    if not _is_int(exit_code_val):
        exit_code_val = 2
    return exit_code_val, report


def _error_report(status: str, exit_code: int, errors: list[str]) -> dict:
    return {
        "status": status, "passed": False, "exit_code": exit_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "readiness-2.1.0", "blockers": [],
        "errors": errors, "checks": {}, "check_passed": {},
        "dataset_id": None, "batch_id": None,
        "dataset_manifest_sha256": None, "pack_manifest_sha256": None,
        "human_verified_count": 0, "human_labels_complete": False,
        "calibration_allowed": False, "kappa": 0.0,
        "kappa_threshold": KAPPA_THRESHOLD, "disagreement_adjudicated": True,
        "fixture_substitute_detected": False,
        "minimums": {
            "authorized_candidates": MIN_AUTHORIZED_CANDIDATES,
            "development": MIN_DEVELOPMENT, "calibration": MIN_CALIBRATION,
            "test_blind": MIN_TEST_BLIND, "double_label": MIN_DOUBLE_LABEL,
            "double_label_ratio": DOUBLE_LABEL_RATIO,
        },
    }


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="P13-2-2-2A real annotation launch readiness gate")
    p.add_argument("--evidence-dir", default=str(EVIDENCE_DIR_DEFAULT))
    p.add_argument("--real-candidate-path", default=None)
    p.add_argument("--real-rejections-path", default=None)
    p.add_argument("--launch-config", default=None)
    p.add_argument("--environment", default=None)
    p.add_argument("--no-publish", action="store_true")
    p.add_argument("--verify-evidence", action="store_true",
                   help="Read-only: verify JSON + sidecar SHA match")
    args = p.parse_args()

    if args.verify_evidence:
        e_dir = Path(args.evidence_dir)
        ok, errs = verify_evidence(e_dir)
        if ok:
            print("verify-evidence: PASS")
            return 0
        else:
            print(f"verify-evidence: FAIL ({len(errs)} errors)")
            for e in errs:
                print(f"  ERROR: {e}")
            return 1

    params: dict[str, Any] = {
        "evidence_dir": Path(args.evidence_dir),
        "environment": args.environment,
        "publish": not args.no_publish,
    }
    if args.launch_config:
        params["launch_config_path"] = Path(args.launch_config)
    if args.real_candidate_path:
        params["real_candidate_path"] = Path(args.real_candidate_path)
    if args.real_rejections_path:
        params["real_rejections_path"] = Path(args.real_rejections_path)

    exit_code, report = main(**params)

    status = report.get("status", "UNKNOWN")
    print(f"P13-2-2-2A readiness: {status}")
    print(f"  passed:                 {report.get('passed', False)}")
    print(f"  exit_code:              {exit_code}")
    print(f"  human_verified_count:   {report.get('human_verified_count', 0)}")
    print(f"  human_labels_complete:  {report.get('human_labels_complete', False)}")
    print(f"  calibration_allowed:    {report.get('calibration_allowed', False)}")
    blockers = report.get("blockers", [])
    if blockers:
        print(f"  blockers ({len(blockers)}):")
        for b in blockers:
            print(f"    - {b}")
    errors = report.get("errors", [])
    if errors:
        print(f"  errors ({len(errors)}):")
        for e in errors[:10]:
            print(f"    - {e}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more")
    return exit_code


if __name__ == "__main__":
    sys.exit(_cli())
