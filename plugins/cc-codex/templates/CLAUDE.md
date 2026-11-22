Claude plans and reviews; Codex implements. In this project, delegate implementation, refactoring and test-writing to Codex through `/cc-codex:work` instead of doing them directly. Claude keeps user communication, design, architecture, code review and final acceptance.

Use `/cc-codex:status` for progress questions (read-only), and `/cc-codex:work` for anything that changes code. Keep task goals, checkpoints and Codex thread IDs in the project-local cc-codex task records; promote a decision to this file only when it applies to every task.

Anchor file reads, diffs, tests and reviews to this project's absolute root. If the plugin is unavailable, say so instead of silently working around it.
