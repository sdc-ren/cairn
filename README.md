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
- **Local and plain.** Markdown files under `~/.cairn`, mode `0600`. No database, no network,
  no LLM calls, Python standard library only.

> Status: **0.0.1, early preview.** It is used daily by its author. File format and commands
> may still change before 0.1.

## Install

Requirements: macOS or Linux, `git` 2.31+, `python3` 3.9+ (the one shipped with macOS works).

### Claude Code plugin (recommended)

```bash
claude plugin marketplace add sdc-ren/cairn
claude plugin install cairn@cairn
```

The plugin bundles the CLI, so nothing else is needed: skills and hooks call it directly.
Start a new session afterwards. To try a local checkout instead, use
`claude plugin marketplace add /path/to/cairn`.

### CLI in your terminal (optional)

```bash
pipx install git+https://github.com/sdc-ren/cairn
```

Or, from a checkout, put `bin/cairn` on your `PATH`; it runs the bundled source with your
system `python3`.

## Usage

### Save

Near the end of a session, type:

```
/cairn:handoff
```

or just say "save context", "running out of quota", "lưu ngữ cảnh". The agent fills the
template, runs `cairn save`, fixes anything cairn rejects, and replies with the handoff ID.
Add a title with `/cairn:handoff Fix cart total`.

A handoff looks like this (abridged):

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

## Workspace
- worktree: .worktrees/proj-268-app
- pipeline: .pipeline/PROJ-268-e2e
- db: app_db_proj_268
```

`Goal`, `Current state` and `Next steps` are required. `Workspace` lines labelled `worktree`
or `pipeline` are checked by cairn; other labels are kept as written.

### Resume

Open a new session in the same project. The hook injects the newest open handoff (preferring
the current branch) and lists the other open ones, so you can simply say what you want:
"continue PROJ-268". The agent summarises the goal, what is done and the next step, and waits
for your go-ahead if anything drifted.

To pick explicitly:

```
/cairn:resume PROJ-268
/cairn:resume            # several open tasks: shows a table and asks which one
```

### CLI

```bash
cairn list                    # handoffs of this project, newest first
cairn list --status open      # only the ones nobody has resumed
cairn show PROJ-268            # print the handoff file
cairn show --path             # path of the best match for this directory
cairn resume PROJ-268          # print it with the drift report and mark it resumed
```

Every command accepts `--dir PATH` to act on another directory.

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
- **Lifecycle**: saving again for the same task (or branch) replaces the previous handoff.
  Resuming never deletes; it marks the handoff `resumed` so it is not injected twice.

## Privacy and safety

- Everything stays on your machine. cairn makes no network calls; the hook never runs `gh`.
- Files are `0600`, directories `0700`. No diffs or file contents are stored, only paths,
  branches, SHAs and commit subjects.
- Bodies containing likely secrets (private keys, AWS, GitHub, Slack, OpenAI, Anthropic keys,
  JWTs, `password = ...`) are rejected; the value is never printed.
- The hook always exits 0 and stays silent on errors, so it cannot break a session.

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `CAIRN_HOME` | `~/.cairn` | Root folder for all Stores |
| `CAIRN_HOOK` | on | `off` disables the `SessionStart` hook |
| `CAIRN_HOOK_MAX_AGE` | `7d` | Ignore open handoffs older than this (`d`, `h`, `m`) |
| `CAIRN_AGENT` | `unknown` | Agent name recorded when `--agent` is not given |
| `CAIRN_STORE` | | Use this exact folder as the Store (tests, debugging) |

## Uninstall

```bash
claude plugin uninstall cairn@cairn
rm -rf ~/.cairn        # deletes every saved handoff
```

## Development

```bash
make setup     # Python 3.9 virtualenv with dev tools
make lint      # ruff
make test      # pytest
```

The design is spec-driven: requirements, design decisions and the task plan live in
[`docs/specs/`](docs/specs/README.md) (Vietnamese), and code follows
[`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md). See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
