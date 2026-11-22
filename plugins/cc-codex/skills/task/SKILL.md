---
name: task
description: List, select or create a cc-codex task without starting engineering work.
argument-hint: "list [--all] | use <T-number or ID> | new <title>"
disable-model-invocation: true
---

Request: $ARGUMENTS

Run Python 3 with `"${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}"` from the Claude launch project. The bridge resolves the session's selected root. Treat each title as one safely quoted literal argument.

- With no arguments or `list`, run `task list`; forward `--all` if requested. Display refs, titles, states and the selection marker.
- `use T2` (or full task ID): run `task use T2`. Show the selected project and task, last checkpoint and next known action.
- `new TITLE`: run `task new TITLE`. The title is the initial brief. Report the new selected task ref and planned state. Additional requirements can follow in conversation.
- For incomplete arguments, show the supported forms. A bare `/cc-codex:work` can later resume the selected task.

Finish after reporting the result. Listing and selection do not dispatch, retry, cancel or review engineering work.
