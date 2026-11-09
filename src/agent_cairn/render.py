"""Turn captured facts into the markdown stored after the captured marker (R2.7)."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from agent_cairn import __version__, assets, capture, document, timeutil
from agent_cairn.constants import (
    CAPTURED_HEADING,
    LIST_TITLE_MAX_CHARS,
    PRS_UNAVAILABLE,
    RESOURCE_WORKTREE,
    SHORT_SHA_CHARS,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from agent_cairn.capture import OtherWorktree, RepoState, Resource, WorktreeState
    from agent_cairn.document import Handoff
    from agent_cairn.drift import Drift
    from agent_cairn.gh import PullRequest

PREAMBLE_ASSET = "preamble.md"


def captured(repo: RepoState, resources: tuple[Resource, ...], *, captured_at: datetime) -> str:
    """Render the Captured state: current worktree, other worktrees, Workspace, JSON block."""
    lines = [
        CAPTURED_HEADING,
        "",
        f"Captured at {timeutil.to_iso(captured_at)} by cairn {__version__}",
        "",
        *repo_lines(repo),
    ]
    if resources:
        lines += ["", "### Workspace", *(_resource_line(r) for r in resources)]
    lines += ["", document.captured_json_line(capture.captured_json(repo, resources))]
    return "\n".join(lines)


def repo_lines(repo: RepoState) -> list[str]:
    """Render the current worktree in full and the others as a table (R4.2, R5.7)."""
    state = repo.current
    if not state.is_git:
        return [f"### Directory (current): {state.path}", "- not a git repository"]
    lines = [f"### Worktree (current): {state.path}", *_current_lines(state)]
    if repo.prs.status == PRS_UNAVAILABLE:
        lines.append(f"- PRs: unavailable ({repo.prs.error})")
    if repo.others:
        lines += [
            "",
            "### Other worktrees",
            "| Branch | Path | Uncommitted | PR |",
            "|---|---|---|---|",
        ]
        lines += [_other_row(other) for other in repo.others]
    return lines


def _current_lines(state: WorktreeState) -> list[str]:
    branch = state.branch or f"(detached at {state.head[:SHORT_SHA_CHARS]})"
    if state.upstream:
        branch += f" → {state.upstream} (ahead {state.ahead}, behind {state.behind})"
    lines = [
        f"- Branch: {branch}",
        f"- HEAD: {state.head[:SHORT_SHA_CHARS]} {state.head_subject}",
        *(f"- PR: {_pr_text(pr)}" for pr in state.prs),
    ]
    if state.stashes is not None:
        lines.append(f"- Stashes: {state.stashes}")
    lines.append(f"- Uncommitted ({state.changes_total}):")
    lines += [f"  - `{change.xy}` {change.path}" for change in state.changes]
    hidden = state.changes_total - len(state.changes)
    if hidden:
        lines.append(f"  - … and {hidden} more")
    lines.append("- Recent commits:")
    lines += [f"  - {c.sha} {c.subject}" for c in state.recent_commits]
    lines += [f"- error: {error}" for error in state.errors]
    return lines


def _other_row(other: OtherWorktree) -> str:
    branch = other.branch or f"(detached at {other.head[:SHORT_SHA_CHARS]})"
    changes = "error" if other.changes_total is None else str(other.changes_total)
    prs = ", ".join(f"#{pr.number}" for pr in other.prs) or "—"
    return f"| {branch} | {other.path} | {changes} | {prs} |"


def _pr_text(pr: PullRequest) -> str:
    draft = " (draft)" if pr.draft else ""
    return f'#{pr.number} "{pr.title}"{draft} {pr.url}'


def _resource_line(resource: Resource) -> str:
    where = f"- {resource.kind} `{resource.path}`"
    if not resource.exists:
        return f"{where}: missing"
    if resource.kind != RESOURCE_WORKTREE or not resource.head:
        return f"{where}: present"
    branch = resource.branch or "(detached)"
    head = resource.head[:SHORT_SHA_CHARS]
    return f"{where}: branch {branch}, HEAD {head}, {resource.changes_total} uncommitted"


def resume(handoff: Handoff, drift: Drift, *, brief: bool, others: Sequence[Handoff] = ()) -> str:
    """Render what a new session reads: preamble, body, drift, captured state (R9.1, R9.2).

    ``brief`` leaves out the captured state; the hook uses it to stay small. ``others`` are the
    project's other open handoffs, listed so the user can switch (R13.9).
    """
    meta = handoff.meta
    captured = "" if brief else f"\n{document.without_captured_json(handoff.captured_md)}\n"
    count = int(meta.get("resume_count", 0))
    already = (
        f"Note: already resumed {count} time(s), last {meta.get('resumed_at')}.\n" if count else ""
    )
    return assets.fill(
        PREAMBLE_ASSET,
        id=str(meta.get("id", "")),
        agent=str(meta.get("agent", "")),
        created_at=str(meta.get("created_at", "")),
        context="".join(f", {key} {meta[key]}" for key in ("task", "branch") if meta.get(key)),
        body=handoff.body,
        drift="\n".join(f"- {line.level}: {line.text}" for line in drift.lines),
        captured=captured,
        others=_others_block(others),
        already=already,
    ).rstrip("\n")


def _others_block(others: Sequence[Handoff]) -> str:
    if not others:
        return ""
    lines = ["Other open handoffs in this project (switch with /cairn:resume <task or id>):"]
    for other in others:
        name = other.meta.get("task") or other.meta.get("id")
        lines.append(f"- {name}: {other.meta.get('title', '')} ({other.meta.get('id')})")
    return "\n" + "\n".join(lines) + "\n"


def handoff_table(handoffs: Sequence[Handoff], *, now: datetime) -> str:
    """Render handoffs as aligned columns: ID, task (or branch), status, age, title (R6.1)."""
    header = ("ID", "TASK", "STATUS", "AGE", "TITLE")
    rows = [header, *(_table_row(handoff, now) for handoff in handoffs)]
    widths = [max(len(row[column]) for row in rows) for column in range(len(header) - 1)]
    return "\n".join(
        "  ".join([*(cell.ljust(width) for cell, width in zip(row, widths)), row[-1]])
        for row in rows
    )


def _table_row(handoff: Handoff, now: datetime) -> tuple[str, str, str, str, str]:
    meta = handoff.meta
    title = str(meta.get("title", ""))
    if len(title) > LIST_TITLE_MAX_CHARS:
        title = title[:LIST_TITLE_MAX_CHARS] + "…"
    created = timeutil.parse_iso(str(meta.get("created_at", "")))
    return (
        str(meta.get("id", "")),
        str(meta.get("task") or meta.get("branch") or "-"),
        str(meta.get("status", "")),
        timeutil.age(created, now),
        title,
    )


def resume_json(handoff: Handoff, drift: Drift) -> str:
    """Render ``resume --json``: the handoff and its drift report (design §4.4)."""
    payload = {
        "handoff": {
            "meta": dict(handoff.meta),
            "body": handoff.body,
            "path": str(handoff.path) if handoff.path else None,
        },
        "drift": {
            "state": drift.state,
            "new_commits": [asdict(c) for c in drift.new_commits],
            "new_commits_total": drift.new_commits_total,
            "merge_base": drift.merge_base,
            "lines": [asdict(line) for line in drift.lines],
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
