"""Score a handoff against the rubric of docs/specs/eval (R24.2).

Only the body counts (text before the captured marker) and template hints in <!-- --> are
ignored. Prints ``k/n`` and the missing facts; exits 1 when ``k`` is below the threshold.
Standard library only, and independent of agent_cairn so it never grades itself.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUBRIC = ROOT / "docs" / "specs" / "eval" / "rubric.json"
MARKER = "<!-- cairn:captured -->"
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def body_of(text: str) -> str:
    """Return the agent-written part of a handoff file without HTML comments."""
    return COMMENT.sub("", text.split(MARKER, 1)[0])


def score(body: str, rubric: dict[str, object]) -> tuple[list[str], list[str]]:
    """Return (facts found, facts missing) for ``body``."""
    found, missing = [], []
    for fact in rubric["facts"]:  # type: ignore[attr-defined]
        hit = any(re.search(pattern, body) for pattern in fact["patterns"])
        (found if hit else missing).append(fact["name"])
    return found, missing


def main(argv: list[str] | None = None) -> int:
    """Print the score of a handoff file and return 1 below the threshold."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    args = parser.parse_args(argv)
    rubric = json.loads(args.rubric.read_text(encoding="utf-8"))
    found, missing = score(body_of(args.handoff.read_text(encoding="utf-8")), rubric)
    total = len(found) + len(missing)
    sys.stdout.write(f"{len(found)}/{total}\n")
    for name in missing:
        sys.stdout.write(f"missing: {name}\n")
    return 0 if len(found) >= int(rubric["threshold"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
