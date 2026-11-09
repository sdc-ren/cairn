import io
import json
from datetime import timedelta

import pytest
from conftest import CREATED, FILLED_BODY, commit, git, make_handoff

from agent_cairn import document, resolve, store
from agent_cairn.cli import main
from agent_cairn.errors import NotFoundError


@pytest.fixture
def repo(git_repo, clock):
    commit(git_repo, "initial")
    return git_repo


def _save(monkeypatch, *args):
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))
    assert main(["save", "--no-gh", *args]) == 0


def _only(repo):
    (path,) = store.root(repo).glob("*.md")
    return document.parse(path.read_text())


def _handoffs(*ids):
    return [make_handoff(id=hid) for hid in ids]


@pytest.mark.req("R7.1")
def test_select_by_unique_id_prefix():
    handoffs = _handoffs("20261109-083012-main", "20261108-083012-main")

    chosen, _ = resolve.select(handoffs, ref="20261108", branch=None)

    assert chosen.meta["id"] == "20261108-083012-main"


@pytest.mark.req("R7.1")
def test_select_short_prefix_is_not_found():
    with pytest.raises(NotFoundError, match="handoff not found: 202"):
        resolve.select(_handoffs("20261109-083012-main"), ref="202", branch=None)


@pytest.mark.req("R7.4")
def test_select_ambiguous_prefix_lists_ids():
    handoffs = _handoffs("20261109-083012-a", "20261109-093012-b")

    with pytest.raises(NotFoundError) as caught:
        resolve.select(handoffs, ref="20261109", branch=None)

    assert caught.value.exit_code == 4
    assert caught.value.details == ("20261109-083012-a", "20261109-093012-b")


@pytest.mark.req("R7.3")
def test_select_any_branch_takes_newest_without_warning():
    handoffs = [make_handoff(id="new", branch="feat"), make_handoff(id="old", branch="main")]

    chosen, warning = resolve.select(handoffs, ref=None, branch="main", any_branch=True)

    assert (chosen.meta["id"], warning) == ("new", None)


@pytest.mark.req("R7.4")
def test_cli_ambiguous_prefix_exits_4_with_ids(repo, monkeypatch, capsys, clock):
    _save(monkeypatch, "--task", "A-1")
    clock(CREATED + timedelta(hours=1))
    _save(monkeypatch, "--task", "A-2")
    capsys.readouterr()

    code = main(["show", "20261109"])

    err = capsys.readouterr().err.splitlines()
    assert code == 4
    assert err[0].startswith("cairn: ambiguous handoff id: 20261109")
    assert len(err) == 3


@pytest.mark.req("R9.4")
def test_resume_peek_changes_nothing(repo, monkeypatch):
    _save(monkeypatch)
    (path,) = store.root(repo).glob("*.md")
    before = path.read_text()

    assert main(["resume", "--peek"]) == 0
    assert path.read_text() == before


@pytest.mark.req("R9.6")
def test_resume_brief_leaves_out_captured_state(repo, monkeypatch, capsys):
    _save(monkeypatch)
    capsys.readouterr()

    main(["resume", "--brief"])

    out = capsys.readouterr().out
    assert "## Drift since handoff" in out
    assert "## Captured state" not in out


@pytest.mark.req("R9.7")
def test_resume_json_has_handoff_and_drift(repo, monkeypatch, capsys):
    _save(monkeypatch)
    capsys.readouterr()

    main(["resume", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["handoff"]["meta"]["status"] == "open"
    assert payload["handoff"]["body"].startswith("# Login form")
    assert payload["drift"]["state"] == "same"
    assert payload["drift"]["lines"][0]["level"] == "info"


@pytest.mark.req("R9.8")
def test_resume_twice_notes_previous_resume(repo, monkeypatch, capsys):
    _save(monkeypatch)
    main(["resume"])
    capsys.readouterr()

    main(["resume"])

    captured = capsys.readouterr()
    assert "already resumed 1 time(s), last 2026-11-09T08:30:12Z" in captured.out
    assert "was already resumed" in captured.err
    assert _only(repo).meta["resume_count"] == 2


@pytest.mark.req("R10.9")
def test_resume_with_warning_drift_still_exits_0(repo, monkeypatch, capsys):
    _save(monkeypatch)
    commit(repo, "after handoff")
    capsys.readouterr()

    assert main(["resume"]) == 0
    assert "- warn: 1 new commit(s) since handoff:" in capsys.readouterr().out


@pytest.mark.req("R6.3")
def test_list_filters_by_branch_and_here(repo, monkeypatch, capsys):
    _save(monkeypatch)
    git(repo, "checkout", "-q", "-b", "feat")
    _save(monkeypatch)
    capsys.readouterr()

    main(["list", "--branch", "main"])
    by_branch = capsys.readouterr().out.splitlines()[1:]
    main(["list", "--here"])
    here = capsys.readouterr().out.splitlines()[1:]

    assert [row.split()[1] for row in by_branch] == ["main"]
    assert [row.split()[1] for row in here] == ["feat"]


@pytest.mark.req("R6.4")
def test_list_json_prints_frontmatter(repo, monkeypatch, capsys):
    _save(monkeypatch, "--task", "A-1")
    capsys.readouterr()

    main(["list", "--json"])

    (meta,) = json.loads(capsys.readouterr().out)
    assert meta["task"] == "A-1"
    assert meta["status"] == "open"


@pytest.mark.req("R6.1")
def test_list_handles_25_handoffs(repo, monkeypatch, capsys, clock):
    for n in range(25):
        clock(CREATED + timedelta(minutes=n))
        _save(monkeypatch, "--task", f"T-{n}")
    capsys.readouterr()

    main(["list"])
    default = capsys.readouterr().out.splitlines()
    main(["list", "--all"])
    everything = capsys.readouterr().out.splitlines()

    assert (len(default), len(everything)) == (21, 26)
