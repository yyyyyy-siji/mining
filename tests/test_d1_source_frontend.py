"""Run D1 source/lead SPA interaction checks with Node (no network)."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_d1_source_frontend_behaviour():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the offline SPA interaction checks")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("d1_source_frontend.test.cjs"))],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
