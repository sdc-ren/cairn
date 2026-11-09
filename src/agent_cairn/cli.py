"""Command line: parse arguments, read input, dispatch, map errors to exit codes (R17)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable, NoReturn

from agent_cairn import (
    __version__,
    clipboard,
    commands,
    doctor,
    gitio,
    hook,
    integrations,
    out,
    render,
    store,
    timeutil,
)
from agent_cairn.constants import (
    AGENT_ENV,
    LIST_DEFAULT_LIMIT,
    NO_HANDOFFS_MESSAGE,
    SKILL_NAMES,
    STATUS_OPEN,
    STATUS_RESUMED,
    UNKNOWN_AGENT,
)
from agent_cairn.errors import CairnError, UsageError

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INTERRUPTED = 130
HELP_FLAGS = ("-h", "--help")
STORE_COMMANDS = ("save", "show", "resume", "list", "capture", "doctor", "rm", "init")
AGENT_CLAUDE = "claude"
AGENT_AGENTS_MD = "agents-md"


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that raises UsageError instead of printing and exiting itself."""

    def error(self, message: str) -> NoReturn:
        """Turn a parse error into UsageError so cli.main owns output and exit codes."""
        raise UsageError(message)


def _build_parser() -> tuple[_Parser, dict[str, argparse.ArgumentParser]]:
    parser = _Parser(
        prog="cairn",
        add_help=False,
        description="Hand off agent work between sessions, accounts and agents.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def command(name: str, summary: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, add_help=False, help=summary, description=summary)

    _add_save(command)
    _add_reading(command)
    _add_maintenance(command)
    for name in STORE_COMMANDS:
        sub.choices[name].add_argument("--dir", help="act on DIR instead of the current directory")
    return parser, dict(sub.choices)


def _add_save(command: Callable[[str, str], argparse.ArgumentParser]) -> None:
    """Declare ``save`` and its flags (R5)."""
    save = command("save", "save a handoff (body on stdin or --file)")
    save.add_argument("--file", help="read the body from FILE ('-' for stdin)")
    save.add_argument("--title", help="replace the body's '# ' title")
    save.add_argument("--task", help="task or ticket id, e.g. PROJ-268; one handoff per task")
    save.add_argument("--agent", help=f"agent name to record (default: ${AGENT_ENV})")
    save.add_argument("--session", help="id of the agent session writing the handoff")
    save.add_argument("--redact", action="store_true", help="replace secrets instead of failing")
    save.add_argument("--no-gh", action="store_true", help="do not ask gh for pull requests")
    save.add_argument("--dry-run", action="store_true", help="print the file, write nothing")


def _add_reading(command: Callable[[str, str], argparse.ArgumentParser]) -> None:
    """Declare the commands that read handoffs: show, resume, list (R6-R9)."""
    show = command("show", "print a handoff file")
    show.add_argument("--path", action="store_true", help="print only its file path")
    resume = command("resume", "print a handoff with its drift report and mark it resumed")
    resume.add_argument("--peek", action="store_true", help="do not mark it resumed")
    resume.add_argument("--brief", action="store_true", help="leave out the captured state")
    resume.add_argument("--json", action="store_true", help="print JSON")
    resume.add_argument("--copy", action="store_true", help="also copy the output to the clipboard")
    for selector in (show, resume):
        selector.add_argument("ref", nargs="?", help="task, handoff id or id prefix")
        selector.add_argument("--any-branch", action="store_true", help="ignore the branch")
    listing = command("list", "list the project's handoffs, newest first")
    listing.add_argument(
        "--status", choices=[STATUS_OPEN, STATUS_RESUMED], help="only handoffs with this status"
    )
    listing.add_argument("--branch", help="only handoffs saved on this branch")
    listing.add_argument("--here", action="store_true", help="only the current branch")
    listing.add_argument(
        "--limit", type=int, default=LIST_DEFAULT_LIMIT, help="rows to show (default: 20)"
    )
    listing.add_argument("--all", action="store_true", help="no row limit")
    listing.add_argument("--json", action="store_true", help="print frontmatter as JSON")


def _add_maintenance(command: Callable[[str, str], argparse.ArgumentParser]) -> None:
    """Declare capture, doctor, rm, init, prompt, template, hook, version."""
    snapshot = command("capture", "print the git state cairn would attach to a handoff")
    snapshot.add_argument("--json", action="store_true", help="print JSON")
    snapshot.add_argument("--no-gh", action="store_true", help="do not ask gh for pull requests")
    command("doctor", "check the environment")
    remove = command("rm", "delete handoffs after confirmation")
    remove.add_argument("refs", nargs="+", help="tasks, handoff ids or id prefixes")
    remove.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    init = command("init", "install cairn for setups without the Claude Code plugin")
    init.add_argument("--agent", choices=[AGENT_CLAUDE, AGENT_AGENTS_MD], default=AGENT_CLAUDE)
    init.add_argument("--global", dest="global_scope", action="store_true", help="~/.claude/skills")
    init.add_argument("--force", action="store_true", help="replace files cairn did not write")
    init.add_argument("--dry-run", action="store_true", help="show what would change")
    init.add_argument("--uninstall", action="store_true", help="remove what cairn installed")
    prompt = command("prompt", "print handoff or resume instructions to paste into any agent")
    prompt.add_argument("skill", choices=list(SKILL_NAMES))
    command("template", "print the handoff body template")
    hook_parser = command("hook", "run a Claude Code hook")
    hook_parser.add_argument("event", choices=hook.EVENTS)
    command("version", "print the cairn version")


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "version":
        out.emit(f"cairn {__version__}")
    elif args.command == "template":
        out.emit(commands.template())
    elif args.command == "prompt":
        out.emit(integrations.prompt(args.skill))
    elif args.command == "hook":
        return hook.run(args.event)
    else:
        return _store_command(args, Path(args.dir) if args.dir else Path.cwd())
    return EXIT_OK


def _store_command(args: argparse.Namespace, cwd: Path) -> int:
    if args.command == "save":
        out.emit(commands.save(cwd, _read_body(args.file), _save_options(args)))
    elif args.command == "show":
        path = commands.show(cwd, args.ref, any_branch=args.any_branch)
        out.emit(str(path) if args.path else path.read_text(encoding="utf-8").rstrip("\n"))
    elif args.command == "resume":
        options = commands.ResumeOptions(
            args.ref, args.peek, args.brief, args.json, args.any_branch
        )
        text = commands.resume(cwd, options)
        out.emit(text)
        if args.copy and not clipboard.copy(text):
            out.warn("no clipboard tool found (pbcopy, wl-copy, xclip); printed only")
    elif args.command == "list":
        _print_list(args, cwd)
    elif args.command == "capture":
        out.emit(commands.capture_report(cwd, use_gh=not args.no_gh, as_json=args.json))
    elif args.command == "rm":
        commands.remove(cwd, args.refs, confirmed=args.yes)
    elif args.command == "init":
        _init(args, cwd)
    else:
        return _print_doctor(cwd)
    return EXIT_OK


def _init(args: argparse.Namespace, cwd: Path) -> None:
    project = store.project_dir(cwd)
    if args.uninstall:
        changes = integrations.uninstall(
            project, global_scope=args.global_scope, dry_run=args.dry_run
        )
    elif args.agent == AGENT_AGENTS_MD:
        changes = [integrations.install_agents_md(project, dry_run=args.dry_run)]
    else:
        root = integrations.skills_root(project, global_scope=args.global_scope)
        changes = integrations.install_skills(root, force=args.force, dry_run=args.dry_run)
    for change in changes:
        out.emit(f"{change.action}: {change.path}")
    if not changes:
        out.emit("nothing to do")


def _save_options(args: argparse.Namespace) -> commands.SaveOptions:
    return commands.SaveOptions(
        agent=args.agent or os.environ.get(AGENT_ENV) or UNKNOWN_AGENT,
        session_id=args.session,
        task=args.task,
        title=args.title,
        redact=args.redact,
        dry_run=args.dry_run,
        use_gh=not args.no_gh,
    )


def _print_list(args: argparse.Namespace, cwd: Path) -> None:
    branch = gitio.current_branch(cwd) if args.here else args.branch
    wanted = commands.ListFilter(args.status, branch, None if args.all else args.limit)
    found = commands.list_handoffs(cwd, wanted)
    if args.json:
        out.emit(json.dumps([dict(h.meta) for h in found], indent=2, ensure_ascii=False))
    elif found:
        out.emit(render.handoff_table(found, now=timeutil.now_utc()))
    else:
        out.emit(NO_HANDOFFS_MESSAGE)


def _print_doctor(cwd: Path) -> int:
    checks = doctor.run(cwd)
    for check in checks:
        out.emit(f"{check.level:<4}  {check.name:<10}  {check.detail}")
    return EXIT_FAILED if any(check.level == doctor.FAIL for check in checks) else EXIT_OK


def _read_body(file_arg: str | None) -> str:
    """Read the handoff body from ``--file`` or stdin (R5.1, R5.2)."""
    if file_arg and file_arg != "-":
        try:
            return Path(file_arg).read_text(encoding="utf-8")
        except OSError as err:
            raise UsageError(f"cannot read {file_arg}: {err.strerror}") from err
    if file_arg is None and sys.stdin.isatty():
        raise UsageError(
            "no handoff body given; pipe it on stdin or pass --file FILE "
            "(run `cairn template` for the format)"
        )
    return sys.stdin.read()


def _help(
    args: list[str], parser: _Parser, subparsers: dict[str, argparse.ArgumentParser]
) -> str | None:
    """Return help text for ``cairn [-h]`` or ``cairn <command> -h``, else None (R17.2)."""
    if not args or args[0] in HELP_FLAGS:
        return parser.format_help()
    if args[0] in subparsers and any(arg in HELP_FLAGS for arg in args[1:]):
        return subparsers[args[0]].format_help()
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Run cairn with ``argv`` (default: ``sys.argv[1:]``) and return the exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    parser, subparsers = _build_parser()
    try:
        text = _help(args, parser, subparsers)
        if text is not None:
            out.emit(text.rstrip())
            return EXIT_OK
        if args[0] == "--version":
            args = ["version"]
        return _dispatch(parser.parse_args(args))
    except CairnError as err:
        out.note(str(err))
        for line in err.details:
            out.detail(line)
        return err.exit_code
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except BrokenPipeError:  # e.g. `cairn list | head`: the reader left; nothing to report
        return EXIT_OK
    except Exception as err:  # last-resort guard (CS-28): one line, no traceback (R17.6)
        if os.environ.get("CAIRN_DEBUG") == "1":
            raise
        out.note(f"internal error: {type(err).__name__}: {err} (set CAIRN_DEBUG=1 for details)")
        return EXIT_FAILED
