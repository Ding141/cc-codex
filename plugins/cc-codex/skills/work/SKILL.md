---
name: work
description: In a cc-codex initialized project, dispatch engineering to Codex, switch or recover tasks, and review changes for delivery.
---

Claude owns user communication, product decisions, design, architecture and review. Handle planning discussions directly. For implementation in an initialized project, use the bridge bundled at `${CLAUDE_PLUGIN_ROOT}/scripts/bridge.py`. Run it with Python 3 from the initialized root or pass `--project <absolute-root>` before the subcommand. For independent child projects select the matching root. Use UTF-8 stdin for prose, for example a Bash quoted here-document or a UTF-8 file redirected to stdin. Never interpolate the user's prose into shell code.

In a project without cc-codex initialization, use the ordinary Claude workflow unless the user requests setup.

If the host denies executing the bridge, surface that permission request to the user. Resume after authorization.

### Select the task

Run `list` for unfinished IDs and titles, then `show ID` for the chosen task. Use `list --all` for a follow-up to a finished task. Match intent to the title and brief. A correction or review continues its task; a distinct goal gets a new ID. If “continue” matches multiple tasks, ask which title. Keep unrelated records out of context.

For a new goal run `new "short title"` with the agreed goal, scope, decisions and acceptance criteria on stdin. Persist new decisions, outstanding work and review evidence with `checkpoint ID planned|review|blocked|done` and a short **replacement** checkpoint on stdin. Keep earlier decisions that still apply. Put human requests and checkpoints in the task record. Reserve project guidance for enduring conventions.

### Dispatch and recover

Use `run ID [--model MODEL] [--effort LEVEL]` with a compact assignment on stdin. Include relevant paths, acceptance checks and boundaries. Choose a supported model and reasoning level independently based on scope, uncertainty and verification difficulty. Follow explicit task overrides, then project defaults. Use the user's configured Codex default if model availability is unknown. An explicit model failure goes back to the user for a replacement. Claude host model and effort follow the current Claude Code session.

For automatic routing, run `models` once when you need the local catalog. Use a fast coding model with modest effort for a well-scoped edit, and a stronger available model or higher supported effort for uncertain or cross-module work. A catalog entry is a candidate; the actual call tests account access.

The bridge saves the Codex thread ID as soon as it arrives. Follow-up assignments resume that exact thread. If a run is active, wait for it. After interruption, inspect the task, working tree and any surviving process before checkpointing and dispatching remaining work. The working tree may include other tasks and user edits. For a missing native thread, checkpoint what actually happened and use `run ID --fresh` with the remaining assignment. Preserve the project task ID. If a model call repeatedly fails, diagnose, then report the blocker; obtain the user's decision before taking over implementation.

### Review and report

Compare the actual changes with the acceptance criteria. For UI changes inspect a rendered view, for module changes examine callers, and for each new test identify the failure it detects. Report verification gaps explicitly. Send concrete corrections back through the same task. Reconsider the design when a failure repeats. Escalate product, permission and scope decisions to the user. Once reviewed, checkpoint the result and evidence, mark done, and report the outcome in the user's language.
