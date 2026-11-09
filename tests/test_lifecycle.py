import io
from datetime import timedelta

import pytest
from conftest import CREATED, FILLED_BODY, commit, git

from agent_cairn import document, secrets, store
from agent_cairn.cli import main

RETENTION = store.Retention(resumed=timedelta(days=7), open=timedelta(days=30))
TOKEN = "ghp_" + "k" * 36


@pytest.fixture
def repo(git_repo, clock):
    commit(git_repo, "initial")
    return git_repo


def _save(monkeypatch, body=FILLED_BODY, *args):
    monkeypatch.setattr("sys.stdin", io.StringIO(body))
    return main(["save", "--no-gh", *args])


def _files(repo):
    root = store.root(repo)
    return sorted(root.glob("*.md")) if root.is_dir() else []


@pytest.mark.req("R14.2")
@pytest.mark.req("R14.3")
@pytest.mark.parametrize(
    ("meta", "age", "gone"),
    [
        ({"status": "resumed", "resumed_at": "2026-11-09T08:30:12Z"}, timedelta(days=7), False),
        (
            {"status": "resumed", "resumed_at": "2026-11-09T08:30:12Z"},
            timedelta(days=7, seconds=1),
            True,
        ),
        ({"status": "open"}, timedelta(days=30), False),
        ({"status": "open"}, timedelta(days=30, seconds=1), True),
        ({"status": "open", "created_at": "garbage"}, timedelta(days=99), False),
        ({"status": "other"}, timedelta(days=99), False),
    ],
)
def test_expired_respects_each_retention(meta, age, gone):
    fields = {"created_at": "2026-11-09T08:30:12Z", **meta}

    assert store.expired(fields, CREATED + age, RETENTION) is gone


@pytest.mark.req("R14.2")
def test_retention_reads_environment(monkeypatch):
    monkeypatch.setenv("CAIRN_KEEP_RESUMED", "1d")
    monkeypatch.setenv("CAIRN_KEEP_OPEN", "2h")

    assert store.retention_from_env() == store.Retention(timedelta(days=1), timedelta(hours=2))


@pytest.mark.req("R14.4")
@pytest.mark.req("R14.5")
def test_save_removes_expired_handoffs_of_other_keys(repo, monkeypatch, capsys, clock):
    _save(monkeypatch, FILLED_BODY, "--task", "OLD-1")
    clock(CREATED + timedelta(days=31))
    capsys.readouterr()

    _save(monkeypatch, FILLED_BODY, "--task", "NEW-1")

    assert [document.parse(p.read_text()).meta["task"] for p in _files(repo)] == ["NEW-1"]
    assert "(expired)" in capsys.readouterr().err


@pytest.mark.req("R14.6")
@pytest.mark.req("R5.8")
def test_save_dry_run_prints_file_and_changes_nothing(repo, monkeypatch, capsys, clock):
    _save(monkeypatch)
    before = [p.read_text() for p in _files(repo)]
    clock(CREATED + timedelta(days=60))
    capsys.readouterr()

    code = _save(monkeypatch, FILLED_BODY, "--dry-run")

    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("---\nid: dry-run\n")
    assert [p.read_text() for p in _files(repo)] == before


@pytest.mark.req("R14.7")
def test_resume_keeps_the_handoff_it_resumes_even_if_expired(repo, monkeypatch, clock):
    _save(monkeypatch)
    clock(CREATED + timedelta(days=60))

    assert main(["resume"]) == 0
    assert len(_files(repo)) == 1


@pytest.mark.req("R14.8")
def test_cleanup_never_deletes_unreadable_files(repo, monkeypatch, clock):
    _save(monkeypatch)
    broken = store.root(repo) / "20200101-000000-broken.md"
    broken.write_text("not a handoff")
    clock(CREATED + timedelta(days=365))

    _save(monkeypatch, FILLED_BODY, "--task", "X-1")

    assert broken.exists()


@pytest.mark.req("R14.4")
def test_list_and_show_never_delete(repo, monkeypatch, clock):
    _save(monkeypatch)
    clock(CREATED + timedelta(days=365))

    main(["list"])
    main(["show"])

    assert len(_files(repo)) == 1


@pytest.mark.req("R12.3")
def test_save_redact_replaces_secret_and_saves(repo, monkeypatch, capsys):
    body = FILLED_BODY.replace("Callback route exchanges the code.", f"CI token {TOKEN} here.")

    code = _save(monkeypatch, body, "--redact")

    (path,) = _files(repo)
    text = path.read_text()
    assert code == 0
    assert TOKEN not in text
    assert "CI token [REDACTED:github-token] here." in text
    assert "redacted 1 secret value(s)" in capsys.readouterr().err


@pytest.mark.req("R12.3")
def test_redact_keeps_rest_of_line_and_placeholders():
    text = f"a {TOKEN} b\npassword = hunter2hunter2 ok\npassword = <placeholder>"

    redacted, count = secrets.redact(text)

    assert count == 2
    assert redacted.splitlines() == [
        "a [REDACTED:github-token] b",
        "password = [REDACTED:assignment] ok",
        "password = <placeholder>",
    ]
    assert secrets.scan(redacted) == []


@pytest.mark.req("R5.5")
def test_save_title_option_replaces_heading(repo, monkeypatch):
    _save(monkeypatch, FILLED_BODY, "--title", "Renamed task")

    (path,) = _files(repo)
    handoff = document.parse(path.read_text())
    assert handoff.meta["title"] == "Renamed task"
    assert handoff.body.startswith("# Renamed task\n")


@pytest.mark.req("R5.3")
def test_save_prints_warnings_but_saves(repo, monkeypatch, capsys):
    body = FILLED_BODY.replace("## Decisions", "## Notes")

    code = _save(monkeypatch, body)

    assert code == 0
    assert "warning: missing-recommended: consider adding '## Decisions'" in capsys.readouterr().err


@pytest.mark.req("R5.2")
def test_save_no_input_hint_mentions_template(repo, monkeypatch, capsys):
    class Tty(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr("sys.stdin", Tty())

    assert main(["save"]) == 2
    assert "cairn template" in capsys.readouterr().err


@pytest.mark.req("R2.6")
def test_unknown_sections_are_kept(repo, monkeypatch):
    _save(monkeypatch, FILLED_BODY + "\n## Extra notes\nKeep me.\n")

    (path,) = _files(repo)
    assert "## Extra notes\nKeep me." in document.parse(path.read_text()).body


@pytest.mark.req("R20.3")
def test_git_fixture_is_real_repo(git_repo):
    assert git(git_repo, "rev-parse", "--is-inside-work-tree") == "true"
