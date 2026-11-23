"""Offline need-assessment UI checks; no model or market validation."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_opportunity_admission_frontend_behaviour():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node required for offline SPA tests")
    script = Path(__file__).with_name("opportunity_admission_frontend.test.cjs")
    result = subprocess.run(
        [node, "--test", str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
