"""List requirement criteria of a level that no test and no manual evidence covers (R20.2).

A criterion is covered by ``@pytest.mark.req("Rn.m")`` in tests/, or, when it is marked
``[manual]``, by its ID appearing in docs/specs/verification.md. Exit 1 if any is missing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "docs" / "specs" / "requirements.md"
VERIFICATION = ROOT / "docs" / "specs" / "verification.md"
TESTS = ROOT / "tests"
HEADING = re.compile(r"^### (R\d+)\. .*?(?:`\[(M\d)\]`)?\s*$")
CRITERION = re.compile(r"^(\d+)\. ")
LEVEL_TAG = re.compile(r"`\[(M\d)\]`")
MARKER = re.compile(r"""req\(\s*["'](R\d+\.\d+)["']\s*\)""")
ID = re.compile(r"R\d+\.\d+")
PENDING = "| Chờ |"


def criteria(text: str) -> dict[str, tuple[str, bool]]:
    """Return ``{"Rn.m": (level, manual)}``; a criterion's own tag overrides its heading."""
    found: dict[str, tuple[str, bool]] = {}
    group, group_level = None, None
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            group, group_level = heading.group(1), heading.group(2)
            continue
        if line.startswith("## "):
            group = None
        number = CRITERION.match(line)
        if group and number:
            tags = LEVEL_TAG.findall(line)
            level = tags[-1] if tags else group_level
            manual = line.rstrip().endswith("`[manual]`")
            found[f"{group}.{number.group(1)}"] = (level or "", manual)
    return found


def manual_evidence(text: str) -> set[str]:
    """Return IDs cited in verification.md, ignoring rows still marked as pending ("Chờ")."""
    return {rid for line in text.splitlines() if PENDING not in line for rid in ID.findall(line)}


def tested() -> set[str]:
    """Return every requirement ID used in a ``req`` marker under tests/."""
    return {m for path in TESTS.rglob("*.py") for m in MARKER.findall(path.read_text())}


def main(argv: list[str] | None = None) -> int:
    """Print uncovered criteria of ``--level`` and return 1 if there is any."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", default="M1")
    parser.add_argument("--allow-missing", action="store_true", help="report but exit 0")
    parser.add_argument(
        "--automated-only", action="store_true", help="skip [manual] criteria (checked by hand)"
    )
    args = parser.parse_args(argv)
    evidence = manual_evidence(VERIFICATION.read_text()) if VERIFICATION.exists() else set()
    covered = tested()
    missing = [
        rid
        for rid, (level, manual) in criteria(REQUIREMENTS.read_text()).items()
        if level == args.level
        and not (manual and args.automated_only)
        and rid not in (evidence if manual else covered)
    ]
    for rid in missing:
        sys.stderr.write(f"not covered: {rid}\n")
    sys.stderr.write(f"{len(missing)} {args.level} criteria not covered\n")
    return 1 if missing and not args.allow_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
