---
name: status
description: Show the selected cc-codex project, last environment check, task checkpoint and other open tasks.
argument-hint: "[project name or absolute path]"
---

Request: $ARGUMENTS

From the Claude launch project, run Python 3 with `"${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}" status`. Pass an optional project name or absolute path as a single literal argument. Use safe shell quoting for user values.

Report the absolute project path, last recorded probe and timestamp, selected task reference/title/state, its checkpoint, and other open tasks. Attribute Codex's result to Codex and distinguish it from Claude's review. For an uninitialized directory, indicate the init command. If no task is selected, point to task list/use. This command reads stored state only; finish after reporting it.
