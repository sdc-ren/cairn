"""Environment checks for ``cairn doctor`` (R15)."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from agent_cairn import __version__, clipboard, gitio, proc, store
from agent_cairn.constants import GH_TIMEOUT_SECONDS, MIN_GIT_VERSION, MIN_PYTHON
from agent_cairn.errors import CairnError, NotAGitRepoError

OK = "ok"
WARN = "warn"
FAIL = "fail"
PLUGIN_MANIFEST = Path(__file__).resolve().parents[2] / ".claude-plugin" / "plugin.json"


@dataclass(frozen=True)
class Check:
    """One line of the report: level (ok, warn, fail), what was checked, and the finding."""

    level: str
    name: str
    detail: str


def run(cwd: Path) -> list[Check]:
    """Run every check for ``cwd``; none raises."""
    checks = [_python(), _git(cwd), _repository(cwd), _store(cwd), _gh(cwd), _plugin()]
    return [*checks, _clipboard(), _command()]


def _clipboard() -> Check:
    tool = clipboard.available()
    if tool:
        return Check(OK, "clipboard", tool)
    return Check(WARN, "clipboard", "no pbcopy, wl-copy or xclip; resume --copy only prints")


def _command() -> Check:
    found = shutil.which("cairn")
    if found:
        return Check(OK, "command", found)
    return Check(WARN, "command", "cairn is not on PATH; `pipx install agent-cairn` adds it")


def _python() -> Check:
    found = ".".join(str(part) for part in sys.version_info[:3])
    level = OK if sys.version_info[:2] >= MIN_PYTHON else FAIL
    return Check(level, "python", found)


def _git(cwd: Path) -> Check:
    try:
        found = gitio.version(cwd)
    except CairnError as err:
        return Check(FAIL, "git", str(err))
    shown = ".".join(str(part) for part in found)
    if found >= MIN_GIT_VERSION:
        return Check(OK, "git", shown)
    needed = ".".join(str(part) for part in MIN_GIT_VERSION)
    return Check(FAIL, "git", f"{shown}; {needed} or newer is required")


def _repository(cwd: Path) -> Check:
    try:
        return Check(OK, "repository", str(gitio.common_dir(cwd).parent))
    except NotAGitRepoError:
        return Check(WARN, "repository", "not a git repository; only Workspace drift is checked")


def _store(cwd: Path) -> Check:
    root = store.root(cwd)
    try:
        with store.lock(root):
            return Check(OK, "store", str(root))
    except OSError as err:
        return Check(FAIL, "store", f"{root}: {err.strerror}")


def _gh(cwd: Path) -> Check:
    try:
        result = proc.run(["gh", "auth", "status"], cwd=cwd, timeout=GH_TIMEOUT_SECONDS)
    except CairnError:
        return Check(WARN, "gh", "not installed; pull requests are not captured")
    if result.returncode != 0:
        return Check(WARN, "gh", "not logged in; run `gh auth login` to capture pull requests")
    return Check(OK, "gh", "logged in")


def _plugin() -> Check:
    try:
        manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Check(WARN, "plugin", "not running from a plugin checkout")
    version = manifest.get("version")
    if version != __version__:
        return Check(FAIL, "plugin", f"plugin.json says {version}, package is {__version__}")
    return Check(OK, "plugin", f"{PLUGIN_MANIFEST.parents[1]} ({version})")
