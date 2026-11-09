import io
import os
from pathlib import Path

import pytest
from conftest import FILLED_BODY, ROOT_DIR, commit

from agent_cairn import __version__, integrations, store
from agent_cairn.cli import main

MARKER = f"<!-- managed-by: cairn v{__version__} -->"


@pytest.fixture
def repo(git_repo):
    commit(git_repo)
    return git_repo


def _skill(root, name):
    return root / ".claude" / "skills" / f"cairn-{name}" / "SKILL.md"


@pytest.mark.req("R21.1")
@pytest.mark.req("R21.5")
def test_init_installs_standalone_skills_from_the_plugin_assets(repo, capsys):
    code = main(["init"])

    handoff = _skill(repo, "handoff").read_text()
    plugin = (ROOT_DIR / "skills" / "handoff" / "SKILL.md").read_text()
    assert code == 0
    assert "name: cairn-handoff" in handoff
    assert MARKER in handoff
    assert plugin.endswith(handoff.split(MARKER + "\n", 1)[1])
    assert capsys.readouterr().out.count("written: ") == 2


@pytest.mark.req("R21.1")
def test_init_global_writes_under_home(repo):
    main(["init", "--global"])

    assert _skill(Path.home(), "resume").exists()


@pytest.mark.req("R21.1")
def test_init_never_overwrites_foreign_file_without_force(repo, capsys):
    path = _skill(repo, "handoff")
    path.parent.mkdir(parents=True)
    path.write_text("my own skill")

    main(["init"])
    kept = path.read_text()
    main(["init", "--force"])

    assert kept == "my own skill"
    assert "skipped (not written by cairn; use --force)" in capsys.readouterr().out
    assert MARKER in path.read_text()
    assert path.with_name("SKILL.md.bak").read_text() == "my own skill"


@pytest.mark.req("R21.1")
def test_init_dry_run_writes_nothing(repo, capsys):
    main(["init", "--dry-run"])

    assert not (repo / ".claude").exists()
    assert "would write: " in capsys.readouterr().out


@pytest.mark.req("R21.2")
def test_init_agents_md_adds_then_refreshes_one_block(repo):
    (repo / "AGENTS.md").write_text("# Project rules\n\nUse tabs.\n")

    main(["init", "--agent", "agents-md"])
    main(["init", "--agent", "agents-md"])

    text = (repo / "AGENTS.md").read_text()
    assert text.startswith("# Project rules\n\nUse tabs.\n\n<!-- cairn:begin -->")
    assert text.count("<!-- cairn:begin -->") == 1
    assert "## cairn: handoff" in text
    assert "## cairn: resume" in text


@pytest.mark.req("R21.3")
@pytest.mark.req("R21.5")
@pytest.mark.parametrize("name", ["handoff", "resume"])
def test_prompt_is_the_skill_without_claude_specifics(name, capsys):
    code = main(["prompt", name])

    text = capsys.readouterr().out
    assert code == 0
    assert "CLAUDE_" not in text
    assert "ARGUMENTS" not in text
    assert "--dir ." in text or "Let `DIR` be `.`" in text


def test_prompt_handoff_embeds_template(capsys):
    main(["prompt", "handoff"])

    assert "## Next steps" in capsys.readouterr().out


@pytest.mark.req("R21.4")
def test_uninstall_removes_only_cairn_files_and_block(repo):
    main(["init"])
    main(["init", "--agent", "agents-md"])
    other = repo / ".claude" / "skills" / "mine" / "SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("keep")

    main(["init", "--uninstall"])

    assert not _skill(repo, "handoff").exists()
    assert not _skill(repo, "handoff").parent.exists()
    assert other.read_text() == "keep"
    assert "cairn:begin" not in (repo / "AGENTS.md").read_text()


def _save(monkeypatch, task):
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))
    assert main(["save", "--no-gh", "--task", task]) == 0


class _Tty(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.req("R14.9")
def test_rm_asks_and_deletes_on_yes(repo, monkeypatch, capsys):
    _save(monkeypatch, "A-1")
    monkeypatch.setattr("sys.stdin", _Tty("y\n"))

    code = main(["rm", "A-1"])

    assert code == 0
    assert list(store.root(repo).glob("*.md")) == []
    assert "delete 1 handoff(s)? [y/N]" in capsys.readouterr().err


@pytest.mark.req("R14.9")
def test_rm_keeps_everything_on_no(repo, monkeypatch):
    _save(monkeypatch, "A-1")
    monkeypatch.setattr("sys.stdin", _Tty("n\n"))

    main(["rm", "A-1"])

    assert len(list(store.root(repo).glob("*.md"))) == 1


@pytest.mark.req("R14.9")
def test_rm_without_terminal_needs_yes(repo, monkeypatch, capsys):
    _save(monkeypatch, "A-1")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    assert main(["rm", "A-1"]) == 2
    assert main(["rm", "A-1", "--yes"]) == 0
    assert list(store.root(repo).glob("*.md")) == []


@pytest.mark.req("R14.9")
def test_rm_unknown_ref_deletes_nothing(repo, monkeypatch):
    _save(monkeypatch, "A-1")

    assert main(["rm", "A-1", "NOPE-9", "--yes"]) == 4
    assert len(list(store.root(repo).glob("*.md"))) == 1


@pytest.mark.req("R9.9")
def test_resume_copy_sends_output_to_clipboard(repo, monkeypatch, capsys, tmp_path):
    _save(monkeypatch, "A-1")
    bin_dir = tmp_path / "clip"
    bin_dir.mkdir()
    sink = tmp_path / "clipboard.txt"
    tool = bin_dir / "pbcopy"
    tool.write_text(f"#!/bin/sh\ncat > {sink}\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    capsys.readouterr()

    main(["resume", "A-1", "--copy"])

    printed = capsys.readouterr().out
    assert sink.read_text() == printed.rstrip("\n")


@pytest.mark.req("R9.9")
def test_resume_copy_without_tool_warns_and_still_prints(repo, monkeypatch, capsys, no_gh):
    _save(monkeypatch, "A-1")
    capsys.readouterr()

    code = main(["resume", "A-1", "--copy"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.startswith("=== cairn handoff")
    assert "no clipboard tool found" in captured.err


def test_skill_text_matches_generated_plugin_file():
    text = integrations.skill_text("resume", header="<!-- x -->")

    assert text.split("<!-- x -->\n", 1)[1] in (ROOT_DIR / "skills/resume/SKILL.md").read_text()
