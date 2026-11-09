"""Time formatting; the only module allowed to read the clock (CODING_STANDARDS CS-2)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_DURATION = re.compile(r"^(\d+)([dhm])$")
_DURATION_UNITS = {"d": "days", "h": "hours", "m": "minutes"}


def to_iso(moment: datetime) -> str:
    """Format ``moment`` as ISO 8601 UTC with a ``Z`` suffix, e.g. ``2026-11-09T08:30:12Z``."""
    return moment.astimezone(timezone.utc).strftime(ISO_FORMAT)


def now_utc() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc)


def parse_iso(text: str) -> datetime:
    """Parse an ISO 8601 UTC timestamp written by ``to_iso``."""
    return datetime.strptime(text, ISO_FORMAT).replace(tzinfo=timezone.utc)


def parse_duration(text: str) -> timedelta:
    """Parse ``<n>d``, ``<n>h`` or ``<n>m`` into a timedelta.

    Raises:
        ValueError: ``text`` is not in that form.
    """
    match = _DURATION.match(text.strip())
    if match is None:
        raise ValueError(f"invalid duration {text!r}; use e.g. 7d, 12h or 30m")
    return timedelta(**{_DURATION_UNITS[match.group(2)]: int(match.group(1))})


def age(then: datetime, now: datetime) -> str:
    """Return a short age such as ``just now``, ``5m ago``, ``2h ago`` or ``3d ago`` (R6.1)."""
    minutes = int((now - then).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    for unit, size in (("d", 60 * 24), ("h", 60)):
        if minutes >= size:
            return f"{minutes // size}{unit} ago"
    return f"{minutes}m ago"
