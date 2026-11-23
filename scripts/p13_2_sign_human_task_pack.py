#!/usr/bin/env python3
"""P13-2-2-1A: Sign human task packs with HMAC-SHA256 external trust root.

Generates a canonical manifest from the four human_tasks_*.json pack files
AND a frozen dataset manifest, then signs it with HMAC-SHA256.

Key resolution rules (enforced by ``pack_trust.resolve_signing_key``):

  - **Fixture / test mode** (``--fixture`` flag): requires ALL of:
      1. ``APP_ENVIRONMENT=test`` (single source of truth)
      2. ``--fixture`` flag set
      3. ``ANNOTATION_PACK_TEST_SIGNING_KEY`` env var explicitly injected
    No built-in default test key exists. Any missing condition → exit 1
    with target ``test_key_environment_boundary=false``.

  - **Production mode** (no ``--fixture``): key from
    ``ANNOTATION_PACK_SIGNING_KEY``. Missing → exit 2 BLOCKED.

  - Production/development/empty/unknown environments NEVER enable test key,
    even if ``--fixture`` is passed.

Structured checks output: key_resolved / manifest_generated /
signature_valid / no_plaintext_key.

Exit codes:
  0 = manifest written and signed
  1 = validation failure (test key boundary violation, schema, signing)
  2 = BLOCKED (no production key in production mode)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from signal_miner.evaluation.pack_trust import (  # noqa: E402
    FIXTURE_KEY_ID,
    PROD_KEY_ID,
    SCHEMA_VERSION,
    canonicalize_manifest,
    generate_pack_manifest,
    resolve_signing_key,
    sign_manifest,
)


def _write_report(
    out_path: str,
    status: str,
    passed: bool,
    checks: dict[str, dict] | None = None,
    **extra,
) -> None:
    result: dict = {"status": status, "passed": passed}
    if checks is not None:
        result["checks"] = checks
        recomputed = all(c["passed"] for c in checks.values())
        result["passed"] = passed and recomputed if checks else passed
    result.update(extra)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False))


def _new_check_buckets() -> dict[str, list[str]]:
    return {
        "key_resolved": [],
        "manifest_generated": [],
        "signature_valid": [],
        "no_plaintext_key": [],
    }


def _build_checks_report(buckets: dict[str, list[str]]) -> dict[str, dict]:
    checks: dict[str, dict] = {}
    for name, errs in buckets.items():
        checks[name] = {
            "passed": len(errs) == 0,
            "observations": {
                "error_codes": errs[:50],
                "error_count": len(errs),
            },
        }
    return checks


def main() -> int:
    p = argparse.ArgumentParser(
        description="Sign human task packs with HMAC-SHA256 trust root",
    )
    p.add_argument(
        "--tasks",
        default="sample_data/p13_2/human_tasks",
        help="Directory containing the four human_tasks_*.json packs",
    )
    p.add_argument(
        "--dataset-manifest",
        required=True,
        help="Frozen dataset manifest JSON (SHA-256 bound into signed pack manifest)",
    )
    p.add_argument(
        "--dataset-id",
        default="",
        help="Dataset identifier. Defaults to dataset manifest's dataset_id.",
    )
    p.add_argument(
        "--fixture",
        action="store_true",
        help="Fixture/test mode: requires APP_ENVIRONMENT=test + injected test key",
    )
    p.add_argument(
        "--out",
        default="",
        help="Optional report JSON path (for mutation gate plumbing)",
    )
    p.add_argument(
        "--manifest-out",
        default="",
        help="Output path for signed manifest. Defaults to <tasks>/human-task-pack-manifest.json",
    )
    args = p.parse_args()

    task_dir = Path(args.tasks)
    dataset_manifest_path = Path(args.dataset_manifest)
    buckets = _new_check_buckets()

    # ── 1. Resolve signing key (environment-aware) ──
    fixture = args.fixture
    key, key_error, key_error_kind = resolve_signing_key(fixture)

    if key is None:
        buckets["key_resolved"].append(key_error or "key resolution failed")
        checks = _build_checks_report(buckets)

        if key_error_kind == "test_key_environment_boundary":
            # Non-test environment tried to use test key → FAIL exit 1
            status = "FAIL_TEST_KEY_ENVIRONMENT_BOUNDARY"
            if args.out:
                _write_report(args.out, status, passed=False,
                              checks=checks, fixture_only=False,
                              error_kind=key_error_kind)
            print(json.dumps({
                "status": status, "passed": False,
                "fixture_only": False,
                "reason": key_error,
                "error_kind": key_error_kind,
            }, ensure_ascii=False))
            return 1

        # BLOCKED (production no key or test no injected key)
        if "TEST" in (key_error_kind or ""):
            status = "BLOCKED_MISSING_TEST_KEY"
        else:
            status = "BLOCKED_MISSING_PACK_SIGNING_KEY"
        if args.out:
            _write_report(args.out, status, passed=False,
                          checks=checks, fixture_only=False,
                          error_kind=key_error_kind)
        print(json.dumps({
            "status": status, "passed": False,
            "fixture_only": False,
            "reason": key_error,
            "error_kind": key_error_kind,
        }, ensure_ascii=False))
        return 2

    # ── 2. Determine dataset_id from dataset manifest ──
    if not dataset_manifest_path.exists():
        buckets["manifest_generated"].append(
            f"dataset manifest not found: {dataset_manifest_path}"
        )
        checks = _build_checks_report(buckets)
        if args.out:
            _write_report(args.out, "FAIL_DATASET_MANIFEST_MISSING",
                          passed=False, checks=checks)
        print(json.dumps({
            "status": "FAIL_DATASET_MANIFEST_MISSING", "passed": False,
        }, ensure_ascii=False))
        return 1

    dataset_id = args.dataset_id
    if not dataset_id:
        try:
            dm = json.loads(dataset_manifest_path.read_text())
            dataset_id = dm.get("dataset_id", "")
        except Exception:  # noqa: BLE001
            pass
        if not dataset_id:
            dataset_id = "unknown-dataset"

    # ── 3. Generate manifest ──
    try:
        manifest = generate_pack_manifest(
            task_dir=task_dir,
            dataset_id=dataset_id,
            fixture=fixture,
            dataset_manifest_path=dataset_manifest_path,
            signer_key_id=FIXTURE_KEY_ID if fixture else PROD_KEY_ID,
        )
    except Exception as e:  # noqa: BLE001
        buckets["manifest_generated"].append(f"manifest_generation_error: {e}")
        checks = _build_checks_report(buckets)
        if args.out:
            _write_report(args.out, "FAIL_MANIFEST_GENERATION",
                          passed=False, checks=checks)
        print(json.dumps({
            "status": "FAIL_MANIFEST_GENERATION",
            "passed": False, "error": str(e)[:300],
        }, ensure_ascii=False))
        return 1

    if not manifest.get("packs"):
        buckets["manifest_generated"].append("no pack files found in task directory")
        checks = _build_checks_report(buckets)
        if args.out:
            _write_report(args.out, "FAIL_NO_PACKS", passed=False, checks=checks)
        print(json.dumps({"status": "FAIL_NO_PACKS", "passed": False},
                         ensure_ascii=False))
        return 1

    # ── 4. Sign ──
    # fixture_only added BEFORE signing so it is part of the signed payload
    manifest["fixture_only"] = fixture
    signature = sign_manifest(manifest, key)
    signed_manifest = dict(manifest)
    signed_manifest["signature"] = signature

    # Verify signature round-trips
    canon = canonicalize_manifest(
        {k: v for k, v in signed_manifest.items() if k != "signature"},
    )
    expected = hmac.new(key.encode("utf-8"), canon, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        buckets["signature_valid"].append("signature_roundtrip_failed")

    # ── 5. Verify no plaintext key leak ──
    manifest_json = json.dumps(signed_manifest, ensure_ascii=False)
    if key in manifest_json:
        buckets["no_plaintext_key"].append("signing_key_found_in_manifest_output")

    checks = _build_checks_report(buckets)
    all_passed = all(c["passed"] for c in checks.values())

    if not all_passed:
        if args.out:
            _write_report(args.out, "FAIL_SIGNING", passed=False, checks=checks)
        print(json.dumps({"status": "FAIL_SIGNING", "passed": False},
                         ensure_ascii=False))
        return 1

    # ── 6. Write manifest ──
    manifest_out = Path(args.manifest_out) if args.manifest_out else (
        task_dir / "human-task-pack-manifest.json"
    )
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(json.dumps(signed_manifest, indent=2, ensure_ascii=False))

    if args.out:
        _write_report(
            args.out, "SIGNED", passed=True, checks=checks,
            manifest_path=str(manifest_out),
            fixture_only=fixture,
            signer_key_id=signed_manifest.get("signer_key_id", ""),
            schema_version=SCHEMA_VERSION,
            pack_count=len(manifest["packs"]),
            total_task_count=manifest["total_task_count"],
            dataset_manifest_sha256=manifest.get("dataset_manifest_sha256", ""),
        )

    print(json.dumps({
        "status": "SIGNED", "passed": True,
        "fixture_only": fixture,
        "manifest_path": str(manifest_out),
        "pack_count": len(manifest["packs"]),
        "total_task_count": manifest["total_task_count"],
        "signer_key_id": signed_manifest.get("signer_key_id", ""),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
