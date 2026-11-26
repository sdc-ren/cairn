"""``cairn share``: pack a handoff with everything another machine needs to continue (R25).

The bundle is a gzip tarball: ``HANDOFF.md`` (paths scrubbed, captured state rebuilt for the
receiver), ``attachments/`` (files named by the handoff that a clone would not have) and
``patches/`` (uncommitted work of each worktree, as ``git apply`` input).
"""

from __future__ import annotations

import io
import json
import tarfile
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from agent_cairn import capture, document, gh, gitio, out, portable, secrets, store, timeutil
from agent_cairn.constants import (
    BINARY_SNIFF_BYTES,
    BUNDLE_ATTACHMENTS,
    BUNDLE_HANDOFF,
    BUNDLE_PATCHES,
    BUNDLE_SUFFIX,
    FILE_MODE,
    RESOURCE_PIPELINE,
    RESOURCE_WORKTREE,
    SHARE_MAX_FILE_BYTES,
    SHARE_MAX_TOTAL_BYTES,
)
from agent_cairn.document import Handoff
from agent_cairn.errors import CairnError, InvalidHandoffError
from agent_cairn.portable import Contents, SharedWorktree, Skipped

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from agent_cairn.capture import Resource


@dataclass(frozen=True)
class ShareOptions:
    """Flags of ``cairn share``."""

    output: Path | None = None
    redact: bool = False
    use_gh: bool = True


@dataclass(frozen=True)
class _Scope:
    """The sender's project: its spellings for scrubbing, and the directories to attach from."""

    project: Path
    roots: tuple[str, ...]
    home: str

    def scrub(self, text: str) -> str:
        return portable.scrub(text, roots=self.roots, home=self.home)

    def relative(self, path: Path) -> str | None:
        try:
            return path.resolve().relative_to(self.project.resolve()).as_posix() or "."
        except ValueError:
            return None


def share(handoff: Handoff, cwd: Path, options: ShareOptions) -> Path:
    """Write the bundle of ``handoff`` and return its path (R25.1).

    Raises:
        InvalidHandoffError: an attachment or patch holds a likely secret and ``redact`` is off.
    """
    project = store.project_dir(cwd)
    scope = _Scope(project, (str(project), str(project.resolve())), str(Path.home()))
    hid = str(handoff.meta.get("id"))
    files: dict[str, bytes] = {}
    worktrees = _worktrees(handoff, scope, files, use_gh=options.use_gh)
    attachments, skipped = _attachments(handoff, scope, files)
    _check_secrets(files, redact=options.redact)
    shared_at = timeutil.to_iso(timeutil.now_utc())
    contents = Contents(worktrees, tuple(attachments), tuple(skipped))
    files[BUNDLE_HANDOFF] = _handoff_text(handoff, scope, contents, shared_at).encode("utf-8")
    target = options.output or cwd / f"{hid}{BUNDLE_SUFFIX}"
    _write_tar(target, files)
    for worktree in worktrees:
        if not worktree.pushed:
            out.warn(f"{worktree.path}: HEAD {worktree.head[:7]} is not on any remote; push it")
    for item in skipped:
        out.warn(f"not attached: {item.path} ({item.reason})")
    return target


def _handoff_text(handoff: Handoff, scope: _Scope, contents: Contents, shared_at: str) -> str:
    body, _ = secrets.redact(scope.scrub(handoff.body))
    hid = str(handoff.meta.get("id"))
    resources = []
    for resource in _saved_resources(handoff):
        relative = scope.relative(Path(resource.location))
        if relative is not None:  # the receiver's copy lives at the same relative path
            resources.append({**asdict(resource), "path": relative, "location": relative})
    payload = json.dumps({"schema": 1, "current": _current(handoff), "resources": resources})
    captured = portable.captured(contents, handoff_id=hid, shared_at=shared_at)
    captured += "\n\n" + document.captured_json_line(payload)
    meta = portable.shared_meta(handoff.meta, shared_at=shared_at)
    return document.render(Handoff(meta, body, captured))


def _current(handoff: Handoff) -> dict[str, object]:
    changes = capture.changes_from_json(document.captured_json(handoff.captured_md)) or ()
    return {
        "branch": handoff.meta.get("branch") or None,
        "head": handoff.meta.get("head", ""),
        "changes": list(changes),
    }


def _saved_resources(handoff: Handoff) -> tuple[Resource, ...]:
    return capture.resources_from_json(document.captured_json(handoff.captured_md))


def _worktrees(
    handoff: Handoff, scope: _Scope, files: dict[str, bytes], *, use_gh: bool
) -> tuple[SharedWorktree, ...]:
    """Collect every git worktree of the handoff: the saved one and the Workspace ones."""
    candidates = [Path(str(handoff.meta.get("worktree", "")))]
    candidates += [Path(r.location) for r in _resources(handoff, RESOURCE_WORKTREE)]
    found: dict[Path, SharedWorktree] = {}
    for path in candidates:
        if not path.is_dir() or path.resolve() in found:
            continue
        try:
            top = gitio.toplevel(path)
        except CairnError:
            continue  # not a git checkout (the project may be a plain folder of worktrees)
        if top.resolve() in found:
            continue
        try:
            found[top.resolve()] = _worktree(top, scope, files, use_gh=use_gh)
        except CairnError as err:
            out.warn(f"{scope.relative(top) or top.name}: left out of the bundle: {err}")
    return tuple(found.values())


def _worktree(
    path: Path, scope: _Scope, files: dict[str, bytes], *, use_gh: bool
) -> SharedWorktree:
    relative = scope.relative(path) or path.name
    sha, subject = gitio.head(path)
    branch = gitio.current_branch(path)
    remote = gitio.remote_url(path)
    changes = len(gitio.status(path))
    patch = None
    if changes:
        patch = "root.patch" if relative == "." else f"{store.slugify(relative)}.patch"
        with tempfile.TemporaryDirectory() as temp:
            text = gitio.uncommitted_patch(path, Path(temp) / "index")
        files[f"{BUNDLE_PATCHES}/{patch}"] = text.encode("utf-8")
    lookup = gh.open_prs(path) if use_gh and remote else gh.PrLookup(gh.SKIPPED)
    prs = tuple(pr for pr in lookup.prs if branch and pr.head_ref == branch)
    errors = (f"PRs: {lookup.error}",) if lookup.status == gh.UNAVAILABLE else ()
    return SharedWorktree(
        path=relative,
        branch=branch,
        head=sha,
        subject=subject,
        remote=portable.public_url(remote) if remote else None,
        pushed=bool(remote) and gitio.on_remote(path, sha),
        changes_total=changes,
        patch=patch,
        prs=prs,
        errors=errors,
    )


def _resources(handoff: Handoff, kind: str) -> list[Resource]:
    return [r for r in _saved_resources(handoff) if r.kind == kind and r.exists]


def _attachments(
    handoff: Handoff, scope: _Scope, files: dict[str, bytes]
) -> tuple[list[str], list[Skipped]]:
    """Pick the files git does not carry: pipeline folders, ignored or non-git Key files."""
    picked: dict[str, Path] = {}
    skipped: list[Skipped] = []
    for resource in _resources(handoff, RESOURCE_PIPELINE):
        for found in sorted(Path(resource.location).rglob("*")):
            _consider(found, scope, picked, skipped)
    bases = [scope.project] + [Path(r.location) for r in _resources(handoff, RESOURCE_WORKTREE)]
    for written in document.key_files(handoff.body):
        path = _locate(written, bases)
        if path is None:
            skipped.append(Skipped(scope.scrub(written), "not found on the sender's machine"))
        elif scope.relative(path) is None:
            skipped.append(Skipped(scope.scrub(written), "outside the project"))
        elif not _in_git(path):
            _consider(path, scope, picked, skipped)
    total = 0
    attached = []
    for name, path in picked.items():
        data = path.read_bytes()
        if total + len(data) > SHARE_MAX_TOTAL_BYTES:
            skipped.append(Skipped(name, "the bundle reached its size limit"))
            continue
        total += len(data)
        files[f"{BUNDLE_ATTACHMENTS}/{name}"] = _clean_text(data, scope)
        attached.append(name)
    return attached, skipped


def _consider(path: Path, scope: _Scope, picked: dict[str, Path], skipped: list[Skipped]) -> None:
    name = scope.relative(path)
    if name is None or not path.is_file() or path.is_symlink() or name in picked:
        return
    if path.stat().st_size > SHARE_MAX_FILE_BYTES:
        skipped.append(Skipped(name, "larger than the per-file limit"))
        return
    picked[name] = path


def _locate(written: str, bases: Sequence[Path]) -> Path | None:
    path = Path(written).expanduser()
    if path.is_absolute():
        return path if path.exists() else None
    return next((base / path for base in bases if (base / path).exists()), None)


def _in_git(path: Path) -> bool:
    """Whether git carries the file: a clone has it, or the worktree patch adds it."""
    try:
        gitio.toplevel(path.parent)
    except CairnError:
        return False  # outside git: only the bundle can carry it
    return not gitio.is_ignored(path.parent, path)


def _clean_text(data: bytes, scope: _Scope) -> bytes:
    """Scrub paths in text attachments; binary files travel unchanged."""
    text = _text(data)
    return data if text is None else scope.scrub(text).encode("utf-8")


def _check_secrets(files: dict[str, bytes], *, redact: bool) -> None:
    """Refuse (or, with ``redact``, mask) likely secrets in text attachments and patches."""
    problems = []
    for name, data in list(files.items()):
        text = _text(data)
        if text is None:
            continue
        findings = secrets.scan(text)
        if findings and redact:
            files[name] = secrets.redact(text)[0].encode("utf-8")
            out.warn(f"{name}: redacted {len(findings)} likely secret(s)")
        else:
            problems += [f"{name}: line {f.line}: secret-{f.pattern}" for f in findings]
    if problems:
        raise InvalidHandoffError(
            "share refused: likely secrets in the bundle (values not shown); remove them, "
            "or pass --redact to mask them",
            tuple(problems),
        )


def _text(data: bytes) -> str | None:
    if b"\0" in data[:BINARY_SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _write_tar(target: Path, files: dict[str, bytes]) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in _ordered(files):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = FILE_MODE
            archive.addfile(info, io.BytesIO(data))
    target.write_bytes(buffer.getvalue())
    target.chmod(FILE_MODE)


def _ordered(files: dict[str, bytes]) -> Iterator[tuple[str, bytes]]:
    yield BUNDLE_HANDOFF, files[BUNDLE_HANDOFF]
    yield from sorted((k, v) for k, v in files.items() if k != BUNDLE_HANDOFF)
