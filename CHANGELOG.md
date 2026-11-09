# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

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
