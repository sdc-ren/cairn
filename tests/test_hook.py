import io
import json
import os
from datetime import timedelta

import pytest
from conftest import CREATED, FILLED_BODY, commit, git

from agent_cairn import document, render, store
from agent_cairn.cli import main
from agent_cairn.drift import Drift, DriftLine


@pytest.fixture
def repo(git_repo, clock):
    commit(git_repo, "initial")
    return git_repo


def _save(monkeypatch, body=FILLED_BODY):
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert main(["save"]) == 0


def _hook(monkeypatch, capsys, event=None):
    payload = json.dumps(event if event is not None else {"hook_event_name": "SessionStart"})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    capsys.readouterr()
    code = main(["hook", "session-start"])
    return code, capsys.readouterr()


def _stored(repo):
    (path,) = store.root(repo).glob("*.md")
    return document.parse(path.read_text())


@pytest.mark.req("R13.3")
@pytest.mark.req("R9.1")
def test_hook_injects_open_handoff_as_additional_context(repo, monkeypatch, capsys):
    _save(monkeypatch)

    code, captured = _hook(monkeypatch, capsys)

    payload = json.loads(captured.out)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert code == 0
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert context.startswith("=== cairn handoff ")
    assert "## Goal\nUsers can sign in with Google." in context
    assert "no drift: nothing changed since the handoff" in context
    assert "## Captured state" not in context  # the hook injects the brief form


@pytest.mark.req("R13.3")
@pytest.mark.req("R9.3")
def test_hook_marks_handoff_resumed_so_it_is_injected_once(repo, monkeypatch, capsys):
    _save(monkeypatch)

    _hook(monkeypatch, capsys)
    _, second = _hook(monkeypatch, capsys)

    assert _stored(repo).meta["status"] == "resumed"
    assert second.out == ""


@pytest.mark.req("R9.5")
def test_hook_never_deletes_the_handoff(repo, monkeypatch, capsys):
    _save(monkeypatch)

    _hook(monkeypatch, capsys)

    assert _stored(repo).body == FILLED_BODY.strip()


@pytest.mark.req("R13.1")
def test_hook_uses_cwd_from_event(repo, tmp_path, monkeypatch, capsys):
    _save(monkeypatch)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    _, captured = _hook(monkeypatch, capsys, {"cwd": str(repo)})

    assert "additionalContext" in captured.out


@pytest.mark.req("R13.4")
def test_hook_without_handoff_prints_nothing(repo, monkeypatch, capsys):
    code, captured = _hook(monkeypatch, capsys)

    assert (code, captured.out) == (0, "")


@pytest.mark.req("R13.3")
def test_hook_injects_handoff_from_another_branch(repo, monkeypatch, capsys):
    _save(monkeypatch)
    git(repo, "checkout", "-q", "-b", "session-worktree-branch")

    _, captured = _hook(monkeypatch, capsys)

    assert "Login form" in captured.out


@pytest.mark.req("R13.3")
def test_hook_prefers_handoff_of_current_branch(repo, monkeypatch, capsys, clock):
    _save(monkeypatch)
    git(repo, "checkout", "-q", "-b", "feat")
    clock(CREATED + timedelta(minutes=5))
    _save(monkeypatch, FILLED_BODY.replace("Login form", "Feature work"))
    git(repo, "checkout", "-q", "main")

    _, captured = _hook(monkeypatch, capsys)

    context = json.loads(captured.out)["hookSpecificOutput"]["additionalContext"]
    assert "# Login form" in context


@pytest.mark.req("R13.9")
def test_hook_lists_other_open_handoffs_and_keeps_them_open(repo, monkeypatch, capsys, clock):
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))
    main(["save", "--task", "PROJ-1"])
    clock(CREATED + timedelta(minutes=5))
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY.replace("Login form", "Cart fix")))
    main(["save", "--task", "PROJ-2"])

    _, captured = _hook(monkeypatch, capsys)

    context = json.loads(captured.out)["hookSpecificOutput"]["additionalContext"]
    assert "# Cart fix" in context
    assert "/cairn:resume <task or id>" in context
    assert "- PROJ-1: Login form: wire OAuth callback (20261109-083012-proj-1)" in context
    statuses = {h.meta["task"]: h.meta["status"] for h in store.handoffs(store.root(repo))}
    assert statuses == {"PROJ-1": "open", "PROJ-2": "resumed"}


@pytest.mark.req("R1.9")
def test_hook_works_outside_git(outside_repo, monkeypatch, capsys, clock):
    _save(monkeypatch)

    _, captured = _hook(monkeypatch, capsys, {"cwd": str(outside_repo)})

    assert "# Login form" in captured.out


@pytest.mark.req("R13.3")
def test_hook_ignores_handoff_older_than_max_age(repo, monkeypatch, capsys, clock):
    _save(monkeypatch)
    clock(CREATED + timedelta(days=7, seconds=1))

    _, captured = _hook(monkeypatch, capsys)

    assert captured.out == ""


@pytest.mark.req("R13.3")
def test_hook_max_age_is_configurable(repo, monkeypatch, capsys, clock):
    _save(monkeypatch)
    clock(CREATED + timedelta(hours=2))
    monkeypatch.setenv("CAIRN_HOOK_MAX_AGE", "1h")

    _, captured = _hook(monkeypatch, capsys)

    assert captured.out == ""


@pytest.mark.req("R13.7")
@pytest.mark.parametrize("stdin", ["not json", "[]", ""])
def test_hook_tolerates_bad_event_input(repo, monkeypatch, capsys, stdin):
    _save(monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    capsys.readouterr()

    code = main(["hook", "session-start"])

    assert code == 0
    assert "additionalContext" in capsys.readouterr().out


@pytest.mark.req("R13.7")
def test_hook_unexpected_error_exits_0_with_stderr_only(repo, monkeypatch, capsys):
    _save(monkeypatch)

    def explode(*args, **kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr(store, "handoffs", explode)

    code, captured = _hook(monkeypatch, capsys)

    assert (code, captured.out) == (0, "")
    assert "cairn: warning: hook: disk on fire" in captured.err


@pytest.mark.req("R13.7")
def test_hook_outside_repo_exits_0_silently(outside_repo, monkeypatch, capsys):
    code, captured = _hook(monkeypatch, capsys)

    assert (code, captured.out) == (0, "")


@pytest.mark.req("R13.8")
def test_hook_disabled_by_env(repo, monkeypatch, capsys):
    _save(monkeypatch)
    monkeypatch.setenv("CAIRN_HOOK", "off")

    _, captured = _hook(monkeypatch, capsys)

    assert captured.out == ""
    assert _stored(repo).meta["status"] == "open"


@pytest.mark.req("R13.6")
def test_hook_never_runs_gh(repo, monkeypatch, capsys, tmp_path):
    _save(monkeypatch)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    fake_gh = bin_dir / "gh"
    fake_gh.write_text(f"#!/bin/sh\necho called >> {log}\n")
    fake_gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    _hook(monkeypatch, capsys)

    assert not log.exists()


@pytest.mark.req("R13.5")
def test_hook_truncates_long_context(repo, monkeypatch, capsys):
    long_state = "Callback route exchanges the code. " + "x" * 11_000
    _save(monkeypatch, FILLED_BODY.replace("Callback route exchanges the code.", long_state))

    _, captured = _hook(monkeypatch, capsys)

    context = json.loads(captured.out)["hookSpecificOutput"]["additionalContext"]
    assert len(context) <= 9000
    assert context.endswith("[truncated — run: cairn show " + _stored(repo).meta["id"] + "]")


@pytest.mark.req("R9.1")
@pytest.mark.req("R9.2")
def test_resume_full_orders_preamble_body_drift_captured(repo, monkeypatch):
    _save(monkeypatch)
    handoff = store.newest(store.root(repo), branch="main")
    result = Drift("same", (), 0, None, (DriftLine("info", "no drift: x"),))

    text = render.resume(handoff, result, brief=False)

    positions = [
        text.index("=== cairn handoff"),
        text.index("Before changing anything"),
        text.index("## Goal"),
        text.index("## Drift since handoff"),
        text.index("## Captured state"),
        text.index("=== end cairn handoff ==="),
    ]
    assert positions == sorted(positions)
    assert "wait for the user to confirm" in text
