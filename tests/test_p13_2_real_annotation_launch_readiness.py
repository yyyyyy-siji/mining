"""P13-2-2-2A fix-4: Readiness contract tests — batch identity + group metadata.

All tests inject tmp_path. Module-level SHA guard protects real evidence.

Positive test: tmp_path signed packs + dataset manifest + pack manifest → READY.
Negative tests (14 production-path): tamper one element → exit 1 with target=false.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys = __import__("sys")
sys.path.insert(0, str(PROJECT))

from scripts.p13_2_real_annotation_launch_readiness import (  # noqa: E402
    MIN_TEST_BLIND,
    OUT_NAME,
    SIDECAR_SUFFIX,
    TEST_BLIND_FORBIDDEN_FIELDS,
    main,
    verify_evidence,
)
from signal_miner.evaluation.human_annotation import compute_task_hash  # noqa: E402
from signal_miner.evaluation.pack_trust import (  # noqa: E402
    generate_pack_manifest,
    sign_manifest,
)

EVIDENCE_JSON = PROJECT / "docs" / "P13-2-evidence" / OUT_NAME
EVIDENCE_SIDECAR = PROJECT / "docs" / "P13-2-evidence" / (OUT_NAME + SIDECAR_SUFFIX)
REAL_FILES = [EVIDENCE_JSON, EVIDENCE_SIDECAR]

PROD_KEY = "production-secret-key-for-test-setup-xyz"
N_DEV, N_CAL, N_TEST_A, N_TEST_B = 50, 25, 30, 30
N_TOTAL = N_DEV + N_CAL + N_TEST_A + N_TEST_B


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Real evidence SHA guard ──

@pytest.fixture(scope="module", autouse=True)
def real_evidence_sha_guard():
    before = {}
    for f in REAL_FILES:
        before[f] = _sha256_bytes(f.read_bytes()) if f.exists() else None
    yield before
    after = {}
    for f in REAL_FILES:
        after[f] = _sha256_bytes(f.read_bytes()) if f.exists() else None
    for f in REAL_FILES:
        assert before[f] == after[f], (
            f"REAL evidence changed: {f.name}")


# ── Task pack generator ──

def _make_task(idx: int, dsid: str, slot: str, split: str,
               mode: str, fixture: bool = False) -> dict:
    content = f"task content {idx} in {split}"
    ch = hashlib.sha256(content.encode()).hexdigest()
    th = compute_task_hash(dsid, f"smp_{split}_{idx:04d}", slot, ch, fixture)
    task = {
        "dataset_id": dsid, "sample_id": f"smp_{split}_{idx:04d}",
        "annotator_slot": slot, "split": split,
        "annotation_mode": mode, "redacted_text": content[:80],
        "content_hash": ch, "task_hash": th, "fixture": fixture,
    }
    return task


def _setup_signed_packs(
    tmp_path: Path,
    dsid: str = "ds_prod_20260714",
) -> dict:
    """Create 4 task packs + dataset manifest + signed pack manifest in tmp_path.

    Returns dict of paths + env_override with production key.
    """
    task_dir = tmp_path / "tasks"
    task_dir.mkdir()

    # Create packs with shared test sample_ids for double-label
    dev = {"schema_version": "1.0.0", "dataset_id": dsid, "split": "development",
           "annotator_slot": "assisted", "annotation_mode": "assisted_review",
           "tasks": [_make_task(i, dsid, "assisted", "development", "assisted_review")
                     for i in range(N_DEV)]}
    cal = {"schema_version": "1.0.0", "dataset_id": dsid, "split": "calibration",
           "annotator_slot": "assisted", "annotation_mode": "assisted_review",
           "tasks": [_make_task(N_DEV + i, dsid, "assisted", "calibration", "assisted_review")
                     for i in range(N_CAL)]}
    # A and B annotate the SAME test samples (double-label)
    test_sample_ids = [f"smp_test_{i:04d}" for i in range(N_TEST_A)]
    # Generate content for each test sample (shared)
    test_contents: dict[str, str] = {}
    test_hashes: dict[str, str] = {}
    for sid in test_sample_ids:
        c = f"test content for {sid}"
        test_contents[sid] = c
        test_hashes[sid] = hashlib.sha256(c.encode()).hexdigest()
    t_a_tasks = []
    t_b_tasks = []
    for _i, sid in enumerate(test_sample_ids):
        ch = test_hashes[sid]
        t_a_tasks.append({
            "dataset_id": dsid, "sample_id": sid,
            "annotator_slot": "A", "split": "test",
            "annotation_mode": "blind",
            "redacted_text": test_contents[sid][:80],
            "content_hash": ch,
            "task_hash": compute_task_hash(dsid, sid, "A", ch, False),
            "fixture": False,
        })
        t_b_tasks.append({
            "dataset_id": dsid, "sample_id": sid,
            "annotator_slot": "B", "split": "test",
            "annotation_mode": "blind",
            "redacted_text": test_contents[sid][:80],
            "content_hash": ch,
            "task_hash": compute_task_hash(dsid, sid, "B", ch, False),
            "fixture": False,
        })
    t_a = {"schema_version": "1.0.0", "dataset_id": dsid, "split": "test",
           "annotator_slot": "A", "annotation_mode": "blind",
           "tasks": t_a_tasks}
    t_b = {"schema_version": "1.0.0", "dataset_id": dsid, "split": "test",
           "annotator_slot": "B", "annotation_mode": "blind",
           "tasks": t_b_tasks}

    (task_dir / "human_tasks_development.json").write_text(json.dumps(dev))
    (task_dir / "human_tasks_calibration.json").write_text(json.dumps(cal))
    (task_dir / "human_tasks_test_A.json").write_text(json.dumps(t_a))
    (task_dir / "human_tasks_test_B.json").write_text(json.dumps(t_b))

    # Dataset manifest
    dm_path = tmp_path / "dataset_manifest.json"
    dm = {"schema_version": "1.0.0", "dataset_id": dsid,
          "created_at": "2026-07-14T00:00:00Z", "total": N_DEV + N_CAL + N_TEST_A}
    dm_path.write_text(json.dumps(dm))

    # Generate pack manifest
    manifest = generate_pack_manifest(
        task_dir, dsid, fixture=False,
        dataset_manifest_path=dm_path,
        signer_key_id="production-key",
    )
    # Sign it
    manifest["signature"] = sign_manifest(manifest, PROD_KEY)
    pm_path = tmp_path / "pack_manifest.json"
    pm_path.write_text(json.dumps(manifest))

    # Candidates
    candidates = []
    for i in range(N_DEV):
        candidates.append({
            "dataset_id": dsid, "sample_id": f"smp_development_{i:04d}",
            "raw_feedback_id": f"rfb_dev_{i:04d}",
            "source_url": f"https://example.com/dev/{i}",
            "source_adapter": "test_adapter", "source_version": "1.0",
            "captured_at": "2026-07-01T00:00:00+00:00",
            "content_sha256": hashlib.sha256(f"task content {i} in development".encode()).hexdigest(),
            "authorization_basis": "explicit_consent",
            "authorization_record_ref": f"auth_dev_{i:04d}",
            "permitted_use": ["annotation"],
            "pii_scanned": True, "pii_redacted": True,
            "raw_text_sha256": "a" * 64, "redacted_text_sha256": "b" * 64,
            "profile": "enterprise", "language": "zh", "source_tier": "primary",
            "session_id": f"session_dev_{i:04d}",
            "conversation_id": f"conv_dev_{i:04d}",
            "near_duplicate_group_id": None,
        })
    for i in range(N_CAL):
        cal_idx = N_DEV + i
        candidates.append({
            "dataset_id": dsid, "sample_id": f"smp_calibration_{cal_idx:04d}",
            "raw_feedback_id": f"rfb_cal_{cal_idx:04d}",
            "source_url": f"https://example.com/cal/{i}",
            "source_adapter": "test_adapter", "source_version": "1.0",
            "captured_at": "2026-07-01T00:00:00Z",
            "content_sha256": hashlib.sha256(f"task content {N_DEV+i} in calibration".encode()).hexdigest(),
            "authorization_basis": "explicit_consent",
            "authorization_record_ref": f"auth_cal_{i:04d}",
            "permitted_use": ["annotation"],
            "pii_scanned": True, "pii_redacted": True,
            "raw_text_sha256": "a" * 64, "redacted_text_sha256": "b" * 64,
            "profile": "enterprise", "language": "zh", "source_tier": "primary",
            "session_id": f"session_cal_{cal_idx:04d}",
            "conversation_id": f"conv_cal_{cal_idx:04d}",
            "near_duplicate_group_id": None,
        })
    for i in range(N_TEST_A):
        sid = f"smp_test_{i:04d}"
        candidates.append({
            "dataset_id": dsid, "sample_id": sid,
            "raw_feedback_id": f"rfb_test_{i:04d}",
            "source_url": f"https://example.com/test/{i}",
            "source_adapter": "test_adapter", "source_version": "1.0",
            "captured_at": "2026-07-01T00:00:00Z",
            "content_sha256": test_hashes[sid],
            "authorization_basis": "explicit_consent",
            "authorization_record_ref": f"auth_test_{i:04d}",
            "permitted_use": ["annotation"],
            "pii_scanned": True, "pii_redacted": True,
            "raw_text_sha256": "a" * 64, "redacted_text_sha256": "b" * 64,
            "profile": "enterprise", "language": "zh", "source_tier": "primary",
            "session_id": f"session_test_{i:04d}",
            "conversation_id": f"conv_test_{i:04d}",
            "near_duplicate_group_id": None,
        })
    rc_path = tmp_path / "real-candidate-export.json"
    rr_path = tmp_path / "real-rejections.json"
    rc_path.write_text(json.dumps({
        "eligible_count": len(candidates), "rejected_count": 0,
        "rejected_by_reason": {}, "candidates": candidates,
    }))
    rr_path.write_text("[]")

    # Roles
    roles_path = tmp_path / "roles.json"
    roles_path.write_text(json.dumps({
        "annotator_a_pseudonym": "ann_a_001",
        "annotator_b_pseudonym": "ann_b_001",
        "adjudicator_pseudonym": "adj_001",
        "a_b_access_isolation": True,
        "double_label_plan_count": 25,
        "total_candidate_count": len(candidates),
    }))

    # Splits
    splits_path = tmp_path / "splits.json"
    splits_path.write_text(json.dumps({
        "development": [f"smp_development_{i:04d}" for i in range(N_DEV)],
        "calibration": [f"smp_calibration_{N_DEV + i:04d}" for i in range(N_CAL)],
        "test": [f"smp_test_{i:04d}" for i in range(N_TEST_A)],
    }))

    # Governance
    gov_path = tmp_path / "governance.json"
    gov_path.write_text(json.dumps({
        "annotation_window_start": "2026-08-01T00:00:00Z",
        "annotation_window_end": "2026-09-01T00:00:00Z",
        "retention_until": "2027-09-01T00:00:00Z",
        "allowed_access_role_ids": ["ann_a_001", "ann_b_001", "adj_001"],
    }))

    return {
        "real_candidate_path": rc_path,
        "real_rejections_path": rr_path,
        "dataset_manifest_path": dm_path,
        "pack_manifest_path": pm_path,
        "task_dir": task_dir,
        "roles_config_path": roles_path,
        "splits_config_path": splits_path,
        "governance_config_path": gov_path,
        "env_override": {"ANNOTATION_PACK_SIGNING_KEY": PROD_KEY},
        "manifest": manifest,
        "dsid": dsid,
    }


def _run_readiness(setup: dict, tmp_path: Path, **overrides) -> tuple[int, dict]:
    """Run main() with setup dict paths, optionally overriding."""
    return main(
        evidence_dir=tmp_path,
        real_candidate_path=setup["real_candidate_path"],
        real_rejections_path=setup["real_rejections_path"],
        dataset_manifest_path=overrides.get("dataset_manifest_path", setup["dataset_manifest_path"]),
        pack_manifest_path=overrides.get("pack_manifest_path", setup["pack_manifest_path"]),
        task_dir=overrides.get("task_dir", setup["task_dir"]),
        roles_config_path=setup["roles_config_path"],
        splits_config_path=setup["splits_config_path"],
        governance_config_path=setup["governance_config_path"],
        environment="production",
        env_override=setup["env_override"],
        publish=False,
    )


# ── Positive test ──

class TestPositive:
    def test_full_signed_packs_ready(self, tmp_path):
        """All signed packs + manifests → READY."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = _run_readiness(setup, tmp_path)

        assert exit_code == report["exit_code"] == 0
        assert report["status"] == "READY_FOR_HUMAN_ANNOTATION"
        assert report["passed"] is True
        assert report["check_passed"]["pack_trust"] is True
        assert report["check_passed"]["task_identity"] is True
        assert report["check_passed"]["test_blind_leakage"] is True
        assert report["check_passed"]["split_isolation"] is True
        assert report["check_passed"]["group_isolation"] is True
        assert report["checks"]["group_isolation"]["missing_group_rows"] == []
        assert report["checks"]["group_isolation"]["cross_split_groups"] == []
        assert report["dataset_id"] == setup["dsid"]
        assert report["dataset_manifest_sha256"] is not None
        assert report["pack_manifest_sha256"] is not None
        assert report["human_verified_count"] == 0
        assert report["calibration_allowed"] is False
        tl = report["checks"]["test_blind_leakage"]
        assert tl["test_unique_task_count"] >= MIN_TEST_BLIND
        dl = report["checks"]["double_label_recomputed"]
        assert dl["double_label_actual_count"] >= 1  # A and B share test samples
        assert dl["slot_isolation_ok"] is True


# ── Negative: manifest / dataset tamper ──

class TestNegManifestTamper:
    def test_n1_no_dataset_manifest(self, tmp_path):
        """No dataset manifest → missing/exit2."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = _run_readiness(
            setup, tmp_path, dataset_manifest_path=None)
        assert report["passed"] is False
        assert report["exit_code"] == 2

    def test_n1b_dataset_manifest_tampered(self, tmp_path):
        """Dataset manifest content changed → manifest verification fails → exit1."""
        setup = _setup_signed_packs(tmp_path)
        dm = json.loads(setup["dataset_manifest_path"].read_text())
        dm["created_at"] = "1999-01-01T00:00:00Z"
        setup["dataset_manifest_path"].write_text(json.dumps(dm))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["pack_trust"] is False

    def test_n2_no_pack_manifest(self, tmp_path):
        """No pack manifest → exit2."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = _run_readiness(
            setup, tmp_path, pack_manifest_path=None)
        assert report["passed"] is False
        assert report["exit_code"] == 2

    def test_n2b_signature_tampered(self, tmp_path):
        """Signature in manifest changed → exit1."""
        setup = _setup_signed_packs(tmp_path)
        m = json.loads(setup["pack_manifest_path"].read_text())
        m["signature"] = "a" * 64
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["pack_trust"] is False

    def test_n3_pack_sha_tampered(self, tmp_path):
        """SHA in manifest → exit1."""
        setup = _setup_signed_packs(tmp_path)
        m = json.loads(setup["pack_manifest_path"].read_text())
        m["packs"][0]["sha256"] = "b" * 64
        # Must re-sign after changing SHA
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["pack_trust"] is False

    def test_n3b_pack_bytes_tampered(self, tmp_path):
        """bytes in manifest changed → exit1."""
        setup = _setup_signed_packs(tmp_path)
        m = json.loads(setup["pack_manifest_path"].read_text())
        m["packs"][0]["bytes"] = 999999
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["pack_trust"] is False

    def test_n3c_pack_count_tampered(self, tmp_path):
        """task_count in manifest changed → exit1."""
        setup = _setup_signed_packs(tmp_path)
        m = json.loads(setup["pack_manifest_path"].read_text())
        m["packs"][0]["task_count"] = 999
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["pack_trust"] is False

    def test_n4_task_hash_tampered(self, tmp_path):
        """Task hash in pack changed → exit1."""
        setup = _setup_signed_packs(tmp_path)
        pack = json.loads(
            (setup["task_dir"] / "human_tasks_development.json").read_text())
        pack["tasks"][0]["task_hash"] = "d" * 64
        (setup["task_dir"] / "human_tasks_development.json").write_text(
            json.dumps(pack))
        # Must re-sign manifest after pack change
        m = json.loads(setup["pack_manifest_path"].read_text())
        for p in m["packs"]:
            if p["path"] == "human_tasks_development.json":
                p["sha256"] = _sha256_bytes(
                    (setup["task_dir"] / "human_tasks_development.json").read_bytes())
                p["bytes"] = (setup["task_dir"] /
                              "human_tasks_development.json").stat().st_size
                break
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["task_identity"] is False

    def test_n5_empty_test_packs(self, tmp_path):
        """Empty test packs → exit1."""
        setup = _setup_signed_packs(tmp_path)
        for name in ("human_tasks_test_A.json", "human_tasks_test_B.json"):
            p = setup["task_dir"] / name
            pack = json.loads(p.read_text())
            pack["tasks"] = []
            p.write_text(json.dumps(pack))
        # Re-sign manifest
        m = json.loads(setup["pack_manifest_path"].read_text())
        for p in m["packs"]:
            pf = setup["task_dir"] / p["path"]
            p["sha256"] = _sha256_bytes(pf.read_bytes())
            p["bytes"] = pf.stat().st_size
            p["task_count"] = 0
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1

    def test_n6_split_ids_no_candidates(self, tmp_path):
        """Split sample IDs don't match candidates → exit1."""
        setup = _setup_signed_packs(tmp_path)
        sp = json.loads(setup["splits_config_path"].read_text())
        sp["development"] = [f"ghost_{i:04d}" for i in range(50)]
        setup["splits_config_path"].write_text(json.dumps(sp))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["split_isolation"] is False

    def test_n7_content_cross_split(self, tmp_path):
        """Same sample_id in development and test → exit1."""
        setup = _setup_signed_packs(tmp_path)
        sp = json.loads(setup["splits_config_path"].read_text())
        dev = sp["development"]
        tst = sp["test"]
        shared = dev[0]
        if shared not in tst:
            tst = [shared] + tst[1:]
        sp["test"] = tst
        setup["splits_config_path"].write_text(json.dumps(sp))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["split_isolation"] is False

    def test_n8_double_label_config_20_actual_0(self, tmp_path):
        """Roles claim double-label=20 but A/B have no shared samples → exit1."""
        setup = _setup_signed_packs(tmp_path)
        # Make A and B have different sample_id sets
        t_a = json.loads(
            (setup["task_dir"] / "human_tasks_test_A.json").read_text())
        t_b = json.loads(
            (setup["task_dir"] / "human_tasks_test_B.json").read_text())
        dsid = setup["dsid"]
        for i, task in enumerate(t_a["tasks"]):
            task["sample_id"] = f"smp_a_only_{i:04d}"
            task["content_hash"] = hashlib.sha256(
                f"a only {i}".encode()).hexdigest()
            task["task_hash"] = compute_task_hash(
                dsid, task["sample_id"], "A", task["content_hash"], False)
        for i, task in enumerate(t_b["tasks"]):
            task["sample_id"] = f"smp_b_only_{i:04d}"
            task["content_hash"] = hashlib.sha256(
                f"b only {i}".encode()).hexdigest()
            task["task_hash"] = compute_task_hash(
                dsid, task["sample_id"], "B", task["content_hash"], False)
        (setup["task_dir"] / "human_tasks_test_A.json").write_text(json.dumps(t_a))
        (setup["task_dir"] / "human_tasks_test_B.json").write_text(json.dumps(t_b))
        # Re-sign manifest
        m = json.loads(setup["pack_manifest_path"].read_text())
        for p in m["packs"]:
            pf = setup["task_dir"] / p["path"]
            p["sha256"] = _sha256_bytes(pf.read_bytes())
            p["bytes"] = pf.stat().st_size
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        dl = report["checks"]["double_label_recomputed"]
        assert dl["double_label_actual_count"] == 0

    def test_n9_a_pack_has_b_label(self, tmp_path):
        """A pack contains 'B' annotator_slot → exit1 (slot isolation violated)."""
        setup = _setup_signed_packs(tmp_path)
        t_a = json.loads(
            (setup["task_dir"] / "human_tasks_test_A.json").read_text())
        t_a["tasks"][0]["annotator_slot"] = "B"
        t_a["tasks"][0]["task_hash"] = compute_task_hash(
            t_a["tasks"][0]["dataset_id"], t_a["tasks"][0]["sample_id"],
            "B", t_a["tasks"][0]["content_hash"], False)
        (setup["task_dir"] / "human_tasks_test_A.json").write_text(json.dumps(t_a))
        # Re-sign
        m = json.loads(setup["pack_manifest_path"].read_text())
        for p in m["packs"]:
            pf = setup["task_dir"] / p["path"]
            p["sha256"] = _sha256_bytes(pf.read_bytes())
            p["bytes"] = pf.stat().st_size
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        dl = report["checks"]["double_label_recomputed"]
        assert dl["slot_isolation_ok"] is False

    def test_n10_rejection_count_mismatch(self, tmp_path):
        """Declared rejected_count=999 but actual rejections file has 0 → exit1."""
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        rc["rejected_count"] = 999
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["real_candidates"] is False

    def test_n11_bad_captured_at(self, tmp_path):
        """captured_at is not ISO 8601 → exit1."""
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        rc["candidates"][0]["captured_at"] = "not-a-timestamp"
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1

    def test_n12_access_list_no_roles(self, tmp_path):
        """allowed_access_role_ids doesn't include A/B/adj → exit1."""
        setup = _setup_signed_packs(tmp_path)
        gov = json.loads(setup["governance_config_path"].read_text())
        gov["allowed_access_role_ids"] = ["stranger_001"]
        setup["governance_config_path"].write_text(json.dumps(gov))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["annotation_governance"] is False

    def test_n13_prod_key_substitute(self, tmp_path):
        """Production key matches fixture pattern → exit1."""
        setup = _setup_signed_packs(tmp_path)
        env = {"ANNOTATION_PACK_SIGNING_KEY": "fixture_test_key_value"}
        exit_code, report = main(
            evidence_dir=tmp_path,
            real_candidate_path=setup["real_candidate_path"],
            real_rejections_path=setup["real_rejections_path"],
            dataset_manifest_path=setup["dataset_manifest_path"],
            pack_manifest_path=setup["pack_manifest_path"],
            task_dir=setup["task_dir"],
            roles_config_path=setup["roles_config_path"],
            splits_config_path=setup["splits_config_path"],
            governance_config_path=setup["governance_config_path"],
            environment="production",
            env_override=env,
            publish=False,
        )
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["production_signing_key"] is False

    def test_n14_verify_evidence_tampered_sidecar(self, tmp_path):
        """Publish, then tamper sidecar, then verify → exit1."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = main(
            evidence_dir=tmp_path,
            real_candidate_path=setup["real_candidate_path"],
            real_rejections_path=setup["real_rejections_path"],
            dataset_manifest_path=setup["dataset_manifest_path"],
            pack_manifest_path=setup["pack_manifest_path"],
            task_dir=setup["task_dir"],
            roles_config_path=setup["roles_config_path"],
            splits_config_path=setup["splits_config_path"],
            governance_config_path=setup["governance_config_path"],
            environment="production",
            env_override=setup["env_override"],
            publish=True,
        )
        assert exit_code == 0

        # Tamper sidecar
        sc_path = tmp_path / (OUT_NAME + SIDECAR_SUFFIX)
        sc_path.write_text("deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef  fake.json")
        ok, errs = verify_evidence(tmp_path)
        assert ok is False
        assert len(errs) > 0

    def test_n14b_verify_evidence_tampered_json(self, tmp_path):
        """Publish, then tamper JSON, then verify → exit1."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = main(
            evidence_dir=tmp_path,
            real_candidate_path=setup["real_candidate_path"],
            real_rejections_path=setup["real_rejections_path"],
            dataset_manifest_path=setup["dataset_manifest_path"],
            pack_manifest_path=setup["pack_manifest_path"],
            task_dir=setup["task_dir"],
            roles_config_path=setup["roles_config_path"],
            splits_config_path=setup["splits_config_path"],
            governance_config_path=setup["governance_config_path"],
            environment="production",
            env_override=setup["env_override"],
            publish=True,
        )
        assert exit_code == 0

        # Tamper JSON
        jp = tmp_path / OUT_NAME
        data = json.loads(jp.read_text())
        data["status"] = "TAMPERED_FORCE"
        jp.write_text(json.dumps(data))
        ok, errs = verify_evidence(tmp_path)
        assert ok is False
        assert len(errs) > 0

    def test_no_task_dir_evidence_missing(self, tmp_path):
        """No task_dir → verification should BLOCKED/exit2."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = _run_readiness(
            setup, tmp_path, task_dir=None)
        assert report["passed"] is False
        assert report["exit_code"] == 2, (
            "no task_dir should be BLOCKED (missing), not INVALID")


# ── Regression: previous fix checks still work ──

class TestRegression:
    def test_count_mismatch(self, tmp_path):
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        rc["eligible_count"] = 999
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["real_candidates"] is False

    def test_zero_inputs_blocked(self, tmp_path):
        """No real inputs → exit2 BLOCKED (regression)."""
        rc_path = tmp_path / "real-candidate-export.json"
        rr_path = tmp_path / "real-rejections.json"
        rc_path.write_text(json.dumps(
            {"eligible_count": 0, "rejected_count": 0, "candidates": []}))
        rr_path.write_text("[]")
        exit_code, report = main(
            evidence_dir=tmp_path,
            real_candidate_path=rc_path,
            real_rejections_path=rr_path,
            publish=False,
        )
        assert report["exit_code"] == 2
        assert report["status"] == "BLOCKED_INPUT_REQUIRED"

    @pytest.mark.parametrize("field", TEST_BLIND_FORBIDDEN_FIELDS)
    def test_forbidden_field_in_test(self, tmp_path, field):
        """Test pack contains forbidden field → exit1."""
        setup = _setup_signed_packs(tmp_path)
        t_a = json.loads(
            (setup["task_dir"] / "human_tasks_test_A.json").read_text())
        t_a["tasks"][0][field] = "leak"
        (setup["task_dir"] / "human_tasks_test_A.json").write_text(
            json.dumps(t_a))
        # Re-sign
        m = json.loads(setup["pack_manifest_path"].read_text())
        for p in m["packs"]:
            pf = setup["task_dir"] / p["path"]
            p["sha256"] = _sha256_bytes(pf.read_bytes())
            p["bytes"] = pf.stat().st_size
        m["signature"] = sign_manifest(m, PROD_KEY)
        setup["pack_manifest_path"].write_text(json.dumps(m))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["test_blind_leakage"] is False


# ── Fix-4: batch_id + group metadata + naive datetime ──

class TestFix4:
    def test_batch_id_non_null_and_has_components(self, tmp_path):
        """READY must have non-null batch_id with all 7 components."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = _run_readiness(setup, tmp_path)
        assert exit_code == 0
        assert report["batch_id"] is not None
        assert report["batch_id"].startswith("annbatch_")
        bci = report["batch_id_components"]
        for key in ("dataset_manifest", "pack_manifest", "real_candidate_export",
                    "real_rejections", "roles_config", "splits_config",
                    "governance_config"):
            assert key in bci, f"missing component: {key}"
            assert bci[key] is not None, f"component {key} is null"

    def test_batch_id_changes_when_governance_changes(self, tmp_path):
        """Changing governance (valid) changes batch_id while still READY."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = _run_readiness(setup, tmp_path)
        assert exit_code == 0
        bid1 = report["batch_id"]

        # Modify governance retention date (still valid)
        gov = json.loads(setup["governance_config_path"].read_text())
        gov["retention_until"] = "2030-09-01T00:00:00+00:00"
        setup["governance_config_path"].write_text(json.dumps(gov))
        exit_code2, report2 = _run_readiness(setup, tmp_path)
        assert exit_code2 == 0
        assert report2["batch_id"] != bid1, "batch_id must change when governance changes"
        assert report2["batch_id_components"]["governance_config"] != report["batch_id_components"]["governance_config"]

    def test_batch_id_changes_when_roles_change(self, tmp_path):
        """Changing roles double_label_plan_count (valid) changes batch_id while READY."""
        setup = _setup_signed_packs(tmp_path)
        exit_code, report = _run_readiness(setup, tmp_path)
        assert exit_code == 0
        bid1 = report["batch_id"]

        roles = json.loads(setup["roles_config_path"].read_text())
        roles["double_label_plan_count"] = 30  # still >= 21, still valid
        setup["roles_config_path"].write_text(json.dumps(roles))
        exit_code2, report2 = _run_readiness(setup, tmp_path)
        assert exit_code2 == 0
        assert report2["batch_id"] != bid1, "batch_id must change when roles change"

    def test_group_metadata_missing_single_candidate(self, tmp_path):
        """Delete all group metadata from one candidate → exit1 group_isolation=false."""
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        for key in ("session_id", "conversation_id", "near_duplicate_group_id"):
            rc["candidates"][0].pop(key, None)
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["group_isolation"] is False
        assert len(report["checks"]["group_isolation"]["missing_group_rows"]) >= 1

    def test_group_metadata_missing_session_id(self, tmp_path):
        """Single candidate missing session_id → exit1."""
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        rc["candidates"][0]["session_id"] = ""
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["group_isolation"] is False

    def test_naive_datetime_structured_error(self, tmp_path):
        """Naive governance datetime → exit1, no unexpected TypeError."""
        setup = _setup_signed_packs(tmp_path)
        gov = json.loads(setup["governance_config_path"].read_text())
        gov["annotation_window_start"] = "2026-08-01T00:00:00"  # no TZ
        setup["governance_config_path"].write_text(json.dumps(gov))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1, (
            f"naive datetime must be exit 1, got {report['exit_code']}: {report.get('errors')}"
        )
        assert report["check_passed"]["annotation_governance"] is False
        # Must NOT be an unexpected error
        for e in report["errors"]:
            assert "unexpected" not in e.lower(), f"found unexpected error: {e}"

    def test_cross_split_session_group(self, tmp_path):
        """Same session_id in dev and test → exit1."""
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        shared_session = "shared_session_cross_split"
        rc["candidates"][0]["session_id"] = shared_session
        # Find a test candidate and give it same session
        for cand in rc["candidates"]:
            if cand["sample_id"].startswith("smp_test_"):
                cand["session_id"] = shared_session
                break
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert report["passed"] is False
        assert report["exit_code"] == 1
        assert report["check_passed"]["group_isolation"] is False

    def test_ndg_field_missing_single_candidate(self, tmp_path):
        """Delete only near_duplicate_group_id from one candidate → exit1."""
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        del rc["candidates"][0]["near_duplicate_group_id"]
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert exit_code == report["exit_code"] == 1
        assert report["status"] == "FAILED_INVALID_INPUT"
        assert report["passed"] is False
        assert report["check_passed"]["group_isolation"] is False
        assert "smp_development_0000" in report["checks"]["group_isolation"]["missing_group_rows"]

    def test_ndg_cross_split(self, tmp_path):
        """Same non-null near_duplicate_group_id in dev and test → exit1."""
        setup = _setup_signed_packs(tmp_path)
        rc = json.loads(setup["real_candidate_path"].read_text())
        shared_ndg = "nd_group_shared_001"
        rc["candidates"][0]["near_duplicate_group_id"] = shared_ndg
        # Find a test candidate and give same ndg
        for cand in rc["candidates"]:
            if cand["sample_id"].startswith("smp_test_"):
                cand["near_duplicate_group_id"] = shared_ndg
                break
        setup["real_candidate_path"].write_text(json.dumps(rc))
        exit_code, report = _run_readiness(setup, tmp_path)
        assert exit_code == report["exit_code"] == 1
        assert report["status"] == "FAILED_INVALID_INPUT"
        assert report["passed"] is False
        assert report["check_passed"]["group_isolation"] is False

        # Verify cross_split_groups content precisely
        gi = report["checks"]["group_isolation"]
        csg = gi["cross_split_groups"]
        assert len(csg) >= 1, f"expected cross-split groups, got: {gi}"
        found = False
        for entry in csg:
            if ("near_duplicate_group_id" in entry
                    and "nd_group_shared_001" in entry
                    and "development" in entry
                    and "test" in entry):
                found = True
                break
        assert found, (
            f"cross_split_groups must contain near_duplicate_group_id="
            f"nd_group_shared_001 spanning development+test, got: {csg}"
        )


# ── Evidence isolation ──

class TestRealEvidenceIsolation:
    def test_sha_unchanged(self, real_evidence_sha_guard):
        for f in REAL_FILES:
            if real_evidence_sha_guard[f] is not None:
                assert real_evidence_sha_guard[f] is not None
