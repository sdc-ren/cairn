"""The only place that starts external processes (CODING_STANDARDS CS-2, R18.4)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent_cairn.errors import CairnError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass(frozen=True)
class Result:
    """Exit status and decoded output of a finished process."""

    returncode: int
    stdout: str
    stderr: str


def run(args: Sequence[str], *, cwd: Path, timeout: float, stdin: str | None = None) -> Result:
    """Run ``args`` without a shell and return its result.

    ``stdin`` is sent to the child; without it stdin is closed so a child never consumes input
    meant for cairn (hooks read JSON from it).

    Raises:
        CairnError: the executable is missing or did not finish within ``timeout`` seconds.
    """
    try:
        done = subprocess.run(
            list(args),
            cwd=cwd,
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as err:
        raise CairnError(f"{args[0]} is not installed or not on PATH") from err
    except subprocess.TimeoutExpired as err:
        raise CairnError(f"{args[0]} did not finish within {timeout:g}s") from err
    return Result(done.returncode, done.stdout, done.stderr)
