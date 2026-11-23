#!/usr/bin/env python3
"""P13-1 fix-2: Consumes behavior_probe.json for real observations.
No inspect.getsource, no hardcoded PASS, no source-string-as-gate.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent.parent

REQUIRED_GATES = {
    "confidence_contract", "signal_type_validation", "evidence_validation",
    "pseudo_embedding_blocked", "no_new_destructive_dismiss", "frontend_semantics",
    "regression",
}


def _pytest(module: str = "", k: str = "") -> subprocess.CompletedProcess:
    args = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q"]
    if module:
        args.append(f"tests/{module}")
    if k:
        args.extend(["-k", k])
    return subprocess.run(args, cwd=PROJECT, capture_output=True, text=True, timeout=180)


def _count_tests(r: subprocess.CompletedProcess) -> int:
    m = re.search(r"(\d+)\s+passed", r.stdout)
    return int(m.group(1)) if m else 0


def _load_probe() -> dict:
    path = PROJECT / "docs" / "P13-1-evidence" / "behavior_probe.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


# ── Gate functions ──

def check_confidence_contract(probe: dict) -> dict:
    lp = probe.get("low_score", {})
    return {
        "method": "behavior_probe-low_score",
        "passed": lp.get("passed", False),
        "observations": {
            "persisted_count": lp.get("persisted_count"),
            "model_self_score": lp.get("model_self_score"),
            "calibrated_confidence": lp.get("calibrated_confidence"),
            "low_score_persists": lp.get("passed", False),
        },
    }


def check_signal_type_validation(_probe: dict) -> dict:
    r = _pytest(module="test_confidence_contract.py", k="TestSignalTypeWhitelist")
    return {
        "method": "pytest-whitelist",
        "exit_code": r.returncode,
        "passed": r.returncode == 0,
        "observations": {"test_count": _count_tests(r)},
    }


def check_evidence_validation(_probe: dict) -> dict:
    r = _pytest(module="test_evidence_validation.py")
    return {
        "method": "pytest-evidence",
        "exit_code": r.returncode,
        "passed": r.returncode == 0,
        "observations": {"test_count": _count_tests(r)},
    }


def check_pseudo_embedding_blocked(probe: dict) -> dict:
    nc = probe.get("no_capability", {})
    af = probe.get("all_real_embeddings_failed", {})
    return {
        "method": "behavior_probe-circuit_breaker",
        "passed": nc.get("passed", False) and af.get("passed", False),
        "observations": {
            "no_capability": {
                "dedup_await_count": nc.get("dedup_await_count", -1),
                "cluster_await_count": nc.get("cluster_await_count", -1),
                "asset_await_count": nc.get("asset_await_count", -1),
                "passed": nc.get("passed", False),
            },
            "all_real_embeddings_failed": {
                "stored_real_count": af.get("stored_real_count", -1),
                "dedup_await_count": af.get("dedup_await_count", -1),
                "cluster_await_count": af.get("cluster_await_count", -1),
                "asset_await_count": af.get("asset_await_count", -1),
                "semantic_phase": af.get("semantic_phase", "?"),
                "passed": af.get("passed", False),
            },
        },
    }


def check_no_new_destructive_dismiss(_probe: dict) -> dict:
    r = _pytest(module="test_embedding_safety.py", k="TestDeduplicationSafety")
    return {
        "method": "pytest-dedup",
        "exit_code": r.returncode,
        "passed": r.returncode == 0,
        "observations": {},
    }


def check_frontend_semantics(probe: dict) -> dict:
    sse = probe.get("sse_terminal", {})
    return {
        "method": "behavior_probe-sse_terminal",
        "passed": sse.get("passed", False),
        "observations": {
            "evidence_type": "behavior_probe_sse",
            "terminal_status": sse.get("status", "?"),
            "stream_closed": sse.get("stream_closed", False),
            "subscriber_removed": sse.get("subscriber_removed", False),
        },
    }


def check_regression(_probe: dict) -> dict:
    r = _pytest()
    count = _count_tests(r)
    return {
        "method": "pytest-full-suite",
        "exit_code": r.returncode,
        "passed": r.returncode == 0 and count > 0,
        "observations": {
            "test_count": count,
            "stdout_tail": r.stdout.strip().split("\n")[-2:] if r.stdout else [],
        },
    }


# ── Main ──

def main() -> int:
    probe = _load_probe()
    deltas = probe.get("deltas", {})

    checks = {
        "confidence_contract": check_confidence_contract(probe),
        "signal_type_validation": check_signal_type_validation(probe),
        "evidence_validation": check_evidence_validation(probe),
        "pseudo_embedding_blocked": check_pseudo_embedding_blocked(probe),
        "no_new_destructive_dismiss": check_no_new_destructive_dismiss(probe),
        "frontend_semantics": check_frontend_semantics(probe),
        "regression": check_regression(probe),
    }

    gates_present = set(checks.keys())
    missing = REQUIRED_GATES - gates_present

    # ── P13-1 fix-3: static contract gates (prevent recurrence) ──
    static_checks = {}
    streamlit_text = (PROJECT / "frontend" / "app.py").read_text()
    static_checks["streamlit_no_confidence_threshold_payload"] = (
        '"confidence_threshold":' not in streamlit_text
    )
    browser_text = (PROJECT / "scripts" / "p13_1_browser_verify.js").read_text()
    static_checks["browser_no_doSimpleVerify"] = "doSimpleVerify" not in browser_text
    static_checks["browser_no_app_dot_js"] = "app.js" not in browser_text
    static_checks["browser_no_http_dot_get"] = "http.get" not in browser_text
    static_pass = all(static_checks.values())

    all_passed = (
        all(c.get("passed", False) for c in checks.values())
        and len(missing) == 0
        and static_pass
    )

    result = {
        "passed": all_passed,
        "checks": checks,
        "deltas": deltas,
        "static_contracts": static_checks,
        "gates_completeness": {
            "required_count": len(REQUIRED_GATES),
            "present_count": len(gates_present),
            "missing_gates": sorted(missing),
        },
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }

    out = PROJECT / "docs" / "P13-1-evidence" / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"Metrics → {out}")
    print(f"Overall: {'PASS' if all_passed else 'FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
