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


# Allowed internal imports per module (design §3). Adding an edge is a design change.
ALLOWED = {
    "__init__": set(),
    "__main__": {"cli"},
    "assets": set(),
    "capture": {"constants", "errors", "gh", "gitio"},
    "cli": {
        "clipboard",
        "commands",
        "constants",
        "doctor",
        "errors",
        "gitio",
        "hook",
        "integrations",
        "out",
        "render",
        "store",
        "timeutil",
    },
    "commands": {
        "assets",
        "capture",
        "constants",
        "document",
        "drift",
        "errors",
        "gitio",
        "out",
        "render",
        "resolve",
        "secrets",
        "store",
        "timeutil",
        "validate",
    },
    "clipboard": {"constants", "errors", "proc"},
    "constants": set(),
    "doctor": {"clipboard", "constants", "errors", "gitio", "proc", "store"},
    "document": {"constants", "errors"},
    "drift": {"capture", "constants", "document", "errors", "gitio"},
    "errors": set(),
    "gh": {"constants", "errors", "proc"},
    "gitio": {"constants", "errors", "proc"},
    "hook": {"assets", "commands", "constants", "out", "store", "timeutil"},
    "integrations": {"assets", "constants"},
    "out": set(),
    "proc": {"errors"},
    "render": {"assets", "capture", "constants", "document", "timeutil"},
    "resolve": {"constants", "document", "errors"},
    "secrets": set(),
    "store": {"constants", "document", "errors", "gitio", "out", "timeutil"},
    "timeutil": set(),
    "validate": {"constants", "document"},
}
PURE_CORE = {"document", "validate", "secrets", "resolve", "render", "timeutil"}
IO_SHELL = {"proc", "gitio", "gh", "store", "out", "cli", "hook", "commands", "doctor", "clipboard"}


def _runtime_nodes(tree):
    """Yield every node except those under ``if TYPE_CHECKING:`` (type hints only)."""
    for statement in tree.body:
        is_type_block = (
            isinstance(statement, ast.If)
            and isinstance(statement.test, ast.Name)
            and statement.test.id == "TYPE_CHECKING"
        )
        if not is_type_block:
            yield from ast.walk(statement)


def _internal_imports(path):
    found = set()
    for node in _runtime_nodes(_tree(path)):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("agent_cairn")
        ):
            if node.module == "agent_cairn":
                found |= {alias.name for alias in node.names if alias.name != "__version__"}
            else:
                found.add(node.module.split(".")[1])
    return found


@pytest.mark.req("R18.1")
def test_internal_imports_follow_the_design_graph():
    graph = {path.stem: _internal_imports(path) for path in MODULES if path.parent == PACKAGE}

    unexpected = {
        name: deps - ALLOWED[name] for name, deps in graph.items() if deps - ALLOWED[name]
    }

    assert set(graph) == set(ALLOWED)
    assert unexpected == {}


def test_pure_core_never_imports_the_io_shell():
    for name in PURE_CORE:
        assert not ALLOWED[name] & IO_SHELL, name
