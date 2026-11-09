"""Claude Code hook entry points; a hook never fails or slows the session (R13, R23).

Each hook runs inside ``_guarded``: any error becomes a warning on stderr and exit code 0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable

from agent_cairn import assets, commands, out, store, timeutil
from agent_cairn.constants import (
    HOOK_ENV,
    HOOK_EVENT_NAME,
    HOOK_MAX_AGE_DEFAULT,
    HOOK_MAX_AGE_ENV,
    NUDGE_ASSET,
    NUDGE_ENV,
    NUDGE_WINDOW_DEFAULT,
    NUDGE_WINDOW_ENV,
    OFF,
    PRECOMPACT_ASSET,
)

SESSION_START = "session-start"
PRE_COMPACT = "pre-compact"
POST_COMPACT = "post-compact"
EVENTS = (SESSION_START, PRE_COMPACT, POST_COMPACT)


def run(event: str) -> int:
    """Run the hook for ``event``; always returns 0."""
    handlers: dict[str, tuple[str, Callable[[], None]]] = {
        SESSION_START: (HOOK_ENV, _session_start),
        PRE_COMPACT: (NUDGE_ENV, _pre_compact),
        POST_COMPACT: (NUDGE_ENV, _post_compact),
    }
    switch, handler = handlers[event]
    if os.environ.get(switch) != OFF:
        _guarded(handler)
    return 0


def _guarded(handler: Callable[[], None]) -> None:
    try:
        handler()
    except Exception as err:  # the one guard besides cli.main (CS-28): never break a session
        out.warn(f"hook: {err}")


def _session_start() -> None:
    """Inject the project's open handoff as ``additionalContext`` (R13.3)."""
    max_age = timeutil.parse_duration(os.environ.get(HOOK_MAX_AGE_ENV, HOOK_MAX_AGE_DEFAULT))
    context = commands.session_context(_event_cwd(), max_age=max_age)
    if context is not None:
        _emit_context(context)


def _pre_compact() -> None:
    """Print summary instructions; Claude Code uses PreCompact stdout for them (R23.2)."""
    _event_cwd()  # drain stdin so Claude Code never blocks on a full pipe
    out.emit(assets.fill(PRECOMPACT_ASSET).rstrip("\n"))


def _post_compact() -> None:
    """Show the user a one-line reminder when no handoff was saved recently (R23.5).

    ``systemMessage`` reaches the user at once; ``additionalContext`` would wait for the
    agent's next reply, which after ``/compact`` may never come before the session ends.
    """
    root = store.root(_event_cwd())
    text = os.environ.get(NUDGE_WINDOW_ENV, NUDGE_WINDOW_DEFAULT)
    window = timeutil.parse_duration(text)
    latest = store.newest(root)
    now = timeutil.now_utc()
    if latest and now - timeutil.parse_iso(str(latest.meta.get("created_at"))) <= window:
        return
    out.emit(json.dumps({"systemMessage": assets.fill(NUDGE_ASSET, window=text).rstrip("\n")}))


def _emit_context(context: str) -> None:
    payload = {"hookEventName": HOOK_EVENT_NAME, "additionalContext": context}
    out.emit(json.dumps({"hookSpecificOutput": payload}))


def _event_cwd() -> Path:
    """Return ``cwd`` from the hook event on stdin (R13.1), else the process directory."""
    raw = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        event = None
    cwd = event.get("cwd") if isinstance(event, dict) else None
    return Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
