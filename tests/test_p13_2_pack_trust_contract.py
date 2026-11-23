"""P13-2-2-1A fix: Pack trust contract tests.

All paths use tmp_path. NO project artifact is ever modified.

Covers (after Commander P0/P1 fix):
  - Manifest generation with dataset manifest hash binding
  - HMAC-SHA256 signing in test environment with injected key
  - Test key environment boundary: production/development/empty/unknown rejected
  - Manifest mandatory for ALL imports (fixture + production)
  - Tamper detection (SHA, bytes, count, signature, dataset manifest)
  - Production mode: no key → BLOCKED exit 2
  - Test mode: no injected key → BLOCKED exit 2
  - Fixture mode: no manifest → rejected
  - Key safety (no plaintext in outputs)
  - Artifact SHA invariance
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent.parent
PY = sys.executable
PREPARE = str(PROJECT / "scripts" / "p13_2_prepare_human_tasks.py")
GENFIX = str(PROJECT / "scripts" / "p13_2_generate_fixture_annotations.py")
IMPORT = str(PROJECT / "scripts" / "p13_2_import_human_annotations.py")
SIGN = str(PROJECT / "scripts" / "p13_2_sign_human_task_pack.py")

CANDIDATES = PROJECT / "sample_data" / "p13_2" / "positive" / "candidates.json"
MANIFEST = PROJECT / "sample_data" / "p13_2" / "manifest.json"
PREANN = PROJECT / "sample_data" / "p13_2" / "positive" / "preannotations.json"

TEST_KEY = "test-key-for-ci-pipeline"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_artifacts() -> dict[str, str]:
    artifacts = {}
    for p in [CANDIDATES, MANIFEST, PREANN]:
        if p.exists():
            artifacts[str(p)] = _sha256(p)
    return artifacts


def _prepare(tmp_path: Path) -> subprocess.CompletedProcess:
    tasks = tmp_path / "tasks"
    readiness = tmp_path / "readiness.json"
    return subprocess.run(
        [PY, PREPARE,
         "--candidates", str(CANDIDATES),
         "--manifest", str(MANIFEST),
         "--preannotations", str(PREANN),
         "--out-dir", str(tasks),
         "--out", str(readiness),
         "--fixture"],
        cwd=PROJECT, capture_output=True, text=True, timeout=60,
    )


def _genfix(tmp_path: Path) -> subprocess.CompletedProcess:
    tasks = tmp_path / "tasks"
    out = tmp_path / "fixture_annotations.json"
    return subprocess.run(
        [PY, GENFIX, "--tasks", str(tasks), "--out", str(out)],
        cwd=PROJECT, capture_output=True, text=True, timeout=30,
    )


def _sign(tmp_path: Path, fixture: bool = True,
          extra_env: dict | None = None,
          replace_env: bool = False) -> subprocess.CompletedProcess:
    """Sign manifest. Default: test env + injected key."""
    tasks = tmp_path / "tasks"
    out = tmp_path / "sign_report.json"
    cmd = [PY, SIGN, "--tasks", str(tasks),
           "--dataset-manifest", str(MANIFEST)]
    if fixture:
        cmd.append("--fixture")
    cmd.extend(["--out", str(out)])
    if replace_env:
        env = dict(extra_env or {})
    else:
        env = {
            "APP_ENVIRONMENT": "test",
            "ANNOTATION_PACK_TEST_SIGNING_KEY": TEST_KEY,
            "PATH": os.environ.get("PATH", ""),
        }
        if extra_env:
            env.update(extra_env)
    return subprocess.run(cmd, cwd=PROJECT, capture_output=True,
                          text=True, timeout=30, env=env)


def _import(tmp_path: Path, tasks_dir: Path | None = None,
            manifest: Path | None = None,
            dataset_manifest: Path | None = None,
            fixture: bool = True,
            input_path: Path | None = None,
            extra_env: dict | None = None,
            replace_env: bool = False) -> subprocess.CompletedProcess:
    td = tasks_dir or (tmp_path / "tasks")
    store = tmp_path / "store.json"
    inp = input_path or (tmp_path / "fixture_annotations.json")
    report = tmp_path / "import_report.json"
    cmd = [PY, IMPORT, "--input", str(inp),
           "--tasks", str(td), "--store", str(store),
           "--out", str(report)]
    if manifest:
        cmd.extend(["--manifest", str(manifest)])
    if dataset_manifest:
        cmd.extend(["--dataset-manifest", str(dataset_manifest)])
    if fixture:
        cmd.append("--fixture")
    if replace_env:
        env = dict(extra_env or {})
    else:
        env = {
            "APP_ENVIRONMENT": "test",
            "ANNOTATION_PACK_TEST_SIGNING_KEY": TEST_KEY,
            "PATH": os.environ.get("PATH", ""),
        }
        if extra_env:
            env.update(extra_env)
    return subprocess.run(cmd, cwd=PROJECT, capture_output=True,
                          text=True, timeout=30, env=env)


def _read_report(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "import_report.json").read_text())


def _read_sign_report(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "sign_report.json").read_text())


def _setup_full(tmp_path: Path):
    """Prepare + genfix + sign in test env. Common setup."""
    r = _prepare(tmp_path)
    assert r.returncode == 0, r.stderr[:300]
    r = _genfix(tmp_path)
    assert r.returncode == 0, r.stderr[:300]
    r = _sign(tmp_path)
    assert r.returncode == 0, r.stderr[:300]


# ── Manifest generation ──


class TestManifestGeneration:
    def test_manifest_has_dataset_manifest_binding(self, tmp_path):
        _setup_full(tmp_path)
        m = json.loads(
            (tmp_path / "tasks" / "human-task-pack-manifest.json").read_text()
        )
        assert m["schema_version"] == "1.1.0"
        assert "dataset_manifest_path" in m
        assert m["dataset_manifest_path"] == "manifest.json"
        assert "dataset_manifest_sha256" in m
        assert len(m["dataset_manifest_sha256"]) == 64
        # SHA must match actual dataset manifest
        assert m["dataset_manifest_sha256"] == _sha256(MANIFEST)

    def test_total_task_count_matches(self, tmp_path):
        _setup_full(tmp_path)
        m = json.loads(
            (tmp_path / "tasks" / "human-task-pack-manifest.json").read_text()
        )
        assert m["total_task_count"] == sum(p["task_count"] for p in m["packs"])

    def test_packs_sha_match_files(self, tmp_path):
        _setup_full(tmp_path)
        m = json.loads(
            (tmp_path / "tasks" / "human-task-pack-manifest.json").read_text()
        )
        for p in m["packs"]:
            actual = _sha256(tmp_path / "tasks" / p["path"])
            assert p["sha256"] == actual


# ── Signature and environment boundary ──


class TestSignatureAndEnvBoundary:
    def test_valid_test_env_signing_passes(self, tmp_path):
        _prepare(tmp_path)
        r = _sign(tmp_path)
        assert r.returncode == 0
        report = _read_sign_report(tmp_path)
        assert report["status"] == "SIGNED"
        assert report["fixture_only"] is True

    def test_production_env_fixture_rejected_exit1(self, tmp_path):
        """P0-1: APP_ENVIRONMENT=production + --fixture → FAIL exit1."""
        _prepare(tmp_path)
        r = _sign(tmp_path, extra_env={"APP_ENVIRONMENT": "production"})
        assert r.returncode == 1
        result = json.loads(r.stdout)
        assert result["status"] == "FAIL_TEST_KEY_ENVIRONMENT_BOUNDARY"
        assert result["error_kind"] == "test_key_environment_boundary"

    def test_development_env_fixture_rejected_exit1(self, tmp_path):
        """P0-1: APP_ENVIRONMENT=development + --fixture → FAIL exit1."""
        _prepare(tmp_path)
        r = _sign(tmp_path, extra_env={"APP_ENVIRONMENT": "development"})
        assert r.returncode == 1
        result = json.loads(r.stdout)
        assert "BOUNDARY" in result["status"]

    def test_empty_env_fixture_rejected_exit1(self, tmp_path):
        """P0-1: no APP_ENVIRONMENT + --fixture → FAIL exit1."""
        _prepare(tmp_path)
        r = _sign(tmp_path, replace_env=True,
                  extra_env={"PATH": os.environ.get("PATH", "")})
        assert r.returncode == 1

    def test_unknown_env_fixture_rejected_exit1(self, tmp_path):
        """P0-1: APP_ENVIRONMENT=staging + --fixture → FAIL exit1."""
        _prepare(tmp_path)
        r = _sign(tmp_path, extra_env={"APP_ENVIRONMENT": "staging"})
        assert r.returncode == 1

    def test_test_env_no_injected_key_blocked_exit2(self, tmp_path):
        """Test env but no ANNOTATION_PACK_TEST_SIGNING_KEY → BLOCKED exit2."""
        _prepare(tmp_path)
        r = _sign(tmp_path, replace_env=True,
                  extra_env={"APP_ENVIRONMENT": "test",
                             "PATH": os.environ.get("PATH", "")})
        assert r.returncode == 2

    def test_production_no_key_blocked_exit2(self, tmp_path):
        """Production mode no key → BLOCKED exit2."""
        _prepare(tmp_path)
        r = _sign(tmp_path, fixture=False, replace_env=True,
                  extra_env={"PATH": os.environ.get("PATH", "")})
        assert r.returncode == 2


# ── Manifest mandatory ──


class TestManifestMandatory:
    def test_fixture_no_manifest_rejected(self, tmp_path):
        """P0-2: fixture mode without manifest → rejected, store not created."""
        _setup_full(tmp_path)
        r = _import(tmp_path, manifest=None)
        assert r.returncode != 0
        assert not (tmp_path / "store.json").exists()

    def test_fixture_with_valid_manifest_passes(self, tmp_path):
        """Positive: fixture + valid manifest in test env → IMPORTED."""
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        r = _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        assert r.returncode == 0
        report = _read_report(tmp_path)
        assert report["checks"]["pack_trust"]["passed"] is True


# ── Tamper detection ──


class TestTamperDetection:
    def test_pack_content_modified_sha_stale(self, tmp_path):
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        pack_path = tmp_path / "tasks" / "human_tasks_development.json"
        pack = json.loads(pack_path.read_text())
        pack["tasks"][0]["sample_id"] = "TAMPERED"
        pack_path.write_text(json.dumps(pack))
        r = _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        assert r.returncode == 1
        report = _read_report(tmp_path)
        assert report["checks"]["pack_trust"]["passed"] is False

    def test_signature_tampered_rejected(self, tmp_path):
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        m = json.loads(manifest.read_text())
        m["signature"] = "a" * 64
        manifest.write_text(json.dumps(m))
        r = _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        assert r.returncode == 1
        report = _read_report(tmp_path)
        assert report["checks"]["pack_trust"]["passed"] is False

    def test_dataset_manifest_content_changed_rejected(self, tmp_path):
        """P1-1: dataset manifest content differs → pack_trust fails."""
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        # Tamper a copy of dataset manifest
        dm_copy = tmp_path / "dm_tampered.json"
        dm_data = json.loads(MANIFEST.read_text())
        dm_data["created_at"] = "2099-01-01T00:00:00+00:00"
        dm_copy.write_text(json.dumps(dm_data))
        r = _import(tmp_path, manifest=manifest, dataset_manifest=dm_copy)
        assert r.returncode == 1
        report = _read_report(tmp_path)
        assert report["checks"]["pack_trust"]["passed"] is False
        errs = report["checks"]["pack_trust"]["observations"]["error_codes"]
        assert any("dataset_manifest_sha256 mismatch" in e for e in errs)

    def test_path_traversal_in_manifest_rejected(self, tmp_path):
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        m = json.loads(manifest.read_text())
        m["packs"][0]["path"] = "../../../etc/passwd"
        manifest.write_text(json.dumps(m))
        r = _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        assert r.returncode == 1
        report = _read_report(tmp_path)
        assert report["checks"]["pack_trust"]["passed"] is False

    def test_dataset_manifest_path_traversal_rejected(self, tmp_path):
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        m = json.loads(manifest.read_text())
        m["dataset_manifest_path"] = "../../../etc/passwd"
        # Re-sign to isolate the path traversal check
        payload = json.dumps(m, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        m["signature"] = hmac.new(
            TEST_KEY.encode(), payload, hashlib.sha256,
        ).hexdigest()
        manifest.write_text(json.dumps(m))
        r = _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        assert r.returncode == 1
        report = _read_report(tmp_path)
        assert report["checks"]["pack_trust"]["passed"] is False


# ── Key safety ──


class TestKeySafety:
    def test_no_test_key_in_manifest(self, tmp_path):
        _setup_full(tmp_path)
        manifest_json = (
            tmp_path / "tasks" / "human-task-pack-manifest.json"
        ).read_text()
        assert TEST_KEY not in manifest_json

    def test_no_test_key_in_sign_report(self, tmp_path):
        _setup_full(tmp_path)
        report_json = (tmp_path / "sign_report.json").read_text()
        assert TEST_KEY not in report_json

    def test_no_test_key_in_import_report(self, tmp_path):
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        report_json = (tmp_path / "import_report.json").read_text()
        assert TEST_KEY not in report_json


# ── Artifact invariance ──


class TestArtifactInvariance:
    def test_artifacts_unchanged(self, tmp_path):
        before = _snapshot_artifacts()
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        after = _snapshot_artifacts()
        for path, sha in before.items():
            assert after[path] == sha, f"Artifact changed: {path}"


# ── State invariants ──


class TestStateInvariants:
    def test_fixture_annotations_never_counted_as_real(self, tmp_path):
        """Fixture imports never produce real human_verified_count."""
        _setup_full(tmp_path)
        manifest = tmp_path / "tasks" / "human-task-pack-manifest.json"
        r = _import(tmp_path, manifest=manifest, dataset_manifest=MANIFEST)
        assert r.returncode == 0
        store = json.loads((tmp_path / "store.json").read_text())
        for entry in store.get("annotations", []):
            ann = entry.get("annotation", entry)
            assert ann.get("fixture") is True
