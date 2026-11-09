"""Command implementations; cli.py only parses arguments and maps errors (design §3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_cairn import (
    __version__,
    capture,
    document,
    drift,
    gitio,
    out,
    render,
    secrets,
    store,
    timeutil,
)
from agent_cairn.constants import (
    GIT_TIMEOUT_SECONDS,
    HOOK_CONTEXT_MAX_CHARS,
    HOOK_GIT_TIMEOUT_SECONDS,
    NO_GIT_LABEL,
    RULE_CREDENTIAL_PREFIX,
    SCHEMA_VERSION,
    SHORT_SHA_CHARS,
    STATUS_OPEN,
)
from agent_cairn.document import Handoff
from agent_cairn.errors import InvalidHandoffError, NotFoundError
from agent_cairn.validate import Violation, validate

if TYPE_CHECKING:
    from datetime import timedelta
    from pathlib import Path

    from agent_cairn.document import MetaValue


def save(
    cwd: Path, body: str, *, agent: str, session_id: str | None = None, task: str | None = None
) -> str:
    """Check ``body``, attach the captured state and store it as an open handoff; return its ID.

    Raises:
        InvalidHandoffError: the body breaks a rule or contains a secret; nothing is written.
    """
    _reject_invalid(body)
    project = store.project_dir(cwd)
    state = capture.collect(cwd)
    resources = capture.collect_resources(project, document.workspace_entries(body))
    now = timeutil.now_utc()
    heading = document.title(body)
    meta: dict[str, MetaValue] = {
        "schema": SCHEMA_VERSION,
        "created_at": timeutil.to_iso(now),
        "title": heading[1] if heading else "",
        "status": STATUS_OPEN,
        "repo": state.repo,
        "worktree": str(state.path),
        "branch": state.branch or "",
        "head": state.head,
        "agent": agent,
        "cairn_version": __version__,
    }
    optional = (("task", task), ("session_id", session_id))
    meta.update({key: value for key, value in optional if value})
    captured = render.captured(state, resources, captured_at=now)
    detached = f"detached-{state.head[:SHORT_SHA_CHARS]}" if state.head else NO_GIT_LABEL
    label = task or state.branch or detached
    root = store.root(cwd)
    store.record_project(root, project)
    with store.lock(root):
        hid = store.write_new(
            root, Handoff(meta, body.strip(), captured), created_at=now, label=label
        )
        store.cleanup(root, key=store.handoff_key(meta), keep=hid)
    return hid


def list_handoffs(cwd: Path, *, status: str | None, limit: int | None) -> list[Handoff]:
    """Return the project's handoffs, newest first, optionally by ``status`` and capped (R6)."""
    found = [h for h in store.handoffs(store.root(cwd)) if status in (None, h.meta.get("status"))]
    return found if limit is None else found[:limit]


def show(cwd: Path, ref: str | None = None) -> Path:
    """Return the file of the handoff ``ref`` names, or the best one for ``cwd`` (R7, R8).

    Raises:
        NotFoundError: nothing matches ``ref``, or the project has no handoff at all.
    """
    return store.path_of(_select(cwd, ref))


def resume(cwd: Path, ref: str | None = None) -> str:
    """Render the full resume text for the selected handoff and mark it resumed (R9)."""
    handoff = _select(cwd, ref)
    report = drift.compute(handoff, git_timeout=GIT_TIMEOUT_SECONDS)
    text = render.resume(handoff, report, brief=False)
    with store.lock(store.root(cwd)):
        store.mark_resumed(handoff, now=timeutil.now_utc())
    return text


def session_context(cwd: Path, *, max_age: timedelta) -> str | None:
    """Return the brief resume text a new session receives, or None; marks it resumed (R13.3).

    Every session may be a fresh worktree on a new branch, so any open handoff of the project
    qualifies; one on the current branch wins. The rest are listed so the user can switch.
    """
    root = store.root(cwd)
    now = timeutil.now_utc()
    fresh = [
        handoff
        for handoff in store.handoffs(root)
        if handoff.meta.get("status") == STATUS_OPEN
        and now - timeutil.parse_iso(str(handoff.meta.get("created_at"))) <= max_age
    ]
    if not fresh:
        return None
    chosen = _pick(fresh, gitio.current_branch(cwd))
    report = drift.compute(chosen, git_timeout=HOOK_GIT_TIMEOUT_SECONDS)
    others = [handoff for handoff in fresh if handoff is not chosen]
    text = _truncate(render.resume(chosen, report, brief=True, others=others), chosen)
    with store.lock(root):
        store.mark_resumed(chosen, now=now)
    return text


def _truncate(text: str, handoff: Handoff) -> str:
    """Keep hook context within Claude Code's limit, pointing at the full handoff (R13.5)."""
    if len(text) <= HOOK_CONTEXT_MAX_CHARS:
        return text
    marker = f"\n[truncated — run: cairn show {handoff.meta.get('id')}]"
    return text[: HOOK_CONTEXT_MAX_CHARS - len(marker)] + marker


def _select(cwd: Path, ref: str | None) -> Handoff:
    root = store.root(cwd)
    if ref:
        found = store.find(root, ref)
        if found is None:
            raise NotFoundError(f"handoff not found: {ref}")
        return found
    candidates = store.handoffs(root)
    if not candidates:
        raise NotFoundError("no handoff saved for this project yet")
    branch = gitio.current_branch(cwd)
    chosen = _pick(candidates, branch)
    if branch and chosen.meta.get("branch") != branch:
        out.warn(f"no handoff for branch {branch}; using latest in project")
    return chosen


def _pick(candidates: list[Handoff], branch: str | None) -> Handoff:
    """Return the newest candidate on ``branch`` if any, else the newest overall."""
    same = [handoff for handoff in candidates if branch and handoff.meta.get("branch") == branch]
    return (same or candidates)[0]


def _reject_invalid(body: str) -> None:
    leak_message = "remove the secret; never put credentials in a handoff (value not shown)"
    violations = validate(body) + [
        Violation(f"{RULE_CREDENTIAL_PREFIX}{finding.pattern}", leak_message, finding.line)
        for finding in secrets.scan(body)
    ]
    if violations:
        raise InvalidHandoffError(
            f"handoff rejected: {len(violations)} problem(s); fix each line below and save again",
            tuple(str(violation) for violation in violations),
        )
