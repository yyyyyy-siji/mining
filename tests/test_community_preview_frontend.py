"""Run O2's offline SPA interaction tests through the local Node runtime."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_community_preview_frontend_behaviour():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the offline SPA interaction checks")
    script = Path(__file__).with_name("community_preview_frontend.test.cjs")
    result = subprocess.run(
        [node, "--test", str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
