import json
import shutil

import pytest
from conftest import CREATED, add_worktree, bare_remote, commit, git

from agent_cairn import capture, render
from agent_cairn.cli import main
from agent_cairn.errors import CairnError

PRS_JSON = (
    '[{"number": 142, "title": "Login with Google", "url": "https://example.test/pr/142",'
    ' "headRefName": "feat", "isDraft": true}]'
)


@pytest.fixture
def repo(git_repo):
    commit(git_repo, "initial")
    return git_repo


@pytest.mark.req("R4.1")
def test_collect_repo_lists_other_worktrees_and_skips_prunable(repo):
    feat = add_worktree(repo, "feat-wt", "-b", "feat")
    gone = add_worktree(repo, "gone-wt", "-b", "gone")
    (feat / "x.txt").write_text("x")
    shutil.rmtree(gone)  # git now reports it as prunable

    state = capture.collect_repo(repo, use_gh=False)

    assert [(o.branch, o.changes_total) for o in state.others] == [("feat", 1)]


@pytest.mark.req("R4.2")
def test_collect_reads_upstream_ahead_behind_and_stashes(repo):
    bare_remote(repo)
    commit(repo, "local only")
    (repo / "s.txt").write_text("s")
    git(repo, "add", "s.txt")
    git(repo, "stash", "-q")

    state = capture.collect(repo)

    assert (state.upstream, state.ahead, state.behind, state.stashes) == ("origin/main", 1, 0, 1)


@pytest.mark.req("R4.2")
def test_collect_handles_spaces_and_unicode_in_paths(repo):
    (repo / "dir with space").mkdir()
    (repo / "dir with space" / "tệp mới.txt").write_text("x")

    paths = [c.path for c in capture.collect(repo).changes]

    assert paths in (["dir with space/"], ["dir with space/tệp mới.txt"])


@pytest.mark.req("R4.4")
def test_collect_repo_attaches_pull_requests_by_branch(repo, fake_gh):
    fake_gh(f"echo '{PRS_JSON}'")
    add_worktree(repo, "feat-wt", "-b", "feat")

    state = capture.collect_repo(repo, use_gh=True)

    assert state.prs.status == "ok"
    assert [pr.number for pr in state.others[0].prs] == [142]
    assert state.current.prs == ()


@pytest.mark.req("R4.5")
@pytest.mark.parametrize(
    ("script", "reason"),
    [
        ("exit 1", "gh failed"),
        ("echo 'not json'", "unexpected output from gh"),
        ("sleep 9", "did not finish"),
    ],
)
def test_collect_repo_degrades_when_gh_fails(repo, fake_gh, monkeypatch, script, reason):
    monkeypatch.setattr("agent_cairn.gh.GH_TIMEOUT_SECONDS", 0.5)
    fake_gh(script)

    state = capture.collect_repo(repo, use_gh=True)

    assert state.prs.status == "unavailable"
    assert reason in state.prs.error


@pytest.mark.req("R4.5")
def test_collect_repo_without_gh_installed_is_unavailable(repo, no_gh):
    state = capture.collect_repo(repo, use_gh=True)

    text = render.captured(state, (), captured_at=CREATED)
    assert state.prs.status == "unavailable"
    assert "- PRs: unavailable (gh is not installed or not on PATH)" in text


@pytest.mark.req("R4.8")
def test_collect_records_git_errors_per_field(repo, monkeypatch):
    def broken(cwd):
        raise CairnError("git stash failed: boom")

    monkeypatch.setattr("agent_cairn.gitio.stash_count", broken)

    state = capture.collect(repo)

    assert state.stashes is None
    assert state.errors == ("stashes: git stash failed: boom",)


@pytest.mark.req("R5.7")
def test_captured_markdown_summarises_other_worktrees(repo):
    add_worktree(repo, "feat-wt", "-b", "feat")

    text = render.captured(capture.collect_repo(repo, use_gh=False), (), captured_at=CREATED)

    assert "### Other worktrees" in text
    assert "| feat |" in text


@pytest.mark.req("R4.6")
@pytest.mark.req("R4.7")
def test_capture_json_puts_current_worktree_first(repo, capsys):
    add_worktree(repo, "feat-wt", "-b", "feat")

    code = main(["capture", "--json", "--no-gh"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["schema"] == 1
    assert payload["prs_status"] == "skipped"
    assert [w["current"] for w in payload["worktrees"]] == [True, False]
    assert payload["worktrees"][0]["branch"] == "main"


@pytest.mark.req("R4.6")
@pytest.mark.req("R4.9")
def test_capture_prints_readable_state_without_touching_store(repo, capsys, tmp_path):
    code = main(["capture", "--no-gh"])

    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("### Worktree (current): ")
    assert not (tmp_path.parent / ".cairn").exists()


@pytest.mark.req("R1.7")
def test_capture_outside_git_exits_5(outside_repo, capsys):
    assert main(["capture"]) == 5
    assert "not a git repository" in capsys.readouterr().err
