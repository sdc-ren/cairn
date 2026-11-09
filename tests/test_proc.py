import sys

import pytest

from agent_cairn import proc
from agent_cairn.errors import CairnError


@pytest.mark.req("R18.4")
def test_run_returns_exit_code_and_output(tmp_path):
    result = proc.run([sys.executable, "-c", "print('hi')"], cwd=tmp_path, timeout=10)

    assert result.returncode == 0
    assert result.stdout == "hi\n"


@pytest.mark.req("R18.4")
def test_run_missing_executable_raises_cairn_error(tmp_path):
    with pytest.raises(CairnError, match="no-such-tool-xyz"):
        proc.run(["no-such-tool-xyz"], cwd=tmp_path, timeout=10)


@pytest.mark.req("R18.4")
def test_run_slow_process_raises_cairn_error(tmp_path):
    slow = [sys.executable, "-c", "import time; time.sleep(5)"]

    with pytest.raises(CairnError, match="did not finish"):
        proc.run(slow, cwd=tmp_path, timeout=0.2)
