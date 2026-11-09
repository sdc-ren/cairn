Let `DIR` be `"${CLAUDE_PROJECT_DIR}"` in every command below.

1. If an `ARGUMENTS:` line names a task or id, run `cairn resume --dir DIR <task>` and go to
   step 4.
2. If the user only asked to continue and a block starting with `=== cairn handoff` is already in
   your context (injected at session start), use it, run nothing, and go to step 4.
3. Otherwise run `cairn list --dir DIR --status open`:
   - no handoff: run `cairn list --dir DIR --limit 5`, show it, say nothing is open, and stop;
   - exactly one: run `cairn resume --dir DIR <its task or id>`;
   - several: show the table as it is and ask the user which task to continue. Stop and wait;
     after they answer, run `cairn resume --dir DIR <task>`.
   If the user only asked what is open, show the table and stop without resuming anything.
4. Follow the preamble in the output exactly: summarise for the user, in their language, the
   goal, what is done, open questions and the exact next step. Continue in the worktrees listed
   under Workspace. If any drift line is a warning, wait for the user to confirm before editing
   code.
