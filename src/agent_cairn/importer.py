"""``cairn import``: store a shared bundle as an open handoff of this project (R25.4).

The bundle comes from someone else, so every member is checked before anything is written:
only regular files under the known names, no absolute paths, no ``..``, within size limits.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from agent_cairn import document, out, portable, store, timeutil
from agent_cairn.constants import (
    BUNDLE_ATTACHMENTS,
    BUNDLE_HANDOFF,
    BUNDLE_PATCHES,
    DIR_MODE,
    NO_GIT_LABEL,
    SHARE_DIR,
    SHARE_MAX_TOTAL_BYTES,
)
from agent_cairn.document import Handoff
from agent_cairn.errors import InvalidHandoffError, UsageError

if TYPE_CHECKING:
    from agent_cairn.document import MetaValue

_ALLOWED_TOP = (BUNDLE_ATTACHMENTS, BUNDLE_PATCHES)
_IGNORE_ALL = "*\n"
_MIN_PARTS = 2  # a folder and a file name: attachments/<path>, patches/<file>


def import_bundle(bundle: Path, cwd: Path) -> str:
    """Unpack ``bundle`` under ``.cairn-shared/<id>/`` and save its handoff; return a summary.

    Raises:
        UsageError: the file cannot be read, or this bundle was already imported here.
        InvalidHandoffError: the bundle is malformed or holds an unsafe member.
    """
    members = _read(bundle)
    handoff = document.parse(members.pop(BUNDLE_HANDOFF).decode("utf-8"), BUNDLE_HANDOFF)
    shared_id = str(handoff.meta.get("id", ""))
    if not shared_id or "/" in shared_id or shared_id.startswith("."):
        raise InvalidHandoffError(f"{bundle.name}: the handoff has no usable id")
    project = store.project_dir(cwd)
    target = project / portable.unpacked_dir(shared_id)
    if target.exists():
        raise UsageError(f"already imported into {target.relative_to(project)}; delete it first")
    _unpack(project, target, members)
    hid = _save(project, cwd, handoff)
    name = handoff.meta.get("task") or hid
    return (
        f"imported {hid} ({len(members)} file(s) in {target.relative_to(project)}/)\n"
        f"continue with: /cairn:resume {name}"
    )


def _read(bundle: Path) -> dict[str, bytes]:
    try:
        with tarfile.open(bundle, mode="r:gz") as archive:
            members = _members(archive, bundle.name)
    except (OSError, tarfile.TarError) as err:
        raise UsageError(f"cannot read {bundle}: {err}") from err
    if BUNDLE_HANDOFF not in members:
        raise InvalidHandoffError(f"{bundle.name}: no {BUNDLE_HANDOFF}; not a cairn bundle")
    return members


def _members(archive: tarfile.TarFile, source: str) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    total = 0
    for info in archive.getmembers():
        name = _safe_name(info)
        total += info.size
        if total > SHARE_MAX_TOTAL_BYTES:
            raise InvalidHandoffError(f"{source}: larger than the bundle size limit")
        stream = archive.extractfile(info)
        if stream is not None:
            members[name] = stream.read()
    return members


def _safe_name(info: tarfile.TarInfo) -> str:
    path = PurePosixPath(info.name)
    unsafe = (
        not info.isfile()
        or path.is_absolute()
        or ".." in path.parts
        or (
            str(path) != BUNDLE_HANDOFF
            and (len(path.parts) < _MIN_PARTS or path.parts[0] not in _ALLOWED_TOP)
        )
    )
    if unsafe:
        raise InvalidHandoffError(f"unsafe or unexpected bundle member: {info.name}")
    return str(path)


def _unpack(project: Path, target: Path, members: dict[str, bytes]) -> None:
    shared = project / SHARE_DIR
    shared.mkdir(mode=DIR_MODE, exist_ok=True)
    ignore = shared / ".gitignore"
    if not ignore.exists():
        ignore.write_text(_IGNORE_ALL, encoding="utf-8")  # never commit someone's bundle
    for name, data in members.items():
        path = target / name
        path.parent.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
        path.write_bytes(data)


def _save(project: Path, cwd: Path, handoff: Handoff) -> str:
    """Store the handoff with this machine's paths, replacing an older one of the same task."""
    meta: dict[str, MetaValue] = {**handoff.meta, "worktree": str(project)}
    meta.pop("id", None)
    captured = _localise(handoff.captured_md, project)
    root = store.root(cwd)
    store.record_project(root, project)
    now = timeutil.now_utc()
    label = str(meta.get("task") or meta.get("branch") or NO_GIT_LABEL)
    with store.lock(root):
        hid = store.write_new(
            root, Handoff(meta, handoff.body, captured), created_at=now, label=label
        )
        retention = store.retention_from_env()
        store.cleanup(root, key=store.handoff_key(meta), keep=hid, now=now, retention=retention)
    out.note(f"shared from {handoff.meta.get('id')}")
    return hid


def _localise(captured_md: str, project: Path) -> str:
    """Point the saved resources at this project, so drift checks the receiver's checkouts."""
    payload = document.captured_json(captured_md)
    if payload is None:
        return captured_md
    try:
        data = json.loads(payload)
        for resource in data.get("resources", []):
            resource["location"] = str(project / str(resource["path"]))
    except (ValueError, TypeError, KeyError, AttributeError):
        return document.without_captured_json(captured_md)
    text = document.without_captured_json(captured_md)
    return f"{text}\n\n{document.captured_json_line(json.dumps(data))}"
