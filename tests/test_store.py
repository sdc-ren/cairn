import re
import stat
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import CREATED, commit, git, make_handoff

from agent_cairn import document, store

LATER = CREATED + timedelta(hours=2)


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def store_root(tmp_path):
    return tmp_path / "store"


@pytest.mark.req("R1.1")
def test_root_is_project_folder_under_cairn_home(git_repo):
    root = store.root(git_repo)

    assert root.parent == Path.home() / ".cairn"
    assert re.fullmatch(r"repo-[0-9a-f]{8}", root.name)


@pytest.mark.req("R1.1")
def test_root_differs_for_two_repos_with_same_folder_name(git_repo, tmp_path):
    other = tmp_path / "elsewhere" / "repo"
    other.mkdir(parents=True)
    git(other, "init", "-q")

    assert store.root(other) != store.root(git_repo)


@pytest.mark.req("R1.2")
def test_root_honours_cairn_home(git_repo, monkeypatch, tmp_path):
    monkeypatch.setenv("CAIRN_HOME", str(tmp_path / "custom"))

    assert store.root(git_repo).parent == tmp_path / "custom"


@pytest.mark.req("R1.3")
def test_write_new_makes_cairn_home_private(git_repo):
    root = store.root(git_repo)

    store.write_new(root, make_handoff(), created_at=CREATED, label="main")

    assert _mode(Path.home() / ".cairn") == 0o700
    assert _mode(Path.home() / ".cairn") == 0o700


@pytest.mark.req("R1.1")
def test_root_from_linked_worktree_is_main_repo_store(git_repo):
    commit(git_repo)
    linked = git_repo.parent / "linked"
    git(git_repo, "worktree", "add", "-q", "-b", "feat", str(linked))

    assert store.root(linked) == store.root(git_repo)


@pytest.mark.req("R1.2")
def test_root_honours_store_override(git_repo, monkeypatch, store_root):
    monkeypatch.setenv("CAIRN_STORE", str(store_root))

    assert store.root(git_repo) == store_root


@pytest.mark.req("R1.3")
@pytest.mark.req("R1.4")
def test_write_new_creates_private_dirs_and_file(store_root):
    hid = store.write_new(store_root, make_handoff(), created_at=CREATED, label="main")

    path = store_root / f"{hid}.md"
    assert _mode(store_root) == 0o700
    assert _mode(path) == 0o600


@pytest.mark.req("R1.4")
def test_write_new_file_parses_back_with_id(store_root):
    hid = store.write_new(store_root, make_handoff(), created_at=CREATED, label="feat/Login UI")

    parsed = document.parse((store_root / f"{hid}.md").read_text())

    assert hid == "20261109-083012-feat-login-ui"
    assert parsed.meta["id"] == hid
    assert parsed.body == make_handoff().body.strip()


@pytest.mark.req("R1.5")
def test_write_new_leaves_no_temp_files(store_root):
    store.write_new(store_root, make_handoff(), created_at=CREATED, label="main")

    assert [p.name for p in store_root.iterdir()] == ["20261109-083012-main.md"]


@pytest.mark.req("R1.6")
def test_write_new_same_second_gets_suffix_instead_of_overwrite(store_root):
    ids = [
        store.write_new(store_root, make_handoff(title=f"t{n}"), created_at=CREATED, label="main")
        for n in range(3)
    ]

    assert ids == ["20261109-083012-main", "20261109-083012-main-2", "20261109-083012-main-3"]


@pytest.mark.parametrize(
    ("branch", "slug"),
    [("feat/login", "feat-login"), ("--A__b--", "a-b"), ("x" * 60, "x" * 40), ("///", "branch")],
)
def test_new_id_slugifies_branch(branch, slug):
    assert store.new_id(CREATED, branch) == f"20261109-083012-{slug}"


def test_newest_picks_latest_matching_branch_and_status(store_root):
    store.write_new(store_root, make_handoff(), created_at=CREATED, label="main")
    newer = make_handoff(created_at="2026-11-09T10:30:12Z")
    newest_id = store.write_new(store_root, newer, created_at=LATER, label="main")
    store.write_new(store_root, make_handoff(branch="feat"), created_at=LATER, label="feat")

    found = store.newest(store_root, branch="main", status="open")

    assert found is not None
    assert found.meta["id"] == newest_id


def test_newest_returns_none_for_empty_store(store_root):
    assert store.newest(store_root, branch="main") is None


@pytest.mark.req("R6.6")
def test_newest_skips_corrupt_file_with_warning(store_root, capsys):
    hid = store.write_new(store_root, make_handoff(), created_at=CREATED, label="main")
    (store_root / "zzz-broken.md").write_text("not a handoff")

    found = store.newest(store_root, branch="main")

    assert found is not None
    assert found.meta["id"] == hid
    assert "zzz-broken.md" in capsys.readouterr().err


@pytest.mark.req("R9.3")
def test_mark_resumed_updates_meta_and_keeps_body_bytes(store_root):
    hid = store.write_new(store_root, make_handoff(), created_at=CREATED, label="main")
    path = store_root / f"{hid}.md"
    before = path.read_text().split("\n---\n", 1)[1]
    handoff = store.newest(store_root, branch="main")

    store.mark_resumed(handoff, now=LATER)
    again = store.mark_resumed(store.newest(store_root, branch="main"), now=LATER)

    assert again.meta["status"] == "resumed"
    assert again.meta["resumed_at"] == "2026-11-09T10:30:12Z"
    assert again.meta["resume_count"] == 2
    assert path.read_text().split("\n---\n", 1)[1] == before
    assert _mode(path) == 0o600


@pytest.mark.req("R1.4")
def test_lock_file_is_private(store_root):
    with store.lock(store_root):
        pass

    assert _mode(store_root / ".lock") == 0o600
