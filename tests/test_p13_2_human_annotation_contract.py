"""P13-2-2-1: Human annotation contract tests.

All paths use tmp_path. NO project artifact is ever modified.
Covers:
  - Positive fixture toolchain (prepare → generate → import → validate)
  - BLOCKED path when real candidates are 0
  - 20+ adversarial mutations targeting the validator and importer
  - Artifact SHA invariance (project artifacts unchanged after tests)
  - human_verified_count / human_labels_complete / calibration_allowed
    invariant across all operations
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent.parent
PY = sys.executable
PREPARE = str(PROJECT / "scripts" / "p13_2_prepare_human_tasks.py")
IMPORT = str(PROJECT / "scripts" / "p13_2_import_human_annotations.py")
VALIDATE = str(PROJECT / "scripts" / "p13_2_validate_human_annotations.py")
GENFIX = str(PROJECT / "scripts" / "p13_2_generate_fixture_annotations.py")
SIGN = str(PROJECT / "scripts" / "p13_2_sign_human_task_pack.py")

CANDIDATES = PROJECT / "sample_data" / "p13_2" / "positive" / "candidates.json"
MANIFEST = PROJECT / "sample_data" / "p13_2" / "manifest.json"
PREANN = PROJECT / "sample_data" / "p13_2" / "positive" / "preannotations.json"

TEST_KEY = "test-key-for-ci-pipeline"


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_artifacts() -> dict[str, str]:
    """Hash all project artifacts that MUST NOT change during tests."""
    artifacts = {}
    for p in [
        CANDIDATES, MANIFEST, PREANN,
        PROJECT / "sample_data" / "p13_2" / "positive" / "annotation_pack_test_A.json",
        PROJECT / "sample_data" / "p13_2" / "positive" / "annotation_pack_test_B.json",
        PROJECT / "sample_data" / "p13_2" / "positive" / "annotation_pack_development.json",
        PROJECT / "sample_data" / "p13_2" / "positive" / "annotation_pack_calibration.json",
    ]:
        if p.exists():
            artifacts[str(p)] = _sha256(p)
    return artifacts


def _prepare(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    tasks = tmp_path / "tasks"
    readiness = tmp_path / "readiness.json"
    cmd = [PY, PREPARE,
           "--candidates", str(CANDIDATES),
           "--manifest", str(MANIFEST),
           "--preannotations", str(PREANN),
           "--out-dir", str(tasks),
           "--out", str(readiness),
           "--fixture"]
    cmd.extend(extra)
    return subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=60)


def _genfix(tmp_path: Path) -> subprocess.CompletedProcess:
    tasks = tmp_path / "tasks"
    out = tmp_path / "fixture_annotations.json"
    return subprocess.run(
        [PY, GENFIX, "--tasks", str(tasks), "--out", str(out)],
        cwd=PROJECT, capture_output=True, text=True, timeout=30,
    )


def _sign_dir(tasks_path: Path, manifest_out: str | None = None) -> subprocess.CompletedProcess:
    """Sign manifest for a specific tasks directory."""
    import os
    out = tasks_path.parent / "sign_report.json"
    cmd = [PY, SIGN,
           "--tasks", str(tasks_path),
           "--dataset-manifest", str(MANIFEST),
           "--fixture",
           "--out", str(out)]
    if manifest_out:
        cmd.extend(["--manifest-out", manifest_out])
    env = dict(os.environ)
    env["APP_ENVIRONMENT"] = "test"
    env["ANNOTATION_PACK_TEST_SIGNING_KEY"] = TEST_KEY
    return subprocess.run(
        cmd, cwd=PROJECT, capture_output=True, text=True, timeout=30, env=env,
    )


def _sign(tmp_path: Path) -> subprocess.CompletedProcess:
    """Sign a valid fixture manifest in test env with injected key."""
    import os
    tasks = tmp_path / "tasks"
    out = tmp_path / "sign_report.json"
    env = dict(os.environ)
    env["APP_ENVIRONMENT"] = "test"
    env["ANNOTATION_PACK_TEST_SIGNING_KEY"] = TEST_KEY
    return subprocess.run(
        [PY, SIGN,
         "--tasks", str(tasks),
         "--dataset-manifest", str(MANIFEST),
         "--fixture",
         "--out", str(out)],
        cwd=PROJECT, capture_output=True, text=True, timeout=30, env=env,
    )


def _import(tmp_path: Path, input_path: Path | None = None,
            skip_manifest: bool = False) -> subprocess.CompletedProcess:
    """Run the importer with signed manifest + test env.

    skip_manifest=True omits --manifest (used by manifest-mandatory tests).
    """
    import os
    tasks = tmp_path / "tasks"
    store = tmp_path / "store.json"
    inp = input_path or (tmp_path / "fixture_annotations.json")
    report = tmp_path / "import_report.json"
    cmd = [PY, IMPORT, "--input", str(inp),
           "--tasks", str(tasks), "--store", str(store),
           "--out", str(report),
           "--fixture"]
    if not skip_manifest:
        cmd.extend([
            "--manifest", str(tasks / "human-task-pack-manifest.json"),
            "--dataset-manifest", str(MANIFEST),
        ])
    env = dict(os.environ)
    env["APP_ENVIRONMENT"] = "test"
    env["ANNOTATION_PACK_TEST_SIGNING_KEY"] = TEST_KEY
    return subprocess.run(
        cmd, cwd=PROJECT, capture_output=True, text=True, timeout=30, env=env,
    )


def _validate(tmp_path: Path) -> subprocess.CompletedProcess:
    tasks = tmp_path / "tasks"
    store = tmp_path / "store.json"
    metrics = tmp_path / "metrics.json"
    return subprocess.run(
        [PY, VALIDATE, "--tasks", str(tasks), "--store", str(store),
         "--out", str(metrics)],
        cwd=PROJECT, capture_output=True, text=True, timeout=30,
    )


def _full_pipeline(tmp_path: Path):
    """Run the complete fixture toolchain. Returns the validate result."""
    r1 = _prepare(tmp_path)
    assert r1.returncode == 0, f"Prepare failed: {r1.stderr[:200]}"
    r2 = _genfix(tmp_path)
    assert r2.returncode == 0, f"Generate failed: {r2.stderr[:200]}"
    r_sign = _sign(tmp_path)
    assert r_sign.returncode == 0, f"Sign failed: {r_sign.stderr[:200]}"
    r3 = _import(tmp_path)
    assert r3.returncode == 0, f"Import failed: {r3.stderr[:200]}"
    return _validate(tmp_path)


def _prepare_genfix_sign(tmp_path: Path):
    """Prepare + genfix + sign. Common setup for tests that need seeded store."""
    _prepare(tmp_path)
    _genfix(tmp_path)
    _sign(tmp_path)


class TestPositivePath:
    """The complete fixture toolchain must PASS end to end."""

    def test_full_pipeline_fixture_pass(self, tmp_path):
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0, f"Validate failed: {r.stderr[:200]}"
        data = json.loads(r.stdout)
        assert data["status"] == "FIXTURE_PASS"
        assert data["passed"] is True

    def test_task_packs_structure(self, tmp_path):
        _prepare(tmp_path)
        tasks = tmp_path / "tasks"
        for name in ("human_tasks_development.json", "human_tasks_calibration.json",
                     "human_tasks_test_A.json", "human_tasks_test_B.json"):
            assert (tasks / name).exists(), f"{name} missing"

    def test_blind_packs_no_leakage(self, tmp_path):
        _prepare(tmp_path)
        tasks = tmp_path / "tasks"
        for slot in ("A", "B"):
            pack = json.loads((tasks / f"human_tasks_test_{slot}.json").read_text())
            for task in pack["tasks"]:
                assert task["suggestion"] is None
                for forbidden in ("model", "provider", "prompt", "confidence", "score"):
                    assert forbidden not in task

    def test_assisted_packs_have_scrubbed_suggestion(self, tmp_path):
        _prepare(tmp_path)
        dev_pack = json.loads((tmp_path / "tasks" / "human_tasks_development.json").read_text())
        for task in dev_pack["tasks"]:
            if task["suggestion"] is not None:
                # Suggestion must NOT carry model identity
                sug = task["suggestion"]
                assert "suggestion_model" not in sug
                assert "suggestion_model_version" not in sug
                assert "suggestion_prompt_version" not in sug
                assert sug.get("suggestion_label") == "suggestion_only"

    def test_a_b_isolation(self, tmp_path):
        """A pack must not contain B's samples and vice versa."""
        _prepare(tmp_path)
        a = json.loads((tmp_path / "tasks" / "human_tasks_test_A.json").read_text())
        b = json.loads((tmp_path / "tasks" / "human_tasks_test_B.json").read_text())
        a_ids = {t["sample_id"] for t in a["tasks"]}
        b_ids = {t["sample_id"] for t in b["tasks"]}
        # B should be a subset of A (double annotation)
        assert b_ids.issubset(a_ids)
        # B pack must be smaller or equal
        assert len(b["tasks"]) <= len(a["tasks"])


class TestBlockedPath:
    """Real candidate = 0 → BLOCKED / exit 2."""

    def test_blocked_candidates_returns_exit2(self, tmp_path):
        blocked = tmp_path / "candidates.json"
        blocked.write_text(json.dumps({
            "status": "BLOCKED_INSUFFICIENT_AUTHORIZED_SAMPLES",
            "eligible_count": 0,
        }))
        r = subprocess.run(
            [PY, PREPARE,
             "--candidates", str(blocked),
             "--manifest", str(MANIFEST),
             "--out-dir", str(tmp_path / "tasks"),
             "--out", str(tmp_path / "readiness.json")],
            cwd=PROJECT, capture_output=True, text=True, timeout=30,
        )
        assert r.returncode == 2
        data = json.loads(r.stdout)
        assert data["status"] == "BLOCKED_WAITING_AUTHORIZED_DATA"


class TestArtifactInvariance:
    """Project artifacts must not change during any test."""

    def test_artifacts_unchanged_after_full_pipeline(self, tmp_path):
        before = _snapshot_artifacts()
        _full_pipeline(tmp_path)
        after = _snapshot_artifacts()
        assert before == after, "Project artifacts were modified!"


class TestStateInvariants:
    """human_verified_count, human_labels_complete, calibration_allowed."""

    def test_fixtures_do_not_count_as_human(self, tmp_path):
        _full_pipeline(tmp_path)
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["human_verified_count"] == 0
        assert metrics["human_labels_complete"] is False
        assert metrics["calibration_allowed"] is False
        assert metrics["fixture_count"] > 0
        assert metrics["real_count"] == 0


class TestImportRejection:
    """Importer must reject adversarial annotations."""

    def _seed(self, tmp_path):
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)

    def test_unknown_field_rejected(self, tmp_path):
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["mystery_field"] = "boom"
        inp = tmp_path / "bad.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1

    def test_signal_count_mismatch_rejected(self, tmp_path):
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        if ann["signals"]:
            ann["signal_count"] = ann["signal_count"] + 1
            inp = tmp_path / "bad.json"
            inp.write_text(json.dumps({"annotations": [ann]}))
            r = _import(tmp_path, inp)
            assert r.returncode == 1

    def test_invalid_signal_type_rejected(self, tmp_path):
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        if ann["signals"]:
            ann["signals"][0]["signal_type"] = "nonexistent_type"
            inp = tmp_path / "bad.json"
            inp.write_text(json.dumps({"annotations": [ann]}))
            r = _import(tmp_path, inp)
            assert r.returncode == 1

    def test_idempotent_reimport(self, tmp_path):
        """Re-importing identical annotations is a no-op (exit 0)."""
        _prepare_genfix_sign(tmp_path)
        r1 = _import(tmp_path)
        assert r1.returncode == 0
        r2 = _import(tmp_path)
        assert r2.returncode == 0

    def test_conflict_different_content_same_id(self, tmp_path):
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["has_signals"] = not ann["has_signals"]
        ann["signal_count"] = 999
        inp = tmp_path / "conflict.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1

    def test_self_pairing_rejected(self, tmp_path):
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        # Find a double sample, force B pseudonym = A pseudonym
        by_sample: dict[str, dict] = {}
        for e in data["annotations"]:
            ann = e["annotation"]
            if ann["annotator_slot"] in ("A", "B"):
                by_sample.setdefault(ann["sample_id"], {})[ann["annotator_slot"]] = ann
        for _sid, slots in by_sample.items():
            if "A" in slots and "B" in slots:
                slots["B"]["annotator_pseudonym"] = slots["A"]["annotator_pseudonym"]
                break
        inp = tmp_path / "selfpair.json"
        inp.write_text(json.dumps({"annotations": [
            {"annotation": s, "content_hash_annotation": ""}
            for pair in by_sample.values() for s in pair.values()
        ]}))
        # Need a fresh store for this
        (tmp_path / "store.json").unlink()
        r = _import(tmp_path, inp)
        assert r.returncode == 1


class TestValidatorNegativeCases:
    """Validator must catch mutations targeting the store."""

    def _seed_and_validate(self, tmp_path, mutate_fn):
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)
        # Apply mutation to store
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        mutate_fn(data)
        store.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return _validate(tmp_path)

    def test_task_hash_tampered_detected(self, tmp_path):
        def mutate(data):
            data["annotations"][0]["annotation"]["task_hash"] = "x" * 64
        r = self._seed_and_validate(tmp_path, mutate)
        assert r.returncode == 1
        m = json.loads((tmp_path / "metrics.json").read_text())
        assert m["checks"]["task_identity"]["passed"] is False

    def test_content_hash_tampered_detected(self, tmp_path):
        def mutate(data):
            data["annotations"][0]["annotation"]["content_hash"] = "y" * 64
        r = self._seed_and_validate(tmp_path, mutate)
        assert r.returncode == 1
        m = json.loads((tmp_path / "metrics.json").read_text())
        assert m["checks"]["task_identity"]["passed"] is False

    def test_fixture_flipped_to_real_detected(self, tmp_path):
        def mutate(data):
            for e in data["annotations"]:
                e["annotation"]["fixture"] = False
                break
        r = self._seed_and_validate(tmp_path, mutate)
        assert r.returncode == 1
        m = json.loads((tmp_path / "metrics.json").read_text())
        assert m["checks"]["real_vs_fixture_count"]["passed"] is False

    def test_double_annotation_removed_detected(self, tmp_path):
        def mutate(data):
            data["annotations"] = [
                e for e in data["annotations"]
                if e["annotation"]["annotator_slot"] != "B"
            ]
        r = self._seed_and_validate(tmp_path, mutate)
        assert r.returncode == 1
        m = json.loads((tmp_path / "metrics.json").read_text())
        assert m["checks"]["double_annotation_coverage"]["passed"] is False


class TestDegenerateKappa:
    """P0-2: Constant labels must NOT produce kappa=1.0."""

    def test_all_true_returns_degenerate(self):
        from signal_miner.evaluation.human_annotation import (
            DEGENERATE_KAPPA,
            cohens_kappa,
        )
        k = cohens_kappa([True] * 20, [True] * 20)
        assert k == DEGENERATE_KAPPA, f"Expected {DEGENERATE_KAPPA}, got {k}"

    def test_all_false_returns_degenerate(self):
        from signal_miner.evaluation.human_annotation import (
            DEGENERATE_KAPPA,
            cohens_kappa,
        )
        k = cohens_kappa([False] * 20, [False] * 20)
        assert k == DEGENERATE_KAPPA

    def test_mixed_labels_returns_valid_kappa(self):
        from signal_miner.evaluation.human_annotation import (
            DEGENERATE_KAPPA,
            cohens_kappa,
        )
        # Perfect agreement with class variation → high kappa, not degenerate
        k = cohens_kappa([True, False, True, False, True, False],
                         [True, False, True, False, True, False])
        assert k != DEGENERATE_KAPPA
        assert k > 0.5  # high agreement

    def test_low_kappa_below_threshold(self):
        from signal_miner.evaluation.human_annotation import cohens_kappa
        # Mostly disagreeing
        k = cohens_kappa([True, True, True, True, False, False],
                         [False, False, False, False, True, True])
        assert k < 0.0  # negative kappa


class TestStagePolicy:
    """P1-1: calibration_allowed must be read from a mutable stage policy file."""

    def test_calibration_true_rejected(self, tmp_path):
        """Mutating stage-policy.json to true must fail the validator."""
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)
        # Create a mutated policy
        bad_policy = tmp_path / "bad-policy.json"
        bad_policy.write_text(json.dumps({"calibration_allowed": True}))
        store = tmp_path / "store.json"
        metrics = tmp_path / "metrics.json"
        r = subprocess.run(
            [PY, VALIDATE, "--tasks", str(tmp_path / "tasks"),
             "--store", str(store), "--stage-policy", str(bad_policy),
             "--out", str(metrics)],
            cwd=PROJECT, capture_output=True, text=True, timeout=30,
        )
        assert r.returncode == 1
        m = json.loads(metrics.read_text())
        assert m["checks"]["calibration_not_allowed"]["passed"] is False

    def test_calibration_missing_rejected(self, tmp_path):
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)
        bad_policy = tmp_path / "missing-policy.json"  # does not exist
        store = tmp_path / "store.json"
        metrics = tmp_path / "metrics.json"
        r = subprocess.run(
            [PY, VALIDATE, "--tasks", str(tmp_path / "tasks"),
             "--store", str(store), "--stage-policy", str(bad_policy),
             "--out", str(metrics)],
            cwd=PROJECT, capture_output=True, text=True, timeout=30,
        )
        assert r.returncode == 1
        m = json.loads(metrics.read_text())
        assert m["checks"]["calibration_not_allowed"]["passed"] is False

    def test_calibration_wrong_type_rejected(self, tmp_path):
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)
        bad_policy = tmp_path / "bad-policy.json"
        bad_policy.write_text(json.dumps({"calibration_allowed": "yes"}))
        store = tmp_path / "store.json"
        metrics = tmp_path / "metrics.json"
        r = subprocess.run(
            [PY, VALIDATE, "--tasks", str(tmp_path / "tasks"),
             "--store", str(store), "--stage-policy", str(bad_policy),
             "--out", str(metrics)],
            cwd=PROJECT, capture_output=True, text=True, timeout=30,
        )
        assert r.returncode == 1
        m = json.loads(metrics.read_text())
        assert m["checks"]["calibration_not_allowed"]["passed"] is False


class TestImporterStructuredChecks:
    """P13-2-2-1 fix-2: importer --out must emit a structured `checks` object
    so mutation gates can target a SPECIFIC rule rather than inferring
    pass/fail from the exit code. Each named check must report
    {passed: bool, observations: {error_codes: [...]}}.
    """

    def _seed(self, tmp_path):
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)

    def test_clean_import_all_checks_pass(self, tmp_path):
        """A clean fixture import must report every check as passed."""
        # Fresh store (no pre-seed) for a clean import.
        _prepare_genfix_sign(tmp_path)
        r = _import(tmp_path)
        assert r.returncode == 0
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["passed"] is True
        assert isinstance(report["checks"], dict)
        for name, chk in report["checks"].items():
            assert chk["passed"] is True, f"{name} should pass on clean import"
            assert "error_codes" in chk["observations"]

    def test_unknown_field_targeted_to_schema_strict(self, tmp_path):
        """An unknown field must fail ONLY schema_strict in the report."""
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["mystery_field"] = "boom"
        inp = tmp_path / "bad.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["passed"] is False
        assert report["checks"]["schema_strict"]["passed"] is False
        # No content-related checks should be falsely implicated.
        assert report["checks"]["task_exists"]["passed"] is True

    def test_dataset_id_mismatch_targeted_to_dataset_identity(self, tmp_path):
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["dataset_id"] = "nonexistent_dataset_0"
        inp = tmp_path / "bad.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["dataset_identity"]["passed"] is False

    def test_unknown_sample_targeted_to_task_exists(self, tmp_path):
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["sample_id"] = "gs_nonexistent_sample"
        inp = tmp_path / "bad.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["task_exists"]["passed"] is False

    def test_fixture_impersonation_targeted_to_fixture_provenance(self, tmp_path):
        """fixture=false + fixann_ id tag must fail fixture_provenance."""
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["fixture"] = False
        # Force a different content hash so it is not an idempotent skip.
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        inp = tmp_path / "bad.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["fixture_provenance"]["passed"] is False

    def test_conflict_targeted_to_annotation_id_conflict(self, tmp_path):
        """Same annotation_id + different content → annotation_id_conflict
        fails (and per-item checks remain green so the conflict is the
        SOLE detected violation)."""
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        # Change only started_at/completed_at (part of content hash) so every
        # per-item rule still passes and the conflict is the sole failure.
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        inp = tmp_path / "conflict.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["annotation_id_conflict"]["passed"] is False
        # Per-item checks must all still pass so the conflict is unambiguous.
        for name in ("schema_strict", "task_exists", "dataset_identity"):
            assert report["checks"][name]["passed"] is True

    def test_top_level_passed_recomputed_from_checks(self, tmp_path):
        """Top-level passed must equal AND of all checks' passed."""
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["mystery_field"] = "boom"
        inp = tmp_path / "bad.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        _import(tmp_path, inp)
        report = json.loads((tmp_path / "import_report.json").read_text())
        recomputed = all(c["passed"] for c in report["checks"].values())
        assert report["passed"] is recomputed
        assert report["passed"] is False


class TestImporterMutationMetaNegatives:
    """The importer mutation runner's detection contract must NOT be fooled
    by exit-code-only failures. These tests exercise the SAME evaluation
    logic the gate uses (_evaluate_detection) via synthetic reports."""

    def _eval(self, exit_code, report_dict_or_none, target_check):
        import tempfile
        d = tempfile.mkdtemp()
        rp = f"{d}/report.json"
        if report_dict_or_none is not None:
            Path(rp).write_text(json.dumps(report_dict_or_none))
        # Import the evaluation helper from the gate script.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gate", str(PROJECT / "scripts" / "p13_2_annotation_mutation_gate.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._evaluate_detection(exit_code, rp, target_check)

    def test_exit1_target_true_not_detected(self):
        """exit 1 + target check passed=true → NOT detected."""
        detected, check_exists, target_passed = self._eval(
            1,
            {"status": "FAIL_VALIDATION", "passed": False,
             "checks": {"schema_strict": {"passed": True,
                           "observations": {"error_codes": [], "error_count": 0}}}},
            "schema_strict")
        assert detected is False
        assert check_exists is True
        assert target_passed is True

    def test_exit1_target_absent_not_detected(self):
        """exit 1 + target check absent → NOT detected."""
        detected, check_exists, target_passed = self._eval(
            1,
            {"status": "FAIL_VALIDATION", "passed": False,
             "checks": {"schema_strict": {"passed": False,
                           "observations": {"error_codes": ["x"], "error_count": 1}}}},
            "fixture_provenance")
        assert detected is False
        assert check_exists is False

    def test_exit1_only_unrelated_check_false_not_detected(self):
        """exit 1 + only an unrelated check false, target true → NOT detected."""
        detected, check_exists, target_passed = self._eval(
            1,
            {"status": "FAIL_VALIDATION", "passed": False,
             "checks": {
                 "fixture_provenance": {"passed": True,
                                        "observations": {"error_codes": [], "error_count": 0}},
                 "schema_strict": {"passed": False,
                                   "observations": {"error_codes": ["y"], "error_count": 1}}}},
            "fixture_provenance")
        assert detected is False
        assert check_exists is True
        assert target_passed is True

    def test_report_missing_not_detected(self):
        """report missing → NOT detected."""
        detected, check_exists, target_passed = self._eval(
            1, None, "schema_strict")
        assert detected is False
        assert check_exists is False


class TestFixtureProvenanceTaskBinding:
    """P13-2-2-1 fix-3: fixture provenance must be bound to frozen task
    fixture field, NOT annotation_id heuristics."""

    def _seed(self, tmp_path):
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)

    def test_commander_bypass_normal_id_rejected(self, tmp_path):
        """Commander's bypass: fixture annotation + normal ID + fixture=false
        must be REJECTED with fixture_provenance=false."""
        self._seed(tmp_path)
        store = tmp_path / "store.json"
        store_before = store.read_bytes() if store.exists() else b""
        data = json.loads(store.read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["annotation_id"] = "ann_human_20260713_0001"
        ann["fixture"] = False
        inp = tmp_path / "bypass.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1, f"Commander bypass must be rejected, got exit {r.returncode}"
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["fixture_provenance"]["passed"] is False, \
            "fixture_provenance must be false for normal ID + fixture=false"
        # Store must be unchanged
        if store.exists():
            assert store.read_bytes() == store_before, "store must not be modified"

    def test_commander_bypass_uuid_id_rejected(self, tmp_path):
        """UUID annotation ID + fixture=false must be rejected."""
        import uuid
        self._seed(tmp_path)
        data = json.loads((tmp_path / "store.json").read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["annotation_id"] = str(uuid.uuid4())
        ann["fixture"] = False
        inp = tmp_path / "bypass_uuid.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["fixture_provenance"]["passed"] is False

    def test_fixture_true_annotation_passes(self, tmp_path):
        """A clean fixture annotation with fixture=true must pass."""
        self._seed(tmp_path)
        data = json.loads((tmp_path / "store.json").read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["annotation_id"] = "ann_clean_fixture_ok"
        ann["fixture"] = True
        # Change started_at to avoid idempotent skip
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        inp = tmp_path / "clean.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 0
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["fixture_provenance"]["passed"] is True

    def test_annotation_id_change_does_not_affect_provenance(self, tmp_path):
        """Changing annotation_id alone (keeping fixture=true) must pass.
        Provenance comes from task fixture, not ID."""
        self._seed(tmp_path)
        data = json.loads((tmp_path / "store.json").read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["annotation_id"] = "completely_different_id_123"
        ann["fixture"] = True  # match task fixture
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        inp = tmp_path / "rename.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 0

    def test_task_fixture_missing_rejected(self, tmp_path):
        """Removing fixture from a task must reject annotations for that task."""
        _prepare_genfix_sign(tmp_path)
        # Corrupt task pack: remove fixture from first task
        dev_pack = json.loads((tmp_path / "tasks" / "human_tasks_development.json").read_text())
        for t in dev_pack["tasks"]:
            if "fixture" in t:
                del t["fixture"]
                break
        (tmp_path / "tasks" / "human_tasks_development.json").write_text(
            json.dumps(dev_pack))
        # Re-sign so pack_trust passes (we want fixture_provenance to catch the fault)
        r_sign = _sign(tmp_path)
        assert r_sign.returncode == 0, f"Re-sign failed: {r_sign.stderr[:200]}"
        # Import a fixture annotation with fixture=true for the corrupted task
        anns = json.loads(
            (tmp_path / "fixture_annotations.json").read_text())["annotations"]
        ann = dict(anns[0])
        ann["annotation_id"] = "test_task_fixture_missing"
        ann["started_at"] = "2020-01-01T00:00:00+00:00"
        ann["completed_at"] = "2020-01-01T00:00:00+00:00"
        inp = tmp_path / "bad.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        r = _import(tmp_path, inp)
        assert r.returncode == 1
        report = json.loads((tmp_path / "import_report.json").read_text())
        assert report["checks"]["fixture_provenance"]["passed"] is False


class TestTaskHashRecompute:
    """P13-2-2-1 fix-4: importer must independently recompute task hash."""

    def test_commander_full_pack_flip_old_hash_rejected(self, tmp_path):
        """Full pack fixture flip + old hash = dataset_identity rejects."""
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)
        import shutil
        tasks_dir = tmp_path / "tasks_corrupt"
        tasks_dir.mkdir()
        for f in ("human_tasks_development.json", "human_tasks_calibration.json",
                  "human_tasks_test_A.json", "human_tasks_test_B.json"):
            src = tmp_path / "tasks" / f
            if src.exists():
                shutil.copy(str(src), str(tasks_dir / f))
        dev_pack = json.loads((tasks_dir / "human_tasks_development.json").read_text())
        dev_pack["fixture"] = False
        for t in dev_pack["tasks"]:
            t["fixture"] = False
        (tasks_dir / "human_tasks_development.json").write_text(json.dumps(dev_pack))
        # Re-sign corrupt directory so pack_trust passes (dataset_identity catches the fault)
        r_sign = _sign_dir(tasks_dir)
        assert r_sign.returncode == 0, f"Re-sign failed: {r_sign.stderr[:200]}"
        data = json.loads((tmp_path / "store.json").read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["annotation_id"] = "commander_bypass_fix4"
        ann["fixture"] = False
        inp = tmp_path / "bypass_fix4.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        import os
        env = dict(os.environ)
        env["APP_ENVIRONMENT"] = "test"
        env["ANNOTATION_PACK_TEST_SIGNING_KEY"] = TEST_KEY
        r = subprocess.run(
            [PY, IMPORT, "--input", str(inp),
             "--tasks", str(tasks_dir),
             "--store", str(tmp_path / "store_bypass.json"),
             "--out", str(tmp_path / "report_bypass.json"),
             "--manifest", str(tasks_dir / "human-task-pack-manifest.json"),
             "--dataset-manifest", str(MANIFEST),
             "--fixture"],
            cwd=PROJECT, capture_output=True, text=True, timeout=30, env=env,
        )
        assert r.returncode == 1
        report = json.loads((tmp_path / "report_bypass.json").read_text())
        assert report["checks"]["dataset_identity"]["passed"] is False

    def test_task_hash_rewritten_both_sides_rejected(self, tmp_path):
        """Same fake hash on both sides = rejected by recompute."""
        _prepare_genfix_sign(tmp_path)
        _import(tmp_path)
        import shutil
        tasks_dir = tmp_path / "tasks_corrupt2"
        tasks_dir.mkdir()
        for f in ("human_tasks_development.json", "human_tasks_calibration.json",
                  "human_tasks_test_A.json", "human_tasks_test_B.json"):
            src = tmp_path / "tasks" / f
            if src.exists():
                shutil.copy(str(src), str(tasks_dir / f))
        fake_hash = "b" * 64
        dev_pack = json.loads((tasks_dir / "human_tasks_development.json").read_text())
        for t in dev_pack["tasks"]:
            t["task_hash"] = fake_hash
            break
        (tasks_dir / "human_tasks_development.json").write_text(json.dumps(dev_pack))
        # Re-sign corrupt directory so pack_trust passes (dataset_identity catches the fault)
        r_sign = _sign_dir(tasks_dir)
        assert r_sign.returncode == 0, f"Re-sign failed: {r_sign.stderr[:200]}"
        data = json.loads((tmp_path / "store.json").read_text())
        ann = dict(data["annotations"][0]["annotation"])
        ann["annotation_id"] = "test_fake_hash_both"
        ann["task_hash"] = fake_hash
        inp = tmp_path / "fake_hash.json"
        inp.write_text(json.dumps({"annotations": [ann]}))
        import os
        env = dict(os.environ)
        env["APP_ENVIRONMENT"] = "test"
        env["ANNOTATION_PACK_TEST_SIGNING_KEY"] = TEST_KEY
        r = subprocess.run(
            [PY, IMPORT, "--input", str(inp),
             "--tasks", str(tasks_dir),
             "--store", str(tmp_path / "store_bypass2.json"),
             "--out", str(tmp_path / "report_bypass2.json"),
             "--manifest", str(tasks_dir / "human-task-pack-manifest.json"),
             "--dataset-manifest", str(MANIFEST),
             "--fixture"],
            cwd=PROJECT, capture_output=True, text=True, timeout=30, env=env,
        )
        assert r.returncode == 1
        report = json.loads((tmp_path / "report_bypass2.json").read_text())
        assert report["checks"]["dataset_identity"]["passed"] is False
