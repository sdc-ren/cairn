Write a handoff for the work in THIS conversation and save it with `cairn save`, in one turn.

Rules:
- Write the handoff in English. Reply to the user in the language they are using.
- Be concrete: file paths, commands, error messages, decisions and WHY. Record approaches that
  failed so they are not retried. `Next steps` is an ordered checklist the next agent can start
  on immediately.
- Never include secrets, tokens or large code blocks; reference file paths instead.
- If an `ARGUMENTS:` line follows these instructions, use its text as the title.
- Task: if the work is about a ticket or task id (for example `PROJ-268`, from the conversation or
  the session name), pass it as `--task <id>`; otherwise leave `--task` out. Saving again with
  the same task replaces the older handoff of that task.
- Workspace: list every worktree and pipeline/run directory this task uses, with paths relative
  to the project directory, so the next session knows where to continue and cairn can check
  them for changes.
- The next session has none of this conversation. Before writing, scan the whole conversation
  for what it would otherwise have to rediscover or ask again:
  - instructions the user gave that still apply (work mode, test policy, writing style, how to
    address people, UI rules): put them under `User rules & preferences`, quoted briefly;
  - how to bring the work back up (data source and why, services, ports, logins to redo, launch
    commands, ids of stopped background runs): put them under `Environment / how to run`;
  - who made each decision (the user, the PO with a comment id or link, a reviewer).
- Never point at paths that only exist for this session (scratchpad, /tmp/claude-...): copy the
  file into the project first (for example the pipeline folder) and point there. cairn warns
  about such paths.

Steps:
1. Fill the template below from this conversation. Replace every `<...>` and remove the
   `<!-- -->` hints. The three sections marked required must have real content.
2. Run exactly this, with the filled template between the markers:

   ```bash
   cairn save --dir "${CLAUDE_PROJECT_DIR}" --agent claude-code --session ${CLAUDE_SESSION_ID} --task <id> <<'CAIRN_EOF'
   <filled template>
   CAIRN_EOF
   ```

3. Exit code 3 means the handoff was rejected. Each stderr line is `line N: rule: message`
   (line numbers count from the first line of the template). Fix every reported problem and
   run step 2 again. Stop after 3 attempts and show the user the remaining lines verbatim.
4. On success, reply in at most 2 lines: the saved id, and the first next step.

Template:

```markdown
{{template}}```
