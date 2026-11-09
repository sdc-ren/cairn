"""Where handoffs live: paths, IDs, keys, atomic writes, status updates (R1, R14).

The only module that builds Store paths or file names (CODING_STANDARDS CS-2).
"""

from __future__ import annotations

import fcntl
import hashlib
import itertools
import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from agent_cairn import document, gitio, out, timeutil
from agent_cairn.constants import (
    DIR_MODE,
    FILE_MODE,
    HANDOFF_SUFFIX,
    HOME_DIR_NAME,
    HOME_ENV,
    LOCK_FILE_NAME,
    PROJECT_FILE_NAME,
    PROJECT_HASH_CHARS,
    SLUG_FALLBACK,
    SLUG_MAX_CHARS,
    STATUS_RESUMED,
    STORE_ENV,
)
from agent_cairn.errors import InvalidHandoffError, NotAGitRepoError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from datetime import datetime

    from agent_cairn.document import Handoff, MetaValue

_NOT_SLUG = re.compile(r"[^a-z0-9-]+")
_DASHES = re.compile(r"-{2,}")


def home() -> Path:
    """Return the Cairn home that holds every Store: ``$CAIRN_HOME`` or ``~/.cairn``."""
    override = os.environ.get(HOME_ENV)
    return Path(override) if override else Path.home() / HOME_DIR_NAME


def project_dir(cwd: Path) -> Path:
    """Return the project of ``cwd``: the main repo root in git, else ``cwd`` itself (glossary)."""
    try:
        return gitio.common_dir(cwd).parent
    except NotAGitRepoError:
        return cwd.resolve()


def root(cwd: Path) -> Path:
    """Return the Store of the project at ``cwd``: ``<home>/<project-slug>-<hash8>`` (R1.1, R1.2).

    The hash keeps two folders with the same name apart; ``$CAIRN_STORE`` overrides the path.
    """
    override = os.environ.get(STORE_ENV)
    if override:
        return Path(override)
    project = project_dir(cwd)
    digest = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:PROJECT_HASH_CHARS]
    return home() / f"{slugify(project.name)}-{digest}"


def slugify(text: str) -> str:
    """Lowercase ``text``, turn runs of other characters into ``-``, cap the length (glossary)."""
    slug = _DASHES.sub("-", _NOT_SLUG.sub("-", text.lower())).strip("-")
    return slug[:SLUG_MAX_CHARS].strip("-") or SLUG_FALLBACK


def new_id(created_at: datetime, label: str) -> str:
    """Return ``YYYYMMDD-HHMMSS-<label-slug>`` for a handoff created at ``created_at``."""
    return f"{created_at:%Y%m%d-%H%M%S}-{slugify(label)}"


def handoff_key(meta: Mapping[str, MetaValue]) -> str | None:
    """Return what a newer save replaces: task, else branch, else the project (R14.1).

    A detached HEAD without a task has no key, so it is never replaced.
    """
    task = str(meta.get("task", ""))
    if task:
        return f"task:{task.casefold()}"
    branch = str(meta.get("branch", ""))
    if branch:
        return f"branch:{branch}"
    return None if meta.get("head") else "project"


def record_project(store: Path, project: Path) -> None:
    """Write ``.project.json`` naming the project, once, so Stores can be told apart (R1.8)."""
    _ensure(store)
    target = store / PROJECT_FILE_NAME
    if not target.exists():
        _write_temp(store, json.dumps({"path": str(project)}) + "\n").replace(target)


@contextmanager
def lock(store: Path) -> Iterator[None]:
    """Hold an exclusive lock on the Store for a read-modify-write sequence."""
    _ensure(store)
    descriptor = os.open(store / LOCK_FILE_NAME, os.O_RDWR | os.O_CREAT, FILE_MODE)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)  # closing releases the lock


def write_new(store: Path, handoff: Handoff, *, created_at: datetime, label: str) -> str:
    """Write ``handoff`` as a new file and return its ID; never overwrites (R1.4-R1.6).

    Each attempt writes a private temp file and hard-links it to the final name; the link fails
    if the name exists, so a clash moves on to the ``-2``, ``-3`` suffix instead of overwriting.
    """
    _ensure(store)
    base = new_id(created_at, label)
    for attempt in itertools.count(1):
        hid = base if attempt == 1 else f"{base}-{attempt}"
        text = document.render(replace(handoff, meta={**handoff.meta, "id": hid}))
        temp = _write_temp(store, text)
        try:
            os.link(temp, store / f"{hid}{HANDOFF_SUFFIX}")
        except FileExistsError:
            continue
        finally:
            temp.unlink()
        return hid
    raise AssertionError("unreachable")  # itertools.count never ends


def handoffs(store: Path) -> list[Handoff]:
    """Return every readable handoff in the Store, newest first; broken files are skipped."""
    return sorted(_iter_handoffs(store), key=_recency, reverse=True)


def newest(store: Path, *, branch: str | None = None, status: str | None = None) -> Handoff | None:
    """Return the most recent handoff, optionally of ``branch`` and with ``status``, or None."""
    for handoff in handoffs(store):
        if (branch is None or handoff.meta.get("branch") == branch) and (
            status is None or handoff.meta.get("status") == status
        ):
            return handoff
    return None


def find(store: Path, ref: str) -> Handoff | None:
    """Return the newest handoff whose task matches ``ref`` (any case) or whose ID is ``ref``."""
    wanted = ref.casefold()
    for handoff in handoffs(store):
        if str(handoff.meta.get("task", "")).casefold() == wanted or handoff.meta.get("id") == ref:
            return handoff
    return None


def mark_resumed(handoff: Handoff, *, now: datetime) -> Handoff:
    """Mark ``handoff`` resumed and count it; body and captured state stay byte-exact (R9.3)."""
    path = path_of(handoff)
    text = path.read_text(encoding="utf-8")
    current = document.parse(text, str(path))
    meta = {
        **current.meta,
        "status": STATUS_RESUMED,
        "resumed_at": timeutil.to_iso(now),
        "resume_count": int(current.meta.get("resume_count", 0)) + 1,
    }
    _write_temp(path.parent, document.replace_meta(text, meta)).replace(path)
    return replace(current, meta=meta, path=path)


def cleanup(store: Path, *, key: str | None, keep: str) -> None:
    """Delete other handoffs with the same key after a save (R14.1, R14.5). Call inside ``lock``."""
    if key is None:
        return
    for handoff in _iter_handoffs(store):
        hid = handoff.meta.get("id")
        if handoff_key(handoff.meta) == key and hid != keep:
            path_of(handoff).unlink()
            out.note(f"removed {hid} (replaced)")


def path_of(handoff: Handoff) -> Path:
    """Return the file a handoff was loaded from; handoffs built in memory have none."""
    if handoff.path is None:
        raise InvalidHandoffError("handoff was not loaded from the store")
    return handoff.path


def _iter_handoffs(store: Path) -> Iterator[Handoff]:
    if not store.is_dir():
        return
    for path in sorted(store.glob(f"*{HANDOFF_SUFFIX}")):
        try:
            handoff = document.parse(path.read_text(encoding="utf-8"), path.name)
        except (InvalidHandoffError, OSError, UnicodeDecodeError) as err:
            out.warn(f"skipping {path.name}: {err}")
            continue
        yield replace(handoff, path=path)


def _recency(handoff: Handoff) -> tuple[str, str]:
    return str(handoff.meta.get("created_at", "")), str(handoff.meta.get("id", ""))


def _ensure(store: Path) -> None:
    store.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    base = home()
    # mkdir's mode is reduced by umask, so chmod; never touch an unrelated $CAIRN_STORE parent.
    for directory in (base, store) if store.parent == base else (store,):
        directory.chmod(DIR_MODE)


def _write_temp(directory: Path, text: str) -> Path:
    descriptor, name = tempfile.mkstemp(dir=directory, prefix=".tmp-")  # created 0600
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(text)
    return Path(name)
