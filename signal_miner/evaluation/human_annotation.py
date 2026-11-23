"""P13-2-2-1: Human annotation schema, task packs, and inter-annotator agreement.

All Pydantic models use extra="forbid".
Signal types always come from the production profile single source of truth
(signal_miner.pipeline.pipeline_profile.get_profile). NEVER define a local
whitelist here.

This module is import-only; it exposes schemas and pure functions. CLI
entry points live in scripts/p13_2_*.py.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field, field_validator

from signal_miner.evaluation import sha256  # reuse existing helper
from signal_miner.pipeline.pipeline_profile import get_profile

# Annotator slots are exactly "A" or "B" for blind test tasks; assisted-review
# tasks use the literal string "assisted".
ANNOTATOR_SLOTS = frozenset({"A", "B"})
ASSISTED_SLOT = "assisted"

# Review actions are only meaningful for assisted-review tasks.
REVIEW_ACTIONS = frozenset({"accepted", "modified", "rejected"})

# Status vocabulary used by the validator and import tool. "READY" is reserved
# for the final state and must never be assigned by fixture-only runs.
STATUS_FIXTURE_PASS = "FIXTURE_PASS"
STATUS_BLOCKED_WAITING_AUTHORIZED_DATA = "BLOCKED_WAITING_AUTHORIZED_DATA"
STATUS_BLOCKED_INSUFFICIENT_DOUBLE = "BLOCKED_INSUFFICIENT_DOUBLE_ANNOTATION"
STATUS_BLOCKED_GUIDELINE_REVISION = "BLOCKED_GUIDELINE_REVISION"
STATUS_BLOCKED_PENDING_ADJUDICATION = "BLOCKED_PENDING_ADJUDICATION"
STATUS_READY = "READY"


# ──────────────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────────────

class EvidenceSpanAnnotation(BaseModel):
    """A single evidence span inside a human-annotated signal.

    The `text` field must equal redacted_text[start:end] (verified by caller).
    """

    model_config = {"extra": "forbid"}
    start: int
    end: int
    text: str


class SignalAnnotationHuman(BaseModel):
    """A single human-annotated signal.

    `signal_type` is validated against the production profile whitelist by the
    caller (not here, because this model is profile-agnostic on purpose).

    Note: summary / evidence non-emptiness is validated at the CHECK layer
    (not here) so that the validator can report it under a dedicated check
    name rather than collapsing into schema_strict.
    """

    model_config = {"extra": "forbid"}
    signal_type: str = ""
    summary: str = ""
    evidence_spans: list[EvidenceSpanAnnotation] = Field(default_factory=list)
    implicit_need: str | None = None
    implicit_need_has_basis: bool = False
    hallucination: bool = False
    notes: str | None = None


class HumanAnnotationV2(BaseModel):
    """A complete human annotation for one (sample, annotator_slot) pair.

    Strict schema (extra="forbid"). The caller verifies:
    - signal_count == len(signals)
    - has_signals consistency
    - signal_type whitelist
    - evidence offset correctness
    - task_hash / content_hash match the frozen task
    - annotator_slot match
    """

    model_config = {"extra": "forbid"}
    annotation_id: str
    dataset_id: str
    sample_id: str
    annotator_slot: str
    annotator_pseudonym: str
    annotation_mode: str  # "assisted_review" | "blind"
    has_signals: bool = False
    signal_count: int = 0
    signals: list[SignalAnnotationHuman] = Field(default_factory=list)
    review_action: str | None = None  # required for assisted_review
    started_at: str
    completed_at: str
    task_hash: str
    content_hash: str
    fixture: bool = False  # MUST be true for fixture annotations

    @field_validator("annotator_slot")
    @classmethod
    def _valid_slot(cls, v: str) -> str:
        if v not in ANNOTATOR_SLOTS and v != ASSISTED_SLOT:
            raise ValueError(f"annotator_slot must be 'A', 'B' or '{ASSISTED_SLOT}'")
        return v

    @field_validator("annotator_pseudonym")
    @classmethod
    def _nonempty_pseudonym(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("annotator_pseudonym must be non-empty")
        return v


class AnnotatorTask(BaseModel):
    """A single frozen task handed to one annotator.

    For blind A/B tasks: prediction/suggestion/model/confidence fields are
    forbidden. For assisted-review tasks: a `suggestion` block may carry
    an explicitly-labeled suggestion, but model identity / provider / prompt /
    score are scrubbed.
    """

    model_config = {"extra": "forbid"}
    dataset_id: str
    sample_id: str
    annotator_slot: str
    split: str
    annotation_mode: str  # "assisted_review" | "blind"
    redacted_text: str
    content_hash: str
    task_hash: str
    profile: str
    # Optional suggestion (assisted_review only). Blind tasks leave this null.
    suggestion: dict[str, Any] | None = None
    fixture: bool = False


class AnnotationPack(BaseModel):
    """A frozen pack of tasks for one split + slot."""

    model_config = {"extra": "forbid"}
    schema_version: str = "1.0.0"
    dataset_id: str
    split: str
    annotator_slot: str
    annotation_mode: str
    tasks: list[AnnotatorTask]
    fixture: bool = False


class AdjudicationRecord(BaseModel):
    """A disagreement adjudication. Independent from A/B original labels."""

    model_config = {"extra": "forbid"}
    adjudication_id: str
    sample_id: str
    annotator_a_pseudonym: str
    annotator_b_pseudonym: str
    field_in_dispute: str
    final_value: str
    adjudicator_pseudonym: str
    adjudicated_at: str


# ──────────────────────────────────────────────────────────────────────────
# Hashing / identity helpers
# ──────────────────────────────────────────────────────────────────────────

def compute_task_hash(dataset_id: str, sample_id: str, annotator_slot: str,
                      content_hash: str, fixture: bool = True) -> str:
    """Deterministic task hash. Inputs are joined in fixed order.

    P13-2-2-1 fix-3: fixture is now part of the hash so that flipping a
    fixture task to fixture=false also changes the task hash. A mutated
    annotation must then fail both fixture_provenance AND task_identity,
    making the provenance check robust against annotation-side fixture
    tampering.
    """
    payload = "|".join([dataset_id, sample_id, annotator_slot, content_hash,
                        str(fixture).lower()])
    return sha256(payload)


def compute_annotation_hash(annotation: HumanAnnotationV2) -> str:
    """Stable hash over the annotation content (excluding annotation_id).

    Used for idempotent re-import: same hash → safe to skip; different content
    under same annotation_id → conflict.
    """
    payload = json_sorted({
        "dataset_id": annotation.dataset_id,
        "sample_id": annotation.sample_id,
        "annotator_slot": annotation.annotator_slot,
        "annotator_pseudonym": annotation.annotator_pseudonym,
        "annotation_mode": annotation.annotation_mode,
        "has_signals": annotation.has_signals,
        "signal_count": annotation.signal_count,
        "signals": [s.model_dump() for s in annotation.signals],
        "review_action": annotation.review_action,
        "started_at": annotation.started_at,
        "completed_at": annotation.completed_at,
        "task_hash": annotation.task_hash,
        "content_hash": annotation.content_hash,
    })
    return sha256(payload)


def json_sorted(obj: Any) -> str:
    """Stable JSON serialization (sorted keys, no ASCII escape)."""
    import json

    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_pseudonym(identity: str) -> str:
    """Irreversible pseudonym from any identity string (name/email/account)."""

    return "anno_" + sha256(identity)[:12]


# ──────────────────────────────────────────────────────────────────────────
# Signal-type validation (production single source of truth)
# ──────────────────────────────────────────────────────────────────────────

def allowed_signal_types(profile: str) -> list[str]:
    """Return the production whitelist for a profile. Empty if unknown."""
    try:
        return list(get_profile(profile).signal_types)
    except KeyError:
        return []


def validate_signal_types(signals: list[SignalAnnotationHuman],
                          profile: str) -> list[str]:
    """Return list of error strings. Empty list = all valid."""
    allowed = set(allowed_signal_types(profile))
    errors: list[str] = []
    for i, sig in enumerate(signals):
        if sig.signal_type not in allowed:
            errors.append(
                f"signal[{i}].signal_type '{sig.signal_type}' not in "
                f"profile '{profile}' whitelist"
            )
    return errors


# ──────────────────────────────────────────────────────────────────────────
# Evidence offset validation (Unicode-safe)
# ──────────────────────────────────────────────────────────────────────────

def validate_evidence_offsets(redacted_text: str,
                              signals: list[SignalAnnotationHuman]) -> list[str]:
    """Return list of error strings. start:end slice must equal text field."""
    errors: list[str] = []
    for i, sig in enumerate(signals):
        for j, span in enumerate(sig.evidence_spans):
            try:
                actual = redacted_text[span.start:span.end]
            except Exception:  # noqa: BLE001
                errors.append(
                    f"signal[{i}].evidence[{j}] offset [{span.start}:{span.end}] invalid"
                )
                continue
            if actual != span.text:
                errors.append(
                    f"signal[{i}].evidence[{j}] text mismatch: "
                    f"expected={span.text[:60]!r} actual={actual[:60]!r}"
                )
    return errors


# ──────────────────────────────────────────────────────────────────────────
# Inter-annotator agreement
# ──────────────────────────────────────────────────────────────────────────

def _confusion(y_true: list[bool], y_pred: list[bool]) -> tuple[int, int, int, int]:
    """Return (tp, fn, fp, tn)."""
    # strict=False (default) because caller pre-trims lengths.
    tp = sum(1 for a, b in zip(y_true, y_pred) if a and b)  # noqa: B905
    fn = sum(1 for a, b in zip(y_true, y_pred) if a and not b)  # noqa: B905
    fp = sum(1 for a, b in zip(y_true, y_pred) if not a and b)  # noqa: B905
    tn = sum(1 for a, b in zip(y_true, y_pred) if not a and not b)  # noqa: B905
    return tp, fn, fp, tn


def cohens_kappa(y_true: list[bool], y_pred: list[bool]) -> float:
    """Cohen's kappa for two binary label vectors.

    Returns:
    - A float in [-1, 1] for normal data.
    - 0.0 when fewer than 2 paired samples.
    - -1.0 (DEGENERATE_KAPPA) when the labels have no class variation
      (all True or all False across both raters). A degenerate kappa is
      NOT a measure of high agreement — it means the metric is uncomputable
      because no annotator exercised both classes. Callers MUST treat
      degenerate kappa as a readiness blocker, not as evidence of quality.

    The degenerate case is the P0-2 defense: constant labels must never
    satisfy a kappa >= threshold gate.
    """
    n = min(len(y_true), len(y_pred))
    if n < 2:
        return 0.0
    yt = y_true[:n]
    yp = y_pred[:n]

    tp, fn, fp, tn = _confusion(yt, yp)
    po = (tp + tn) / n  # observed agreement
    # expected agreement
    a_yes = (tp + fn) / n
    b_yes = (tp + fp) / n
    a_no = 1.0 - a_yes
    b_no = 1.0 - b_yes
    pe = a_yes * b_yes + a_no * b_no

    if abs(1.0 - pe) < 1e-12:
        # Degenerate: no class variation across both raters. Kappa is
        # mathematically undefined (0/0). We MUST NOT return 1.0 here,
        # because that would let constant labels pass any threshold gate.
        # Return -1.0 as a sentinel that callers treat as a hard blocker.
        return DEGENERATE_KAPPA
    return (po - pe) / (1.0 - pe)


# Sentinel for degenerate (uncomputable) kappa. Callers must treat this as
# "kappa cannot be computed" and block READY status.
DEGENERATE_KAPPA = -1.0


def jaccard_index(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard similarity of two sets. 1.0 when both empty."""
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)


def _evidence_overlap(sa: list[EvidenceSpanAnnotation],
                      sb: list[EvidenceSpanAnnotation]) -> bool:
    """True if any span pair overlaps by at least 1 character."""
    for pa in sa:
        for pb in sb:
            start = max(pa.start, pb.start)
            end = min(pa.end, pb.end)
            if end > start:
                return True
    return False


def compute_pair_agreement(ann_a: HumanAnnotationV2,
                           ann_b: HumanAnnotationV2) -> dict[str, Any]:
    """Compute per-sample agreement metrics for a single A/B pair.

    Returns dict with:
    - has_signals_agree: bool
    - signal_count_exact: bool
    - signal_type_jaccard: float
    - evidence_overlap: bool
    - disagree_fields: list[str]
    """
    disagree: list[str] = []
    has_agree = ann_a.has_signals == ann_b.has_signals
    if not has_agree:
        disagree.append("has_signals")

    count_exact = ann_a.signal_count == ann_b.signal_count
    if not count_exact:
        disagree.append("signal_count")

    types_a = {s.signal_type for s in ann_a.signals}
    types_b = {s.signal_type for s in ann_b.signals}
    jac = jaccard_index(types_a, types_b)
    if jac < 1.0:
        disagree.append("signal_type_set")

    # evidence overlap: at least one matching-type signal pair has overlapping spans
    ev_overlap = False
    for sa in ann_a.signals:
        for sb in ann_b.signals:
            if sa.signal_type == sb.signal_type and _evidence_overlap(
                    sa.evidence_spans, sb.evidence_spans):
                ev_overlap = True
                break
        if ev_overlap:
            break
    if not ev_overlap and ann_a.signals and ann_b.signals:
        disagree.append("evidence_span")

    return {
        "has_signals_agree": has_agree,
        "signal_count_exact": count_exact,
        "signal_type_jaccard": round(jac, 4),
        "evidence_overlap": ev_overlap,
        "disagree_fields": disagree,
    }


def compute_agreement_metrics(pairs: list[tuple[HumanAnnotationV2, HumanAnnotationV2]]
                              ) -> dict[str, Any]:
    """Aggregate agreement across all A/B pairs.

    Returns:
    - has_signals_kappa: float
    - signal_count_exact_rate: float
    - mean_signal_type_jaccard: float
    - evidence_overlap_rate: float
    - disagreement_sample_count: int
    - disagreement_fields: dict[str, int]  (field → count)
    - pair_count: int
    """
    n = len(pairs)
    if n == 0:
        return {
            "has_signals_kappa": 0.0,
            "signal_count_exact_rate": 0.0,
            "mean_signal_type_jaccard": 0.0,
            "evidence_overlap_rate": 0.0,
            "disagreement_sample_count": 0,
            "disagreement_fields": {},
            "pair_count": 0,
        }

    y_a = [p[0].has_signals for p in pairs]
    y_b = [p[1].has_signals for p in pairs]
    kappa = cohens_kappa(y_a, y_b)

    count_exact = sum(1 for p in pairs if p[0].signal_count == p[1].signal_count)
    jaccards = []
    ev_overlaps = 0
    disagree_count = 0
    field_counter: dict[str, int] = {}

    for a, b in pairs:
        agg = compute_pair_agreement(a, b)
        jaccards.append(agg["signal_type_jaccard"])
        if agg["evidence_overlap"]:
            ev_overlaps += 1
        if agg["disagree_fields"]:
            disagree_count += 1
            for f in agg["disagree_fields"]:
                field_counter[f] = field_counter.get(f, 0) + 1

    return {
        "has_signals_kappa": round(kappa, 4),
        "kappa_degenerate": kappa == DEGENERATE_KAPPA,
        "signal_count_exact_rate": round(count_exact / n, 4),
        "mean_signal_type_jaccard": round(sum(jaccards) / n, 4),
        "evidence_overlap_rate": round(ev_overlaps / n, 4),
        "disagreement_sample_count": disagree_count,
        "disagreement_fields": field_counter,
        "pair_count": n,
    }


# ──────────────────────────────────────────────────────────────────────────
# Required double-annotation ratio
# ──────────────────────────────────────────────────────────────────────────

def required_double_count(n: int) -> int:
    """max(20, ceil(n * 0.20))."""
    return max(20, math.ceil(n * 0.20))


__all__ = [
    "ANNOTATOR_SLOTS",
    "ASSISTED_SLOT",
    "REVIEW_ACTIONS",
    "STATUS_FIXTURE_PASS",
    "STATUS_BLOCKED_WAITING_AUTHORIZED_DATA",
    "STATUS_BLOCKED_INSUFFICIENT_DOUBLE",
    "STATUS_BLOCKED_GUIDELINE_REVISION",
    "STATUS_BLOCKED_PENDING_ADJUDICATION",
    "STATUS_READY",
    "EvidenceSpanAnnotation",
    "SignalAnnotationHuman",
    "HumanAnnotationV2",
    "AnnotatorTask",
    "AnnotationPack",
    "AdjudicationRecord",
    "compute_task_hash",
    "compute_annotation_hash",
    "compute_pseudonym",
    "allowed_signal_types",
    "validate_signal_types",
    "validate_evidence_offsets",
    "cohens_kappa",
    "DEGENERATE_KAPPA",
    "jaccard_index",
    "compute_pair_agreement",
    "compute_agreement_metrics",
    "required_double_count",
    "json_sorted",
]
