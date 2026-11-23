#!/usr/bin/env python3
"""P13-2-2-1: Prepare human annotation task packs.

Generates four task packs from a P13-2-1 candidate dataset + manifest:
  - development assisted-review (slot = "assisted")
  - calibration assisted-review  (slot = "assisted")
  - test A blind                 (slot = "A")
  - test B blind                 (slot = "B", only double-annotated samples)

Rules enforced here (defense in depth; the validator re-checks):
  - Assisted-review tasks MAY include an explicitly-labeled suggestion block,
    but model identity / provider / prompt / score fields are scrubbed.
  - Blind A/B tasks MUST NOT contain any prediction/suggestion/model/confidence
    field. The suggestion key is forced to None.
  - A and B packs are fully isolated: A never sees B's label, status or notes
    and vice versa. Each pack is written to its own file.
  - Each task carries dataset_id, sample_id, annotator_slot, task_hash and the
    frozen content_hash.
  - When the candidate dataset is BLOCKED (status key present) or there are
    zero real authorized samples, output is
      BLOCKED_WAITING_AUTHORIZED_DATA  with exit code 2
    UNLESS --fixture is passed, in which case fixture packs are produced and
    clearly tagged fixture=true.

Exit codes:
  0 = packs written (READY or FIXTURE_PASS)
  1 = internal error (missing inputs, schema failure)
  2 = BLOCKED (waiting on authorized data) — NOT a contract violation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from signal_miner.evaluation import (  # noqa: E402
    SCHEMA_VERSION,
    FrozenManifest,
    GoldRecord,
)
from signal_miner.evaluation.human_annotation import (  # noqa: E402
    ASSISTED_SLOT,
    STATUS_BLOCKED_WAITING_AUTHORIZED_DATA,
    STATUS_FIXTURE_PASS,
    STATUS_READY,
    AnnotationPack,
    AnnotatorTask,
    compute_task_hash,
)

# Fields that must NEVER appear in any task (blind or assisted) — they leak
# model identity or confidence that the annotator must not see.
LEAK_FIELDS = {
    "prediction", "predicted_signals",
    "model", "model_name", "model_version", "model_id",
    "provider", "llm_provider",
    "prompt", "prompt_version", "prompt_template",
    "confidence", "score", "self_score", "calibrated_confidence",
    "suggestion_model", "suggestion_model_version", "suggestion_prompt_version",
}


def _count_identity_leak(obj) -> int:
    """Count model identity / provider / prompt / score fields anywhere.

    Unlike check_blind_pack_leakage this does NOT flag `suggested_signals`,
    which is an explicitly-labeled suggestion payload ALLOWED in
    assisted-review tasks.
    """
    identity_keys = {
        "model", "model_name", "model_version", "model_id",
        "provider", "llm_provider",
        "prompt", "prompt_version", "prompt_template",
        "confidence", "score", "self_score", "calibrated_confidence",
        "prediction",
        "suggestion_model", "suggestion_model_version", "suggestion_prompt_version",
    }
    count = 0

    def _scan(o):
        nonlocal count
        if isinstance(o, dict):
            for k, v in o.items():
                if k in identity_keys:
                    count += 1
                _scan(v)
        elif isinstance(o, list):
            for item in o:
                _scan(item)
    _scan(obj)
    return count


def _count_task_pack_blind_leak(pack_dict: dict) -> int:
    """Strict blind-leak check for human task packs.

    A blind task pack is allowed to carry the `suggestion` key with value None
    (schema placeholder), but nothing else. Any of the following counts as a
    leak:
      - a non-None `suggestion` value
      - any of: prediction, model*, provider*, prompt*, confidence, score*,
        suggested_signals
    """
    leak = 0

    def _scan_task(task: dict) -> int:
        n = 0
        sug = task.get("suggestion")
        if sug is not None:
            n += 1
        for forbidden in ("prediction", "predicted_signals",
                          "model", "model_name", "model_version", "model_id",
                          "provider", "llm_provider",
                          "prompt", "prompt_version", "prompt_template",
                          "confidence", "score", "self_score",
                          "calibrated_confidence",
                          "suggested_signals", "suggestion_model"):
            if forbidden in task:
                n += 1
        return n

    for task in pack_dict.get("tasks", []):
        leak += _scan_task(task)
    return leak


def _scrub_suggestion(raw_suggestion: dict | None) -> dict | None:
    """Keep only the explicitly-labeled suggestion payload; drop model identity.

    The surviving block carries:
      - suggested_signals (the actual suggestions)
      - suggestion_label  (always "suggestion_only")
    Everything else (model/provider/prompt/score/version) is removed.
    """
    if raw_suggestion is None:
        return None
    cleaned = {
        "suggested_signals": raw_suggestion.get("suggested_signals", []),
        "suggestion_label": "suggestion_only",
    }
    return cleaned


def _build_task(sample: GoldRecord, manifest: FrozenManifest,
                annotator_slot: str, annotation_mode: str,
                suggestion: dict | None, fixture: bool) -> AnnotatorTask:
    """Build one frozen AnnotatorTask."""
    task_hash = compute_task_hash(
        manifest.dataset_id, sample.sample_id, annotator_slot, sample.content_hash,
        fixture=fixture,
    )

    # For assisted-review, keep the scrubbed suggestion; for blind, force None.
    final_suggestion = None
    if annotation_mode == "assisted_review":
        final_suggestion = _scrub_suggestion(suggestion)

    return AnnotatorTask(
        dataset_id=manifest.dataset_id,
        sample_id=sample.sample_id,
        annotator_slot=annotator_slot,
        split=sample.split,
        annotation_mode=annotation_mode,
        redacted_text=sample.redacted_text,
        content_hash=sample.content_hash,
        task_hash=task_hash,
        profile=sample.profile,
        suggestion=final_suggestion,
        fixture=fixture,
    )


def _load_suggestions_map(preannotations_path: Path) -> dict[str, dict]:
    """Load preannotations and return sample_id → suggestion dict."""
    if not preannotations_path.exists():
        return {}
    data = json.loads(preannotations_path.read_text())
    out: dict[str, dict] = {}
    for sg in data.get("suggestions", []):
        sid_raw = sg.get("suggestion_id", "")
        sid = sid_raw.replace("sg_", "") if sid_raw.startswith("sg_") else sid_raw
        out[sid] = sg
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Prepare human annotation task packs")
    p.add_argument("--candidates", default="sample_data/p13_2/positive/candidates.json")
    p.add_argument("--manifest", default="sample_data/p13_2/manifest.json")
    p.add_argument("--preannotations", default="sample_data/p13_2/positive/preannotations.json")
    p.add_argument("--out-dir", default="sample_data/p13_2/human_tasks")
    p.add_argument("--fixture", action="store_true",
                   help="Produce fixture-tagged packs even when candidates are fixture")
    p.add_argument("--out", default="",
                   help="Optional readiness JSON path (for mutation gate plumbing)")
    args = p.parse_args()

    cp = Path(args.candidates)
    mp = Path(args.manifest)
    pp = Path(args.preannotations)
    out_dir = Path(args.out_dir)

    # --- Load candidates ---
    if not cp.exists():
        result = {
            "status": STATUS_BLOCKED_WAITING_AUTHORIZED_DATA,
            "passed": False,
            "reason": "candidates file not found",
        }
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 2

    raw = json.loads(cp.read_text())
    # BLOCKED candidates payload (real DB export with 0 eligible)
    if isinstance(raw, dict) and raw.get("status", "").startswith("BLOCKED"):
        result = {
            "status": STATUS_BLOCKED_WAITING_AUTHORIZED_DATA,
            "passed": False,
            "reason": raw.get("status", "BLOCKED"),
            "eligible_count": raw.get("eligible_count", 0),
        }
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 2

    # Empty candidate list (another form of "no authorized data")
    if isinstance(raw, list) and len(raw) == 0:
        result = {
            "status": STATUS_BLOCKED_WAITING_AUTHORIZED_DATA,
            "passed": False,
            "reason": "zero authorized candidates",
        }
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 2

    try:
        samples = [GoldRecord(**s) for s in raw]
    except Exception as e:  # noqa: BLE001
        result = {
            "status": "FAIL_SCHEMA",
            "passed": False,
            "reason": str(e)[:300],
        }
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 1

    # --- Load manifest ---
    if not mp.exists():
        result = {"status": "FAIL_MANIFEST_MISSING", "passed": False}
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 1

    try:
        manifest = FrozenManifest(**json.loads(mp.read_text()))
    except Exception as e:  # noqa: BLE001
        result = {"status": "FAIL_MANIFEST_SCHEMA", "passed": False, "reason": str(e)[:300]}
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 1

    suggestions_map = _load_suggestions_map(pp)

    fixture = args.fixture
    dev_samples = [s for s in samples if s.split == "development"]
    cal_samples = [s for s in samples if s.split == "calibration"]
    test_samples = [s for s in samples if s.split == "test"]
    double_set = set(manifest.double_annotation_ids)
    test_b_samples = [s for s in test_samples if s.sample_id in double_set]

    # --- Build the four packs ---
    dev_tasks = [
        _build_task(s, manifest, ASSISTED_SLOT, "assisted_review",
                    suggestions_map.get(s.sample_id), fixture)
        for s in dev_samples
    ]
    cal_tasks = [
        _build_task(s, manifest, ASSISTED_SLOT, "assisted_review",
                    suggestions_map.get(s.sample_id), fixture)
        for s in cal_samples
    ]
    a_tasks = [
        _build_task(s, manifest, "A", "blind", None, fixture)
        for s in test_samples
    ]
    b_tasks = [
        _build_task(s, manifest, "B", "blind", None, fixture)
        for s in test_b_samples
    ]

    dev_pack = AnnotationPack(
        schema_version=SCHEMA_VERSION, dataset_id=manifest.dataset_id,
        split="development", annotator_slot=ASSISTED_SLOT,
        annotation_mode="assisted_review", tasks=dev_tasks, fixture=fixture,
    )
    cal_pack = AnnotationPack(
        schema_version=SCHEMA_VERSION, dataset_id=manifest.dataset_id,
        split="calibration", annotator_slot=ASSISTED_SLOT,
        annotation_mode="assisted_review", tasks=cal_tasks, fixture=fixture,
    )
    a_pack = AnnotationPack(
        schema_version=SCHEMA_VERSION, dataset_id=manifest.dataset_id,
        split="test", annotator_slot="A",
        annotation_mode="blind", tasks=a_tasks, fixture=fixture,
    )
    b_pack = AnnotationPack(
        schema_version=SCHEMA_VERSION, dataset_id=manifest.dataset_id,
        split="test", annotator_slot="B",
        annotation_mode="blind", tasks=b_tasks, fixture=fixture,
    )

    # --- Verify zero leakage on every pack (defense in depth) ---
    # Blind packs (A, B): strict check — NO suggestion/model/score of any kind.
    # Assisted packs (dev, cal): identity check only — model/provider/prompt/score
    # forbidden, but the explicitly-labeled suggestion payload is allowed.
    total_leak = 0
    total_leak += _count_task_pack_blind_leak(a_pack.model_dump())
    total_leak += _count_task_pack_blind_leak(b_pack.model_dump())
    total_leak += _count_identity_leak(dev_pack.model_dump())
    total_leak += _count_identity_leak(cal_pack.model_dump())

    if total_leak > 0:
        result = {
            "status": "FAIL_TASK_LEAKAGE",
            "passed": False,
            "leak_count": total_leak,
        }
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False))
        return 1

    # --- Write packs ---
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "human_tasks_development.json").write_text(
        json.dumps(dev_pack.model_dump(), indent=2, ensure_ascii=False))
    (out_dir / "human_tasks_calibration.json").write_text(
        json.dumps(cal_pack.model_dump(), indent=2, ensure_ascii=False))
    (out_dir / "human_tasks_test_A.json").write_text(
        json.dumps(a_pack.model_dump(), indent=2, ensure_ascii=False))
    (out_dir / "human_tasks_test_B.json").write_text(
        json.dumps(b_pack.model_dump(), indent=2, ensure_ascii=False))

    status = STATUS_FIXTURE_PASS if fixture else STATUS_READY

    result = {
        "status": status,
        "passed": True,
        "fixture": fixture,
        "dataset_id": manifest.dataset_id,
        "pack_counts": {
            "development": len(dev_tasks),
            "calibration": len(cal_tasks),
            "test_A": len(a_tasks),
            "test_B": len(b_tasks),
        },
        "leak_count": 0,
    }
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(json.dumps({"status": status, "passed": True,
                      "packs": result["pack_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
