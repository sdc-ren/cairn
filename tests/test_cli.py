import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import FILLED_BODY

from agent_cairn import __version__, gitio
from agent_cairn.cli import main

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.mark.req("R17.3")
def test_main_version_command_prints_version(capsys):
    code = main(["version"])

    assert code == 0
    assert capsys.readouterr().out == f"cairn {__version__}\n"


@pytest.mark.req("R17.3")
def test_main_version_flag_prints_version(capsys):
    code = main(["--version"])

    assert code == 0
    assert capsys.readouterr().out == f"cairn {__version__}\n"


@pytest.mark.req("R17.2")
@pytest.mark.parametrize("argv", [[], ["-h"], ["--help"]])
def test_main_no_command_prints_usage(capsys, argv):
    code = main(argv)

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.startswith("usage: cairn")
    assert captured.err == ""


@pytest.mark.req("R17.5")
def test_main_unknown_command_is_usage_error(capsys):
    code = main(["frobnicate"])

    assert code == 2
    assert capsys.readouterr().err.startswith("cairn: ")


@pytest.mark.req("R1.9")
def test_main_save_outside_repo_works(outside_repo, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))

    code = main(["save"])

    assert code == 0
    assert capsys.readouterr().out.startswith("saved ")


@pytest.mark.req("R1.7")
def test_main_version_outside_repo_succeeds(outside_repo):
    assert main(["version"]) == 0


@pytest.mark.req("R13.7")
def test_main_hook_session_start_outside_repo_exits_0_silently(outside_repo, capsys):
    code = main(["hook", "session-start"])

    assert code == 0
    assert capsys.readouterr().out == ""


@pytest.mark.req("R17.6")
def test_main_unexpected_error_is_one_line_without_traceback(git_repo, monkeypatch, capsys):
    def explode(cwd):
        raise RuntimeError("boom")

    monkeypatch.setattr(gitio, "common_dir", explode)
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))

    code = main(["save"])

    err = capsys.readouterr().err
    assert code == 1
    assert err.startswith("cairn: internal error: RuntimeError: boom")
    assert "CAIRN_DEBUG=1" in err
    assert "Traceback" not in err


@pytest.mark.req("R17.6")
def test_main_unexpected_error_with_debug_reraises(git_repo, monkeypatch):
    def explode(cwd):
        raise RuntimeError("boom")

    monkeypatch.setattr(gitio, "common_dir", explode)
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))
    monkeypatch.setenv("CAIRN_DEBUG", "1")

    with pytest.raises(RuntimeError):
        main(["save"])


@pytest.mark.req("R18.5")
def test_module_runs_with_src_on_pythonpath(outside_repo):
    env = {**os.environ, "PYTHONPATH": str(SRC)}

    done = subprocess.run(
        [sys.executable, "-m", "agent_cairn", "version"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert done.returncode == 0
    assert done.stdout == f"cairn {__version__}\n"
