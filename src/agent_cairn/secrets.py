"""Detect secrets in a handoff body before it is saved (R12, design §6.2).

A finding records only the line and pattern name, never the matched value (CS-32).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}|\bgithub_pat_[A-Za-z0-9_]{60,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
)
_ASSIGNMENT = re.compile(
    r"\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)\b\s*[:=]\s*[\"']?([^\s\"']{8,})",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"^(?:<.*>|\$\{.*\}|\*{3,}.*|x{3,}.*|changeme|example.*)$", re.IGNORECASE)
ASSIGNMENT = "assignment"


@dataclass(frozen=True)
class Finding:
    """A likely secret at a 1-based line; deliberately holds no value."""

    line: int
    pattern: str


def scan(text: str) -> list[Finding]:
    """Return one finding per line and pattern; assignments count only if nothing else matched."""
    findings = []
    for number, line in enumerate(text.split("\n"), start=1):
        names = [name for name, pattern in _PATTERNS if pattern.search(line)]
        if not names and _has_real_assignment(line):
            names = [ASSIGNMENT]
        findings.extend(Finding(number, name) for name in names)
    return findings


def _has_real_assignment(line: str) -> bool:
    return any(not _PLACEHOLDER.match(m.group(1)) for m in _ASSIGNMENT.finditer(line))
