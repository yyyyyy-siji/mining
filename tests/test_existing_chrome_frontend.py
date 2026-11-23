"""Offline SPA interactions; no real Chrome or platform collection."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_existing_chrome_frontend_behaviour():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node required for offline SPA tests")
    script = Path(__file__).with_name("existing_chrome_frontend.test.cjs")
    result = subprocess.run(
        [node, "--test", str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
