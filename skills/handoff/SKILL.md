---
name: handoff
description: >-
  Save a handoff of the current task so a new session (another account, another agent, or
  tomorrow) can continue without the user re-explaining. Use when the user wants to stop,
  switch account, is running out of usage or quota, or says "handoff", "save context",
  "wrap up for the next session", "bàn giao", "lưu ngữ cảnh", "sắp hết quota",
  "đổi tài khoản", "lưu lại để làm tiếp".
argument-hint: "[title]"
allowed-tools: Bash(cairn save *)
---
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
# <short title of the task>

## Goal
<!-- required: what the user wants and what "done" means (tests, behaviour) -->

## Current state
<!-- required: what is finished, half-done or broken right now -->

## Next steps
<!-- required: ordered checklist the next agent can start on immediately -->
- [ ] <first step>

## Decisions
<!-- each decision with its reason -->

## Tried / didn't work
<!-- approaches that failed and why, so they are not retried -->

## Open questions
<!-- questions only the user can answer -->

## Key files
<!-- paths that matter, one per line -->

## Workspace
<!-- one "- label: value" per line; cairn checks worktree and pipeline paths, e.g.
- worktree: .worktrees/proj-268-app
- pipeline: .pipeline/PROJ-268
- db: app_db_proj_268 -->
```
