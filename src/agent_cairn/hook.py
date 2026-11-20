"""Claude Code hook entry points; a hook never fails or slows the session (R13, R23).

Each hook runs inside ``_guarded``: any error becomes a warning on stderr and exit code 0.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
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
    PROMPT_EVENT_NAME,
)

SESSION_START = "session-start"
PRE_COMPACT = "pre-compact"
PROMPT_SUBMIT = "prompt-submit"
POST_COMPACT = "post-compact"
EVENTS = (SESSION_START, PROMPT_SUBMIT, PRE_COMPACT, POST_COMPACT)


def run(event: str) -> int:
    """Run the hook for ``event``; always returns 0."""
    handlers: dict[str, tuple[str, Callable[[], None]]] = {
        SESSION_START: (HOOK_ENV, _session_start),
        PROMPT_SUBMIT: (HOOK_ENV, _prompt_submit),
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
    """List open handoffs, or load the newest after /clear or when just saved (R13.3, R13.10)."""
    event = _event()
    source = str(event.get("source", ""))
    context = commands.session_context(_cwd(event), max_age=_max_age(), source=source)
    if context is not None:
        _emit_context(context, HOOK_EVENT_NAME)


def _prompt_submit() -> None:
    """Load the open handoff the user's message names, once (R13.11)."""
    event = _event()
    prompt = event.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return
    context = commands.prompt_context(_cwd(event), prompt=prompt, max_age=_max_age())
    if context is not None:
        _emit_context(context, PROMPT_EVENT_NAME)


def _max_age() -> timedelta:
    return timeutil.parse_duration(os.environ.get(HOOK_MAX_AGE_ENV, HOOK_MAX_AGE_DEFAULT))


def _pre_compact() -> None:
    """Print summary instructions; Claude Code uses PreCompact stdout for them (R23.2)."""
    _event()  # drain stdin so Claude Code never blocks on a full pipe
    out.emit(assets.fill(PRECOMPACT_ASSET).rstrip("\n"))


def _post_compact() -> None:
    """Show the user a one-line reminder when no handoff was saved recently (R23.5).

    ``systemMessage`` reaches the user at once; ``additionalContext`` would wait for the
    agent's next reply, which after ``/compact`` may never come before the session ends.
    """
    root = store.root(_cwd(_event()))
    text = os.environ.get(NUDGE_WINDOW_ENV, NUDGE_WINDOW_DEFAULT)
    window = timeutil.parse_duration(text)
    latest = store.newest(root)
    now = timeutil.now_utc()
    if latest and now - timeutil.parse_iso(str(latest.meta.get("created_at"))) <= window:
        return
    out.emit(json.dumps({"systemMessage": assets.fill(NUDGE_ASSET, window=text).rstrip("\n")}))


def _emit_context(context: str, event_name: str) -> None:
    payload = {"hookEventName": event_name, "additionalContext": context}
    out.emit(json.dumps({"hookSpecificOutput": payload}))


def _event() -> dict[str, object]:
    """Return the hook event JSON from stdin (R13.1); anything unreadable counts as empty."""
    raw = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        return {}
    return event if isinstance(event, dict) else {}


def _cwd(event: dict[str, object]) -> Path:
    """Return ``cwd`` from the event, else the process directory."""
    cwd = event.get("cwd")
    return Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
