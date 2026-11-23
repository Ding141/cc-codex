---
name: work
description: Plan with Claude, hand implementation to Codex, then review and deliver. Also lists or selects projects and tasks.
argument-hint: "[what to build, fix, continue or review]"
allowed-tools: Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) Bash(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) PowerShell(py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" *) Bash(git -C *) PowerShell(git -C *)
---

Request: $ARGUMENTS

Claude owns user communication, design, architecture and acceptance. Codex works as an autonomous worker: it implements, researches facts, writes and runs tests, and returns a structured report. Never write the implementation yourself unless the user explicitly takes it back.

Claude tokens are the expensive part of this loop. Every Claude turn re-reads the whole conversation, so aim for few turns, and do not repeat work Codex has already done and reported.

## Bridge calls

Use whichever interpreter exists: `python`, else `python3`, else `py -3`. Every call is **one plain command** in this form:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py" --session "${CLAUDE_SESSION_ID}" --project "<root>" <subcommand>
```

Do not use variables, pipes, `;`, redirection or encoding setup: only this exact form matches the skill's `allowed-tools` rules; any other form needs a separate permission check. Pass prose bodies as files: write them with the Write tool under `<root>/.cc-codex/briefs/`, then add `--input "<file>"`.

Subcommands: `status`, `models`, `project list`, `project use TARGET`, `task list [--all]`, `task show REF`, `task use REF`, `task new TITLE --input F`, `task run REF [--input F] [--model M] [--effort E] [--fresh] [--render PAGE]`, `task checkpoint REF planned|review|blocked|done --input F`, `render PAGE [--width W]... [--scheme light|dark]...`.

## 1. Resolve the project

Run `status` once. Use its absolute root for every later call, read and diff. If the project is not initialized, point to `/cc-codex:init`. If the user names another project, run `project list`, then `project use "<absolute root>"`.

## 2. Pick the task

- No argument: continue the selected task from `status`. In `review`, assess the stored report before dispatching again. In `running` or `blocked`, reconcile the real process and working tree first, then checkpoint. In `done`, report and wait.
- A fix to earlier work: `task list`, then `task use REF`. Ask when the match is ambiguous.
- A new goal: settle the acceptance criteria with the user when they are unclear. Then write **one** brief file and run `task new "short title" --input <brief>`. The brief is the whole first assignment: goal, scope and boundaries, design decisions (layout, tone, visual direction: Claude's part), acceptance criteria written so they can be checked, and the checks to run. Leave engineering details and fact-finding to Codex.

## 3. Dispatch

- First run of a task: `task run REF` with no `--input`; the bridge sends the brief and the worker contract. Later runs: `--input` with only the new instructions, because the Codex thread keeps its context.
- For UI work, add `--render <page>`. The bridge takes desktop and mobile screenshots in light and dark after Codex finishes. Codex cannot run browsers in its sandbox, so screenshots come from here.
- Codex runs take minutes. **Start `task run` with `run_in_background: true`** and tell the user it is running. You are notified when it finishes. Do not poll, sleep, or read Codex logs in the meantime.
- `--model` / `--effort`: honour the user's choice. Otherwise omit both (the Codex default), or pick a higher effort for uncertain cross-module work. Call `models` only when the user asks which models exist.
- The bridge saves the thread ID immediately and resumes it on later runs. On failure the task becomes `blocked` with the error saved. If the native thread is gone, use `--fresh` on the same task.
- If the host denies a bridge call, surface the permission request instead of working around it.

## 4. Review

The result holds `report` (outcome, summary, changed_files, checks, criteria with evidence, open_questions), `git_status` when the project is a Git repository, and `screenshots` when requested. Review in this order and stop as soon as you have enough to decide:

1. Read the report. Any criterion that is `unmet` or `unverified`, a failed check, or an open question decides the next step.
2. Compare `changed_files` with `git_status`. Look at diffs (`git -C "<root>" diff -- <file>`) for risky or contract-level changes, not whole generated files.
3. For UI work, read the screenshots: start with one desktop and one mobile shot, and open more only when something looks wrong. Judging the look is Claude's part.
4. Re-run a check or spot-check a fact yourself only when the evidence is missing or doubtful. Do not repeat Codex's web research or test runs by default.

Collect every correction into one fix file and send it in a single `task run REF --input <fix>`. Send product, scope and permission questions to the user, not to Codex.

## 5. Deliver

Run `task checkpoint REF done --input <file>` with a short evidence summary. Then report in the user's language: what changed, what was verified and by whom (Codex's report or Claude's own check), and what remains.
