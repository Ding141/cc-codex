---
name: project
description: List registered cc-codex projects or select the working project for this Claude session.
argument-hint: "list | use <name or absolute path>"
disable-model-invocation: true
---

Request: $ARGUMENTS

Use Python 3 and the bridge `"${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}"` from the Claude launch project. Treat names and paths as literal arguments and quote them for the shell.

- With no arguments or `list`, run `project list`. Show names, full paths and which project is current.
- For `use TARGET`, first run `status TARGET` to resolve the root and confirm initialization. Confirm Claude can read the target project's instructions using the host's ordinary file tools. If access is unavailable, leave the selection as it is and tell the user how to open Claude in that directory. Resolve ambiguous names by asking for a listed path. Once accessible, run `project use ABSOLUTE_ROOT`, then report its root, selected task and checkpoint. Finish at selection.
- For any other input, show the two supported forms.

Switching changes this plugin's session target. Use the selected root and its applicable project instructions for future work and reviews. A shell or host tool may still start in the original directory.
