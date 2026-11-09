# Security

cairn stores agent handoffs on the local disk and runs as a Claude Code hook in every new
session, so bugs that leak data, run unintended commands, or break sessions matter.

## Reporting a vulnerability

Please report privately through GitHub:
**Security → Report a vulnerability** on <https://github.com/sdc-ren/cairn>.
Do not open a public issue. You should get a reply within a week.

## Scope

In scope: secrets reaching a saved handoff or terminal output, files or directories created
with wider permissions than `0600`/`0700`, command injection through branch names, paths or
handoff content, and the hook failing a session or calling the network.

## Design notes

- No network access; the `SessionStart` hook never runs `gh`.
- Subprocesses use argument lists, never a shell, and always have a timeout.
- Secret patterns are checked before saving; matches are reported by line and pattern name
  only.
