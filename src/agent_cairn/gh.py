"""Open pull requests from the GitHub CLI; any failure degrades to "unavailable" (R4.4, R4.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent_cairn import proc
from agent_cairn.constants import (
    GH_LIMIT,
    GH_TIMEOUT_SECONDS,
    PRS_OK,
    PRS_SKIPPED,
    PRS_UNAVAILABLE,
)
from agent_cairn.errors import CairnError

if TYPE_CHECKING:
    from pathlib import Path

OK = PRS_OK
UNAVAILABLE = PRS_UNAVAILABLE
SKIPPED = PRS_SKIPPED
FIELDS = "number,title,url,headRefName,isDraft"


@dataclass(frozen=True)
class PullRequest:
    """An open pull request; only public metadata is kept (R12.5)."""

    number: int
    title: str
    url: str
    draft: bool
    head_ref: str


@dataclass(frozen=True)
class PrLookup:
    """Result of asking ``gh`` for open pull requests."""

    status: str
    error: str | None = None
    prs: tuple[PullRequest, ...] = ()


def open_prs(cwd: Path) -> PrLookup:
    """Return open pull requests of the repository at ``cwd``; never raises."""
    args = ["gh", "pr", "list", "--state", "open", "--json", FIELDS, "--limit", str(GH_LIMIT)]
    try:
        result = proc.run(args, cwd=cwd, timeout=GH_TIMEOUT_SECONDS)
    except CairnError as err:
        return PrLookup(UNAVAILABLE, str(err))
    if result.returncode != 0:
        reason = (result.stderr.strip().splitlines() or ["gh failed"])[0]
        return PrLookup(UNAVAILABLE, reason)
    try:
        items = json.loads(result.stdout)
        prs = tuple(
            PullRequest(
                int(item["number"]),
                str(item["title"]),
                str(item["url"]),
                bool(item["isDraft"]),
                str(item["headRefName"]),
            )
            for item in items
        )
    except (ValueError, TypeError, KeyError):
        return PrLookup(UNAVAILABLE, "unexpected output from gh")
    return PrLookup(OK, None, prs)
