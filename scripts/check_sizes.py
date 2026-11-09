"""Fail when a module under src/ exceeds the line budget of CODING_STANDARDS CS-13.

Blank lines and docstrings do not count. Usage: check_sizes.py [--max-module-lines N] [paths...]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

DEFAULT_MAX = 300
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "src"


def docstring_lines(tree: ast.Module) -> set[int]:
    """Return the line numbers covered by module, class and function docstrings."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        is_docstring = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )
        if is_docstring and first.end_lineno is not None:
            lines.update(range(first.lineno, first.end_lineno + 1))
    return lines


def counted_lines(path: Path) -> int:
    """Return the number of lines that count toward the budget."""
    text = path.read_text(encoding="utf-8")
    skip = docstring_lines(ast.parse(text))
    return sum(
        1
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and number not in skip
    )


def main(argv: list[str] | None = None) -> int:
    """Print every module over budget and return 1 if there is any."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-module-lines", type=int, default=DEFAULT_MAX)
    parser.add_argument("paths", nargs="*", type=Path, default=[DEFAULT_ROOT])
    args = parser.parse_args(argv)
    too_big = [
        (path, size)
        for root in args.paths
        for path in sorted(root.rglob("*.py"))
        if (size := counted_lines(path)) > args.max_module_lines
    ]
    for path, size in too_big:
        sys.stderr.write(f"{path}: {size} lines > {args.max_module_lines}\n")
    return 1 if too_big else 0


if __name__ == "__main__":
    raise SystemExit(main())
