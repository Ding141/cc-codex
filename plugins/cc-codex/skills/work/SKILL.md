---
name: work
description: Plan with Claude, hand implementation to Codex, then review and deliver. Also lists or selects projects and tasks.
argument-hint: "[what to build, fix, continue or review]"
allowed-tools: Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py *) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py *) Bash(py -3 ${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py *) Bash(git -C * *)
---

Request: $ARGUMENTS

Claude owns user communication, design, architecture and review. Codex implements and runs tests. Never write the implementation yourself unless the user explicitly takes it back.

## Bridge calls

Use whichever interpreter exists on this machine: `python`, else `python3`, else `py -3`. Every call takes the same prefix:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}" --project "<root>"
```

`--project` may be omitted on the first call of an operation; the session selection is then used. Output is one JSON document. Pass prose bodies on UTF-8 stdin.

Bridge subcommands: `status`, `init`, `models`, `project list`, `project use TARGET`, `task list [--all]`, `task show REF`, `task use REF`, `task new TITLE`, `task run REF [--model M] [--effort E] [--fresh]`, `task checkpoint REF planned|review|blocked|done`.

## 1. Resolve the project

Run `status` first. Use the returned absolute root for every read, diff, test and review (`git -C "<root>" ...`), and for every later bridge call.

- Not initialized → tell the user to run `/cc-codex:init` (or run the init flow if they asked for setup).
- The user names another project → run `project list`, then `project use "<absolute root>"`. Switching only changes where this session works; the shell may still start elsewhere.

## 2. Pick the task

- No argument: use only the selected task from `status`. In `planned`, resume from its brief. In `review`, inspect the existing result before dispatching again. In `running` or `blocked`, reconcile the real process and working tree first. In `done`, report and wait for a new request.
- Continuation or correction of earlier work: `task list` (or `--all`), then `task use REF`. Match a fix to its original task; ask when ambiguous.
- New goal: `task new "short title"` with goal, scope, decisions and acceptance criteria on stdin. Persist progress with `task checkpoint REF STATUS` and a short replacement summary on stdin.

Keep decisions, progress and thread IDs in task records; put only enduring conventions in project guidance.

## 3. Dispatch

Send `task run REF` a compact assignment on stdin: relevant paths, acceptance checks, boundaries. Pick `--model` / `--effort` from `models` when you need the local catalog — a fast model and modest effort for a scoped edit, a stronger model or higher effort for uncertain or cross-module work. Honour explicit user choices first. If unsure what the account can call, omit both and let the Codex CLI default apply.

The bridge saves the Codex thread ID as soon as it arrives; later runs resume that thread. On failure the task becomes `blocked` with the error saved. After an interruption, check the process and working tree, `task checkpoint` what actually happened, then dispatch the remainder. If the native thread is gone, use `--fresh` on the same task.

If the bridge call is denied by the host, surface the permission request instead of working around it.

## 4. Review and report

Compare the real changes with the acceptance criteria: read the diff, run the tests, render UI changes, check callers of changed modules. Report gaps explicitly and send corrections back through the same task. Escalate product, scope and permission choices to the user.

When done, checkpoint the evidence and mark `done`, then report in the user's language: what changed, what was verified, what remains.
