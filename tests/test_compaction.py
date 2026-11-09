import io
import json
from datetime import timedelta

import pytest
from conftest import CREATED, FILLED_BODY, ROOT_DIR, commit

from agent_cairn.cli import main


@pytest.fixture
def repo(git_repo, clock):
    commit(git_repo, "initial")
    return git_repo


def _run(monkeypatch, capsys, event):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"hook_event_name": event})))
    capsys.readouterr()
    code = main(["hook", event])
    return code, capsys.readouterr()


@pytest.mark.req("R23.1")
@pytest.mark.req("R23.4")
def test_hooks_json_registers_compaction_hooks():
    hooks = json.loads((ROOT_DIR / "hooks" / "hooks.json").read_text())["hooks"]

    (pre,) = hooks["PreCompact"]
    post = [entry for entry in hooks["SessionStart"] if entry["matcher"] == "compact"]
    assert pre["matcher"] == "manual|auto"
    assert pre["hooks"][0]["args"] == ["hook", "pre-compact"]
    assert post[0]["hooks"][0]["args"] == ["hook", "post-compact"]


@pytest.mark.req("R23.2")
@pytest.mark.req("R23.3")
def test_pre_compact_prints_summary_instructions_and_never_blocks(
    outside_repo, monkeypatch, capsys
):
    code, captured = _run(monkeypatch, capsys, "pre-compact")

    assert code == 0
    assert captured.out.startswith("When summarizing this conversation, preserve")
    assert "decision" in captured.out
    assert 'decision": "block' not in captured.out


@pytest.mark.req("R23.5")
@pytest.mark.req("R23.6")
def test_post_compact_nudges_when_no_recent_handoff(repo, monkeypatch, capsys):
    code, captured = _run(monkeypatch, capsys, "post-compact")

    payload = json.loads(captured.out)
    assert code == 0
    assert set(payload) == {"systemMessage"}
    assert payload["systemMessage"] == (
        "cairn: no handoff saved for this project in the last 2h. "
        "Run /cairn:handoff to keep this work for a new session."
    )


@pytest.mark.req("R23.5")
def test_post_compact_silent_after_recent_handoff(repo, monkeypatch, capsys, clock):
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))
    main(["save", "--no-gh"])
    clock(CREATED + timedelta(hours=1))

    _, captured = _run(monkeypatch, capsys, "post-compact")

    assert captured.out == ""


@pytest.mark.req("R23.7")
@pytest.mark.parametrize("event", ["pre-compact", "post-compact"])
def test_compaction_hooks_disabled_by_env(repo, monkeypatch, capsys, event):
    monkeypatch.setenv("CAIRN_NUDGE", "off")

    code, captured = _run(monkeypatch, capsys, event)

    assert (code, captured.out) == (0, "")


@pytest.mark.req("R23.7")
def test_post_compact_error_exits_0(repo, monkeypatch, capsys):
    monkeypatch.setenv("CAIRN_NUDGE_WINDOW", "soon")

    code, captured = _run(monkeypatch, capsys, "post-compact")

    assert (code, captured.out) == (0, "")
    assert "hook: invalid duration" in captured.err
