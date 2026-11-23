"""Offline SPA behavior; not real browser or platform LIVE evidence."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_mediacrawler_frontend_behaviour():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node required for offline SPA tests")
    result = subprocess.run([node, "--test", str(Path(__file__).with_name("mediacrawler_frontend.test.cjs"))], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
