---
name: init
description: Initialize or recheck the Claude to Codex workflow in the current project and optionally start a task.
disable-model-invocation: true
argument-hint: "[task]"
---

Initialize the project selected by the user. Optional task text: $ARGUMENTS

1. Identify the intended project directory. Inspect existing root guidance, including `.claude/CLAUDE.md`, `CLAUDE.local.md` and `AGENTS.override.md` when present. Surface specific conflicts with delegation or permissions. Keep each independent project in its own directory. Preserve existing instructions and user changes.
2. From that project directory run `python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" init` (use `python3` or `py -3` when appropriate). If the user selects a Codex model or reasoning level, pass the applicable `--model` and `--effort`. This makes one real Codex call and maintains the delimited sections of the project instructions. Wait for its exit status. Diagnose a failed check, retain the optional task in the conversation and only start it after a successful check. Never simulate a successful probe by writing its output yourself.
3. Report the tested project and configuration. With an attached task, invoke cc-codex:work and carry it forward immediately. With no task, finish at the readiness report.
