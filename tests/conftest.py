import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent_cairn import timeutil
from agent_cairn.document import Handoff

CREATED = datetime(2026, 11, 9, 8, 30, 12, tzinfo=timezone.utc)
ROOT_DIR = Path(__file__).resolve().parents[1]

FILLED_BODY = """# Login form: wire OAuth callback

## Goal
Users can sign in with Google.

## Current state
Callback route exchanges the code.

## Next steps
- [ ] Set session cookie
- [ ] Run `pnpm test:e2e login`

## Decisions
- iron-session instead of JWT in localStorage: team security guideline.

## Tried / didn't work
- next-auth adapter: conflicts with the custom user table.

## Open questions
- Cookie lifetime 7d or 30d?

## Key files
- app/api/auth/callback/route.ts
"""


def make_handoff(body=FILLED_BODY, captured_md="## Captured state\n- Branch: main", **meta):
    """A Handoff with valid default frontmatter; keyword arguments override fields."""
    fields = {
        "schema": 1,
        "created_at": "2026-11-09T08:30:12Z",
        "title": "Login form: wire OAuth callback",
        "status": "open",
        "repo": "shop-web",
        "worktree": "/code/shop-web",
        "branch": "main",
        "head": "9f2c1e0a7b3d4c5e6f708192a3b4c5d6e7f80912",
        "agent": "claude-code",
        "cairn_version": "0.0.1",
        **meta,
    }
    return Handoff(meta=fields, body=body.strip(), captured_md=captured_md.strip())


def git(cwd, *args):
    """Run git in ``cwd`` and return stdout; fails the test on error."""
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(repo, message="change"):
    """Create an empty commit in ``repo`` and return its SHA."""
    git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        message,
    )
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture(autouse=True)
def isolated_env(tmp_path_factory, monkeypatch):
    """Keep tests away from the real HOME, git config and cairn settings."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path_factory.getbasetemp()))
    monkeypatch.setenv("NO_COLOR", "1")
    for name in ("CAIRN_STORE", "CAIRN_HOME", "CAIRN_HOOK", "CAIRN_DEBUG", "CAIRN_AGENT"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def git_repo(tmp_path, monkeypatch) -> Path:
    """An empty git repository that is also the current directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    return repo


@pytest.fixture
def outside_repo(tmp_path, monkeypatch) -> Path:
    """A plain directory, not inside any git repository, as the current directory."""
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.chdir(plain)
    return plain


@pytest.fixture
def clock(monkeypatch):
    """Freeze timeutil.now_utc at CREATED; returns a setter to move time."""
    now = {"value": CREATED}
    monkeypatch.setattr(timeutil, "now_utc", lambda: now["value"])
    return lambda moment: now.__setitem__("value", moment)


@pytest.fixture
def fake_gh(tmp_path, monkeypatch):
    """Install a fake ``gh`` on PATH; call it with the script body to run. Returns its log."""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    def install(script):
        gh = bin_dir / "gh"
        gh.write_text(f'#!/bin/sh\necho "$@" >> {log}\n{script}\n')
        gh.chmod(0o755)
        return log

    return install


def add_worktree(repo, name, *args):
    """Add a linked worktree next to ``repo`` and return its path."""
    path = repo.parent / name
    git(repo, "worktree", "add", "-q", *args, str(path))
    return path


def bare_remote(repo):
    """Give ``repo`` an ``origin`` remote and push main with upstream tracking."""
    remote = repo.parent / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "-u", "origin", "main")
    return remote
