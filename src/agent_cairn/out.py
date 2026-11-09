"""The only place that writes to stdout or stderr (CODING_STANDARDS CS-2, R17.4-R17.8)."""

import os
import sys

PREFIX = "cairn"
YELLOW = "\033[33m"
RESET = "\033[0m"


def emit(text: str) -> None:
    """Write command output to stdout."""
    print(text)


def note(message: str) -> None:
    """Write an error or notice to stderr as ``cairn: <message>`` (R17.7)."""
    print(f"{PREFIX}: {message}", file=sys.stderr)


def warn(message: str) -> None:
    """Write a warning to stderr as ``cairn: warning: <message>``."""
    print(f"{PREFIX}: {_colored('warning:', YELLOW)} {message}", file=sys.stderr)


def detail(line: str) -> None:
    """Write a machine-readable line to stderr unprefixed, e.g. a violation (R5.4)."""
    print(line, file=sys.stderr)


def _colored(text: str, color: str) -> str:
    """Color only for a terminal and only without ``NO_COLOR`` (R17.8)."""
    if os.environ.get("NO_COLOR") is not None or not sys.stderr.isatty():
        return text
    return f"{color}{text}{RESET}"
