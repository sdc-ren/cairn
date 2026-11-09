"""Copy text to the system clipboard with the first tool found (R9.9)."""

from __future__ import annotations

import shutil
from pathlib import Path

from agent_cairn import proc
from agent_cairn.constants import CLIPBOARD_TIMEOUT_SECONDS
from agent_cairn.errors import CairnError

TOOLS = (("pbcopy",), ("wl-copy",), ("xclip", "-selection", "clipboard"))


def available() -> str | None:
    """Return the name of the clipboard tool cairn would use, or None."""
    return next((tool[0] for tool in TOOLS if shutil.which(tool[0])), None)


def copy(text: str) -> bool:
    """Copy ``text``; return False when no tool exists or the tool fails."""
    for tool in TOOLS:
        if not shutil.which(tool[0]):
            continue
        try:
            result = proc.run(tool, cwd=Path.cwd(), timeout=CLIPBOARD_TIMEOUT_SECONDS, stdin=text)
        except CairnError:
            return False
        return result.returncode == 0
    return False
