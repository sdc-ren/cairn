"""Handoff file format: frontmatter, agent-written body, captured state (R2, design §4).

The only module that knows the frontmatter and section syntax (CODING_STANDARDS CS-2).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Union

from agent_cairn.constants import (
    CAPTURED_JSON_CLOSE,
    CAPTURED_JSON_OPEN,
    CAPTURED_MARKER,
    META_INT_KEYS,
    META_ORDER,
    WORKSPACE_SECTION,
)
from agent_cairn.errors import InvalidHandoffError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

MetaValue = Union[str, int]

FENCE = "---"
CODE_FENCE = "```"
TITLE_PREFIX = "# "
SECTION_PREFIX = "## "
_KEY_LINE = re.compile(r"^([a-z_][a-z0-9_]*):(?: (.*))?$")
# Quote values a YAML reader would misread; plain values stay readable in the file.
_NEEDS_QUOTES = re.compile(r"""^$|^\s|\s$|^["'\[{&*!|>%@`]|: | #|\n""")
_MARKER_LINE = re.compile(rf"^{re.escape(CAPTURED_MARKER)}$", re.MULTILINE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
JSON_SAFE_CLOSE = "--\\u003e"
_ENTRY = re.compile(r"^\s*[-*]\s+`?([A-Za-z][\w-]*)`?\s*:\s*(.+?)\s*$")
_JSON_LINE = re.compile(
    rf"^{re.escape(CAPTURED_JSON_OPEN)}(.*){re.escape(CAPTURED_JSON_CLOSE)}$", re.MULTILINE
)


@dataclass(frozen=True)
class Handoff:
    """A parsed handoff file."""

    meta: Mapping[str, MetaValue]
    body: str
    captured_md: str
    path: Path | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Section:
    """A ``## `` section of the body; ``line`` is the 1-based line of its heading."""

    name: str
    line: int
    text: str


def render(handoff: Handoff) -> str:
    """Render a handoff as file text: frontmatter, body, marker, captured state (R2.1)."""
    body = handoff.body.strip()
    captured = handoff.captured_md.strip()
    return f"{render_meta(handoff.meta)}{body}\n\n{CAPTURED_MARKER}\n{captured}\n"


def render_meta(meta: Mapping[str, MetaValue]) -> str:
    """Render frontmatter in the fixed key order of R2.2, unknown keys last."""
    keys = [key for key in META_ORDER if key in meta] + [k for k in meta if k not in META_ORDER]
    lines = [f"{key}: {_render_value(key, meta[key])}" for key in keys]
    return "\n".join([FENCE, *lines, FENCE]) + "\n"


def parse(text: str, source: str = "<handoff>") -> Handoff:
    """Parse handoff file text; ``source`` names the file in error messages.

    Raises:
        InvalidHandoffError: the frontmatter is missing or malformed.
    """
    meta_lines, rest = _split(text, source)
    parts = _MARKER_LINE.split(rest, maxsplit=1)
    captured = parts[1] if len(parts) > 1 else ""
    return Handoff(_parse_meta(meta_lines, source), parts[0].strip(), captured.strip())


def replace_meta(text: str, meta: Mapping[str, MetaValue]) -> str:
    """Return ``text`` with new frontmatter and everything after it byte-for-byte unchanged."""
    _, rest = _split(text, "<handoff>")
    return render_meta(meta) + rest


def title(body: str) -> tuple[int, str] | None:
    """Return (line, text) of the first ``# `` heading, or None."""
    for number, line in enumerate(body.split("\n"), start=1):
        if line.startswith(TITLE_PREFIX) or line == TITLE_PREFIX.strip():
            return number, line[len(TITLE_PREFIX) :].strip()
    return None


def sections(body: str) -> list[Section]:
    """Split the body into ``## `` sections, ignoring headings inside code fences."""
    found: list[Section] = []
    content: list[str] = []
    in_fence = False
    for number, line in enumerate(body.split("\n"), start=1):
        in_fence ^= line.lstrip().startswith(CODE_FENCE)
        if not in_fence and line.startswith(SECTION_PREFIX):
            _close(found, content)
            found.append(Section(line[len(SECTION_PREFIX) :].strip(), number, ""))
            content = []
        else:
            content.append(line)
    _close(found, content)
    return found


def with_title(body: str, text: str) -> str:
    """Return ``body`` with its ``# `` title set to ``text``, added if missing (R5.5)."""
    heading = title(body)
    lines = body.split("\n")
    if heading is None:
        return f"{TITLE_PREFIX}{text}\n\n{body}"
    lines[heading[0] - 1] = f"{TITLE_PREFIX}{text}"
    return "\n".join(lines)


def strip_comments(text: str) -> str:
    """Remove ``<!-- -->`` hints, which never count as content."""
    return _HTML_COMMENT.sub("", text)


def workspace_entries(body: str) -> list[tuple[str, str]]:
    """Return (label, value) for each ``- label: value`` line of the Workspace section (R4.10)."""
    for section in sections(body):
        if section.name.casefold() == WORKSPACE_SECTION.casefold():
            matches = (_ENTRY.match(line) for line in strip_comments(section.text).splitlines())
            return [(m.group(1).casefold(), m.group(2).strip("`")) for m in matches if m]
    return []


def captured_json_line(payload: str) -> str:
    """Wrap machine-readable captured data in an HTML comment that cannot end early."""
    safe = payload.replace("-->", JSON_SAFE_CLOSE)  # \u003e is '>' in JSON, so data is unchanged
    return f"{CAPTURED_JSON_OPEN}{safe}{CAPTURED_JSON_CLOSE}"


def captured_json(captured_md: str) -> str | None:
    """Return the JSON payload stored by ``captured_json_line``, or None if absent."""
    match = _JSON_LINE.search(captured_md)
    return match.group(1) if match else None


def without_captured_json(captured_md: str) -> str:
    """Return the captured state as people read it, without the machine-readable line."""
    return _JSON_LINE.sub("", captured_md).strip()


def _close(found: list[Section], content: list[str]) -> None:
    if found:
        last = found[-1]
        found[-1] = Section(last.name, last.line, "\n".join(content).strip())


def _split(text: str, source: str) -> tuple[list[str], str]:
    lines = text.split("\n")
    if lines[0] != FENCE or FENCE not in lines[1:]:
        raise InvalidHandoffError(f"{source}: missing frontmatter between '---' lines")
    end = lines.index(FENCE, 1)
    return lines[1:end], "\n".join(lines[end + 1 :])


def _parse_meta(lines: list[str], source: str) -> dict[str, MetaValue]:
    meta: dict[str, MetaValue] = {}
    for number, line in enumerate(lines, start=2):
        match = _KEY_LINE.match(line)
        if match is None:
            raise InvalidHandoffError(f"{source}: line {number}: expected 'key: value'")
        key, raw = match.group(1), match.group(2) or ""
        try:
            meta[key] = _parse_value(key, raw)
        except ValueError as err:
            raise InvalidHandoffError(f"{source}: line {number}: bad value for {key}") from err
    return meta


def _parse_value(key: str, raw: str) -> MetaValue:
    if raw.startswith('"'):
        value = json.loads(raw)
        if not isinstance(value, str):
            raise ValueError(raw)
        return int(value) if key in META_INT_KEYS else value
    return int(raw) if key in META_INT_KEYS else raw


def _render_value(key: str, value: MetaValue) -> str:
    if isinstance(value, int):
        return str(value)
    if key == "title" or _NEEDS_QUOTES.search(value):
        return json.dumps(value, ensure_ascii=False)
    return value
