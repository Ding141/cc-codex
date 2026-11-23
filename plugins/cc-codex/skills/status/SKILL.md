---
name: status
description: Show the cc-codex project selection, last environment check, and task checkpoints. Read-only.
argument-hint: "[project name or path]"
allowed-tools: Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *)
model: haiku
---

Request: $ARGUMENTS

Run, from the directory Claude was started in, using whichever interpreter exists (`python`, `python3`, or `py -3`):

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}" status [TARGET]
```

Pass a project name or absolute path as one literal argument when the user named a project. Also run `project list` when the user asks what projects are registered.

Report in the user's language, briefly:

- the absolute project root and whether it is initialized and Codex-verified;
- the last check time, model and effort;
- the selected task: ref, title, status, and its saved checkpoint or last Codex result;
- other open tasks by ref and title.

Attribute Codex's output to Codex and keep Claude's own review separate. If the directory is uninitialized, say so and point to `/cc-codex:init`. If no task is selected, point to `task list` / `task use`.

This command only reads stored state. Do not dispatch, retry, or review anything.
