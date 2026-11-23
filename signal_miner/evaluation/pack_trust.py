"""P13-2-2-1A: Human task pack external trust root.

Provides:
  - generate_pack_manifest(task_dir, dataset_manifest_path, ...) → manifest dict
  - canonicalize_manifest(manifest) → stable JSON bytes for signing
  - sign_manifest(manifest, key) → HMAC-SHA256 hex signature
  - verify_manifest_file(...) → {valid, errors, manifest}
  - validate_manifest_structure(manifest) → schema validation
  - resolve_signing_key(...) → environment-aware key resolution

Security model (fix after Commander review):
  - Test-only key requires ALL FOUR conditions simultaneously:
      1. APP_ENVIRONMENT == "test" (single source of truth for environment)
      2. CLI flag --fixture is set
      3. manifest / task pack structured fixture=true
      4. ANNOTATION_PACK_TEST_SIGNING_KEY explicitly injected by test process
    Any missing condition → FAIL exit 1, target test_key_environment_boundary=false.
    No built-in default test key exists in the codebase.
  - Production key from ANNOTATION_PACK_SIGNING_KEY env var, missing → BLOCKED exit 2
  - Only key_id (identity, not secret) appears in manifest and logs
  - No keys are ever written to disk, logs, or stdout
  - Manifest mandatory for ALL imports (fixture + production)
  - Manifest binds dataset_manifest_path + dataset_manifest_sha256 + dataset_id
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path  # noqa: TC003
from typing import Any

SCHEMA_VERSION = "1.1.0"
CANONICAL_VERSION = "1"
FIXTURE_KEY_ID = "fixture-test-key-v1"  # key_id label only; actual key MUST be
                                         # injected via env var, never hardcoded
PROD_KEY_ID = "production-key"
ENV_VAR_TEST_KEY = "ANNOTATION_PACK_TEST_SIGNING_KEY"
ENV_VAR_PROD_KEY = "ANNOTATION_PACK_SIGNING_KEY"
ENV_VAR_ENVIRONMENT = "APP_ENVIRONMENT"
ALLOWED_TEST_ENVIRONMENTS = ("test",)
# production/development/empty/unknown must NEVER enable the test key path

# Accepted pack file names in fixed order
PACK_NAMES = (
    "human_tasks_development.json",
    "human_tasks_calibration.json",
    "human_tasks_test_A.json",
    "human_tasks_test_B.json",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


# ── Manifest generation ──

def generate_pack_manifest(
    task_dir: Path,
    dataset_id: str,
    fixture: bool,
    dataset_manifest_path: Path,
    signer_key_id: str = FIXTURE_KEY_ID,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Generate a canonical pack manifest from the four task pack files.

    Returns a dict ready for canonicalization and signing. Every path is a
    controlled relative filename — no absolute paths, no `..`.

    P13-2-2-1A fix: binds dataset_manifest_path + sha256 + dataset_id so the
    task pack's authorized dataset origin is part of the signed payload.
    """
    if not dataset_manifest_path.exists():
        raise FileNotFoundError(
            f"dataset manifest not found: {dataset_manifest_path}"
        )
    dataset_manifest_raw = dataset_manifest_path.read_bytes()
    dataset_manifest_sha256 = hashlib.sha256(dataset_manifest_raw).hexdigest()

    # Path must be a controlled relative filename (no absolute, no ..)
    dmp_name = dataset_manifest_path.name

    packs = []
    total = 0
    for name in PACK_NAMES:
        pf = task_dir / name
        if not pf.exists():
            continue
        pack = _load_json(pf)
        raw = pf.read_bytes()
        packs.append({
            "path": name,
            "sha256": _sha256_file(pf),
            "bytes": len(raw),
            "task_count": len(pack.get("tasks", [])),
            "annotation_mode": _pack_annotation_mode(name, pack),
            "annotator_slot": _pack_annotator_slot(name, pack),
            "split": _pack_split(name, pack),
            "fixture": bool(pack.get("fixture", fixture)),
        })
        total += len(pack.get("tasks", []))

    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "fixture": fixture,
        "signer_key_id": signer_key_id,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "packs": packs,
        "total_task_count": total,
        "canonicalization_version": CANONICAL_VERSION,
        "dataset_manifest_path": dmp_name,
        "dataset_manifest_sha256": dataset_manifest_sha256,
    }


def _pack_annotation_mode(name: str, pack: dict) -> str:
    return _first_task_field(pack, "annotation_mode") or _infer_mode(name)


def _pack_annotator_slot(name: str, pack: dict) -> str:
    return _first_task_field(pack, "annotator_slot") or _infer_slot(name)


def _pack_split(name: str, pack: dict) -> str:
    return _first_task_field(pack, "split") or _infer_split(name)


def _first_task_field(pack: dict, field: str) -> str | None:
    tasks = pack.get("tasks", [])
    if tasks and field in tasks[0]:
        return tasks[0][field]
    return None


def _infer_mode(name: str) -> str:
    mapping = {
        "human_tasks_development.json": "assisted_review",
        "human_tasks_calibration.json": "assisted_review",
        "human_tasks_test_A.json": "blind",
        "human_tasks_test_B.json": "blind",
    }
    return mapping.get(name, "blind")


def _infer_slot(name: str) -> str:
    mapping = {
        "human_tasks_development.json": "assisted",
        "human_tasks_calibration.json": "assisted",
        "human_tasks_test_A.json": "A",
        "human_tasks_test_B.json": "B",
    }
    return mapping.get(name, "A")


def _infer_split(name: str) -> str:
    mapping = {
        "human_tasks_development.json": "development",
        "human_tasks_calibration.json": "calibration",
        "human_tasks_test_A.json": "test",
        "human_tasks_test_B.json": "test",
    }
    return mapping.get(name, "test")


# ── Canonicalization ──

def canonicalize_manifest(manifest: dict[str, Any]) -> bytes:
    """Stable, deterministic JSON bytes for signing."""
    return json.dumps(
        manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        default=str,
    ).encode("utf-8")


# ── Signing ──

def sign_manifest(manifest: dict[str, Any], key: str) -> str:
    """HMAC-SHA256 sign the canonical manifest. Returns hex signature."""
    payload = canonicalize_manifest(manifest)
    return hmac.new(
        key.encode("utf-8"), payload, hashlib.sha256,
    ).hexdigest()


def verify_signature(manifest: dict[str, Any], signature: str, key: str) -> bool:
    """Verify that `signature` is a valid HMAC-SHA256 for `manifest`."""
    expected = sign_manifest(manifest, key)
    return hmac.compare_digest(expected, signature)


# ── Manifest file-level verification ──

def verify_manifest_file(
    manifest_path: Path,
    task_dir: Path,
    key: str | None = None,
    expected_key_id: str | None = None,
    dataset_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Full verification of a signed pack manifest against on-disk task packs.

    Returns {valid, errors, manifest}. `valid` is True only when all
    structural, file-level, dataset-manifest, and signature checks pass.

    Args:
        manifest_path: Path to the manifest JSON file
        task_dir: Directory containing the four human_tasks_*.json packs
        key: Signing key for HMAC verification (None = skip signature check)
        expected_key_id: If set, manifest's signer_key_id must match
        dataset_manifest_path: If None, the check is still performed but an
            error is added (MANDATORY binding — P13-2-2-1A fix-2).
            If set, the actual dataset manifest is re-read and its SHA-256 /
            dataset_id compared to the manifest's declared values.
    """
    errors: list[str] = []

    # 1. Read and parse manifest
    if not manifest_path.exists():
        return {"valid": False, "errors": ["manifest file not found"], "manifest": None}
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as e:  # noqa: BLE001
        return {"valid": False, "errors": [f"manifest parse error: {e}"], "manifest": None}

    # 2. Schema / structure validation
    struct = validate_manifest_structure(manifest)
    errors.extend(struct)

    # 3. File-level checks
    if manifest:
        manifest_packs = manifest.get("packs", [])
        # Check file set exactly matches
        manifest_files = {p["path"] for p in manifest_packs}
        actual_files = {f.name for f in task_dir.glob("human_tasks_*.json")}
        missing_in_manifest = actual_files - manifest_files
        extra_in_manifest = manifest_files - actual_files
        if missing_in_manifest:
            errors.append(f"packs missing from manifest: {sorted(missing_in_manifest)}")
        if extra_in_manifest:
            errors.append(f"manifest references non-existent packs: {sorted(extra_in_manifest)}")

        for p in manifest_packs:
            pname = p["path"]
            pf = task_dir / pname
            if not pf.exists():
                errors.append(f"pack file not found: {pname}")
                continue
            # Validate path (no .., no absolute)
            if ".." in pname or pname.startswith("/"):
                errors.append(f"pack path traversal: {pname}")
                continue
            actual_sha = _sha256_file(pf)
            actual_bytes = pf.stat().st_size
            actual_count = len(_load_json(pf).get("tasks", []))
            if p["sha256"] != actual_sha:
                errors.append(f"{pname}: SHA mismatch manifest={p['sha256'][:16]}... actual={actual_sha[:16]}...")
            if p["bytes"] != actual_bytes:
                errors.append(f"{pname}: bytes mismatch manifest={p['bytes']} actual={actual_bytes}")
            if p["task_count"] != actual_count:
                errors.append(f"{pname}: task_count mismatch manifest={p['task_count']} actual={actual_count}")
            actual_fixture = _load_json(pf).get("fixture")
            if actual_fixture is not None and p.get("fixture") != actual_fixture:
                errors.append(f"{pname}: fixture mismatch manifest={p['fixture']} actual={actual_fixture}")

    # 4. Dataset manifest hash binding (P13-2-2-1A fix-2: MANDATORY)
    if manifest:
        if dataset_manifest_path is None:
            errors.append("dataset manifest path not provided (MANDATORY binding)")
        else:
            declared_dmp = manifest.get("dataset_manifest_path")
            declared_sha = manifest.get("dataset_manifest_sha256")
            declared_dataset_id = manifest.get("dataset_id")

            if not declared_dmp or not isinstance(declared_dmp, str):
                errors.append("manifest missing dataset_manifest_path")
            elif ".." in declared_dmp or declared_dmp.startswith("/"):
                errors.append(f"dataset_manifest_path traversal: {declared_dmp}")

            if not dataset_manifest_path.exists():
                errors.append(f"dataset manifest file not found: {dataset_manifest_path}")
            else:
                actual_sha = hashlib.sha256(
                    dataset_manifest_path.read_bytes(),
                ).hexdigest()
                if declared_sha != actual_sha:
                    errors.append(
                        f"dataset_manifest_sha256 mismatch: "
                        f"manifest={declared_sha[:16] if declared_sha else None}... "
                        f"actual={actual_sha[:16]}..."
                    )
                # Read dataset manifest and compare dataset_id
                try:
                    dm = _load_json(dataset_manifest_path)
                    actual_dataset_id = dm.get("dataset_id")
                    if declared_dataset_id and actual_dataset_id and declared_dataset_id != actual_dataset_id:
                        errors.append(
                            f"dataset_id mismatch: manifest={declared_dataset_id} "
                            f"dataset_manifest={actual_dataset_id}"
                        )
                except Exception as e:  # noqa: BLE001
                    errors.append(f"dataset manifest parse error: {e}")

    # 5. Signature check
    if key is not None and manifest:
        raw = manifest_path.read_text()
        try:
            sig_data = json.loads(raw)
        except Exception:  # noqa: BLE001
            sig_data = {}
        signature = sig_data.get("signature")
        if not signature:
            errors.append("manifest missing signature field")
        else:
            # Strip signature before verifying (signature is over the rest)
            canon = canonicalize_manifest({k: v for k, v in sig_data.items() if k != "signature"})
            expected = hmac.new(
                key.encode("utf-8"), canon, hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                errors.append("manifest signature verification failed")

    # 6. Key ID check
    if expected_key_id and manifest:
        manifest_key_id = manifest.get("signer_key_id")
        if manifest_key_id != expected_key_id:
            errors.append(f"signer_key_id mismatch: manifest={manifest_key_id} expected={expected_key_id}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "manifest": manifest,
    }


# ── Manifest structure validation ──

def validate_manifest_structure(manifest: dict[str, Any] | None) -> list[str]:
    """Validate manifest schema fields. Does NOT check file contents or signatures."""
    errors: list[str] = []
    if not manifest or not isinstance(manifest, dict):
        errors.append("manifest must be a non-null object")
        return errors

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(manifest.get("dataset_id"), str) or not manifest["dataset_id"]:
        errors.append("dataset_id missing or empty")
    if not isinstance(manifest.get("fixture"), bool):
        errors.append("fixture must be boolean")
    if not isinstance(manifest.get("signer_key_id"), str) or not manifest["signer_key_id"]:
        errors.append("signer_key_id missing or empty")
    if not isinstance(manifest.get("generated_at"), str):
        errors.append("generated_at missing or invalid")

    # P13-2-2-1A fix: dataset manifest hash binding required
    dmp = manifest.get("dataset_manifest_path")
    if not isinstance(dmp, str) or not dmp:
        errors.append("dataset_manifest_path missing or empty")
    elif ".." in dmp or dmp.startswith("/"):
        errors.append(f"dataset_manifest_path traversal: {dmp}")
    dm_sha = manifest.get("dataset_manifest_sha256")
    if not isinstance(dm_sha, str) or len(dm_sha) != 64:
        errors.append("dataset_manifest_sha256 missing or invalid (must be 64 hex chars)")

    packs = manifest.get("packs")
    if not isinstance(packs, list) or not packs:
        errors.append("packs must be a non-empty list")
    else:
        for p in packs:
            if not isinstance(p, dict):
                errors.append("pack entry must be an object")
                continue
            pname = p.get("path", "?")
            if ".." in str(pname) or str(pname).startswith("/"):
                errors.append(f"pack path traversal: {pname}")
            if not isinstance(p.get("sha256"), str) or len(p.get("sha256", "")) != 64:
                errors.append(f"pack {pname}: sha256 invalid")
            if not isinstance(p.get("bytes"), int) or p["bytes"] < 0:
                errors.append(f"pack {pname}: bytes invalid")
            if not isinstance(p.get("task_count"), int) or p["task_count"] < 0:
                errors.append(f"pack {pname}: task_count invalid")

    total = sum(p.get("task_count", 0) for p in packs)
    if manifest.get("total_task_count") != total:
        errors.append(f"total_task_count mismatch: declared={manifest.get('total_task_count')} computed={total}")

    return errors


# ── Key resolution ──

def resolve_signing_key(
    fixture: bool,
    test_key: str | None = None,
    environment: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Resolve the signing key based on mode + environment.

    P13-2-2-1A fix (Commander P0-1): test-only key requires ALL FOUR
    conditions simultaneously:
      1. APP_ENVIRONMENT == "test" (or explicitly passed environment="test")
      2. fixture == True (--fixture flag)
      3. ANNOTATION_PACK_TEST_SIGNING_KEY explicitly injected (no default)
      4. (manifest fixture=true is verified separately by importer)

    Any missing condition → FAIL exit 1, returns (None, error, "test_key_environment_boundary").
    Production/development/empty/unknown environments NEVER enable test key.

    Production mode: key from ANNOTATION_PACK_SIGNING_KEY env, missing → BLOCKED exit 2.

    Returns (key, error_message, error_kind). On success, both errors are None.
    error_kind values:
      - None (success)
      - "test_key_environment_boundary" (test key rejected in non-test env)
      - "BLOCKED_MISSING_TEST_KEY" (test env but no injected key)
      - "BLOCKED_MISSING_PACK_SIGNING_KEY" (production, no key)
    """
    # Resolve environment: explicit param wins, else env var
    env = environment if environment is not None else os.environ.get(ENV_VAR_ENVIRONMENT, "")

    if fixture:
        # Test-only key path: require test environment
        if env not in ALLOWED_TEST_ENVIRONMENTS:
            return (
                None,
                f"test_key_environment_boundary: fixture mode requires "
                f"APP_ENVIRONMENT in {ALLOWED_TEST_ENVIRONMENTS}, got '{env}'",
                "test_key_environment_boundary",
            )
        # Test key must be explicitly injected — NO default value
        if not test_key:
            test_key = os.environ.get(ENV_VAR_TEST_KEY)
        if not test_key:
            return (
                None,
                f"BLOCKED: {ENV_VAR_TEST_KEY} not set in test environment",
                "BLOCKED_MISSING_TEST_KEY",
            )
        return test_key, None, None

    # Production path
    key = os.environ.get(ENV_VAR_PROD_KEY)
    if not key:
        return (
            None,
            f"BLOCKED: {ENV_VAR_PROD_KEY} not set in environment",
            "BLOCKED_MISSING_PACK_SIGNING_KEY",
        )
    return key, None, None
