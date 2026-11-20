"""Session start lists open handoffs; a message naming a task loads it (R13.3, R13.10, R13.11)."""

import io
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import CREATED, FILLED_BODY, commit

from agent_cairn import document, store
from agent_cairn.cli import main

LATER = CREATED + timedelta(hours=3)


@pytest.fixture
def repo(git_repo, clock):
    commit(git_repo, "initial")
    return git_repo


def _save(monkeypatch, task, title):
    body = FILLED_BODY.replace("Login form: wire OAuth callback", title)
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert main(["save", "--no-gh", "--task", task]) == 0


def _hook(monkeypatch, capsys, event, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    code = main(["hook", event])
    out = capsys.readouterr().out
    return code, (json.loads(out)["hookSpecificOutput"] if out else None)


def _statuses(repo):
    return {h.meta["task"]: h.meta["status"] for h in store.handoffs(store.root(repo))}


@pytest.fixture
def two_tasks(repo, monkeypatch, clock):
    _save(monkeypatch, "PROJ-2", "Cart fix")
    clock(CREATED + timedelta(minutes=5))
    _save(monkeypatch, "PROJ-21", "Login rework")
    clock(LATER)
    return repo


@pytest.mark.req("R13.10")
def test_session_start_lists_older_handoffs_without_loading_them(two_tasks, monkeypatch, capsys):
    code, output = _hook(monkeypatch, capsys, "session-start", {"source": "startup"})

    context = output["additionalContext"]
    assert code == 0
    assert context.startswith("=== cairn: open handoffs in this project ===")
    assert "- PROJ-21 · 2h ago · Login rework" in context
    assert "- PROJ-2 · 3h ago · Cart fix" in context
    assert "## Goal" not in context
    assert _statuses(two_tasks) == {"PROJ-2": "open", "PROJ-21": "open"}


@pytest.mark.req("R13.3")
def test_session_start_after_clear_loads_newest_in_full(two_tasks, monkeypatch, capsys):
    _, output = _hook(monkeypatch, capsys, "session-start", {"source": "clear"})

    assert "# Login rework" in output["additionalContext"]
    assert _statuses(two_tasks) == {"PROJ-2": "open", "PROJ-21": "resumed"}


@pytest.mark.req("R13.3")
def test_full_window_is_configurable(two_tasks, monkeypatch, capsys):
    monkeypatch.setenv("CAIRN_HOOK_FULL_WINDOW", "4h")

    _, output = _hook(monkeypatch, capsys, "session-start", {"source": "startup"})

    assert "# Login rework" in output["additionalContext"]


@pytest.mark.req("R13.11")
def test_prompt_naming_a_task_loads_exactly_that_handoff(two_tasks, monkeypatch, capsys):
    prompt = "/tf:build proj-2 --lang vi"

    code, output = _hook(monkeypatch, capsys, "prompt-submit", {"prompt": prompt})

    assert code == 0
    assert output["hookEventName"] == "UserPromptSubmit"
    assert "# Cart fix" in output["additionalContext"]
    assert "- PROJ-21: Login rework" in output["additionalContext"]
    assert _statuses(two_tasks) == {"PROJ-2": "resumed", "PROJ-21": "open"}


@pytest.mark.req("R13.11")
@pytest.mark.parametrize("prompt", ["fix the build", "look at PROJ-200", "xPROJ-2 typo", ""])
def test_prompt_without_an_open_task_adds_nothing(two_tasks, monkeypatch, capsys, prompt):
    _, output = _hook(monkeypatch, capsys, "prompt-submit", {"prompt": prompt})

    assert output is None
    assert set(_statuses(two_tasks).values()) == {"open"}


@pytest.mark.req("R13.11")
def test_a_task_is_loaded_only_once(two_tasks, monkeypatch, capsys):
    _hook(monkeypatch, capsys, "prompt-submit", {"prompt": "continue PROJ-21"})

    _, again = _hook(monkeypatch, capsys, "prompt-submit", {"prompt": "PROJ-21 again"})

    assert again is None


@pytest.mark.req("R13.11")
def test_prompt_hook_respects_cairn_hook_off(two_tasks, monkeypatch, capsys):
    monkeypatch.setenv("CAIRN_HOOK", "off")

    _, output = _hook(monkeypatch, capsys, "prompt-submit", {"prompt": "PROJ-2"})

    assert output is None


@pytest.mark.req("R4.11")
def test_save_records_the_writing_session_transcript(repo, monkeypatch):
    folder = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    folder.mkdir(parents=True)
    (folder / "abc-123.jsonl").write_text("{}\n")
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))

    main(["save", "--no-gh", "--session", "abc-123"])

    (path,) = store.root(repo).glob("*.md")
    handoff = document.parse(path.read_text())
    assert handoff.meta["transcript"] == str(folder / "abc-123.jsonl")


@pytest.mark.req("R4.11")
def test_resume_points_to_the_transcript(repo, monkeypatch, capsys):
    folder = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    folder.mkdir(parents=True)
    (folder / "abc-123.jsonl").write_text("{}\n")
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))
    main(["save", "--no-gh", "--session", "abc-123"])
    capsys.readouterr()

    main(["resume", "--peek"])

    assert "search it for the detail instead of reading it all" in capsys.readouterr().out


def test_save_without_transcript_file_records_none(repo, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))

    main(["save", "--no-gh", "--session", "no-such-session"])

    (path,) = store.root(repo).glob("*.md")
    assert "transcript" not in document.parse(path.read_text()).meta
