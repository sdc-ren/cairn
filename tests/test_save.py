import io
import json
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import CREATED, FILLED_BODY, commit, git

from agent_cairn import document, store
from agent_cairn.cli import main


class _Tty(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def repo(git_repo):
    commit(git_repo, "initial")
    return git_repo


def _handoffs(repo):
    directory = store.root(repo)
    return sorted(directory.glob("*.md")) if directory.is_dir() else []


def _save(monkeypatch, body, *args):
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    return main(["save", *args])


@pytest.mark.req("R5.1")
@pytest.mark.req("R5.9")
def test_save_from_stdin_prints_only_saved_id(repo, monkeypatch, capsys):
    code = _save(monkeypatch, FILLED_BODY)

    (path,) = _handoffs(repo)
    assert code == 0
    assert capsys.readouterr().out == f"saved {path.stem}\n"


@pytest.mark.req("R5.9")
def test_save_writes_open_handoff_with_frontmatter_and_captured(repo, monkeypatch):
    _save(monkeypatch, FILLED_BODY, "--agent", "claude-code")

    (path,) = _handoffs(repo)
    handoff = document.parse(path.read_text())
    assert handoff.meta["status"] == "open"
    assert handoff.meta["title"] == "Login form: wire OAuth callback"
    assert handoff.meta["branch"] == "main"
    assert handoff.meta["head"] == git(repo, "rev-parse", "HEAD")
    assert handoff.meta["agent"] == "claude-code"
    assert handoff.meta["repo"] == "repo"
    assert handoff.body == FILLED_BODY.strip()
    assert handoff.captured_md.startswith("## Captured state")


@pytest.mark.req("R5.1")
def test_save_reads_body_from_file(repo, tmp_path, capsys):
    body_file = tmp_path / "body.md"
    body_file.write_text(FILLED_BODY)

    code = main(["save", "--file", str(body_file)])

    assert code == 0
    assert len(_handoffs(repo)) == 1


@pytest.mark.req("R5.2")
def test_save_without_input_on_tty_is_usage_error(repo, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _Tty())

    code = main(["save"])

    assert code == 2
    assert _handoffs(repo) == []


@pytest.mark.req("R5.3")
@pytest.mark.req("R5.4")
def test_save_invalid_body_exits_3_with_one_line_per_violation(repo, monkeypatch, capsys):
    body = FILLED_BODY.replace("## Goal\nUsers can sign in with Google.\n", "").replace(
        "Callback route exchanges the code.", "TODO"
    )

    code = _save(monkeypatch, body)

    err = capsys.readouterr().err.splitlines()
    assert code == 3
    assert "missing-section: add a '## Goal' section" in err
    assert "line 4: empty-section: '## Current state' has no content; fill it in" in err
    assert _handoffs(repo) == []


@pytest.mark.req("R5.6")
@pytest.mark.req("R12.2")
def test_save_rejects_secret_without_printing_it(repo, monkeypatch, capsys):
    token = "ghp_" + "q" * 36
    body = FILLED_BODY.replace("Callback route exchanges the code.", f"Use {token} for CI.")

    code = _save(monkeypatch, body)

    err = capsys.readouterr().err
    assert code == 3
    assert "line 7: secret-github-token:" in err
    assert token not in err
    assert _handoffs(repo) == []


@pytest.mark.req("R14.1")
@pytest.mark.req("R14.5")
def test_save_replaces_older_handoff_of_same_branch(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY)
    (first,) = _handoffs(repo)
    capsys.readouterr()

    _save(monkeypatch, FILLED_BODY.replace("Login form", "Second"))

    (second,) = _handoffs(repo)
    assert second != first
    assert f"cairn: removed {first.stem} (replaced)" in capsys.readouterr().err


@pytest.mark.req("R14.1")
def test_save_keeps_handoffs_of_other_branches(repo, monkeypatch):
    _save(monkeypatch, FILLED_BODY)
    git(repo, "checkout", "-q", "-b", "feat/other")

    _save(monkeypatch, FILLED_BODY)

    branches = sorted(document.parse(p.read_text()).meta["branch"] for p in _handoffs(repo))
    assert branches == ["feat/other", "main"]


@pytest.mark.req("R14.1")
def test_save_on_detached_head_never_replaces(repo, monkeypatch):
    git(repo, "checkout", "-q", "--detach")
    _save(monkeypatch, FILLED_BODY)

    _save(monkeypatch, FILLED_BODY)

    assert len(_handoffs(repo)) == 2
    assert all("-detached-" in p.stem for p in _handoffs(repo))


@pytest.mark.req("R2.3")
@pytest.mark.req("R5.5")
def test_save_records_session_id(repo, monkeypatch):
    _save(monkeypatch, FILLED_BODY, "--session", "4f1c2a9e")

    (path,) = _handoffs(repo)
    assert document.parse(path.read_text()).meta["session_id"] == "4f1c2a9e"


@pytest.mark.req("R1.8")
def test_save_writes_project_json_naming_the_repo(repo, monkeypatch):
    _save(monkeypatch, FILLED_BODY)

    recorded = json.loads((store.root(repo) / ".project.json").read_text())
    assert Path(recorded["path"]).resolve() == repo.resolve()


@pytest.mark.req("R8.1")
@pytest.mark.req("R8.2")
def test_show_prints_latest_handoff_verbatim_without_changing_it(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY)
    (path,) = _handoffs(repo)
    before = path.read_text()
    capsys.readouterr()

    code = main(["show"])

    assert code == 0
    assert capsys.readouterr().out == before
    assert path.read_text() == before


@pytest.mark.req("R8.3")
def test_show_path_prints_absolute_file_path(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY)
    (path,) = _handoffs(repo)
    capsys.readouterr()

    main(["show", "--path"])

    assert capsys.readouterr().out == f"{path}\n"


@pytest.mark.req("R7.2")
def test_show_falls_back_to_latest_in_project_with_warning(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY)
    git(repo, "checkout", "-q", "-b", "feat/other")
    capsys.readouterr()

    code = main(["show"])

    captured = capsys.readouterr()
    assert code == 0
    assert "# Login form" in captured.out
    assert "no handoff for branch feat/other; using latest in project" in captured.err


@pytest.mark.req("R7.5")
def test_show_without_any_handoff_exits_4(repo, capsys):
    assert main(["show"]) == 4


@pytest.mark.req("R5.5")
@pytest.mark.req("R14.1")
def test_save_with_task_names_file_and_replaces_same_task_only(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY, "--task", "PROJ-268")
    _save(monkeypatch, FILLED_BODY, "--task", "PROJ-269")
    capsys.readouterr()

    _save(monkeypatch, FILLED_BODY, "--task", "proj-268")

    tasks = sorted(document.parse(p.read_text()).meta["task"] for p in _handoffs(repo))
    assert tasks == ["PROJ-269", "proj-268"]
    assert all("-proj-26" in p.stem for p in _handoffs(repo))
    assert "(replaced)" in capsys.readouterr().err


@pytest.mark.req("R1.9")
def test_save_outside_git_keeps_one_handoff_per_directory(outside_repo, monkeypatch):
    _save(monkeypatch, FILLED_BODY)
    _save(monkeypatch, FILLED_BODY)

    (path,) = sorted(store.root(outside_repo).glob("*.md"))
    handoff = document.parse(path.read_text())
    assert "-workspace" in path.stem
    assert (handoff.meta["branch"], handoff.meta["head"]) == ("", "")


@pytest.mark.req("R1.10")
def test_save_dir_option_overrides_process_cwd(repo, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    _save(monkeypatch, FILLED_BODY, "--dir", str(repo))

    assert len(_handoffs(repo)) == 1


@pytest.mark.req("R4.10")
def test_save_captures_workspace_section(repo, monkeypatch):
    (repo / "pipe").mkdir()
    body = FILLED_BODY + "\n## Workspace\n- pipeline: pipe\n- db: test_db\n"

    _save(monkeypatch, body)

    (path,) = _handoffs(repo)
    assert "- pipeline `pipe`: present" in path.read_text()


@pytest.mark.req("R7.1")
def test_show_by_task_ignores_case(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY, "--task", "PROJ-268")
    capsys.readouterr()

    assert main(["show", "proj-268", "--path"]) == 0
    assert capsys.readouterr().out.strip().endswith("-proj-268.md")


@pytest.mark.req("R7.5")
def test_show_unknown_ref_exits_4(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY)

    assert main(["show", "NOPE-1"]) == 4
    assert "handoff not found: NOPE-1" in capsys.readouterr().err


@pytest.mark.req("R9.1")
@pytest.mark.req("R9.3")
def test_resume_prints_full_context_and_marks_resumed(repo, monkeypatch, capsys):
    _save(monkeypatch, FILLED_BODY, "--task", "PROJ-268")
    capsys.readouterr()

    code = main(["resume", "PROJ-268"])

    out = capsys.readouterr().out
    (path,) = _handoffs(repo)
    assert code == 0
    assert out.startswith("=== cairn handoff ")
    assert "## Captured state" in out
    assert "cairn:captured-json" not in out
    assert document.parse(path.read_text()).meta["status"] == "resumed"


def _save_task(monkeypatch, task, title):
    _save(
        monkeypatch, FILLED_BODY.replace("Login form: wire OAuth callback", title), "--task", task
    )


@pytest.mark.req("R6.1")
def test_list_prints_table_newest_first(repo, monkeypatch, capsys, clock):
    _save_task(monkeypatch, "PROJ-1", "First task")
    clock(CREATED + timedelta(hours=2))
    _save_task(monkeypatch, "PROJ-2", "Second task " + "x" * 80)
    clock(CREATED + timedelta(hours=3))
    capsys.readouterr()

    code = main(["list"])

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    assert lines[0].split() == ["ID", "TASK", "STATUS", "AGE", "TITLE"]
    assert lines[1].split()[:4] == ["20261109-103012-proj-2", "PROJ-2", "open", "1h"]
    assert lines[1].endswith("…")
    assert len(lines[1].split("  ")[-1].strip()) <= 61
    assert lines[2].split()[:4] == ["20261109-083012-proj-1", "PROJ-1", "open", "3h"]


@pytest.mark.req("R6.3")
def test_list_filters_by_status(repo, monkeypatch, capsys, clock):
    _save_task(monkeypatch, "PROJ-1", "First task")
    _save_task(monkeypatch, "PROJ-2", "Second task")
    main(["resume", "PROJ-1"])
    capsys.readouterr()

    main(["list", "--status", "open"])

    rows = capsys.readouterr().out.splitlines()[1:]
    assert [row.split()[1] for row in rows] == ["PROJ-2"]


@pytest.mark.req("R6.1")
def test_list_shows_branch_when_no_task(repo, monkeypatch, capsys, clock):
    _save(monkeypatch, FILLED_BODY)
    capsys.readouterr()

    main(["list"])

    assert capsys.readouterr().out.splitlines()[1].split()[1] == "main"


@pytest.mark.req("R6.2")
def test_list_limits_rows_unless_all(repo, monkeypatch, capsys, clock):
    for n in range(3):
        clock(CREATED + timedelta(minutes=n))
        _save_task(monkeypatch, f"T-{n}", f"Task {n}")
    capsys.readouterr()

    main(["list", "--limit", "2"])
    limited = capsys.readouterr().out.splitlines()
    main(["list", "--all"])
    everything = capsys.readouterr().out.splitlines()

    assert (len(limited), len(everything)) == (3, 4)


@pytest.mark.req("R6.5")
def test_list_empty_store_says_so(repo, capsys):
    assert main(["list"]) == 0
    assert capsys.readouterr().out == "no handoffs yet\n"
