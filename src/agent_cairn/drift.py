"""What changed in the repository since a handoff was written (R10, design §5.4).

``classify`` decides from plain facts and is pure; ``compute`` only gathers those facts from git.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from agent_cairn import capture, document, gitio
from agent_cairn.capture import Commit, Resource
from agent_cairn.constants import MAX_DRIFT_COMMITS, RESOURCE_WORKTREE, SHORT_SHA_CHARS
from agent_cairn.errors import CairnError

if TYPE_CHECKING:
    from agent_cairn.document import Handoff

INFO = "info"
NO_DRIFT = "no drift: nothing changed since the handoff"
WARN = "warn"


@dataclass(frozen=True)
class Facts:
    """Git facts about the saved head versus the worktree's current HEAD."""

    worktree: str
    worktree_exists: bool
    saved: str
    target: str
    saved_exists: bool
    is_ancestor: bool
    new_commits: tuple[Commit, ...]
    new_commits_total: int
    merge_base: str | None


@dataclass(frozen=True)
class DriftLine:
    """One line of the drift report with its level, ``info`` or ``warn``."""

    level: str
    text: str


@dataclass(frozen=True)
class Drift:
    """The drift report; ``state`` is same, ahead, diverged, missing, unknown, or none (no git)."""

    state: str
    new_commits: tuple[Commit, ...]
    new_commits_total: int
    merge_base: str | None
    lines: tuple[DriftLine, ...]


def compute(handoff: Handoff, *, git_timeout: float) -> Drift:
    """Report what changed since ``handoff``: its repository, then each Workspace resource.

    Never calls ``gh``. Outside git only Workspace resources are checked (R1.9, R10.10).
    """
    main = _main_drift(handoff, git_timeout)
    resources = capture.resources_from_json(document.captured_json(handoff.captured_md))
    main_path = Path(str(handoff.meta.get("worktree", ""))).resolve()
    extra = _resource_lines(
        [r for r in resources if Path(r.location).resolve() != main_path], git_timeout
    )
    lines = [line for line in main.lines if line.text != NO_DRIFT] + extra
    return replace(main, lines=tuple(lines) or (DriftLine(INFO, NO_DRIFT),))


def _main_drift(handoff: Handoff, git_timeout: float) -> Drift:
    worktree = str(handoff.meta.get("worktree", ""))
    saved = str(handoff.meta.get("head", ""))
    if not saved:
        return Drift("none", (), 0, None, ())
    path = Path(worktree)
    if not worktree or not path.is_dir():
        return classify(_unreachable(worktree, saved))
    return classify(_facts(path, saved, git_timeout))


def _facts(path: Path, saved: str, git_timeout: float) -> Facts:
    """Gather git facts comparing ``saved`` with the current HEAD of the checkout at ``path``."""
    target, _ = gitio.head(path, timeout=git_timeout)
    exists = gitio.commit_exists(path, saved, timeout=git_timeout)
    moved = exists and saved != target
    ancestor = moved and gitio.is_ancestor(path, saved, target, timeout=git_timeout)
    commits: list[tuple[str, str]] = []
    total = 0
    if ancestor:
        commits, total = gitio.commits_between(
            path, saved, target, limit=MAX_DRIFT_COMMITS, timeout=git_timeout
        )
    diverged = moved and not ancestor
    base = gitio.merge_base(path, saved, target, timeout=git_timeout) if diverged else None
    return Facts(
        worktree=str(path),
        worktree_exists=True,
        saved=saved,
        target=target,
        saved_exists=exists,
        is_ancestor=ancestor,
        new_commits=tuple(Commit(sha, subject) for sha, subject in commits),
        new_commits_total=total,
        merge_base=base,
    )


def _resource_lines(resources: list[Resource], git_timeout: float) -> list[DriftLine]:
    lines: list[DriftLine] = []
    for resource in resources:
        label = f"{resource.kind} {resource.path}"
        if not resource.exists:
            continue  # already missing when saved; the captured state says so
        if not Path(resource.location).is_dir():
            lines.append(DriftLine(WARN, f"{label} no longer exists"))
        elif resource.kind == RESOURCE_WORKTREE and resource.head:
            lines += _worktree_lines(resource, label, git_timeout)
    return lines


def _worktree_lines(resource: Resource, label: str, git_timeout: float) -> list[DriftLine]:
    location = Path(resource.location)
    try:
        report = classify(_facts(location, resource.head, git_timeout))
        branch = gitio.current_branch(location)
    except CairnError:
        return [DriftLine(WARN, f"{label}: no longer a git checkout")]
    lines = [] if report.state == "same" else [_prefixed(line, label) for line in report.lines]
    if resource.branch and branch != resource.branch:
        now = branch or "(detached)"
        lines.insert(0, DriftLine(WARN, f"{label}: now on {now} (was {resource.branch})"))
    return lines


def _prefixed(line: DriftLine, label: str) -> DriftLine:
    """Put the resource label on headline lines; indented detail lines stay as they are."""
    return line if line.text.startswith(" ") else DriftLine(line.level, f"{label}: {line.text}")


def _unreachable(worktree: str, saved: str) -> Facts:
    """Facts for a worktree that no longer exists; nothing else can be known."""
    return Facts(
        worktree=worktree,
        worktree_exists=False,
        saved=saved,
        target="",
        saved_exists=False,
        is_ancestor=False,
        new_commits=(),
        new_commits_total=0,
        merge_base=None,
    )


def classify(facts: Facts) -> Drift:
    """Turn ``facts`` into a drift report (R10.1-R10.4, R10.8)."""
    if not facts.worktree_exists:
        text = f"worktree {facts.worktree} no longer exists; drift not computed"
        return _report("unknown", facts, [DriftLine(WARN, text)])
    if not facts.saved_exists:
        text = f"saved head {facts.saved[:SHORT_SHA_CHARS]} no longer exists"
        return _report("missing", facts, [DriftLine(WARN, text)])
    if facts.saved == facts.target:
        return _report("same", facts, [DriftLine(INFO, NO_DRIFT)])
    if facts.is_ancestor:
        return _report("ahead", facts, _new_commit_lines(facts))
    base = (
        f"merge-base {facts.merge_base[:SHORT_SHA_CHARS]}" if facts.merge_base else "no merge-base"
    )
    return _report("diverged", facts, [DriftLine(WARN, f"history diverged since handoff ({base})")])


def _new_commit_lines(facts: Facts) -> list[DriftLine]:
    lines = [DriftLine(WARN, f"{facts.new_commits_total} new commit(s) since handoff:")]
    lines += [DriftLine(INFO, f"  {c.sha} {c.subject}") for c in facts.new_commits]
    hidden = facts.new_commits_total - len(facts.new_commits)
    if hidden > 0:
        lines.append(DriftLine(INFO, f"  … and {hidden} more"))
    return lines


def _report(state: str, facts: Facts, lines: list[DriftLine]) -> Drift:
    commits = facts.new_commits if state == "ahead" else ()
    total = facts.new_commits_total if state == "ahead" else 0
    base = facts.merge_base if state == "diverged" else None
    return Drift(state, commits, total, base, tuple(lines))
