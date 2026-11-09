"""Collect facts for the Captured state: the working directory and Workspace resources (R4)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TypeVar

from agent_cairn import gh, gitio
from agent_cairn.constants import (
    MAX_CAPTURED_CHANGES,
    RECENT_COMMITS,
    RESOURCE_PIPELINE,
    RESOURCE_WORKTREE,
    SCHEMA_VERSION,
)
from agent_cairn.errors import CairnError, NotAGitRepoError
from agent_cairn.gh import PrLookup, PullRequest

T = TypeVar("T")

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

    Outside git ``is_git`` is False and the git fields are empty (R1.9). A git command that
    fails leaves its field empty and adds ``"<field>: <reason>"`` to ``errors`` (R4.8).
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
    upstream: str | None = None
    ahead: int | None = None
    behind: int | None = None
    stashes: int | None = None
    prs: tuple[PullRequest, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class OtherWorktree:
    """A one-line summary of another worktree of the same repository (R5.7)."""

    path: Path
    branch: str | None
    head: str
    changes_total: int | None
    prs: tuple[PullRequest, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class RepoState:
    """The current worktree in full, the others in summary, and the open pull requests."""

    current: WorktreeState
    others: tuple[OtherWorktree, ...]
    prs: PrLookup


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
    """Read the working directory ``cwd``; never writes to the Store (R4.2, R4.9)."""
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
    errors: list[str] = []
    upstream = _attempt(errors, "upstream", lambda: gitio.upstream(cwd))
    ahead_behind = (
        _attempt(errors, "ahead/behind", lambda: gitio.ahead_behind(cwd)) if upstream else None
    )
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
        upstream=upstream,
        ahead=ahead_behind[0] if ahead_behind else None,
        behind=ahead_behind[1] if ahead_behind else None,
        stashes=_attempt(errors, "stashes", lambda: gitio.stash_count(cwd)),
        errors=tuple(errors),
    )


def collect_repo(cwd: Path, *, use_gh: bool) -> RepoState:
    """Read the current worktree, every other non-prunable worktree, and open PRs (R4.1-R4.8)."""
    current = collect(cwd)
    if not current.is_git:
        return RepoState(current, (), PrLookup(gh.SKIPPED))
    lookup = gh.open_prs(cwd) if use_gh else PrLookup(gh.SKIPPED)
    others = tuple(
        _other(entry, lookup)
        for entry in gitio.worktrees(cwd)
        if not entry.prunable and entry.path.resolve() != current.path.resolve()
    )
    return RepoState(replace(current, prs=_prs_for(lookup, current.branch)), others, lookup)


def captured_json(repo: RepoState, resources: tuple[Resource, ...]) -> str:
    """Serialise what drift needs later: current branch, head, changed paths, resources."""
    current = repo.current
    payload = {
        "schema": SCHEMA_VERSION,
        "current": {
            "branch": current.branch,
            "head": current.head,
            "changes": [change.path for change in current.changes],
        },
        "resources": [asdict(r) for r in resources],
    }
    return json.dumps(payload)


def changes_from_json(payload: str | None) -> tuple[str, ...] | None:
    """Return the changed paths saved in the captured-json block, or None if absent."""
    try:
        changes = json.loads(payload or "")["current"]["changes"]
        return tuple(str(path) for path in changes)
    except (ValueError, TypeError, KeyError):
        return None


def to_json(repo: RepoState) -> str:
    """Render ``capture --json`` as in design §4.3."""
    current = repo.current
    worktrees = [
        {**_state_dict(current), "current": True},
        *({**asdict(other), "path": str(other.path), "current": False} for other in repo.others),
    ]
    payload = {
        "schema": SCHEMA_VERSION,
        "repo": current.repo,
        "prs_status": repo.prs.status,
        "prs_error": repo.prs.error,
        "worktrees": worktrees,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _state_dict(state: WorktreeState) -> dict[str, object]:
    data = asdict(state)
    data["path"] = str(state.path)
    return data


def _other(entry: gitio.WorktreeEntry, lookup: PrLookup) -> OtherWorktree:
    try:
        total: int | None = len(gitio.status(entry.path))
        error = None
    except CairnError as err:
        total, error = None, str(err)
    return OtherWorktree(
        entry.path, entry.branch, entry.head, total, _prs_for(lookup, entry.branch), error
    )


def _prs_for(lookup: PrLookup, branch: str | None) -> tuple[PullRequest, ...]:
    return tuple(pr for pr in lookup.prs if branch and pr.head_ref == branch)


def _attempt(errors: list[str], name: str, read: Callable[[], T]) -> T | None:
    """Run one git read; on failure record ``name: reason`` and return None (R4.8)."""
    try:
        return read()
    except CairnError as err:
        errors.append(f"{name}: {err}")
        return None


def collect_resources(project: Path, entries: list[tuple[str, str]]) -> tuple[Resource, ...]:
    """Capture each ``worktree``/``pipeline`` entry; paths are relative to ``project``."""
    checked = [(kind, path) for kind, path in entries if kind in CHECKED_RESOURCES]
    return tuple(_resource(project, kind, path) for kind, path in checked)


def resources_from_json(payload: str | None) -> tuple[Resource, ...]:
    """Read resources back from the captured-json block; a missing or bad block means none."""
    try:
        items = json.loads(payload or "").get("resources", [])
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
