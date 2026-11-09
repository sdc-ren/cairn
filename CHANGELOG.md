# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased] - 0.1.0.dev0

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
