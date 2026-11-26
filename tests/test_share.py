import io
import tarfile

import pytest
from conftest import FILLED_BODY, bare_remote, commit, git

from agent_cairn import document, portable, store
from agent_cairn.cli import main

BODY = FILLED_BODY.replace(
    "## Key files\n- app/api/auth/callback/route.ts",
    "## Key files\n- app.txt\n- notes/plan.md\n- ~/.claude/secret.json\n\n"
    "## Workspace\n- pipeline: .pipeline/T-1",
)


@pytest.fixture
def project(git_repo):
    (git_repo / "app.txt").write_text("a\n")
    git(git_repo, "add", ".")
    commit(git_repo, "initial")
    bare_remote(git_repo)
    (git_repo / ".git" / "info" / "exclude").write_text(".pipeline\nnotes\n")
    (git_repo / ".pipeline" / "T-1").mkdir(parents=True)
    (git_repo / ".pipeline" / "T-1" / "ticket.md").write_text(f"see {git_repo}/app.txt\n")
    (git_repo / "notes").mkdir()
    (git_repo / "notes" / "plan.md").write_text("plan\n")
    (git_repo / "app.txt").write_text("a\nchanged\n")
    return git_repo


def _save(monkeypatch, body=BODY):
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    assert main(["save", "--no-gh", "--task", "T-1"]) == 0


def _members(bundle):
    with tarfile.open(bundle, "r:gz") as archive:
        return {m.name: archive.extractfile(m).read().decode() for m in archive.getmembers()}


@pytest.fixture
def bundle(project, monkeypatch, tmp_path):
    _save(monkeypatch)
    target = tmp_path / "t1.cairn.tgz"
    assert main(["share", "T-1", "--no-gh", "--out", str(target)]) == 0
    return target


def test_scrub_project_paths_become_relative_and_home_becomes_tilde():
    text = "/p/app/x.ts and /p/app and /p/apple and /u/me/.claude/a and /Users/other/b"

    result = portable.scrub(text, roots=["/p/app"], home="/u/me")

    assert result == "x.ts and . and /p/apple and ~/.claude/a and ~/b"


def test_public_url_drops_user_and_token():
    assert portable.public_url("https://me:tok@github.com/o/r.git") == "https://github.com/o/r.git"
    assert portable.public_url("git@github.com:o/r.git") == "git@github.com:o/r.git"
    assert portable.public_url("/Users/me/remote.git") == portable.LOCAL_REMOTE


def test_key_files_takes_the_path_of_each_line():
    body = "# t\n\n## Key files\n- `a/b.ts:42` — route\nc.md\n- ~/x.json, note\n"

    assert document.key_files(body) == ["a/b.ts", "c.md", "~/x.json"]


@pytest.mark.req("R25.1")
@pytest.mark.req("R25.3")
@pytest.mark.req("R25.4")
def test_share_bundles_patch_and_files_git_does_not_carry(bundle):
    members = _members(bundle)

    assert set(members) == {
        "HANDOFF.md",
        "attachments/.pipeline/T-1/ticket.md",
        "attachments/notes/plan.md",
        "patches/root.patch",
    }
    assert "+changed" in members["patches/root.patch"]
    assert members["attachments/.pipeline/T-1/ticket.md"] == "see app.txt\n"


@pytest.mark.req("R25.2")
def test_share_handoff_has_no_local_paths_and_lists_what_is_missing(bundle, project):
    text = _members(bundle)["HANDOFF.md"]
    handoff = document.parse(text)

    assert str(project) not in text
    assert str(project.parent) not in text
    assert "worktree" not in handoff.meta
    assert handoff.meta["status"] == "open"
    assert "(on the remote)" in text
    assert "`~/.claude/secret.json`: not found on the sender's machine" in text


@pytest.mark.req("R25.4")
def test_share_leaves_the_users_index_alone(project, monkeypatch, tmp_path):
    _save(monkeypatch)
    (project / "staged.txt").write_text("s\n")
    git(project, "add", "staged.txt")
    before = git(project, "diff", "--cached", "--name-only")

    main(["share", "T-1", "--no-gh", "--out", str(tmp_path / "b.tgz")])

    assert git(project, "diff", "--cached", "--name-only") == before


@pytest.mark.req("R25.5")
def test_share_refuses_secrets_in_attachments_unless_redacted(
    project, monkeypatch, tmp_path, capsys
):
    _save(monkeypatch)
    (project / "notes" / "plan.md").write_text("token = abcdefghijklmnop\n")
    target = tmp_path / "b.tgz"

    refused = main(["share", "T-1", "--no-gh", "--out", str(target)])
    redacted = main(["share", "T-1", "--no-gh", "--redact", "--out", str(target)])

    assert refused == 3
    assert "attachments/notes/plan.md: line 1: secret-assignment" in capsys.readouterr().err
    assert redacted == 0
    assert "abcdefghijklmnop" not in _members(target)["attachments/notes/plan.md"]


def test_share_warns_when_head_is_not_pushed(project, monkeypatch, tmp_path, capsys):
    commit(project, "local only")
    _save(monkeypatch)

    main(["share", "T-1", "--no-gh", "--out", str(tmp_path / "b.tgz")])

    assert "is not on any remote; push it" in capsys.readouterr().err


@pytest.fixture
def receiver(tmp_path, monkeypatch, project):
    clone = tmp_path / "other" / "proj"
    git(tmp_path, "clone", "-q", str(project.parent / "remote.git"), str(clone))
    monkeypatch.setenv("CAIRN_HOME", str(tmp_path / "other-home"))
    monkeypatch.chdir(clone)
    return clone


@pytest.mark.req("R25.6")
def test_import_unpacks_and_saves_an_open_handoff_with_local_paths(bundle, receiver):
    code = main(["import", str(bundle)])

    (handoff,) = store.handoffs(store.root(receiver))
    unpacked = (
        receiver / ".cairn-shared" / str(document.parse(_members(bundle)["HANDOFF.md"]).meta["id"])
    )
    assert code == 0
    assert handoff.meta["status"] == "open"
    assert handoff.meta["worktree"] == str(receiver)
    assert (unpacked / "patches" / "root.patch").is_file()
    assert (receiver / ".cairn-shared" / ".gitignore").read_text() == "*\n"
    assert git(receiver, "status", "--porcelain") == ""


@pytest.mark.req("R25.6")
def test_import_twice_is_refused(bundle, receiver):
    main(["import", str(bundle)])

    assert main(["import", str(bundle)]) == 2


@pytest.mark.req("R25.6")
def test_import_rejects_a_member_outside_the_bundle_folders(receiver, tmp_path):
    evil = tmp_path / "evil.tgz"
    with tarfile.open(evil, "w:gz") as archive:
        for name in ("HANDOFF.md", "../escape.txt"):
            info = tarfile.TarInfo(name)
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))

    assert main(["import", str(evil)]) == 3
    assert not (receiver.parent / "escape.txt").exists()
