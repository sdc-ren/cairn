"""Command implementations; cli.py only parses arguments and maps errors (design §3)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent_cairn import (
    __version__,
    assets,
    capture,
    document,
    drift,
    gitio,
    out,
    render,
    resolve,
    secrets,
    store,
    timeutil,
    validate,
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
    TEMPLATE_ASSET,
)
from agent_cairn.document import Handoff
from agent_cairn.errors import InvalidHandoffError, UsageError
from agent_cairn.validate import Violation

if TYPE_CHECKING:
    from datetime import datetime, timedelta
    from pathlib import Path

    from agent_cairn.capture import RepoState
    from agent_cairn.document import MetaValue

DRY_RUN_ID = "dry-run"


@dataclass(frozen=True)
class SaveOptions:
    """Flags of ``cairn save`` (R5)."""

    agent: str
    session_id: str | None = None
    task: str | None = None
    title: str | None = None
    redact: bool = False
    dry_run: bool = False
    use_gh: bool = True


@dataclass(frozen=True)
class ResumeOptions:
    """Flags of ``cairn resume`` (R9)."""

    ref: str | None = None
    peek: bool = False
    brief: bool = False
    as_json: bool = False
    any_branch: bool = False


@dataclass(frozen=True)
class ListFilter:
    """Flags of ``cairn list`` (R6)."""

    status: str | None = None
    branch: str | None = None
    limit: int | None = None


def template() -> str:
    """Return the body template agents fill in (R3)."""
    return assets.fill(TEMPLATE_ASSET).rstrip("\n")


def save(cwd: Path, body: str, options: SaveOptions) -> str:
    """Check ``body``, attach the captured state and store it as an open handoff (R5).

    Returns ``saved <id>``, or with ``dry_run`` the file that would be written.

    Raises:
        InvalidHandoffError: the body breaks a rule or contains a secret; nothing is written.
    """
    body = _prepare(body, options)
    project = store.project_dir(cwd)
    repo = capture.collect_repo(cwd, use_gh=options.use_gh)
    resources = capture.collect_resources(project, document.workspace_entries(body))
    now = timeutil.now_utc()
    meta = _meta(repo, body, options, now)
    handoff = Handoff(meta, body.strip(), render.captured(repo, resources, captured_at=now))
    if options.dry_run:
        return document.render(
            Handoff({"id": DRY_RUN_ID, **meta}, handoff.body, handoff.captured_md)
        )
    root = store.root(cwd)
    store.record_project(root, project)
    with store.lock(root):
        hid = store.write_new(root, handoff, created_at=now, label=_label(repo, options.task))
        _cleanup(root, key=store.handoff_key(meta), keep=hid, now=now)
    return f"saved {hid}"


def capture_report(cwd: Path, *, use_gh: bool, as_json: bool) -> str:
    """Return ``cairn capture`` output; needs a git repository (R1.7, R4)."""
    gitio.common_dir(cwd)
    repo = capture.collect_repo(cwd, use_gh=use_gh)
    return capture.to_json(repo) if as_json else "\n".join(render.repo_lines(repo))


def list_handoffs(cwd: Path, wanted: ListFilter) -> list[Handoff]:
    """Return the project's handoffs, newest first, filtered and capped (R6)."""
    found = [
        handoff
        for handoff in store.handoffs(store.root(cwd))
        if wanted.status in (None, handoff.meta.get("status"))
        and wanted.branch in (None, handoff.meta.get("branch"))
    ]
    return found if wanted.limit is None else found[: wanted.limit]


def remove(cwd: Path, refs: list[str], *, confirmed: bool) -> list[str]:
    """Delete the handoffs ``refs`` name after confirmation; return the removed IDs (R14.9).

    Raises:
        NotFoundError: a reference matches nothing or is ambiguous; nothing is deleted.
        UsageError: confirmation is needed but stdin is not a terminal.
    """
    root = store.root(cwd)
    chosen = {
        str(h.meta.get("id")): h for h in (resolve.by_ref(store.handoffs(root), r) for r in refs)
    }
    if not confirmed:
        if not sys.stdin.isatty():
            raise UsageError("refusing to delete without --yes when stdin is not a terminal")
        if out.ask(f"delete {len(chosen)} handoff(s)? [y/N]").casefold() not in ("y", "yes"):
            return []
    with store.lock(root):
        for hid, handoff in chosen.items():
            store.path_of(handoff).unlink()
            out.note(f"removed {hid} (manual)")
    return list(chosen)


def show(cwd: Path, ref: str | None, *, any_branch: bool = False) -> Path:
    """Return the file of the handoff ``ref`` names, or the best one for ``cwd`` (R7, R8)."""
    return store.path_of(_select(cwd, ref, any_branch=any_branch))


def resume(cwd: Path, options: ResumeOptions) -> str:
    """Render the selected handoff with its drift; unless ``peek``, mark it resumed (R9)."""
    handoff = _select(cwd, options.ref, any_branch=options.any_branch)
    report = drift.compute(handoff, git_timeout=GIT_TIMEOUT_SECONDS, fallback=cwd)
    if options.as_json:
        text = render.resume_json(handoff, report)
    else:
        text = render.resume(handoff, report, brief=options.brief)
    if int(handoff.meta.get("resume_count", 0)):
        out.warn(f"{handoff.meta.get('id')} was already resumed")
    if not options.peek:
        root = store.root(cwd)
        now = timeutil.now_utc()
        with store.lock(root):
            store.mark_resumed(handoff, now=now)
            _cleanup(root, key=None, keep=str(handoff.meta.get("id")), now=now)
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
    chosen = resolve.pick(fresh, gitio.current_branch(cwd))
    report = drift.compute(chosen, git_timeout=HOOK_GIT_TIMEOUT_SECONDS, fallback=cwd)
    others = [handoff for handoff in fresh if handoff is not chosen]
    text = _truncate(render.resume(chosen, report, brief=True, others=others), chosen)
    with store.lock(root):
        store.mark_resumed(chosen, now=now)
        _cleanup(root, key=None, keep=str(chosen.meta.get("id")), now=now)
    return text


def _prepare(body: str, options: SaveOptions) -> str:
    """Apply ``--title`` and ``--redact``, then reject the body if a rule fails (R5.3, R12)."""
    if options.title:
        body = document.with_title(body, options.title)
    if options.redact:
        body, count = secrets.redact(body)
        if count:
            out.warn(f"redacted {count} secret value(s)")
    leak = "remove the secret; never put credentials in a handoff (value not shown)"
    violations = validate.validate(body) + [
        Violation(f"{RULE_CREDENTIAL_PREFIX}{finding.pattern}", leak, finding.line)
        for finding in secrets.scan(body)
    ]
    violations.sort(key=lambda violation: violation.line or 0)
    blocking = validate.errors(violations)
    if blocking:
        raise InvalidHandoffError(
            f"handoff rejected: {len(blocking)} problem(s); fix each line below and save again",
            tuple(str(violation) for violation in blocking),
        )
    for violation in violations:
        out.warn(str(violation))
    return body


def _meta(repo: RepoState, body: str, options: SaveOptions, now: datetime) -> dict[str, MetaValue]:
    state = repo.current
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
        "agent": options.agent,
        "cairn_version": __version__,
    }
    optional = (("task", options.task), ("session_id", options.session_id))
    meta.update({key: value for key, value in optional if value})
    return meta


def _label(repo: RepoState, task: str | None) -> str:
    state = repo.current
    detached = f"detached-{state.head[:SHORT_SHA_CHARS]}" if state.head else NO_GIT_LABEL
    return task or state.branch or detached


def _cleanup(root: Path, *, key: str | None, keep: str, now: datetime) -> None:
    store.cleanup(root, key=key, keep=keep, now=now, retention=store.retention_from_env())


def _truncate(text: str, handoff: Handoff) -> str:
    """Keep hook context within Claude Code's limit, pointing at the full handoff (R13.5)."""
    if len(text) <= HOOK_CONTEXT_MAX_CHARS:
        return text
    marker = f"\n[truncated — run: cairn show {handoff.meta.get('id')}]"
    return text[: HOOK_CONTEXT_MAX_CHARS - len(marker)] + marker


def _select(cwd: Path, ref: str | None, *, any_branch: bool) -> Handoff:
    handoffs = store.handoffs(store.root(cwd))
    branch = None if ref else gitio.current_branch(cwd)
    chosen, warning = resolve.select(handoffs, ref=ref, branch=branch, any_branch=any_branch)
    if warning:
        out.warn(warning)
    return chosen
