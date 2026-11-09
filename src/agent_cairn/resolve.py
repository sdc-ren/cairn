"""Choose which handoff a command or hook acts on (R7); pure, no I/O."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_cairn.constants import MIN_ID_PREFIX
from agent_cairn.errors import NotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from agent_cairn.document import Handoff


def select(
    handoffs: Sequence[Handoff], *, ref: str | None, branch: str | None, any_branch: bool = False
) -> tuple[Handoff, str | None]:
    """Return the handoff ``ref`` names, else the best one for ``branch``, plus a warning or None.

    ``handoffs`` must be newest first. ``ref`` matches a task (any case), a full ID, or an ID
    prefix of at least four characters that is unique.

    Raises:
        NotFoundError: nothing matches, the prefix is ambiguous, or there is no handoff at all.
    """
    if ref:
        return by_ref(handoffs, ref), None
    if not handoffs:
        raise NotFoundError("no handoff saved for this project yet")
    chosen = pick(handoffs, None if any_branch else branch)
    if branch and not any_branch and chosen.meta.get("branch") != branch:
        return chosen, f"no handoff for branch {branch}; using latest in project"
    return chosen, None


def by_ref(handoffs: Sequence[Handoff], ref: str) -> Handoff:
    """Return the newest handoff matching ``ref`` by task, full ID or unique ID prefix (R7.1)."""
    wanted = ref.casefold()
    for handoff in handoffs:
        if str(handoff.meta.get("task", "")).casefold() == wanted or handoff.meta.get("id") == ref:
            return handoff
    prefixed = [h for h in handoffs if str(h.meta.get("id", "")).startswith(ref)]
    if len(ref) >= MIN_ID_PREFIX and len(prefixed) == 1:
        return prefixed[0]
    if len(ref) >= MIN_ID_PREFIX and prefixed:
        ids = tuple(str(h.meta.get("id")) for h in prefixed)
        raise NotFoundError(f"ambiguous handoff id: {ref} matches {len(ids)} handoffs", ids)
    raise NotFoundError(f"handoff not found: {ref}")


def pick(candidates: Sequence[Handoff], branch: str | None) -> Handoff:
    """Return the newest candidate on ``branch`` if any, else the newest overall."""
    same = [handoff for handoff in candidates if branch and handoff.meta.get("branch") == branch]
    return (same or candidates)[0]
