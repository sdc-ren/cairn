"""Static checks on the plugin files and the bin/cairn launcher (R11, R3, R22)."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
from conftest import FILLED_BODY

from agent_cairn import __version__
from agent_cairn.validate import validate

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "bin" / "cairn"
VIETNAMESE_TRIGGERS = {"handoff": "lưu ngữ cảnh", "resume": "làm tiếp"}


def _json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _skill(name):
    """Return (frontmatter dict, body) of a SKILL.md; folded '>-' values are joined."""
    text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    _, header, body = text.split("---\n", 2)
    meta, key = {}, None
    for line in header.splitlines():
        if line.startswith("  ") and key:
            meta[key] = f"{meta[key]} {line.strip()}".strip()
        else:
            key, _, value = line.partition(": ")
            meta[key] = "" if value == ">-" else value.strip('"')
    return meta, body


def _template():
    _, body = _skill("handoff")
    return re.search(r"```markdown\n(.*?)```", body, re.DOTALL).group(1)


def _run_launcher(*args, env=None):
    return subprocess.run(
        [str(LAUNCHER), *args], capture_output=True, text=True, env=env, check=False
    )


@pytest.mark.req("R11.1")
def test_marketplace_lists_exactly_this_plugin_at_root():
    marketplace = _json(".claude-plugin/marketplace.json")

    assert marketplace["name"] == "cairn"
    assert [(p["name"], p["source"]) for p in marketplace["plugins"]] == [("cairn", "./")]


@pytest.mark.req("R11.1")
def test_plugin_manifest_name_and_version_match_package():
    manifest = _json(".claude-plugin/plugin.json")

    assert (manifest["name"], manifest["version"]) == ("cairn", __version__)


@pytest.mark.req("R11.6")
@pytest.mark.req("R13.2")
def test_hooks_register_session_start_in_exec_form():
    hooks = _json("hooks/hooks.json")["hooks"]

    (entry,) = hooks["SessionStart"]
    (handler,) = entry["hooks"]
    assert entry["matcher"] == "startup|clear"
    assert handler["command"] == "${CLAUDE_PLUGIN_ROOT}/bin/cairn"
    assert handler["args"] == ["hook", "session-start"]


@pytest.mark.req("R11.9")
def test_plugin_ships_no_settings_file():
    assert not (ROOT / "settings.json").exists()


@pytest.mark.req("R11.5")
@pytest.mark.req("R22.1")
@pytest.mark.parametrize("name", ["handoff", "resume"])
def test_skill_frontmatter_is_complete_and_user_invocable(name):
    meta, body = _skill(name)

    assert meta["name"] == name
    assert len(meta["description"]) <= 1000
    assert VIETNAMESE_TRIGGERS[name] in meta["description"]
    assert meta.get("disable-model-invocation") != "true"
    assert body.strip()


@pytest.mark.req("R16.1")
def test_handoff_skill_saves_in_one_command_allowed_without_prompt():
    meta, body = _skill("handoff")

    assert meta["allowed-tools"] == "Bash(cairn save *)"
    assert 'cairn save --dir "${CLAUDE_PROJECT_DIR}" --agent claude-code' in body
    assert "--session ${CLAUDE_SESSION_ID}" in body
    assert "<<'CAIRN_EOF'" in body


@pytest.mark.req("R16.2")
@pytest.mark.req("R16.3")
def test_handoff_skill_bounds_retries_and_reply():
    _, body = _skill("handoff")

    assert "Stop after 3 attempts" in body
    assert "at most 2 lines" in body


@pytest.mark.req("R22.3")
def test_handoff_skill_writes_english_and_replies_in_user_language():
    _, body = _skill("handoff")

    assert "Write the handoff in English" in body
    assert "Reply to the user in the language they are using" in body


@pytest.mark.req("R3.1")
@pytest.mark.req("R3.2")
def test_template_has_required_and_recommended_sections_with_hints():
    template = _template()

    headings = re.findall(r"^## (.+)$", template, re.MULTILINE)
    assert headings == [
        "Goal",
        "Current state",
        "Next steps",
        "Decisions",
        "Tried / didn't work",
        "Open questions",
        "Key files",
        "Workspace",
    ]
    assert template.count("<!-- required:") == 3
    assert template.count("<!--") == 8


@pytest.mark.req("R3.3")
def test_untouched_template_is_rejected_and_filled_one_passes():
    assert validate(_template()) != []
    assert validate(FILLED_BODY) == []


@pytest.mark.req("R11.3")
def test_launcher_runs_bundled_package(tmp_path):
    done = _run_launcher("version")

    assert (done.returncode, done.stdout) == (0, f"cairn {__version__}\n")


@pytest.mark.req("R11.3")
def test_launcher_ignores_user_pythonpath(tmp_path):
    shadow = tmp_path / "agent_cairn"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("raise SystemExit('shadowed')")
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}

    assert _run_launcher("version", env=env).stdout == f"cairn {__version__}\n"


@pytest.mark.req("R11.4")
def test_launcher_rejects_old_python(tmp_path):
    old_python = tmp_path / "python3.8"
    old_python.write_text("#!/bin/sh\nexit 1\n")  # stands in for a Python < 3.9
    old_python.chmod(0o755)
    env = {**os.environ, "CAIRN_PYTHON": str(old_python)}

    done = _run_launcher("version", env=env)

    assert done.returncode == 1
    assert done.stderr == "cairn: python3 >= 3.9 is required\n"
