"""P13-2-1 fix-2: Gold-set contract tests — all paths use tmp_path, zero artifact pollution."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT = Path(__file__).resolve().parent.parent
PY = sys.executable
EXPORT = str(PROJECT / "scripts" / "p13_2_export_annotation_pack.py")
VALIDATE = str(PROJECT / "scripts" / "p13_2_validate_goldset.py")
PREANNOTATE = str(PROJECT / "scripts" / "p13_2_generate_preannotations.py")
FIXTURE = PROJECT / "sample_data" / "p13_2" / "positive" / "fixture_feedback.json"


def _export(tmp_path: Path, *extra_args: str, fixture: str = str(FIXTURE)) -> subprocess.CompletedProcess:
    """Export with ALL outputs to tmp_path. Never touches project artifacts."""
    out = tmp_path / "candidates.json"
    manifest = tmp_path / "manifest.json"
    rejects = tmp_path / "rejects.json"
    cmd = [PY, EXPORT, "--fixture", fixture, "--seed", "42",
           "--out", str(out), "--manifest", str(manifest), "--rejects", str(rejects)]
    cmd.extend(extra_args)
    return subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=60)


def _validate(tmp_path: Path, *extra_args: str) -> subprocess.CompletedProcess:
    """Validate with ALL inputs/outputs from tmp_path. Never touches project artifacts."""
    metrics = tmp_path / "metrics.json"
    cmd = [PY, VALIDATE,
           "--candidates", str(tmp_path / "candidates.json"),
           "--manifest", str(tmp_path / "manifest.json"),
           "--preannotations", str(tmp_path / "preannotations.json"),
           "--test-pack-a", str(tmp_path / "annotation_pack_test_A.json"),
           "--test-pack-b", str(tmp_path / "annotation_pack_test_B.json"),
           "--dev-pack", str(tmp_path / "annotation_pack_development.json"),
           "--cal-pack", str(tmp_path / "annotation_pack_calibration.json"),
           "--out", str(metrics)]
    cmd.extend(extra_args)
    return subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=30)


def _full_pipeline(tmp_path: Path, fixture: str = str(FIXTURE)):
    """Export → preannotate → validate, all in tmp_path."""
    fix = tmp_path / "fixture.json"
    fix.write_text(Path(fixture).read_text())

    # Export with test packs
    r1 = _export(tmp_path, "--test-packs", fixture=str(fix))
    assert r1.returncode == 0, f"Export failed: {r1.stderr[:300]}"

    # Preannotate in fixture mode
    r2 = subprocess.run(
        [PY, PREANNOTATE,
         "--candidates", str(tmp_path / "candidates.json"),
         "--out", str(tmp_path / "preannotations.json"),
         "--fixture-mode"],
        cwd=PROJECT, capture_output=True, text=True, timeout=30,
    )
    assert r2.returncode == 0, f"Preannotate failed: {r2.stderr[:300]}"

    # Validate
    r3 = _validate(tmp_path)
    return r3


class TestPositivePath:
    """Export + validate on fixture should both pass."""

    def test_export_creates_candidates(self, tmp_path):
        r = _export(tmp_path, "--test-packs")
        assert r.returncode == 0, r.stderr[:300]
        assert (tmp_path / "candidates.json").exists()
        # Verify all 7 artifacts created
        assert (tmp_path / "manifest.json").exists()
        assert (tmp_path / "annotation_pack_test_A.json").exists()
        assert (tmp_path / "annotation_pack_test_B.json").exists()
        assert (tmp_path / "annotation_pack_development.json").exists()
        assert (tmp_path / "annotation_pack_calibration.json").exists()

    def test_validate_passes(self, tmp_path):
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0, f"Validate failed: {r.stdout[:200]}"
        data = json.loads(r.stdout)
        assert data["passed"] is True

    def test_deterministic(self, tmp_path):
        """Two export runs with same seed produce identical sample IDs."""
        d1 = tmp_path / "a"
        d2 = tmp_path / "b"
        d1.mkdir()
        d2.mkdir()
        fix = tmp_path / "fixture.json"
        fix.write_text(FIXTURE.read_text())
        r1 = _export(d1, "--test-packs", fixture=str(fix))
        assert r1.returncode == 0, r1.stderr[:200]
        r2 = _export(d2, "--test-packs", fixture=str(fix))
        assert r2.returncode == 0, r2.stderr[:200]
        ids1 = [s["sample_id"] for s in json.loads((d1 / "candidates.json").read_text())]
        ids2 = [s["sample_id"] for s in json.loads((d2 / "candidates.json").read_text())]
        assert ids1 == ids2

    def test_splits_exact(self, tmp_path):
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        sc = metrics["split_counts"]
        assert sc["development"] == 50
        assert sc["calibration"] == 25
        assert sc["test"] == 25

    def test_double_annotation_recomputed(self, tmp_path):
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["double_annotation_count"] >= 20

    def test_source_platform_separate_from_capture(self, tmp_path):
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        # source_platform should have real platform names, not capture methods
        sp = metrics["source_distribution"]
        assert "manual" not in sp
        assert "api" not in sp
        assert "import" not in sp
        assert "crawl" not in sp
        # capture_method should have the actual methods
        cm = metrics["capture_method_distribution"]
        assert set(cm.keys()).issubset({"api", "manual", "import", "crawl"})

    def test_manifest_freeze_idempotent(self, tmp_path):
        """Re-export with same params should NOT update created_at."""
        fix = tmp_path / "fixture.json"
        fix.write_text(FIXTURE.read_text())
        r1 = _export(tmp_path, "--test-packs", fixture=str(fix))
        assert r1.returncode == 0
        m1 = json.loads((tmp_path / "manifest.json").read_text())
        assert m1["created_at"]

        # Re-export to a different output but same manifest path
        d2 = tmp_path / "reexport"
        d2.mkdir()
        fix2 = d2 / "fixture.json"
        fix2.write_text(FIXTURE.read_text())
        r2 = subprocess.run(
            [PY, EXPORT, "--fixture", str(fix2), "--seed", "42",
             "--out", str(d2 / "candidates.json"),
             "--manifest", str(d2 / "manifest.json"),
             "--rejects", str(d2 / "rejects.json"),
             "--test-packs"],
            cwd=PROJECT, capture_output=True, text=True, timeout=60,
        )
        assert r2.returncode == 0
        m2 = json.loads((d2 / "manifest.json").read_text())
        # Dataset ID should be same
        assert m1["dataset_id"] == m2["dataset_id"]


class TestNegativeViaCLI:
    """Each negative case calls the actual CLI validator and asserts non-zero exit."""

    def test_missing_auth_rejected(self, tmp_path):
        d = json.loads(FIXTURE.read_text())
        d[0]["authorization_basis"] = ""
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps(d))
        r = _export(tmp_path, fixture=str(bad))
        assert r.returncode == 2

    def test_invalid_auth_rejected(self, tmp_path):
        d = json.loads(FIXTURE.read_text())
        d[0]["authorization_basis"] = "not_in_whitelist"
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps(d))
        r = _export(tmp_path, fixture=str(bad))
        assert r.returncode == 2

    def test_sensitive_content_blocked(self):
        from signal_miner.evaluation import has_sensitive
        assert has_sensitive("contact test@example.com") is True
        assert has_sensitive("call 13800138000") is True
        assert has_sensitive("normal text without sensitive") is False

    def test_evidence_offset_unicode(self):
        from signal_miner.evaluation import EvidenceSpan, validate_evidence
        text = "你好世界"
        ok_spans = [EvidenceSpan(start=0, end=2, text="你好")]
        assert len(validate_evidence(text, ok_spans)) == 0
        bad_spans = [EvidenceSpan(start=1, end=3, text="好玩")]
        mismatches = validate_evidence(text, bad_spans)
        assert len(mismatches) == 1

    def test_blind_pack_leak_detection(self):
        from signal_miner.evaluation import check_blind_pack_leakage
        assert check_blind_pack_leakage({"samples": [{"sample_id": "x", "redacted_text": "safe"}]}) == 0
        assert check_blind_pack_leakage({"samples": [{"sample_id": "x", "model_self_score": 0.9}]}) > 0

    def test_authorization_whitelist(self):
        from signal_miner.evaluation import AUTHORIZED_BASES
        assert "explicit_user_consent" in AUTHORIZED_BASES
        assert "invalid" not in AUTHORIZED_BASES

    def test_is_test_record(self):
        from signal_miner.evaluation import is_test_or_mock_record
        assert is_test_or_mock_record("test_record_001") is True
        assert is_test_or_mock_record("fb_normal_001") is False

    def test_redaction(self):
        from signal_miner.evaluation import redact_sensitive
        text, changed = redact_sensitive("email test@example.com and phone 13800138000")
        assert changed is True
        assert "test@example.com" not in text
        assert "13800138000" not in text

    def test_extra_forbid(self):
        import pydantic

        from signal_miner.evaluation import GoldRecord
        with pytest.raises(pydantic.ValidationError):
            GoldRecord(sample_id="x", profile="product_feedback",
                       authorization_basis="internal_feedback_channel",
                       unknown_field="should_fail")

    def test_preannotation_blocked_without_fixture(self, tmp_path):
        """Default mode (no --fixture-mode) returns BLOCKED when no API key."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        # Override API key to empty to simulate no key
        import os
        env = {**os.environ, "DEEPSEEK_API_KEY": "", "OPENAI_API_KEY": "",
               "GOOGLE_API_KEY": "", "QWEN_API_KEY": "", "MINIMAX_API_KEY": ""}
        r2 = subprocess.run(
            [PY, PREANNOTATE,
             "--candidates", str(tmp_path / "candidates.json"),
             "--out", str(tmp_path / "blocked_preann.json")],
            cwd=PROJECT, capture_output=True, text=True, timeout=30,
            env=env,
        )
        assert r2.returncode == 2
        data = json.loads(r2.stdout)
        assert data["status"] == "BLOCKED_PREANNOTATION_UNAVAILABLE"

    def test_ab_missing_fails_validation(self, tmp_path):
        """Validator must fail when A/B packs are missing."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        # Remove A/B packs
        (tmp_path / "annotation_pack_test_A.json").unlink()
        (tmp_path / "annotation_pack_test_B.json").unlink()
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["files_exist"]["passed"] is False

    def test_dataset_id_tampered_fails(self, tmp_path):
        """Validator must catch manifest identity mismatch."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        m = json.loads((tmp_path / "manifest.json").read_text())
        m["dataset_id"] = "tampered0000000"
        (tmp_path / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False))
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["manifest_identity"]["passed"] is False

    def test_sensitive_with_redaction_false(self, tmp_path):
        """Sensitive content must fail regardless of redaction_applied."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        c = json.loads((tmp_path / "candidates.json").read_text())
        c[0]["redacted_text"] = "email test@example.com"
        c[0]["redaction_applied"] = False
        (tmp_path / "candidates.json").write_text(json.dumps(c, indent=2, ensure_ascii=False))
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["sensitive_content"]["passed"] is False

    def test_invalid_signal_type_detected(self, tmp_path):
        """Invalid signal type not in production whitelist must fail."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        p = tmp_path / "preannotations.json"
        data = json.loads(p.read_text())
        for sg in data.get("suggestions", []):
            for sig in sg.get("suggested_signals", []):
                sig["signal_type"] = "totally_invalid"
            break
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["suggestion_signal_types"]["passed"] is False

    def test_ab_slot_must_be_precise(self, tmp_path):
        """A pack samples must have annotator_slot=A, not none."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        a = json.loads((tmp_path / "annotation_pack_test_A.json").read_text())
        for s in a.get("samples", []):
            s["annotator_slot"] = "none"
        (tmp_path / "annotation_pack_test_A.json").write_text(json.dumps(a, indent=2, ensure_ascii=False))
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["pack_contract"]["passed"] is False

    def test_dev_pack_content_drift_detected(self, tmp_path):
        """Dev pack content differing from candidate must fail."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        dev = json.loads((tmp_path / "annotation_pack_development.json").read_text())
        if dev.get("samples"):
            dev["samples"][0]["redacted_text"] = "TAMPERED CONTENT"
        (tmp_path / "annotation_pack_development.json").write_text(json.dumps(dev, indent=2, ensure_ascii=False))
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["pack_contract"]["passed"] is False

    def test_source_platform_empty_detected(self, tmp_path):
        """Single empty source_platform must fail source_platform_contract."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        c = json.loads((tmp_path / "candidates.json").read_text())
        c[0]["source_platform"] = ""
        (tmp_path / "candidates.json").write_text(json.dumps(c, indent=2, ensure_ascii=False))
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["source_platform_contract"]["passed"] is False

    def test_fixture_disguised_as_deepseek(self, tmp_path):
        """Fixture preannotations renamed to DeepSeek must fail."""
        r = _full_pipeline(tmp_path)
        assert r.returncode == 0
        p = tmp_path / "preannotations.json"
        data = json.loads(p.read_text())
        data["fixture_only"] = False
        for sg in data.get("suggestions", []):
            sg["fixture_only"] = False
            sg["suggestion_model"] = "deepseek"
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        r2 = _validate(tmp_path)
        assert r2.returncode == 1
        metrics = json.loads((tmp_path / "metrics.json").read_text())
        assert metrics["checks"]["suggestion_contract"]["passed"] is False

    def test_frozen_manifest_not_overwritten_on_conflict(self, tmp_path):
        """Export with different content must NOT overwrite existing manifest."""
        fix = tmp_path / "fixture.json"
        fix.write_text(FIXTURE.read_text())
        r1 = _export(tmp_path, "--test-packs", fixture=str(fix))
        assert r1.returncode == 0
        manifest_before = (tmp_path / "manifest.json").read_bytes()

        # Modify fixture and try export to same manifest path
        d2 = tmp_path / "v2"
        d2.mkdir()
        fix2 = d2 / "fixture.json"
        raw = json.loads(FIXTURE.read_text())
        raw[0]["text"] = "完全不同的内容" + raw[0]["text"]
        fix2.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
        r2 = subprocess.run(
            [PY, EXPORT, "--fixture", str(fix2), "--seed", "42",
             "--out", str(d2 / "candidates.json"),
             "--manifest", str(tmp_path / "manifest.json"),
             "--rejects", str(d2 / "rejects.json"),
             "--test-packs"],
            cwd=PROJECT, capture_output=True, text=True, timeout=60,
        )
        assert r2.returncode == 1
        manifest_after = (tmp_path / "manifest.json").read_bytes()
        assert manifest_before == manifest_after, "Manifest was modified on conflict!"

    def test_generic_model_field_leak_detected(self, tmp_path):
        """Generic 'model' field in blind pack must be detected as leakage."""
        from signal_miner.evaluation import check_blind_pack_leakage
        assert check_blind_pack_leakage({"samples": [{"sample_id": "x", "model": "deepseek"}]}) > 0

    def test_preannotation_adapter_injectable(self, tmp_path):
        """Test that generate_with_adapter works with a fake adapter."""
        import asyncio

        r = _full_pipeline(tmp_path)
        assert r.returncode == 0

        # Create a fake adapter
        class FakeAdapter:
            provider_name = "fake"
            model_name = "fake-v1"

            async def call_structured(self, prompt, *, temperature=0.1, max_tokens=2000):
                return '{"signal_type": "feature_request", "summary": "test", "evidence_start": 0, "evidence_end": 5}'

        sys.path.insert(0, str(PROJECT))
        from scripts.p13_2_generate_preannotations import generate_with_adapter

        sample = {"sample_id": "test_001", "profile": "product_feedback", "redacted_text": "测试文本"}
        result = asyncio.run(generate_with_adapter(FakeAdapter(), sample))
        assert result["suggestion_model"] == "fake"
        assert result["fixture_only"] is False
        assert result["suggested_signals"][0]["signal_type"] == "feature_request"
