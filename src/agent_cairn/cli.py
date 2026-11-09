"""Command line: parse arguments, dispatch, map errors to exit codes (R17)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from agent_cairn import __version__, commands, hook, out, render, timeutil
from agent_cairn.constants import (
    AGENT_ENV,
    LIST_DEFAULT_LIMIT,
    NO_HANDOFFS_MESSAGE,
    STATUS_OPEN,
    STATUS_RESUMED,
    UNKNOWN_AGENT,
)
from agent_cairn.errors import CairnError, UsageError

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INTERRUPTED = 130
HELP_FLAGS = ("-h", "--help")


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that raises UsageError instead of printing and exiting itself."""

    def error(self, message: str) -> NoReturn:
        """Turn a parse error into UsageError so cli.main owns output and exit codes."""
        raise UsageError(message)


def _build_parser() -> _Parser:
    parser = _Parser(
        prog="cairn",
        add_help=False,
        description="Hand off agent work between sessions, accounts and agents.",
    )
    subcommands = parser.add_subparsers(dest="command", metavar="<command>")
    save = subcommands.add_parser(
        "save", add_help=False, help="save a handoff for the current branch"
    )
    save.add_argument("--file", help="read the body from FILE ('-' for stdin)")
    save.add_argument("--agent", help=f"agent name to record (default: ${AGENT_ENV})")
    save.add_argument("--session", help="id of the agent session writing the handoff")
    save.add_argument("--task", help="task or ticket id, e.g. PROJ-268; one handoff per task")
    show = subcommands.add_parser("show", add_help=False, help="print a handoff file")
    show.add_argument("--path", action="store_true", help="print only its file path")
    resume = subcommands.add_parser("resume", add_help=False, help="print a handoff to continue")
    listing = subcommands.add_parser("list", add_help=False, help="list the project's handoffs")
    listing.add_argument("--status", choices=[STATUS_OPEN, STATUS_RESUMED])
    listing.add_argument("--limit", type=int, default=LIST_DEFAULT_LIMIT)
    listing.add_argument("--all", action="store_true", help="show every handoff")
    for command in (save, show, resume, listing):
        command.add_argument("--dir", help="working directory to use instead of the current one")
    for command in (show, resume):
        command.add_argument("ref", nargs="?", help="task or handoff id (default: best match)")
    hook_parser = subcommands.add_parser("hook", add_help=False, help="run a Claude Code hook")
    hook_parser.add_argument("event", choices=["session-start"])
    subcommands.add_parser("version", add_help=False, help="print the cairn version")
    return parser


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "version":
        out.emit(f"cairn {__version__}")
        return EXIT_OK
    if args.command == "hook":
        return hook.session_start()
    cwd = Path(args.dir) if args.dir else Path.cwd()
    if args.command == "show":
        path = commands.show(cwd, args.ref)
        out.emit(str(path) if args.path else path.read_text(encoding="utf-8").rstrip("\n"))
    elif args.command == "resume":
        out.emit(commands.resume(cwd, args.ref))
    elif args.command == "list":
        limit = None if args.all else args.limit
        found = commands.list_handoffs(cwd, status=args.status, limit=limit)
        table = render.handoff_table(found, now=timeutil.now_utc())
        out.emit(table if found else NO_HANDOFFS_MESSAGE)
    else:
        body = _read_body(args.file)
        agent = args.agent or os.environ.get(AGENT_ENV) or UNKNOWN_AGENT
        hid = commands.save(cwd, body, agent=agent, session_id=args.session, task=args.task)
        out.emit(f"saved {hid}")
    return EXIT_OK


def _read_body(file_arg: str | None) -> str:
    """Read the handoff body from ``--file`` or stdin (R5.1, R5.2)."""
    if file_arg and file_arg != "-":
        try:
            return Path(file_arg).read_text(encoding="utf-8")
        except OSError as err:
            raise UsageError(f"cannot read {file_arg}: {err.strerror}") from err
    if file_arg is None and sys.stdin.isatty():
        raise UsageError("no handoff body given; pipe it on stdin or pass --file FILE")
    return sys.stdin.read()


def main(argv: Sequence[str] | None = None) -> int:
    """Run cairn with ``argv`` (default: ``sys.argv[1:]``) and return the exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        if not args or args[0] in HELP_FLAGS:
            out.emit(parser.format_help().rstrip())
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
    except Exception as err:  # last-resort guard (CS-28): one line, no traceback (R17.6)
        if os.environ.get("CAIRN_DEBUG") == "1":
            raise
        out.note(f"internal error: {type(err).__name__}: {err} (set CAIRN_DEBUG=1 for details)")
        return EXIT_INTERNAL
