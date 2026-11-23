---
name: init
description: Set up or re-check the Claude-to-Codex link in a project, then optionally start the first task.
argument-hint: "[task]"
disable-model-invocation: true
allowed-tools: Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *)
---

Optional first task: $ARGUMENTS

Goal: make this project ready for Claude-plans / Codex-builds work, or confirm it already is.

1. Decide the target directory: the directory Claude was started in, unless the user named another one. Read any existing `CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md` or `AGENTS.override.md` there and mention anything that conflicts with delegation.
2. Run the bridge (prefix every call with the interpreter that exists on this machine: `python`, else `python3`, else `py -3`):

   `python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}" status`

   Then initialize the target with the same `--session` flag plus `--project "<absolute target root>"` and the subcommand `init`. Pass `--model` / `--effort` only if the user asked for a specific Codex configuration. Keep each call one plain command (no variables, pipes or `;`) so it matches this skill's `allowed-tools` rules.
3. The init run is a real Codex call: it has Codex echo a random token through a temp file and its reply. Report the tested root, model and effort when it succeeds.

On failure, diagnose before retrying: `codex login status`, `codex --version`, Python availability, write permission in the project. The bridge refuses to dispatch until init succeeds; a failed re-init keeps the old tasks.

4. With a task attached, continue in `/cc-codex:work` immediately. Without one, stop at the readiness report.
