"""Make a handoff safe and complete for another person's machine (R25); pure functions only.

The sender's absolute paths are rewritten (project root to relative, home to ``~``) and the
captured state is rendered from what travels in the bundle: remotes, branches, commits, pull
requests, patches and attachments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent_cairn import __version__, assets
from agent_cairn.constants import (
    SHARE_DIR,
    SHARED_ASSET,
    SHARED_DROPPED_META,
    SHARED_HEADING,
    SHORT_SHA_CHARS,
    STATUS_OPEN,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from agent_cairn.document import MetaValue
    from agent_cairn.gh import PullRequest

# Any other home directory: /Users/<name>, /home/<name>.
_ANY_HOME = re.compile(r"/(?:Users|home)/[^/\s`'\")\]]+")
_URL_USERINFO = re.compile(r"^([a-z][a-z0-9+.-]*://)[^/@]+@", re.IGNORECASE)
_PATH_END = r"(?![\w.-])"
LOCAL_REMOTE = "a folder on the sender's machine (not reachable from here)"


@dataclass(frozen=True)
class SharedWorktree:
    """What the receiver needs to rebuild one worktree: where, which commit, which patch."""

    path: str  # relative to the project, "." for the project itself
    branch: str | None
    head: str
    subject: str
    remote: str | None
    pushed: bool
    changes_total: int
    patch: str | None  # file name under patches/, None without uncommitted changes
    prs: tuple[PullRequest, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Skipped:
    """A file named by the handoff that is not in the bundle, and why."""

    path: str
    reason: str


@dataclass(frozen=True)
class Contents:
    """Everything the shared captured state lists."""

    worktrees: tuple[SharedWorktree, ...]
    attachments: tuple[str, ...]
    skipped: tuple[Skipped, ...]


def scrub(text: str, *, roots: Sequence[str], home: str) -> str:
    """Rewrite the sender's absolute paths: under a project root to relative, home to ``~``.

    ``roots`` are spellings of the project directory (as given and resolved); the longest is
    replaced first so a worktree inside the project keeps its relative path.
    """
    for root in sorted({r.rstrip("/") for r in roots if r}, key=len, reverse=True):
        text = re.sub(re.escape(root) + "/", "", text)
        text = re.sub(re.escape(root) + _PATH_END, ".", text)
    if home:
        text = re.sub(re.escape(home.rstrip("/")) + r"(?=/|" + _PATH_END + ")", "~", text)
    return _ANY_HOME.sub("~", text)


def public_url(url: str) -> str:
    """Drop the user and token of a remote URL; a local folder remote is not shown at all."""
    if url.startswith(("/", "~", ".", "file:")) or re.match(r"^[A-Za-z]:[\\/]", url):
        return LOCAL_REMOTE
    return _URL_USERINFO.sub(r"\1", url)


def shared_meta(meta: Mapping[str, MetaValue], *, shared_at: str) -> dict[str, MetaValue]:
    """Return frontmatter without the sender's paths and session, open again for the receiver."""
    kept = {key: value for key, value in meta.items() if key not in SHARED_DROPPED_META}
    return {**kept, "status": STATUS_OPEN, "shared_at": shared_at}


def unpacked_dir(handoff_id: str) -> str:
    """Return where ``cairn import`` puts a bundle's files, relative to the project."""
    return f"{SHARE_DIR}/{handoff_id}"


def captured(contents: Contents, *, handoff_id: str, shared_at: str) -> str:
    """Render the captured state of a shared handoff (R25.2)."""
    return assets.fill(
        SHARED_ASSET,
        heading=SHARED_HEADING,
        shared_at=shared_at,
        version=__version__,
        id=handoff_id,
        unpacked=unpacked_dir(handoff_id),
        worktrees="\n".join(_worktree_block(w) for w in contents.worktrees),
        attachments=_files_block(contents),
    ).rstrip("\n")


def _worktree_block(worktree: SharedWorktree) -> str:
    branch = worktree.branch or "(detached)"
    pushed = "on the remote" if worktree.pushed else "not on any remote: ask the sender to push"
    lines = [
        f"### Worktree `{worktree.path}`",
        f"- Remote: {worktree.remote or 'none'}",
        f"- Branch: {branch}",
        f"- HEAD: {worktree.head[:SHORT_SHA_CHARS]} {worktree.subject} ({pushed})",
        f"- Full HEAD: {worktree.head}",
        *(f'- PR: #{pr.number} "{pr.title}" {pr.url}' for pr in worktree.prs),
    ]
    if worktree.patch:
        lines.append(
            f"- Uncommitted: {worktree.changes_total} file(s), in `patches/{worktree.patch}`"
        )
    else:
        lines.append("- Uncommitted: none")
    lines += [f"- error: {error}" for error in worktree.errors]
    return "\n".join(lines) + "\n"


def _files_block(contents: Contents) -> str:
    lines = ["### Attachments"]
    lines += [f"- `{path}`" for path in contents.attachments] or ["- none"]
    if contents.skipped:
        lines += ["", "### Not attached"]
        lines += [f"- `{item.path}`: {item.reason}" for item in contents.skipped]
    return "\n".join(lines) + "\n"
