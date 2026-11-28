"""Screen states: runs every tests/js/*.test.mjs with Node (skipped if Node is absent)."""

import shutil
import subprocess
from pathlib import Path

import pytest

import config

SCRIPTS = sorted((config.PROJECT_ROOT / "tests" / "js").glob("*.test.mjs"))
NODE = shutil.which("node")
TIMEOUT_S = 60


@pytest.mark.skipif(NODE is None, reason="Node is not installed")
@pytest.mark.parametrize("script", SCRIPTS, ids=[s.stem for s in SCRIPTS])
def test_screen_states_render_as_designed(script: Path) -> None:
    result = subprocess.run(
        [str(NODE), str(script)], capture_output=True, text=True, timeout=TIMEOUT_S, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "all checks passed" in result.stdout
