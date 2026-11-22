"""Invoke the Codex CLI without a shell and forward only the final reply."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


def launcher():
    """Return the argv prefix that starts the Codex CLI on this machine.

    Order: an explicit CODEX_BIN override, a native executable, then the
    npm shim on Windows (resolved to its node entry point so no shell is used).
    """
    override = os.environ.get("CODEX_BIN")
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return [str(path)]
        raise ValueError(f"CODEX_BIN does not point to a file: {override}")
    for name in ("codex.exe", "codex"):
        program = shutil.which(name)
        if program:
            return [program]
    if os.name == "nt":
        shim = shutil.which("codex.cmd")
        node = shutil.which("node")
        if shim and node:
            entry = Path(shim).parent / "node_modules/@openai/codex/bin/codex.js"
            if entry.is_file():
                return [node, str(entry)]
    raise ValueError("Codex CLI not found. Install it (npm i -g @openai/codex) and check `codex --version`.")


def model_catalog():
    try:
        result = subprocess.run([*launcher(), "debug", "models"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=45)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Model catalog timed out. Use an explicit model or the CLI default.") from exc
    if result.returncode:
        raise ValueError("Model catalog unavailable. Use an explicit model or the CLI default.")
    models = json.loads(result.stdout)["models"]
    return [{"id": model["slug"], "description": model.get("description"),
             "efforts": [level["effort"] for level in model.get("supported_reasoning_levels", [])]}
            for model in models if model.get("visibility") == "list"]


def execute(root, prompt, model=None, effort=None, thread=None, on_thread=None, probe=False):
    """Run one Codex turn; return its final agent message.

    `thread` resumes an existing Codex thread. `on_thread` is called as soon as
    the thread ID is known so the caller can persist it before a crash.
    """
    args = [*launcher(), "exec", "--json", "-C", str(root), "-s", "workspace-write",
            "--skip-git-repo-check"]
    if model:
        args.extend(["-m", model])
    if effort:
        args.extend(["-c", "model_reasoning_effort=" + json.dumps(effort)])
    if probe:
        args.append("--ephemeral")
    if thread:
        args.extend(["resume", str(uuid.UUID(thread))])
    args.append("-")
    completed = False
    message = error = session = None
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as errors:
        source.write(prompt.encode("utf-8"))
        source.seek(0)
        with subprocess.Popen(args, cwd=root, stdin=source, stdout=subprocess.PIPE,
                              stderr=errors, text=True, encoding="utf-8", errors="replace") as process:
            try:
                for line in process.stdout:
                    line = line.strip()
                    if not line.startswith("{"):
                        continue  # Codex logs diagnostics on stdout; ignore non-events.
                    event = json.loads(line)
                    kind = event.get("type")
                    if kind == "thread.started":
                        session = str(uuid.UUID(event["thread_id"]))
                        if thread and thread != session:
                            raise ValueError("Codex returned a different thread on resume.")
                        if on_thread:
                            on_thread(session)
                    elif kind == "item.completed" and event["item"]["type"] == "agent_message":
                        message = event["item"]["text"]
                    elif kind == "turn.completed":
                        completed = True
                    elif kind in ("error", "turn.failed"):
                        error = event.get("message") or event.get("error", {}).get("message")
                code = process.wait()
            finally:
                if process.poll() is None:
                    process.kill()
        if code or not (completed and session and message):
            errors.seek(0, os.SEEK_END)
            errors.seek(max(0, errors.tell() - 1800))
            detail = error or errors.read().decode("utf-8", "replace").strip()
            raise RuntimeError(f"Codex exit {code}: {detail or 'incomplete JSONL turn'}")
    return message
