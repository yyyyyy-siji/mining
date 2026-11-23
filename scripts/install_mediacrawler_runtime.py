"""Install/verify the pinned, isolated non-commercial local collection runtime.

Downloads dependencies and a browser; never launches a browser or a platform task.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PIN = "54a3d92412f4b20c06b45f1d542b78dd92049d6d"
DEFAULT_RUNTIME = ROOT / "tools" / "mediacrawler-runtime"


def run(argv, *, cwd=None, env=None, capture=False):
    try:
        return subprocess.run(argv, cwd=cwd, env=env, check=True, text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"step={Path(argv[0]).name}:{argv[1]} exit={error.returncode}; upstream logs withheld") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    runtime = args.runtime.expanduser().resolve()
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    runtime.chmod(0o700)
    checkout, python = runtime / "upstream", runtime / ".venv" / "bin" / "python"
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TZ") if key in os.environ}
    env.update(PLAYWRIGHT_BROWSERS_PATH=str(runtime / "browsers"), PYTHON_DOTENV_DISABLED="1", NO_COLOR="1")
    if not args.verify_only:
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("uv is required; install uv first")
        if not checkout.exists():
            run(["git", "clone", "--no-checkout", "--filter=blob:none", "https://github.com/NanmiCoder/MediaCrawler.git", str(checkout)])
            run(["git", "checkout", "--detach", PIN], cwd=checkout)
        head = run(["git", "rev-parse", "HEAD"], cwd=checkout, capture=True).stdout.strip()
        if head != PIN:
            raise RuntimeError("Existing checkout pin differs; no automatic reset or pull performed")
        if not python.exists():
            run([uv, "venv", "--python", "3.12", str(runtime / ".venv")], env=env)
        requirements = runtime / "requirements.lock.txt"
        # Keep exact upstream frozen dependency hashes; use official PyPI as the
        # pinned lock's TUNA mirror may be unavailable. Never change uv.lock.
        run([uv, "export", "--quiet", "--frozen", "--format", "requirements-txt", "--no-emit-project",
            "--project", str(checkout), "--output-file", str(requirements)], env=env, capture=True)
        run([uv, "pip", "install", "--python", str(python), "--index-url", "https://pypi.org/simple",
            "--require-hashes", "-r", str(requirements)], env=env)
        run([str(python), "-m", "playwright", "install", "chromium"], env=env)
    # Verification emits only controlled dependency/browser metadata and CLI help.
    head = run(["git", "rev-parse", "HEAD"], cwd=checkout, capture=True).stdout.strip()
    dirty = run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=checkout, capture=True).stdout.strip()
    if head != PIN or dirty or not (checkout / "LICENSE").is_file():
        raise RuntimeError("Pinned checkout/license verification failed")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js required by pinned upstream signing dependencies")
    node_version = run([node, "--version"], env=env, capture=True).stdout.strip()
    probe = run([str(python), "-c", "import json,sys; import httpx,typer; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(json.dumps({'python':sys.version.split()[0], 'prefix':sys.prefix,'browser_executable':p.chromium.executable_path})); p.stop()"], env=env, capture=True)
    metadata = json.loads(probe.stdout.strip())
    browser = Path(metadata["browser_executable"])
    if Path(metadata["prefix"]).resolve() != (runtime / ".venv").resolve() or not browser.is_relative_to(runtime / "browsers") or not browser.is_file():
        raise RuntimeError("Independent interpreter/browser verification failed")
    help_result = run([str(python), str(ROOT / "scripts" / "run_mediacrawler_task.py"),
        "--runtime", str(runtime), "--upstream-help"], env=env, capture=True)
    if "--platform" not in help_result.stdout or "--save_data_path" not in help_result.stdout:
        raise RuntimeError("Real upstream CLI help contract differs")
    (runtime / "upstream-help.txt").write_text(help_result.stdout, encoding="utf-8")
    metadata.update(pin=PIN, node_version=node_version, dependencies_verified=True, help_verified=True,
        installed_at=datetime.now(timezone.utc).isoformat(),
        license="NON-COMMERCIAL LEARNING LICENSE 1.1", live_verified=False)
    marker = runtime / "installed.json"
    marker.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    marker.chmod(0o600)
    print(json.dumps({"installed": True, "pin": PIN, "python": metadata["python"],
        "browser_present": True, "upstream_help_exit_code": help_result.returncode,
        "live_verified": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        # No upstream runtime logs; install/help errors contain no account state.
        print(f"Installation/verification failed: {error if isinstance(error, RuntimeError) else type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
