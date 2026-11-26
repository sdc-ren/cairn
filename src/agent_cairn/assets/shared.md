{{heading}}

Shared at {{shared_at}} by cairn {{version}} from handoff {{id}}. Every path is relative to the
project root of whoever imports it; `~` is that person's home directory. `cairn import`
unpacks the files of this bundle into `{{unpacked}}/`.

{{worktrees}}
{{attachments}}
### How to restore (do this before the next steps)
1. For each worktree above, get the code: clone the remote if the project has no checkout yet,
   then `git fetch` and check out the branch (use `git worktree add <path> <branch>` for a path
   other than `.`). Its HEAD must be the commit listed; if the commit is "not on any remote",
   ask the user to have the sender push it.
2. For a worktree with a patch, apply the uncommitted work on that commit:
   `git -C <path> apply {{unpacked}}/patches/<file>` (add `--3way` if it does not apply
   cleanly). Do not commit it.
3. Copy the attachments to the paths they are listed under:
   `cp -R {{unpacked}}/attachments/. ./`. Ask the user first if that would replace a file
   that already exists.
4. Anything under "Not attached" stays on the sender's machine: ask the user for it when a
   step needs it. Logins, local services, databases and ports under "Environment / how to run"
   must be set up again on this machine.
