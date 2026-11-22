---
name: work
description: In a cc-codex initialized project, dispatch engineering to Codex, switch or recover tasks, and review changes for delivery.
---

User request: $ARGUMENTS

Claude owns user communication, design, architecture and review. From the Claude launch project, first run `python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}" status`. Use the returned absolute root for every file read, diff, render, test and review. Load that root's applicable Claude/project guidance. Use absolute file paths and set the shell working directory explicitly (e.g. `git -C "<root>" diff`). For subsequent bridge calls in this operation pass both `--session "${CLAUDE_SESSION_ID}"` and `--project "<returned root>"` before the subcommand. If host access fails, report it before dispatch. Send prose on UTF-8 stdin using literal quoting.

In a project without cc-codex initialization, use the ordinary Claude workflow unless the user requests setup.

If the host denies executing the bridge, surface that permission request to the user. Resume after authorization.

### Select the task

For a bare /cc-codex:work, use only the selected task from status. With no selection, list refs and ask the user to choose or create one. For a selected planned task, recover the brief and execute the remaining assignment. In review, inspect the existing result before considering another dispatch. In running or blocked, reconcile the actual process, changes and blocker first. For done, report the completion checkpoint and wait for a new request.

For a named goal use `list` (or `list --all` for finished work), then `task use ID` for an existing task. Match a correction to its earlier task; clarify ambiguous requests. Use `show ID` for full details. Status-only questions end at reporting. A selection-only request ends after saving the selection.

For a new goal run `new "short title"` with the agreed goal, scope, decisions and acceptance criteria on stdin. Persist new decisions, outstanding work and review evidence with `checkpoint ID planned|review|blocked|done` and a short **replacement** checkpoint on stdin. Keep earlier decisions that still apply. Put human requests and checkpoints in the task record. Reserve project guidance for enduring conventions.

### Dispatch and recover

Use `run ID [--model MODEL] [--effort LEVEL]` with a compact assignment on stdin. Include relevant paths, acceptance checks and boundaries. Choose a supported model and reasoning level independently based on scope, uncertainty and verification difficulty. Follow explicit task overrides, then project defaults. Use the user's configured Codex default if model availability is unknown. An explicit model failure goes back to the user for a replacement. Claude host model and effort follow the current Claude Code session.

For automatic routing, run `models` once when you need the local catalog. Use a fast coding model with modest effort for a well-scoped edit, and a stronger available model or higher supported effort for uncertain or cross-module work. A catalog entry is a candidate; the actual call tests account access.

The bridge saves the Codex thread ID as soon as it arrives. Follow-up assignments resume that exact thread. If a run is active, wait for it. After interruption, inspect the task, working tree and any surviving process before checkpointing and dispatching remaining work. The working tree may include other tasks and user edits. For a missing native thread, checkpoint what actually happened and use `run ID --fresh` with the remaining assignment. Preserve the project task ID. If a model call repeatedly fails, diagnose, then report the blocker; obtain the user's decision before taking over implementation.

### Review and report

Compare the actual changes with the acceptance criteria. For UI changes inspect a rendered view, for module changes examine callers, and for each new test identify the failure it detects. Report verification gaps explicitly. Send concrete corrections back through the same task. Reconsider the design when a failure repeats. Escalate product, permission and scope decisions to the user. Once reviewed, checkpoint the result and evidence, mark done, and report the outcome in the user's language.
