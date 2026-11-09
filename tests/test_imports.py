"""Static checks on src/: stdlib-only imports and the single-source rules of CS-2."""

import ast
import importlib.util
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "agent_cairn"
MODULES = sorted(PACKAGE.rglob("*.py"))


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_roots(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def _is_stdlib(name):
    spec = importlib.util.find_spec(name)
    origin = spec.origin if spec else None
    return origin in (None, "built-in", "frozen") or "site-packages" not in origin


def _modules_using(predicate):
    return {path.name for path in MODULES if any(predicate(node) for node in ast.walk(_tree(path)))}


@pytest.mark.req("R18.1")
def test_src_imports_only_stdlib_and_itself():
    roots = {root for path in MODULES for root in _imported_roots(_tree(path))}

    foreign = {root for root in roots if root != "agent_cairn" and not _is_stdlib(root)}

    assert foreign == set()


@pytest.mark.req("R18.4")
def test_only_proc_imports_subprocess():
    users = {path.name for path in MODULES if "subprocess" in set(_imported_roots(_tree(path)))}

    assert users == {"proc.py"}


@pytest.mark.req("R18.4")
def test_no_shell_keyword_anywhere():
    users = _modules_using(lambda node: isinstance(node, ast.keyword) and node.arg == "shell")

    assert users == set()


def test_only_out_calls_print():
    def is_print(node):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        )

    assert _modules_using(is_print) == {"out.py"}
