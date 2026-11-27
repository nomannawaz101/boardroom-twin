"""Board screen states: runs tests/js/board_screen.test.mjs with Node (skipped if absent)."""

import shutil
import subprocess

import pytest

import config

SCRIPT = config.PROJECT_ROOT / "tests" / "js" / "board_screen.test.mjs"
NODE = shutil.which("node")
TIMEOUT_S = 60


@pytest.mark.skipif(NODE is None, reason="Node is not installed")
def test_board_screen_states_render_as_designed() -> None:
    result = subprocess.run(
        [str(NODE), str(SCRIPT)], capture_output=True, text=True, timeout=TIMEOUT_S, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "all checks passed" in result.stdout
