"""Collect facts for the Captured state: the working directory and Workspace resources (R4)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from agent_cairn import gitio
from agent_cairn.constants import (
    MAX_CAPTURED_CHANGES,
    RECENT_COMMITS,
    RESOURCE_PIPELINE,
    RESOURCE_WORKTREE,
    SCHEMA_VERSION,
)
from agent_cairn.errors import CairnError, NotAGitRepoError

CHECKED_RESOURCES = (RESOURCE_WORKTREE, RESOURCE_PIPELINE)


@dataclass(frozen=True)
class Change:
    """An uncommitted path with its porcelain XY code."""

    xy: str
    path: str


@dataclass(frozen=True)
class Commit:
    """A commit by short SHA and subject."""

    sha: str
    subject: str


@dataclass(frozen=True)
class WorktreeState:
    """Facts about the working directory; paths and metadata only, never contents (R12.5).

    Outside git ``is_git`` is False and the git fields are empty (R1.9).
    """

    repo: str
    path: Path
    is_git: bool
    branch: str | None
    head: str
    head_subject: str
    changes: tuple[Change, ...]
    changes_total: int
    recent_commits: tuple[Commit, ...]


@dataclass(frozen=True)
class Resource:
    """A ``worktree`` or ``pipeline`` line of the Workspace section as found at save (R4.10)."""

    kind: str
    path: str  # as written by the agent
    location: str  # absolute
    exists: bool
    branch: str | None = None
    head: str = ""
    changes_total: int = 0


def collect(cwd: Path) -> WorktreeState:
    """Read the working directory ``cwd``; never writes to the Store (R4.9)."""
    try:
        repo = gitio.common_dir(cwd).parent.name
    except NotAGitRepoError:
        return WorktreeState(
            repo=cwd.name,
            path=cwd.resolve(),
            is_git=False,
            branch=None,
            head="",
            head_subject="",
            changes=(),
            changes_total=0,
            recent_commits=(),
        )
    sha, subject = gitio.head(cwd)
    changes = [Change(xy, path) for xy, path in gitio.status(cwd)]
    return WorktreeState(
        repo=repo,
        path=gitio.toplevel(cwd),
        is_git=True,
        branch=gitio.current_branch(cwd),
        head=sha,
        head_subject=subject,
        changes=tuple(changes[:MAX_CAPTURED_CHANGES]),
        changes_total=len(changes),
        recent_commits=tuple(Commit(*c) for c in gitio.recent_commits(cwd, RECENT_COMMITS)),
    )


def collect_resources(project: Path, entries: list[tuple[str, str]]) -> tuple[Resource, ...]:
    """Capture each ``worktree``/``pipeline`` entry; paths are relative to ``project``."""
    checked = [(kind, path) for kind, path in entries if kind in CHECKED_RESOURCES]
    return tuple(_resource(project, kind, path) for kind, path in checked)


def resources_json(resources: tuple[Resource, ...]) -> str:
    """Serialise resources for the captured-json block."""
    return json.dumps({"schema": SCHEMA_VERSION, "resources": [asdict(r) for r in resources]})


def resources_from_json(payload: str | None) -> tuple[Resource, ...]:
    """Read resources back from the captured-json block; a missing or bad block means none."""
    if not payload:
        return ()
    try:
        items = json.loads(payload).get("resources", [])
        return tuple(Resource(**item) for item in items)
    except (ValueError, TypeError, AttributeError):
        return ()


def _resource(project: Path, kind: str, written: str) -> Resource:
    location = Path(written).expanduser()
    location = location if location.is_absolute() else project / location
    if not location.is_dir():
        return Resource(kind, written, str(location), exists=False)
    if kind != RESOURCE_WORKTREE:
        return Resource(kind, written, str(location), exists=True)
    try:
        sha, _ = gitio.head(location)
        changes = len(gitio.status(location))
    except CairnError:  # not a git checkout, or no commits: keep what is known
        return Resource(kind, written, str(location), exists=True)
    branch = gitio.current_branch(location)
    return Resource(
        kind, written, str(location), exists=True, branch=branch, head=sha, changes_total=changes
    )
