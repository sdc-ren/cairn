"""The only place that writes to stdout or stderr (CODING_STANDARDS CS-2)."""

import sys

PREFIX = "cairn"


def emit(text: str) -> None:
    """Write command output to stdout."""
    print(text)


def warn(message: str) -> None:
    """Write a warning to stderr as ``cairn: warning: <message>``."""
    print(f"{PREFIX}: warning: {message}", file=sys.stderr)


def note(message: str) -> None:
    """Write an error or notice to stderr as ``cairn: <message>`` (R17.7)."""
    print(f"{PREFIX}: {message}", file=sys.stderr)


def detail(line: str) -> None:
    """Write a machine-readable line to stderr unprefixed, e.g. a violation (R5.4)."""
    print(line, file=sys.stderr)
