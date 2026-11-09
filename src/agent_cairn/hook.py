"""Claude Code hook entry points; a hook never fails or slows the session (R13, design §5.5)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from agent_cairn import commands, out, timeutil
from agent_cairn.constants import (
    HOOK_ENV,
    HOOK_EVENT_NAME,
    HOOK_MAX_AGE_DEFAULT,
    HOOK_MAX_AGE_ENV,
    OFF,
)


def session_start() -> int:
    """Inject the project's open handoff as ``additionalContext``; always exit 0."""
    if os.environ.get(HOOK_ENV) == OFF:
        return 0
    try:
        max_age = timeutil.parse_duration(os.environ.get(HOOK_MAX_AGE_ENV, HOOK_MAX_AGE_DEFAULT))
        context = commands.session_context(_event_cwd(), max_age=max_age)
        if context is not None:
            payload = {"hookEventName": HOOK_EVENT_NAME, "additionalContext": context}
            out.emit(json.dumps({"hookSpecificOutput": payload}))
    except Exception as err:  # the one guard besides cli.main (CS-28): never break a session
        out.warn(f"hook: {err}")
    return 0


def _event_cwd() -> Path:
    """Return ``cwd`` from the hook event on stdin (R13.1), else the process directory."""
    raw = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        event = None
    cwd = event.get("cwd") if isinstance(event, dict) else None
    return Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
