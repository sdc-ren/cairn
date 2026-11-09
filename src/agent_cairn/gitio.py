"""Every git command cairn runs, one function each (design §8)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_cairn import proc
from agent_cairn.constants import GIT_TIMEOUT_SECONDS, SHORT_SHA_CHARS
from agent_cairn.errors import CairnError, NotAGitRepoError

FIELD_SEPARATOR = "\x00"
RENAME_OR_COPY = ("R", "C")


def common_dir(cwd: Path) -> Path:
    """Return the absolute git common dir for ``cwd``.

    Raises:
        NotAGitRepoError: ``cwd`` is not inside a git working tree (R1.7).
    """
    result = _run(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if result.returncode != 0:
        raise NotAGitRepoError("not a git repository (run cairn inside a git working tree)")
    return Path(result.stdout.strip())


def toplevel(cwd: Path) -> Path:
    """Return the root of the working tree containing ``cwd``."""
    return Path(_output(cwd, "rev-parse", "--show-toplevel"))


def current_branch(cwd: Path) -> str | None:
    """Return the checked-out branch name, or None on a detached HEAD."""
    result = _run(cwd, "symbolic-ref", "-q", "--short", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def head(cwd: Path, *, timeout: float = GIT_TIMEOUT_SECONDS) -> tuple[str, str]:
    """Return (full SHA, subject) of HEAD.

    Raises:
        CairnError: the repository has no commits yet.
    """
    result = _run(cwd, "log", "-1", "--format=%H%x00%s", timeout=timeout)
    if result.returncode != 0 or not result.stdout.strip():
        raise CairnError("the repository has no commits yet; commit once before saving a handoff")
    sha, subject = result.stdout.strip().split(FIELD_SEPARATOR, 1)
    return sha, subject


def status(cwd: Path, *, timeout: float = GIT_TIMEOUT_SECONDS) -> list[tuple[str, str]]:
    """Return (porcelain XY code, path) for each uncommitted change, renames by new path."""
    records = _output(
        cwd, "status", "--porcelain=v1", "-z", "--untracked-files=normal", timeout=timeout
    )
    changes = []
    skip_next = False
    for record in records.split(FIELD_SEPARATOR):
        if skip_next or not record:
            skip_next = False
            continue
        xy, path = record[:2], record[3:]
        skip_next = xy[0] in RENAME_OR_COPY  # the next record is the old path
        changes.append((xy, path))
    return changes


def recent_commits(cwd: Path, limit: int) -> list[tuple[str, str]]:
    """Return (short SHA, subject) of the last ``limit`` commits, newest first."""
    return _commits(_output(cwd, "log", f"-{limit}", "--format=%h%x00%s"))


def commit_exists(cwd: Path, sha: str, *, timeout: float) -> bool:
    """Return whether ``sha`` names a commit in the repository."""
    return _run(cwd, "cat-file", "-e", f"{sha}^{{commit}}", timeout=timeout).returncode == 0


def is_ancestor(cwd: Path, older: str, newer: str, *, timeout: float) -> bool:
    """Return whether ``older`` is an ancestor of ``newer``."""
    result = _run(cwd, "merge-base", "--is-ancestor", older, newer, timeout=timeout)
    return result.returncode == 0


def commits_between(
    cwd: Path, older: str, newer: str, *, limit: int, timeout: float
) -> tuple[list[tuple[str, str]], int]:
    """Return up to ``limit`` commits of ``older..newer`` (newest first) and their total."""
    span = f"{older}..{newer}"
    listed = _output(cwd, "log", f"-{limit}", "--format=%h%x00%s", span, timeout=timeout)
    total = int(_output(cwd, "rev-list", "--count", span, timeout=timeout))
    return _commits(listed), total


def merge_base(cwd: Path, first: str, second: str, *, timeout: float) -> str | None:
    """Return the merge base of two commits, or None if they share no history."""
    result = _run(cwd, "merge-base", first, second, timeout=timeout)
    return result.stdout.strip() if result.returncode == 0 else None


@dataclass(frozen=True)
class WorktreeEntry:
    """One entry of ``git worktree list --porcelain``."""

    path: Path
    head: str
    branch: str | None
    prunable: bool


def worktrees(cwd: Path) -> list[WorktreeEntry]:
    """Return every worktree of the repository at ``cwd``, main worktree first (R4.1)."""
    entries = []
    for block in _output(cwd, "worktree", "list", "--porcelain").split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines() if line)
        if "worktree" in fields:
            branch = fields.get("branch", "").removeprefix("refs/heads/") or None
            prunable = "prunable" in fields
            entries.append(
                WorktreeEntry(Path(fields["worktree"]), fields.get("HEAD", ""), branch, prunable)
            )
    return entries


def upstream(cwd: Path) -> str | None:
    """Return the upstream of the current branch, such as ``origin/main``, or None."""
    result = _run(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    return result.stdout.strip() if result.returncode == 0 else None


def ahead_behind(cwd: Path) -> tuple[int, int]:
    """Return (ahead, behind) of HEAD relative to its upstream."""
    behind, ahead = _output(cwd, "rev-list", "--left-right", "--count", "@{u}...HEAD").split()
    return int(ahead), int(behind)


def stash_count(cwd: Path) -> int:
    """Return the number of stash entries."""
    return len(_output(cwd, "stash", "list", "--format=%H").splitlines())


def branch_tip(cwd: Path, branch: str, *, timeout: float = GIT_TIMEOUT_SECONDS) -> str | None:
    """Return the commit ``refs/heads/<branch>`` points to, or None if it does not exist."""
    result = _run(cwd, "rev-parse", "--verify", "-q", f"refs/heads/{branch}", timeout=timeout)
    return result.stdout.strip() if result.returncode == 0 else None


def version(cwd: Path) -> tuple[int, ...]:
    """Return git's version as numbers, such as ``(2, 39, 5)`` (R18.3)."""
    # "git version 2.39.5 (Apple Git-154)": the third word holds the number
    words = _output(cwd, "--version").split()[2:3]
    numbers = words[0].split(".") if words else []
    return tuple(int(part) for part in numbers if part.isdigit())


def _commits(text: str) -> list[tuple[str, str]]:
    pairs = (line.split(FIELD_SEPARATOR, 1) for line in text.splitlines())
    return [(sha[:SHORT_SHA_CHARS], subject) for sha, subject in pairs]  # %h grows in big repos


def _run(cwd: Path, *args: str, timeout: float = GIT_TIMEOUT_SECONDS) -> proc.Result:
    return proc.run(["git", *args], cwd=cwd, timeout=timeout)


def _output(cwd: Path, *args: str, timeout: float = GIT_TIMEOUT_SECONDS) -> str:
    result = _run(cwd, *args, timeout=timeout)
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[:1] or ["no error output"]
        raise CairnError(f"git {args[0]} failed: {detail[0]}")
    return result.stdout.rstrip("\n")
