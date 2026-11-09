import json
import os

import pytest
from conftest import commit

from agent_cairn import __version__, doctor
from agent_cairn.cli import main


def _levels(cwd):
    return {check.name: check.level for check in doctor.run(cwd)}


@pytest.mark.req("R15.1")
def test_doctor_reports_each_check(git_repo, fake_gh, capsys):
    commit(git_repo)
    fake_gh("exit 0")

    code = main(["doctor"])

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    names = [line.split()[1] for line in lines]
    assert names == ["python", "git", "repository", "store", "gh", "plugin", "clipboard", "command"]
    assert all(line.split()[0] == "ok" for line in lines[:6])


@pytest.mark.req("R15.1")
def test_doctor_warns_outside_repo_and_without_gh(outside_repo, no_gh):
    levels = _levels(outside_repo)

    assert levels["repository"] == "warn"
    assert levels["gh"] == "warn"


@pytest.mark.req("R15.2")
def test_doctor_fails_on_plugin_version_mismatch(git_repo, monkeypatch, tmp_path, capsys):
    manifest = tmp_path / "plugin.json"
    manifest.write_text(json.dumps({"version": "9.9.9"}))
    monkeypatch.setattr(doctor, "PLUGIN_MANIFEST", manifest)

    code = main(["doctor"])

    assert code == 1
    assert f"plugin.json says 9.9.9, package is {__version__}" in capsys.readouterr().out


@pytest.mark.req("R18.3")
def test_doctor_fails_on_old_git(git_repo, monkeypatch):
    monkeypatch.setattr("agent_cairn.gitio.version", lambda _cwd: (2, 20, 0))

    check = next(c for c in doctor.run(git_repo) if c.name == "git")

    assert (check.level, check.detail) == ("fail", "2.20.0; 2.31 or newer is required")


def test_doctor_store_not_writable_fails(git_repo, monkeypatch, tmp_path):
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o500)
    monkeypatch.setenv("CAIRN_STORE", str(blocked / "store"))

    check = next(c for c in doctor.run(git_repo) if c.name == "store")

    blocked.chmod(0o700)
    assert check.level == ("ok" if os.geteuid() == 0 else "fail")


@pytest.mark.req("R15.1")
def test_doctor_reports_clipboard_and_command_install(git_repo, no_gh):
    levels = _levels(git_repo)

    assert levels["clipboard"] == "warn"
    assert levels["command"] == "warn"
