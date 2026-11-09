"""Skills and instructions for setups without the plugin: standalone skills, AGENTS.md, prompts.

Every text comes from the same assets as the plugin skills (R21.5); this module only adapts
the Claude Code specific parts (D10).
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

from agent_cairn import __version__, assets
from agent_cairn.constants import (
    AGENTS_BEGIN,
    AGENTS_END,
    AGENTS_FILE,
    BACKUP_SUFFIX,
    CLAUDE_DIR,
    MANAGED_MARKER,
    MANAGED_PREFIX,
    SKILL_FILE,
    SKILL_NAMES,
    SKILLS_ASSET,
    SKILLS_DIR,
    STANDALONE_SKILL_PREFIX,
    TEMPLATE_ASSET,
)

FOLD_WIDTH = 96
YAML_SPECIAL = "[]:#"
# What only Claude Code understands, and what any other agent should read instead.
GENERIC_REPLACEMENTS = (
    ('"${CLAUDE_PROJECT_DIR}"', "."),
    (" --session ${CLAUDE_SESSION_ID}", ""),
    ("--agent claude-code", "--agent <your agent name>"),
    (
        "If an `ARGUMENTS:` line follows these instructions, use its text",
        "If the user gave a title, use it",
    ),
    ("If an `ARGUMENTS:` line names a task or id", "If the user named a task or id"),
)


@dataclass(frozen=True)
class Change:
    """One file action of ``cairn init``: what happens to ``path`` and why."""

    action: str
    path: Path


def skill_text(name: str, *, header: str, standalone: bool = False) -> str:
    """Return a SKILL.md for skill ``name``; ``standalone`` renames it for non-plugin installs."""
    meta = dict(_skills_meta()[name])
    if standalone:
        meta["name"] = STANDALONE_SKILL_PREFIX + name
    body = assets.fill(f"skill_{name}.md", template=_template())
    return f"{frontmatter(meta)}{header}\n{body}"


def frontmatter(meta: dict[str, str]) -> str:
    """Render skill frontmatter; the description is folded so the file stays readable."""
    lines = ["---"]
    for key, value in meta.items():
        if key == "description":
            lines.append(f"{key}: >-")
            lines += textwrap.wrap(value, FOLD_WIDTH, initial_indent="  ", subsequent_indent="  ")
        elif any(char in value for char in YAML_SPECIAL):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join([*lines, "---"]) + "\n"


def prompt(name: str) -> str:
    """Return the instructions of skill ``name`` for any agent: paste them, or put in AGENTS.md."""
    text = assets.fill(f"skill_{name}.md", template=_template())
    for claude_only, generic in GENERIC_REPLACEMENTS:
        text = text.replace(claude_only, generic)
    return text.rstrip("\n")


def skills_root(project: Path, *, global_scope: bool) -> Path:
    """Return ``~/.claude/skills`` or ``<project>/.claude/skills`` (R21.1)."""
    return (Path.home() if global_scope else project) / CLAUDE_DIR / SKILLS_DIR


def install_skills(root: Path, *, force: bool, dry_run: bool) -> list[Change]:
    """Write cairn's standalone skills under ``root``; never overwrite files cairn did not write."""
    header = MANAGED_MARKER.format(version=__version__)
    changes = []
    for name in SKILL_NAMES:
        path = root / f"{STANDALONE_SKILL_PREFIX}{name}" / SKILL_FILE
        text = skill_text(name, header=header, standalone=True)
        changes.append(_write(path, text, force=force, dry_run=dry_run))
    return changes


def install_agents_md(project: Path, *, dry_run: bool) -> Change:
    """Add or refresh cairn's block between markers in ``AGENTS.md`` (R21.2)."""
    path = project / AGENTS_FILE
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    block = f"{AGENTS_BEGIN}\n{_agents_block()}\n{AGENTS_END}"
    has_block = AGENTS_BEGIN in current
    updated = _replace_block(current, block) if has_block else _append(current, block)
    if updated == current:
        return Change("unchanged", path)
    action = "updated" if path.exists() else "created"
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return Change(f"would be {action}" if dry_run else action, path)


def uninstall(project: Path, *, global_scope: bool, dry_run: bool) -> list[Change]:
    """Remove every skill file and AGENTS.md block that carries cairn's marker (R21.4)."""
    changes = []
    root = skills_root(project, global_scope=global_scope)
    for name in SKILL_NAMES:
        path = root / f"{STANDALONE_SKILL_PREFIX}{name}" / SKILL_FILE
        if path.exists() and _managed(path.read_text(encoding="utf-8")):
            if not dry_run:
                path.unlink()
                _remove_empty_dirs(path.parent, stop=root.parent.parent)
            changes.append(Change("would remove" if dry_run else "removed", path))
    agents = project / AGENTS_FILE
    text = agents.read_text(encoding="utf-8") if agents.exists() else ""
    if AGENTS_BEGIN in text:
        changes.append(_strip_agents_block(agents, text, dry_run=dry_run))
    return changes


def _strip_agents_block(path: Path, text: str, *, dry_run: bool) -> Change:
    """Remove cairn's block; delete the file when nothing else was in it."""
    rest = _replace_block(text, "").strip("\n")
    if dry_run:
        return Change("would remove" if not rest else "would update", path)
    if rest:
        path.write_text(rest + "\n", encoding="utf-8")
        return Change("updated", path)
    path.unlink()
    return Change("removed", path)


def _remove_empty_dirs(directory: Path, *, stop: Path) -> None:
    """Remove ``directory`` and its parents while they are empty, never ``stop`` or above."""
    while directory != stop and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def _write(path: Path, text: str, *, force: bool, dry_run: bool) -> Change:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == text:
        return Change("unchanged", path)
    if current is not None and not _managed(current) and not force:
        return Change("skipped (not written by cairn; use --force)", path)
    if dry_run:
        return Change("would write", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if current is not None and not _managed(current):
        path.with_name(path.name + BACKUP_SUFFIX).write_text(current, encoding="utf-8")
    path.write_text(text, encoding="utf-8")
    return Change("written", path)


def _managed(text: str) -> bool:
    return MANAGED_PREFIX in text


def _agents_block() -> str:
    sections = [f"## cairn: {name}\n\n{prompt(name)}" for name in SKILL_NAMES]
    return "\n\n".join(["# Agent handoff with cairn", *sections])


def _replace_block(text: str, block: str) -> str:
    start = text.index(AGENTS_BEGIN)
    end = text.index(AGENTS_END, start) + len(AGENTS_END)
    return text[:start] + block + text[end:]


def _append(text: str, block: str) -> str:
    return f"{text.rstrip()}\n\n{block}\n" if text.strip() else f"{block}\n"


def _skills_meta() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = json.loads(
        (assets.ASSETS_DIR / SKILLS_ASSET).read_text(encoding="utf-8")
    )
    return data


def _template() -> str:
    return (assets.ASSETS_DIR / TEMPLATE_ASSET).read_text(encoding="utf-8")
