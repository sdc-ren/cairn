# cairn

Hand off work between AI agent sessions without re-explaining it.

When a Claude Code session stops (usage limit, account switch, `/clear`, tomorrow), the next
session loses the *reasoning*: the goal, what was decided and why, what was tried and failed,
and what comes next. Git keeps the code, not the reasoning. cairn keeps it.

- **Save in one command.** `/cairn:handoff` has the agent write a structured handoff while it
  still has the context. cairn validates it, blocks secrets, and attaches git facts.
- **Resume with no command.** A `SessionStart` hook injects the open handoff into the next
  session, together with a drift report of what changed since it was written.
- **One handoff per task.** Handoffs are keyed by ticket (`PROJ-268`), so parallel tasks in one
  workspace never overwrite each other.
- **Worktrees and pipelines included.** List them in the handoff; cairn records their branch
  and HEAD and warns when they moved or disappeared.
- **Local and plain.** Markdown files under `~/.cairn`, mode `0600`. No database, no LLM calls,
  no network except an optional `gh` lookup of pull requests; Python standard library only.

> Status: **0.2.1**, early release, used daily by its author. The file format and commands
> may still change before 1.0.

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [Skills (inside Claude Code)](#skills-inside-claude-code)
- [Command reference](#command-reference)
- [The handoff format](#the-handoff-format)
- [How it works](#how-it-works)
- [Privacy and safety](#privacy-and-safety)
- [Configuration](#configuration)
- [Uninstall](#uninstall)
- [Development](#development)

## Install

Requirements: macOS or Linux, `git` 2.31+, `python3` 3.9+ (the one shipped with macOS works).

| You use | Install with | You get |
|---|---|---|
| Claude Code (recommended) | `claude plugin marketplace add sdc-ren/cairn`<br>`claude plugin install cairn@sdc-ren` | Skills `/cairn:handoff`, `/cairn:resume`, the hooks, and the CLI inside Claude |
| A terminal | `pipx install cairn-handoff` (or `uv tool install cairn-handoff`) | The `cairn` command everywhere |
| A terminal, nothing installed | `uvx --from cairn-handoff cairn <command>`<br>or `npx github:sdc-ren/cairn <command>` | A one-off run, e.g. `uvx --from cairn-handoff cairn list` |
| Claude Code without the plugin | the terminal install, then `cairn init` | Skills `/cairn-handoff`, `/cairn-resume` |
| Codex, Cursor or another agent | the terminal install, then `cairn init --agent agents-md` | Instructions in `AGENTS.md` |

After installing the plugin, start a new Claude Code session. To try a local checkout instead,
use `claude plugin marketplace add /path/to/cairn`, or link its `bin/cairn` into your `PATH`.
Every route, `npx` included, runs the same Python code, so `python3` 3.9+ must be installed.

## Quick start

1. **Save.** Near the end of a session, in Claude Code:
   ```
   /cairn:handoff
   ```
   or just say "save context", "running out of quota", "lưu ngữ cảnh". The agent replies with
   the handoff ID, for example `saved 20261109-083012-proj-268`.
2. **Resume.** Open a new session in the same project, on any account. The handoff is already
   in context; say "continue PROJ-268" and the agent summarises the goal, what is done and the
   next step.
3. **Look around** from a terminal:
   ```bash
   cairn list          # what is saved for this project
   cairn show PROJ-268 # the full handoff
   ```

## Skills (inside Claude Code)

| Skill | Plugin name | Without plugin | What it does |
|---|---|---|---|
| handoff | `/cairn:handoff [title]` | `/cairn-handoff` | The agent writes the handoff from the conversation and saves it in one turn. It passes the ticket as the task when it sees one, fixes anything cairn rejects (up to 3 tries), and replies in at most 2 lines. |
| resume | `/cairn:resume [task]` | `/cairn-resume` | Continue a handoff. With a task, opens it. Without one: uses the handoff the hook already injected; otherwise opens the only open one, or shows a table and asks which one. |

Both skills also trigger from plain language in English or Vietnamese ("handoff", "save
context", "sắp hết quota"; "continue where we left off", "làm tiếp", "còn task nào đang dở").

Hooks run by themselves:

| Hook | When | What it does |
|---|---|---|
| `SessionStart` | new session or `/clear` | Injects the project's newest open handoff (preferring the current branch) with its drift report, lists the other open ones, and marks the injected one `resumed`. |
| `PreCompact` | before context compaction | Asks the summary to keep the goal, decisions, failed attempts, next steps and resources. |
| `SessionStart` (compact) | after compaction | Shows one line suggesting `/cairn:handoff` when nothing was saved in the last 2 hours. |

## Command reference

Run `cairn -h` or `cairn <command> -h` for the same information in the terminal. A `<ref>`
selects a handoff by task (any case), full ID, or a unique ID prefix of at least 4 characters;
without one, cairn picks the newest handoff of the current branch, else the newest of the
project. Commands that work with saved handoffs accept `--dir DIR` to act on another directory.

### `cairn save` — store a handoff

Reads the body from stdin or `--file`, checks it, attaches the git state and saves it as `open`.
Prints `saved <id>`. Saving again for the same task (or branch, without a task) replaces the
previous handoff.

| Option | Effect |
|---|---|
| `--file FILE` | Read the body from `FILE` (`-` for stdin) |
| `--task TASK` | Ticket or task ID, such as `PROJ-268`; names the file and keys replacement |
| `--title TITLE` | Replace the body's `# ` title |
| `--agent AGENT` | Agent name to record (default `$CAIRN_AGENT`, else `unknown`) |
| `--session ID` | ID of the session that wrote it |
| `--redact` | Replace likely secrets with `[REDACTED:<kind>]` instead of rejecting |
| `--dry-run` | Print the file that would be written; change nothing |
| `--no-gh` | Do not ask `gh` for open pull requests |

```bash
cairn template > handoff.md                    # start from the template and fill it in
cairn save --task PROJ-268 --file handoff.md   # then save it
```

### `cairn list` — list handoffs

| Option | Effect |
|---|---|
| `--status open\|resumed` | Only handoffs with this status |
| `--here` | Only the current branch |
| `--branch BRANCH` | Only this branch |
| `--limit N` / `--all` | Rows to show (default 20) / no limit |
| `--json` | Frontmatter of each handoff as JSON |

```
ID                        TASK      STATUS   AGE      TITLE
20261109-100105-proj-274  PROJ-274  resumed  40m ago  QC round 2 fixes
20261109-095106-proj-268  PROJ-268  open     50m ago  Checkout: bulk discount
```

### `cairn show [<ref>]` — print a handoff file

| Option | Effect |
|---|---|
| `--path` | Print only the file path |
| `--any-branch` | Ignore the current branch when choosing |

### `cairn resume [<ref>]` — continue a handoff

Prints the handoff with instructions for the agent and a drift report, then marks it `resumed`.

| Option | Effect |
|---|---|
| `--peek` | Do not mark it resumed |
| `--brief` | Leave out the captured git state |
| `--json` | Handoff and drift as JSON |
| `--copy` | Also copy the output to the clipboard (pbcopy, wl-copy or xclip), e.g. for another agent |
| `--any-branch` | Ignore the current branch when choosing |

### `cairn rm <ref>...` — delete handoffs

Asks `delete N handoff(s)? [y/N]` first. Pass `--yes` to skip the question; it is required when
stdin is not a terminal. If any reference matches nothing, nothing is deleted.

### `cairn capture` — show the git state cairn would attach

Current worktree (branch, upstream, HEAD, stashes, uncommitted paths, recent commits, pull
requests) and a table of the other worktrees. Needs a git repository.

| Option | Effect |
|---|---|
| `--json` | Machine-readable output |
| `--no-gh` | Do not ask `gh` for open pull requests |

### `cairn template` — print the body template

The sections agents fill in; `Goal`, `Current state` and `Next steps` are required.

### `cairn init` — set up without the plugin

| Command | Effect |
|---|---|
| `cairn init` | Skills `/cairn-handoff`, `/cairn-resume` in `<project>/.claude/skills` |
| `cairn init --global` | The same in `~/.claude/skills` |
| `cairn init --agent agents-md` | A marked cairn block in `AGENTS.md`, refreshed on every run |
| `cairn init --uninstall` | Remove the skills and the block; an `AGENTS.md` cairn created is deleted |
| `--dry-run` | Show what would change |
| `--force` | Replace a file cairn did not write (the old one is kept as `.bak`) |

### `cairn prompt handoff|resume` — instructions for any agent

Prints the skill instructions with the Claude Code specific parts removed, ready to paste into
another agent.

### `cairn doctor` — check the setup

One line per check (`ok`, `warn`, `fail`): Python, git ≥ 2.31, repository, Store writable, `gh`,
plugin version, clipboard tool, `cairn` on `PATH`. Exits 1 if anything fails.

### `cairn hook <event>` and `cairn version`

`hook session-start|pre-compact|post-compact` is what Claude Code runs; you do not call it
yourself. `version` (or `--version`) prints the version.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Other error (one line on stderr; `CAIRN_DEBUG=1` shows the traceback) |
| 2 | Wrong usage, such as a missing body or `rm` without `--yes` off a terminal |
| 3 | The handoff was rejected; each problem is printed as `line N: rule: message` |
| 4 | No handoff matches, or an ID prefix is ambiguous |
| 5 | `capture` outside a git repository |

## The handoff format

```markdown
# PROJ-268 Checkout: bulk discount

## Goal
Carts with more than 5 items get 10% off on Web and App. Done = e2e passes on both.

## Current state
API change merged in #633; App rounding fix open in #190.

## Next steps
- [ ] Address review comments on #190
- [ ] Run the price backfill on prod after deploy (dry run first)

## Decisions
- Discount lives in the pricing service, not the API layer: the App calls it too.

## Tried / didn't work
- Rounding in the API layer double-rounded prices; abandoned.

## Open questions
- Does the discount apply before or after tax?

## Key files
- services/pricing/discount.py

## Workspace
- worktree: .worktrees/proj-268-app
- pipeline: .pipeline/PROJ-268-e2e
- db: app_db_proj_268
```

| Rule | Level |
|---|---|
| A `# ` title, and non-empty `Goal`, `Current state` and `Next steps` | Required |
| `Next steps` written as list items | Required |
| No likely secrets (or use `--redact`) | Required |
| At most 12,000 characters | Required |
| `Decisions`, `Tried / didn't work`, `Open questions`, `Key files` | Warning if missing |
| More than 6,000 characters | Warning |

`Workspace` lines labelled `worktree` (a git checkout) or `pipeline` (a folder) are recorded at
save time and checked on resume; other labels are kept as written. Paths are relative to the
project.

## How it works

```
session A                                   session B (new account, new day, new worktree)
─────────                                   ─────────────────────────────────────────────
/cairn:handoff                              SessionStart hook
  └─ agent writes the body                    └─ cairn hook session-start
  └─ cairn save                                    ├─ newest open handoff of this project
       ├─ validate sections, block secrets        ├─ drift: new commits, moved worktrees
       ├─ capture git facts + Workspace           ├─ inject as additionalContext
       └─ ~/.cairn/<project>-<hash>/<id>.md       └─ mark it resumed
```

- **Project**: the main repository root, shared by all its worktrees. Outside git (for example
  a folder holding several repositories) the directory itself is the project.
- **Store**: `~/.cairn/<project>-<hash>/`, one Markdown file per handoff. The hash keeps two
  folders with the same name apart.
- **Drift**: on resume cairn reports new or rewritten commits, a changed branch, uncommitted
  files that are still, newly or no longer modified, and each Workspace worktree or pipeline
  that moved or disappeared. Warnings make the agent wait for your go-ahead.
- **Lifecycle**: resuming never deletes; it marks the handoff `resumed` so it is not injected
  twice. Resumed handoffs are removed after 7 days and unclaimed ones after 30, the next time
  cairn writes. `cairn rm` deletes by hand.

## Privacy and safety

- Everything stays on your machine. The only network call is optional: `gh` for pull request
  titles at save time (`--no-gh` to skip). The hooks never use the network.
- Files are `0600`, directories `0700`. No diffs or file contents are stored, only paths,
  branches, SHAs and commit subjects.
- Bodies containing likely secrets (private keys, AWS, GitHub, Slack, OpenAI, Anthropic keys,
  JWTs, `password = ...`) are rejected; the value is never printed.
- Hooks always exit 0 and report problems on stderr, so they cannot break a session.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `CAIRN_HOME` | `~/.cairn` | Root folder for all Stores |
| `CAIRN_HOOK` | on | `off` disables the `SessionStart` hook |
| `CAIRN_HOOK_MAX_AGE` | `7d` | Ignore open handoffs older than this (`d`, `h`, `m`) |
| `CAIRN_KEEP_RESUMED` | `7d` | Remove resumed handoffs after this long |
| `CAIRN_KEEP_OPEN` | `30d` | Remove handoffs nobody resumed after this long |
| `CAIRN_NUDGE` | on | `off` disables the compaction hooks |
| `CAIRN_NUDGE_WINDOW` | `2h` | No reminder after compaction if a handoff is this recent |
| `CAIRN_AGENT` | `unknown` | Agent name recorded when `--agent` is not given |
| `CAIRN_STORE` | | Use this exact folder as the Store (tests, debugging) |
| `CAIRN_DEBUG` | | `1` shows a traceback for unexpected errors |
| `NO_COLOR` | | Set to disable colored warnings |

## Uninstall

```bash
claude plugin uninstall cairn@sdc-ren   # the plugin
cairn init --uninstall                  # skills or AGENTS.md block installed by cairn init
pipx uninstall cairn-handoff              # the terminal command
rm -rf ~/.cairn                         # every saved handoff
```

## Development

```bash
make setup     # Python 3.9 virtualenv with dev tools
make lint      # ruff, mypy --strict, duplicate and dead code, module size
make test      # pytest (make cov for coverage, make reqcov for requirement coverage)
make gen       # regenerate skills/ from src/agent_cairn/assets
```

The design is spec-driven: requirements, design decisions and the task plan live in
[`docs/specs/`](docs/specs/README.md) (Vietnamese), and code follows
[`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md). See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
