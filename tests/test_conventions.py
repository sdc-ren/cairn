"""CLI conventions (R17), project configuration (R18, R20), plugin generation, evaluation, speed."""

import io
import json
import re
import subprocess
import sys
import time
from datetime import timedelta

import pytest
from conftest import CREATED, FILLED_BODY, ROOT_DIR, add_worktree, commit, make_handoff

from agent_cairn import out, store
from agent_cairn.cli import main

SCRIPTS = ROOT_DIR / "scripts"
CI = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text()


def _script(name, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.req("R17.1")
def test_usage_lists_every_m1_command(capsys):
    main([])

    usage = capsys.readouterr().out
    for name in (
        "template",
        "capture",
        "save",
        "list",
        "show",
        "resume",
        "doctor",
        "hook",
        "version",
    ):
        assert re.search(rf"^\s+{name}\s", usage, re.MULTILINE), name


@pytest.mark.req("R17.2")
@pytest.mark.parametrize("command", ["save", "list", "resume", "hook"])
def test_command_help_is_specific(command, capsys):
    code = main([command, "-h"])

    assert code == 0
    assert capsys.readouterr().out.startswith(f"usage: cairn {command}")


@pytest.mark.req("R3.1")
@pytest.mark.req("R3.2")
def test_template_command_prints_template_outside_repo(outside_repo, capsys):
    code = main(["template"])

    out_text = capsys.readouterr().out
    assert code == 0
    assert out_text.startswith("# <short title of the task>")
    assert out_text.count("<!-- required:") == 3


@pytest.mark.req("R17.4")
@pytest.mark.req("R17.7")
def test_data_goes_to_stdout_and_messages_to_stderr(git_repo, monkeypatch, capsys):
    commit(git_repo)
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY.replace("## Decisions", "## X")))

    main(["save", "--no-gh"])

    captured = capsys.readouterr()
    assert captured.out.startswith("saved ")
    assert captured.err.startswith("cairn: warning: missing-recommended")


@pytest.mark.req("R17.8")
def test_warning_color_only_on_terminal_without_no_color(monkeypatch, capsys):
    monkeypatch.setattr("sys.stderr.isatty", lambda: True, raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    colored = out._colored("warning:", out.YELLOW)
    monkeypatch.setenv("NO_COLOR", "1")
    plain = out._colored("warning:", out.YELLOW)

    assert colored == "\033[33mwarning:\033[0m"
    assert plain == "warning:"


@pytest.mark.req("R17.9")
def test_times_are_stored_in_utc(git_repo, monkeypatch, clock):
    commit(git_repo)
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))

    main(["save", "--no-gh"])

    (path,) = store.root(git_repo).glob("*.md")
    assert "\ncreated_at: 2026-11-09T08:30:12Z\n" in path.read_text()


def test_broken_pipe_exits_quietly(monkeypatch, capsys):
    def broken(text):
        raise BrokenPipeError

    monkeypatch.setattr(out, "emit", broken)

    assert main(["version"]) == 0


@pytest.mark.req("R18.2")
@pytest.mark.req("R20.5")
def test_ci_runs_on_macos_and_linux_with_oldest_and_newest_python():
    assert "macos-latest" in CI
    assert "ubuntu-latest" in CI
    assert '"3.9"' in CI
    assert '"3.13"' in CI


@pytest.mark.req("R20.1")
def test_lint_target_runs_every_tool_of_the_standard():
    makefile = (ROOT_DIR / "Makefile").read_text()
    lint = makefile.split("lint:")[1].split("\n\n")[0]

    for tool in (
        "ruff check",
        "ruff format --check",
        "mypy",
        "pylint",
        "vulture",
        "check_sizes.py",
    ):
        assert tool in lint, tool
    assert "make lint" in CI or "ruff check" in CI


@pytest.mark.req("R20.4")
def test_coverage_floor_is_85_percent():
    pyproject = (ROOT_DIR / "pyproject.toml").read_text()

    assert "fail_under = 85" in pyproject
    assert "branch = true" in pyproject


@pytest.mark.req("R20.2")
def test_every_automated_m1_criterion_has_a_test():
    done = _script("req_coverage.py", "--level", "M1", "--automated-only")

    assert done.returncode == 0, done.stderr


@pytest.mark.req("R18.7")
def test_launcher_runs_source_tree_without_build_step():
    launcher = (ROOT_DIR / "bin" / "cairn").read_text()

    assert '"$root/src"' in launcher


@pytest.mark.req("R11.7")
@pytest.mark.req("R11.8")
def test_generated_plugin_files_are_up_to_date():
    done = _script("gen_plugin.py", "--check")

    assert done.returncode == 0, done.stderr


@pytest.mark.req("R22.2")
def test_skill_descriptions_lead_with_use_case_and_fit_the_limit():
    skills = json.loads((ROOT_DIR / "src/agent_cairn/assets/skills.json").read_text())

    for meta in skills.values():
        description = meta["description"]
        assert len(description) + len(meta.get("when_to_use", "")) <= 1000
        assert description.split()[0] in {"Save", "Continue"}
        assert re.search(r"[ạ-ỹđ]", description)


@pytest.mark.req("R16.6")
def test_preamble_tells_agent_to_summarise_without_the_skill():
    preamble = (ROOT_DIR / "src/agent_cairn/assets/preamble.md").read_text()

    assert "Tell the user, in the language they are using" in preamble
    assert "the exact next step you propose" in preamble


@pytest.mark.req("R16.8")
def test_resume_skill_lists_open_handoffs_to_choose_from():
    body = (ROOT_DIR / "skills/resume/SKILL.md").read_text()

    assert "cairn list --dir DIR --status open" in body
    assert "ask the user which task to continue" in body
    assert "exactly one" in body


@pytest.mark.req("R2.8")
def test_template_and_captured_state_are_english():
    template = (ROOT_DIR / "src/agent_cairn/assets/template.md").read_text()

    assert template.isascii()


@pytest.mark.req("R24.1")
def test_evaluation_scenario_and_rubric_exist():
    rubric = json.loads((ROOT_DIR / "docs/specs/eval/rubric.json").read_text())

    assert len(rubric["facts"]) >= 8
    assert rubric["threshold"] == 7
    assert (ROOT_DIR / "docs/specs/eval/scenario.md").exists()
    assert (SCRIPTS / "eval_setup.sh").stat().st_mode & 0o111


@pytest.mark.req("R24.2")
def test_eval_check_scores_body_and_ignores_template_hints(tmp_path):
    good = tmp_path / "good.md"
    good.write_text(
        "# Bulk discount\n10% off when more than 5 items. Logic in total() because of mobile.\n"
        "ROUND_HALF_UP. API rounding double-rounded. Add tests in test_cart.py, run pytest.\n"
        "Open: before or after tax?\n<!-- cairn:captured -->\ntax mobile"
    )
    hints = tmp_path / "hints.md"
    hints.write_text(
        "# T\n<!-- bulk discount mobile ROUND_HALF_UP double-round total() test_cart pytest tax -->"
    )

    passed, failed = _script("eval_check.py", good), _script("eval_check.py", hints)

    assert (passed.returncode, passed.stdout.splitlines()[0]) == (0, "8/8")
    assert (failed.returncode, failed.stdout.splitlines()[0]) == (1, "0/8")


@pytest.mark.req("R19.1")
def test_list_and_show_are_fast_with_500_handoffs(tmp_path, monkeypatch):
    root = tmp_path / "store"
    monkeypatch.setenv("CAIRN_STORE", str(root))
    for n in range(500):
        store.write_new(
            root,
            make_handoff(task=f"T-{n}"),
            created_at=CREATED + timedelta(seconds=n),
            label=f"t-{n}",
        )

    started = time.perf_counter()
    main(["list", "--dir", str(tmp_path)])
    main(["show", "--dir", str(tmp_path)])
    main(["version"])

    assert time.perf_counter() - started < 0.3 * 3


@pytest.mark.req("R19.2")
def test_save_and_resume_are_fast_with_10_worktrees(git_repo, monkeypatch, capsys):
    commit(git_repo)
    for n in range(9):
        add_worktree(git_repo, f"wt-{n}", "-b", f"b{n}")
    monkeypatch.setattr("sys.stdin", io.StringIO(FILLED_BODY))

    started = time.perf_counter()
    main(["save", "--no-gh"])
    main(["resume"])
    main(["capture", "--no-gh"])

    assert time.perf_counter() - started < 1.5 * 3


@pytest.mark.req("R18.6")
def test_package_installs_as_cairn_command_with_pipx_and_uv():
    pyproject = (ROOT_DIR / "pyproject.toml").read_text()

    assert 'name = "agent-cairn"' in pyproject
    assert 'cairn = "agent_cairn.cli:main"' in pyproject
    assert "pipx install dist/*.whl" in CI
    assert "uv tool install dist/*.whl" in CI


def test_release_workflow_publishes_with_trusted_publishing():
    release = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text()

    assert "id-token: write" in release
    assert "pypa/gh-action-pypi-publish" in release
    assert 'test "v$version" = "$GITHUB_REF_NAME"' in release
