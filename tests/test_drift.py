import pytest
from conftest import CREATED, commit, git, make_handoff

from agent_cairn import capture, drift, render
from agent_cairn.capture import Commit
from agent_cairn.drift import Facts

SAVED = "a" * 40
TARGET = "b" * 40


def _facts(**overrides):
    fields = {
        "worktree": "/code/app",
        "worktree_exists": True,
        "saved": SAVED,
        "target": TARGET,
        "saved_exists": True,
        "is_ancestor": False,
        "new_commits": (),
        "new_commits_total": 0,
        "merge_base": None,
    }
    return Facts(**{**fields, **overrides})


@pytest.mark.req("R10.8")
def test_classify_same_head_reports_no_drift():
    result = drift.classify(_facts(target=SAVED))

    assert result.state == "same"
    assert [(line.level, line.text) for line in result.lines] == [
        ("info", "no drift: nothing changed since the handoff")
    ]


@pytest.mark.req("R10.2")
def test_classify_ahead_lists_new_commits_as_warning():
    commits = (Commit("1111111", "fix a"), Commit("2222222", "fix b"))

    result = drift.classify(_facts(is_ancestor=True, new_commits=commits, new_commits_total=2))

    assert result.state == "ahead"
    assert [line.text for line in result.lines] == [
        "2 new commit(s) since handoff:",
        "  1111111 fix a",
        "  2222222 fix b",
    ]
    assert result.lines[0].level == "warn"


@pytest.mark.req("R10.2")
def test_classify_ahead_mentions_hidden_commits():
    commits = tuple(Commit(f"{n:07}", "c") for n in range(10))

    result = drift.classify(_facts(is_ancestor=True, new_commits=commits, new_commits_total=12))

    assert result.lines[-1].text == "  … and 2 more"


@pytest.mark.req("R10.3")
def test_classify_diverged_warns_with_merge_base():
    result = drift.classify(_facts(merge_base="c" * 40))

    assert result.state == "diverged"
    assert result.lines[0].level == "warn"
    assert result.lines[0].text == "history diverged since handoff (merge-base ccccccc)"


@pytest.mark.req("R10.4")
def test_classify_missing_saved_head_warns():
    result = drift.classify(_facts(saved_exists=False))

    assert result.state == "missing"
    assert result.lines[0].text == "saved head aaaaaaa no longer exists"


def test_classify_missing_worktree_warns():
    result = drift.classify(_facts(worktree_exists=False))

    assert result.lines[0].text == "worktree /code/app no longer exists; drift not computed"


def _saved_at_head(repo):
    return make_handoff(worktree=str(repo), head=git(repo, "rev-parse", "HEAD"))


@pytest.mark.req("R10.1")
def test_compute_unchanged_repo_is_same(git_repo):
    commit(git_repo)

    assert drift.compute(_saved_at_head(git_repo), git_timeout=10).state == "same"


@pytest.mark.req("R10.2")
def test_compute_counts_and_caps_new_commits(git_repo):
    commit(git_repo)
    handoff = _saved_at_head(git_repo)
    for n in range(12):
        commit(git_repo, f"later {n}")

    result = drift.compute(handoff, git_timeout=10)

    assert result.state == "ahead"
    assert result.new_commits_total == 12
    assert len(result.new_commits) == 10
    assert result.new_commits[0].subject == "later 11"


@pytest.mark.req("R10.3")
def test_compute_detects_rewritten_history(git_repo):
    base = commit(git_repo, "base")
    commit(git_repo, "saved")
    handoff = _saved_at_head(git_repo)
    git(git_repo, "reset", "-q", "--hard", base)
    commit(git_repo, "rewritten")

    result = drift.compute(handoff, git_timeout=10)

    assert result.state == "diverged"
    assert result.merge_base == base


@pytest.mark.req("R10.4")
def test_compute_detects_garbage_collected_head(git_repo):
    base = commit(git_repo, "base")
    commit(git_repo, "doomed")
    handoff = _saved_at_head(git_repo)
    git(git_repo, "reset", "-q", "--hard", base)
    git(git_repo, "reflog", "expire", "--expire=now", "--all")
    git(git_repo, "gc", "-q", "--prune=now")

    assert drift.compute(handoff, git_timeout=10).state == "missing"


def _with_resources(repo, resources):
    """A handoff saved at ``repo`` HEAD whose captured state lists ``resources``."""
    captured = render.captured(capture.collect(repo), resources, captured_at=CREATED)
    return make_handoff(
        worktree=str(repo), head=git(repo, "rev-parse", "HEAD"), captured_md=captured
    )


@pytest.fixture
def workspace(git_repo):
    """``git_repo`` with a linked worktree ``wt`` on branch feat and a pipeline dir."""
    commit(git_repo, "base")
    git(git_repo, "worktree", "add", "-q", "-b", "feat", "wt")
    (git_repo / "pipe").mkdir()
    return git_repo


@pytest.mark.req("R10.10")
def test_compute_reports_new_commits_in_listed_worktree(workspace):
    resources = capture.collect_resources(workspace, [("worktree", "wt"), ("pipeline", "pipe")])
    handoff = _with_resources(workspace, resources)
    commit(workspace / "wt", "work in wt")

    texts = [line.text for line in drift.compute(handoff, git_timeout=10).lines]

    assert texts[0] == "worktree wt: 1 new commit(s) since handoff:"
    assert texts[1].endswith("work in wt")


@pytest.mark.req("R10.10")
def test_compute_warns_when_worktree_or_pipeline_disappears(workspace):
    resources = capture.collect_resources(workspace, [("worktree", "wt"), ("pipeline", "pipe")])
    handoff = _with_resources(workspace, resources)
    git(workspace, "worktree", "remove", "wt")
    (workspace / "pipe").rmdir()

    lines = drift.compute(handoff, git_timeout=10).lines

    assert [(line.level, line.text) for line in lines] == [
        ("warn", "worktree wt no longer exists"),
        ("warn", "pipeline pipe no longer exists"),
    ]


@pytest.mark.req("R10.10")
def test_compute_warns_when_listed_worktree_changes_branch(workspace):
    resources = capture.collect_resources(workspace, [("worktree", "wt")])
    handoff = _with_resources(workspace, resources)
    git(workspace / "wt", "checkout", "-q", "-b", "other")

    texts = [line.text for line in drift.compute(handoff, git_timeout=10).lines]

    assert texts == ["worktree wt: now on other (was feat)"]


@pytest.mark.req("R1.9")
def test_compute_outside_git_checks_only_resources(outside_repo):
    handoff = make_handoff(worktree=str(outside_repo), head="", branch="")

    result = drift.compute(handoff, git_timeout=10)

    assert result.state == "none"
    assert [line.text for line in result.lines] == ["no drift: nothing changed since the handoff"]
