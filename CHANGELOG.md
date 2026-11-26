# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `cairn share` packs a handoff for another person: your local paths are rewritten, the
  session and transcript are left out, and the bundle carries the uncommitted work of each
  worktree as a patch, the files git does not carry, remotes, pushed state and open PRs.
  `cairn import` receives it. `/cairn:handoff` runs it when you say the handoff is for someone
  else; `/cairn:resume` imports a bundle you give it.
- The handoff skill asks for project-relative paths and a complete `Key files` list.

### Changed

- `/cairn:resume` without a task always shows every saved handoff, open and already resumed,
  and asks which to continue, even when there is only one or the hook already loaded one.
- A new session no longer loads the newest handoff by default: it gets a short list of open
  handoffs, and the one you mention by task or ID in your message is loaded (new
  `UserPromptSubmit` hook). Loading in full still happens after `/clear` or when the handoff is
  less than an hour old (`CAIRN_HOOK_FULL_WINDOW`). Before, most sessions started on other work
  received the wrong handoff and marked it resumed.
- The handoff template adds `User rules & preferences` and `Environment / how to run`, and asks
  who made each decision.

### Added

- `cairn clean` deletes saved handoffs in bulk: the `resumed` ones by default, or
  `--status open|all`, optionally `--older-than 3d`; it shows the table and asks first
  (`--dry-run`, `--yes`). `/cairn:resume clean` runs it from Claude Code.
- `cairn list` has a `RESUMED` column: when a handoff was last resumed, and how often.
- `save` warns about paths that only exist in the writing session (scratchpad, `/tmp/claude-…`).
- `save --session` records the writing session's transcript path; the resume text tells the
  agent to search it when a detail is missing.

## [0.2.1] - 2026-11-09

### Changed

- The package is published as `cairn-handoff` on PyPI and npm (`pipx install cairn-handoff`,
  `uvx --from cairn-handoff cairn`). PyPI refused `agent-cairn` as too similar to an existing
  project. The command is still `cairn` and the import name is still `agent_cairn`.

## [0.2.0] - 2026-11-09

First public release.

### Added


- `cairn capture`, `cairn template`, `cairn doctor`; `-h` on every command.
- `save --title`, `--redact`, `--dry-run`, `--no-gh`; warnings for missing recommended sections
  and long bodies.
- `resume --peek`, `--brief`, `--json`, `--any-branch`; selection by task, ID or unique ID prefix.
- `list --here`, `--branch`, `--json`.
- Captured state includes upstream, ahead/behind, stashes, open pull requests (via `gh`) and the
  other worktrees of the repository.
- Drift reports uncommitted files that are still, newly or no longer modified, a changed branch,
  and falls back to the branch tip when the saved worktree is gone.
- Automatic cleanup: resumed handoffs after 7 days, unclaimed ones after 30.
- `PreCompact` and post-compaction hooks keep reasoning through compaction and remind you to save.
- Skills are generated from `src/agent_cairn/assets`; CI checks types, duplication, dead code,
  module size, 85% coverage and that every automated requirement has a test.
- Evaluation scenario and rubric for handoff quality (`docs/specs/eval`).


- `cairn init`: standalone skills `/cairn-handoff` and `/cairn-resume` for Claude Code without
  the plugin (`--global`, `--force` with `.bak`, `--dry-run`), or a block in `AGENTS.md`
  (`--agent agents-md`); `--uninstall` removes only what cairn wrote.
- `cairn prompt handoff|resume`: the same instructions, written for any agent.
- `cairn rm`: delete handoffs after confirmation (`--yes` when not on a terminal).
- `resume --copy`: copy the output with pbcopy, wl-copy or xclip.
- `doctor` checks the clipboard and whether `cairn` is on `PATH`.
- `package.json`: run without installing via `npx github:sdc-ren/cairn <command>`; the version
  is kept in sync by `scripts/gen_plugin.py`.

### Fixed


- `bin/cairn` works when called through a symlink (npm's `node_modules/.bin`, a link on `PATH`).
- CI installs the wheel with pip, pipx and uv; `release.yml` publishes to PyPI with Trusted
  Publishing when a `v*` tag is pushed.

## [0.0.1] - 2026-11-09

First preview, used daily by the author.

### Added

- Claude Code plugin with `/cairn:handoff` and `/cairn:resume` skills and a `SessionStart`
  hook that injects the open handoff into new sessions.
- `cairn save`: validates the body (title, Goal, Current state, Next steps), rejects likely
  secrets without printing them, captures git facts and the Workspace section.
- Store under `~/.cairn/<project>-<hash>/`; works in git repositories and in plain folders
  that hold several repositories.
- One handoff per task (`--task`), else per branch; saving again replaces the previous one.
- Drift report on resume: new commits, rewritten history, missing HEAD, and per Workspace
  worktree or pipeline changes.
- `cairn list`, `cairn show`, `cairn resume`, `cairn version`; `--dir` on every Store command.
