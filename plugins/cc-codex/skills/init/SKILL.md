---
name: init
description: Initialize or recheck the Claude to Codex workflow in the current project and optionally start a task.
disable-model-invocation: true
argument-hint: "[task]"
---

Initialize the project selected by the user. Optional task text: $ARGUMENTS

1. Identify the intended project directory. Inspect existing root guidance, including `.claude/CLAUDE.md`, `CLAUDE.local.md` and `AGENTS.override.md` when present. Surface specific conflicts with delegation or permissions. Keep each independent project in its own directory. Preserve existing instructions and user changes.
2. Resolve the target with `python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}" status` from the Claude launch project, unless the user named another directory. Read target instructions there. Run the same bridge with `--session "${CLAUDE_SESSION_ID}" --project "<absolute target root>" init` (use `python3` or `py -3` when appropriate). Pass requested Codex `--model` and `--effort`. Success registers this root and selects it for the session. Wait for the real probe. Diagnose failures before starting the optional task.
3. Report the tested project and configuration. With an attached task, invoke cc-codex:work and carry it forward immediately. With no task, finish at the readiness report.
