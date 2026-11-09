from datetime import timezone
from pathlib import Path

import pytest
from conftest import CREATED, commit, git

from agent_cairn import capture, document, render


@pytest.fixture
def repo_with_work(git_repo):
    """A repo with two commits, a modified tracked file and an untracked file."""
    (git_repo / "tracked.txt").write_text("v1\n")
    git(git_repo, "add", "tracked.txt")
    commit(git_repo, "first")
    commit(git_repo, "second: add login")
    (git_repo / "tracked.txt").write_text("v2\n")
    (git_repo / "new file é.txt").write_text("hello\n")
    return git_repo


@pytest.mark.req("R4.2")
def test_collect_reads_current_worktree(repo_with_work):
    state = capture.collect(repo_with_work)

    assert state.path.resolve() == repo_with_work.resolve()
    assert state.branch == "main"
    assert state.head == git(repo_with_work, "rev-parse", "HEAD")
    assert state.head_subject == "second: add login"
    assert [(c.xy, c.path) for c in state.changes] == [
        (" M", "tracked.txt"),
        ("??", "new file é.txt"),
    ]
    assert state.changes_total == 2
    assert [c.subject for c in state.recent_commits] == ["second: add login", "first"]


@pytest.mark.req("R4.2")
def test_collect_detached_head_has_no_branch(repo_with_work):
    git(repo_with_work, "checkout", "-q", "--detach")

    assert capture.collect(repo_with_work).branch is None


@pytest.mark.req("R4.2")
@pytest.mark.req("R4.3")
def test_collect_caps_changes_and_keeps_total(git_repo):
    commit(git_repo)
    for n in range(55):
        (git_repo / f"f{n:02}.txt").write_text("x")

    state = capture.collect(git_repo)

    assert len(state.changes) == 50
    assert state.changes_total == 55


@pytest.mark.req("R4.2")
def test_collect_rename_reports_new_path_only(repo_with_work):
    git(repo_with_work, "mv", "tracked.txt", "renamed.txt")

    paths = [c.path for c in capture.collect(repo_with_work).changes]

    assert "renamed.txt" in paths
    assert "tracked.txt" not in paths


@pytest.mark.req("R4.9")
def test_collect_does_not_create_store(repo_with_work):
    capture.collect(repo_with_work)

    assert not (Path.home() / ".cairn").exists()


@pytest.mark.req("R12.4")
@pytest.mark.req("R12.5")
def test_captured_markdown_holds_paths_not_file_contents(git_repo):
    commit(git_repo)
    secret_line = "token = " + "ghp_" + "z" * 36
    (git_repo / "leak.env").write_text(secret_line + "\n")

    text = render.captured(capture.collect_repo(git_repo, use_gh=False), (), captured_at=CREATED)

    assert "leak.env" in text
    assert "ghp_" not in text


@pytest.mark.req("R2.7")
def test_captured_markdown_lists_worktree_facts(repo_with_work):
    state = capture.collect(repo_with_work)

    text = render.captured(
        capture.RepoState(state, (), capture.PrLookup("skipped")),
        (),
        captured_at=CREATED.astimezone(timezone.utc),
    )

    assert text.startswith("## Captured state (auto-generated — do not edit)\n")
    assert "Captured at 2026-11-09T08:30:12Z by cairn" in text
    assert "- Branch: main" in text
    assert f"- HEAD: {state.head[:7]} second: add login" in text
    assert "  - ` M` tracked.txt" in text
    assert "- Uncommitted (2):" in text


def test_captured_markdown_notes_truncated_changes(git_repo):
    commit(git_repo)
    for n in range(52):
        (git_repo / f"f{n:02}.txt").write_text("x")

    text = render.captured(capture.collect_repo(git_repo, use_gh=False), (), captured_at=CREATED)

    assert "  - … and 2 more" in text


@pytest.mark.req("R1.9")
def test_collect_outside_git_records_directory_only(outside_repo):
    state = capture.collect(outside_repo)

    text = render.captured(
        capture.RepoState(state, (), capture.PrLookup("skipped")), (), captured_at=CREATED
    )
    assert (state.is_git, state.branch, state.head) == (False, None, "")
    assert "- not a git repository" in text


@pytest.mark.req("R4.10")
def test_collect_resources_reads_worktrees_and_pipelines(outside_repo):
    linked = outside_repo / "wt"
    linked.mkdir()
    git(linked, "init", "-q", "-b", "fix/x")
    sha = commit(linked)
    (linked / "dirty.txt").write_text("x")
    (outside_repo / ".pipeline" / "T-1").mkdir(parents=True)
    entries = [("worktree", "wt"), ("pipeline", ".pipeline/T-1"), ("db", "x"), ("worktree", "gone")]

    resources = capture.collect_resources(outside_repo, entries)

    assert [(r.kind, r.path, r.exists) for r in resources] == [
        ("worktree", "wt", True),
        ("pipeline", ".pipeline/T-1", True),
        ("worktree", "gone", False),
    ]
    assert (resources[0].branch, resources[0].head, resources[0].changes_total) == ("fix/x", sha, 1)


@pytest.mark.req("R4.10")
def test_resources_round_trip_through_captured_json(outside_repo):
    (outside_repo / "p").mkdir()
    resources = capture.collect_resources(outside_repo, [("pipeline", "p")])

    text = render.captured(
        capture.collect_repo(outside_repo, use_gh=False), resources, captured_at=CREATED
    )

    assert "- pipeline `p`: present" in text
    payload = document.captured_json(text)
    assert capture.resources_from_json(payload) == resources
