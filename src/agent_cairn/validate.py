"""Rules a handoff body must pass before it is saved (R5.3, R5.4)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from agent_cairn import document
from agent_cairn.constants import (
    CAPTURED_MARKER,
    EMPTY_PLACEHOLDERS,
    MAX_BODY_CHARS,
    NEXT_STEPS_SECTION,
    REQUIRED_SECTIONS,
    RULE_BODY_TOO_LONG,
    RULE_EMPTY_SECTION,
    RULE_MISSING_SECTION,
    RULE_MISSING_TITLE,
    RULE_NEXT_STEPS_NO_ITEMS,
    RULE_RESERVED_MARKER,
)

_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\S", re.MULTILINE)
_PLACEHOLDER_TITLE = re.compile(r"^<[^>]*>$")


@dataclass(frozen=True)
class Violation:
    """One broken rule, printed as ``line <n>: <rule>: <message>`` so an agent can fix it."""

    rule: str
    message: str
    line: int | None = None

    def __str__(self) -> str:
        """Format as R5.4; the line prefix is left out when no line applies."""
        prefix = f"line {self.line}: " if self.line else ""
        return f"{prefix}{self.rule}: {self.message}"


def validate(body: str) -> list[Violation]:
    """Return every rule ``body`` breaks; an empty list means it can be saved."""
    return [*_check_size_and_marker(body), *_check_title(body), *_check_sections(body)]


def _check_size_and_marker(body: str) -> list[Violation]:
    found = [
        Violation(RULE_RESERVED_MARKER, "remove this line; cairn reserves it", number)
        for number, line in enumerate(body.split("\n"), start=1)
        if line.strip() == CAPTURED_MARKER
    ]
    if len(body) > MAX_BODY_CHARS:
        message = (
            f"body has {len(body)} characters, limit is {MAX_BODY_CHARS}; "
            "shorten it and reference files instead of pasting them"
        )
        found.append(Violation(RULE_BODY_TOO_LONG, message))
    return found


def _check_title(body: str) -> list[Violation]:
    heading = document.title(body)
    if heading is None:
        return [Violation(RULE_MISSING_TITLE, "start the body with '# <short title>'")]
    line, text = heading
    if not text or _PLACEHOLDER_TITLE.match(text) or text.casefold() in EMPTY_PLACEHOLDERS:
        return [Violation(RULE_MISSING_TITLE, "replace the placeholder with a real title", line)]
    return []


def _check_sections(body: str) -> list[Violation]:
    by_name = {section.name.casefold(): section for section in document.sections(body)}
    found = []
    for name in REQUIRED_SECTIONS:
        section = by_name.get(name.casefold())
        if section is None:
            found.append(Violation(RULE_MISSING_SECTION, f"add a '## {name}' section"))
            continue
        content = document.strip_comments(section.text).strip()
        if not content or content.casefold() in EMPTY_PLACEHOLDERS:
            message = f"'## {name}' has no content; fill it in"
            found.append(Violation(RULE_EMPTY_SECTION, message, section.line))
        elif name == NEXT_STEPS_SECTION and not _LIST_ITEM.search(content):
            message = "write next steps as list items ('- ...' or '1. ...')"
            found.append(Violation(RULE_NEXT_STEPS_NO_ITEMS, message, section.line))
    return found
