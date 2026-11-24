"""cc-codex bridge: project setup, task records and Codex dispatch.

Every command prints one JSON document to stdout.

    bridge.py [--session ID] [--project ROOT] models
    bridge.py [--session ID] [--project ROOT] status [TARGET]
    bridge.py [--session ID] [--project ROOT] init [--model M] [--effort E]
    bridge.py [--session ID] [--project ROOT] project list
    bridge.py [--session ID] [--project ROOT] project use TARGET
    bridge.py [--session ID] [--project ROOT] task list [--all]
    bridge.py [--session ID] [--project ROOT] task show REF
    bridge.py [--session ID] [--project ROOT] task use REF
    bridge.py [--session ID] [--project ROOT] task new TITLE [--input FILE]
    bridge.py [--session ID] [--project ROOT] task checkpoint REF STATUS [--input FILE]
    bridge.py [--session ID] [--project ROOT] task run REF [--model M] [--effort E] [--fresh]
                                              [--input FILE] [--render PAGE]
    bridge.py [--session ID] [--project ROOT] render PAGE [--width W]... [--scheme S]...

Text bodies (brief, checkpoint, assignment) come from --input FILE, or UTF-8 stdin with --input -.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
import uuid

import subprocess

from codex_cli import execute, model_catalog
import navigation
import render


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
REPORT_SCHEMA = TEMPLATES / "report.schema.json"
BEGIN = b"<!-- cc-codex:begin -->"
END = b"<!-- cc-codex:end -->"
STATE = ".cc-codex"
STATUSES = ("planned", "running", "review", "blocked", "done")

# Sent once at the start of every Codex thread. Resumed turns inherit it.
WORKER = """\
You are the implementation worker for this task. Claude planned it and will review your report; the user talks only to Claude.
Work on your own until every acceptance criterion is met or you are blocked: plan the steps, implement, add or update tests, run them, fix failures, then check the diff against each criterion. Choose engineering details yourself. Stop and report instead of guessing about product behaviour, public interfaces or scope.
When the work depends on facts (dates, versions, API behaviour), verify them yourself and name the source in the evidence, so Claude does not have to research them again.
Do not start browsers or other GUI programs (Chrome, Edge, Firefox, Playwright, Electron), even headless, and do not download browsers. They cannot run in this sandbox, and their crashes open error dialogs on the user's desktop. Check UI work statically (HTML parsing, jsdom, unit tests); the bridge takes screenshots for Claude after you finish.
Your final reply is a JSON report: outcome, summary, changed_files, checks (each command you ran and whether it passed), criteria (each acceptance criterion: met, unmet or unverified, with concrete evidence), open_questions. Write the text in the language of the brief and keep it short."""


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, data):
    if path.is_symlink():
        raise ValueError(f"Refusing to replace symlink: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as pending:
        temp = Path(pending.name)
        try:
            pending.write(data)
            pending.flush()
            os.fsync(pending.fileno())
        except BaseException:
            pending.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        if path.exists():
            temp.chmod(path.stat().st_mode)
        elif os.name != "nt":
            umask = os.umask(0)
            os.umask(umask)
            temp.chmod(0o666 & ~umask)  # mkstemp creates 0600; new files should follow the umask
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def save(path, record):
    atomic_write(path, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode())


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def probe_directory(state):
    # Inherit the project ACL. Windows TemporaryDirectory grants owner-only
    # access, while Codex may run its filesystem tools as a sandbox account.
    probe = state / ("probe-" + uuid.uuid4().hex)
    probe.mkdir()
    try:
        yield probe
    finally:
        shutil.rmtree(probe, ignore_errors=True)


@contextmanager
def writer(state):
    # One Codex writer at a time per worktree. The OS releases the lock on exit.
    with (state / "writer.lock").open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("Another cc-codex operation is active in this project.") from exc
        yield


def instruction(path, content):
    """Return file bytes with the cc-codex block replaced or appended."""
    if path.is_symlink():
        raise ValueError(f"Inspect linked instructions manually: {path}")
    old = path.read_bytes() if path.exists() else b""
    old.decode("utf-8-sig")  # Reject incompatible encodings; preserve hand-written bytes.
    newline = b"\r\n" if b"\r\n" in old else b"\n"
    block = newline.join([BEGIN, *content.splitlines(), END])
    if BEGIN in old or END in old:
        if old.count(BEGIN) != 1 or old.count(END) != 1 or old.index(BEGIN) > old.index(END):
            raise ValueError(f"Ambiguous cc-codex markers in {path}")
        left, rest = old.split(BEGIN)
        _, right = rest.split(END)
        return left + block + right
    return old + (newline * 2 if old else b"") + block + newline


def initialize(root, state, args):
    """Probe Codex end to end, then write project guidance.

    The readiness marker is written before the probe and only replaced with a
    successful result afterwards, so a failed probe keeps dispatch blocked.
    """
    readiness = state / "project.json"
    save(readiness, {"ready": False, "checked": timestamp(), "error": None})
    instructions = {}
    for name in ("CLAUDE.md", "AGENTS.md"):
        path = root / name
        if name == "CLAUDE.md" and not path.exists() and (root / ".claude/CLAUDE.md").is_file():
            path = root / ".claude/CLAUDE.md"
        if name == "AGENTS.md" and (root / "AGENTS.override.md").is_file():
            path = root / "AGENTS.override.md"
        original = path.read_bytes() if path.exists() else None
        content = instruction(path, (TEMPLATES / name).read_bytes())
        if name == "CLAUDE.md" and not path.exists() and (root / "AGENTS.md").is_file():
            content = b"@AGENTS.md\n\n" + content
        instructions[path] = (original, content)

    with probe_directory(state) as probe:
        token = secrets.token_hex(16)
        (probe / "input.txt").write_text(token, encoding="ascii")
        relative = probe.relative_to(root).as_posix()
        reply = execute(root, f"Environment check. Read {relative}/input.txt. Write its exact "
                        f"value to {relative}/output.txt in UTF-8. Modify only that output. "
                        "Reply with only the value you read.", args.model, args.effort, probe=True)
        output = probe / "output.txt"
        if not output.is_file():
            raise ValueError(f"Probe failed: Codex did not create output.txt. Reply: {reply[:800]}")
        if output.read_text(encoding="utf-8-sig").strip() != token:
            raise ValueError("Probe failed: the contents of output.txt differ from input.txt.")
        if token not in reply:
            raise ValueError(f"Probe failed: the reply omitted the value read. Reply: {reply[:800]}")

    for path, (original, data) in instructions.items():
        current = path.read_bytes() if path.exists() else None
        if current != original:
            raise ValueError(f"{path} changed during the probe. Retry with the latest instructions.")
        if original != data:
            atomic_write(path, data)
    result = {"ready": True, "checked": timestamp(), "error": None,
              "probe_model": args.model or "CLI default",
              "probe_effort": args.effort or "CLI default"}
    save(readiness, result)
    return result


def stdin_text(required=True, source=None):
    """Read a prose body from `--input FILE`, or from stdin for `--input -`.

    A file keeps the shell command a single plain call, which permission
    rules can match without pipes, variables or console-encoding setup.
    Stdin is never read implicitly: under an agent shell it is an open pipe
    that never closes, so an implicit read would hang the command.
    """
    body = ""
    if source == "-":
        body = sys.stdin.buffer.read().decode("utf-8-sig").strip()
    elif source:
        try:
            body = Path(source).expanduser().read_bytes().decode("utf-8-sig").strip()
        except OSError as exc:
            raise ValueError(f"Cannot read --input file: {source}") from exc
        except UnicodeDecodeError as exc:
            raise ValueError(f"--input file is not UTF-8: {source}") from exc
    if not body and required:
        raise ValueError("Expected a UTF-8 body: pass --input FILE (or --input - for stdin).")
    return body


def parse_report(message):
    try:
        report = json.loads(message)
    except (TypeError, ValueError):
        return {"raw": message}
    return report if isinstance(report, dict) else {"raw": message}


def git_changes(root, limit=40):
    """Short working-tree status, or None outside a Git repository."""
    try:
        result = subprocess.run(["git", "-C", str(root), "status", "--short",
                                 "--untracked-files=all"], capture_output=True, timeout=20,
                                text=True, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    lines = result.stdout.splitlines()
    return lines[:limit] + ([f"... {len(lines) - limit} more"] if len(lines) > limit else [])


def screenshots(root, state, target, widths=None, schemes=None, height=None):
    shots = state / "shots"
    if shots.is_symlink():
        raise ValueError("Use project-local cc-codex state.")
    for old in shots.glob("*.png") if shots.is_dir() else ():
        old.unlink()
    return render.render(root, target, shots, widths=widths or render.WIDTHS,
                         schemes=schemes or render.SCHEMES, height=height)


def task_records(state, migrate=False):
    """Load task records, giving pre-0.2 records deterministic T-numbers."""
    records = []
    for path in sorted((state / "tasks").glob("*.json")):
        task = read(path)
        if task["id"] != path.stem or not re.fullmatch("[a-f0-9]{32}", path.stem):
            raise ValueError(f"Task record ID mismatch: {path.name}")
        records.append(task)
    used = {t["number"] for t in records if "number" in t}
    number = 0
    for task in records:
        if "number" not in task:
            number += 1
            while number in used:
                number += 1
            task["number"] = number
            if migrate:
                save(state / "tasks" / (task["id"] + ".json"), task)
    return records


def task_summary(task):
    return {"ref": f"T{task['number']}",
            **{key: task[key] for key in ("id", "title", "status", "updated")}}


def resolve_task(state, ref):
    if re.fullmatch("[a-f0-9]{32}", ref):
        path = state / "tasks" / (ref + ".json")
        if path.is_file():
            task = read(path)
            if task["id"] != ref:
                raise ValueError(f"Task record ID mismatch: {path.name}")
            if "number" in task:
                return task
    for task in task_records(state):
        if ref == task["id"] or ref.upper() == f"T{task['number']}":
            return task
    raise ValueError(f"Unknown task {ref}. Use task list --all in this project.")


def project_status(root, session):
    state = root / STATE
    selected = navigation.selected_task(session, root)
    records = sorted(task_records(state), key=lambda t: t["updated"], reverse=True)
    task = next((t for t in records if t["id"] == selected), None)
    details = None
    if task:
        details = {**task_summary(task), **{key: task[key] for key in
                   ("brief", "result", "checkpoint", "error") if task.get(key)}}
    marker = state / "project.json"
    probe = read(marker) if marker.is_file() else None
    return {"project": root.name, "root": str(root), "initialized": marker.is_file(),
            "ready": bool(probe and probe.get("ready")), "last_probe": probe,
            "selected": details,
            "open_tasks": [task_summary(t) for t in records
                           if t["id"] != selected and t["status"] != "done"]}


def require_ready(state):
    marker = state / "project.json"
    probe = read(marker) if marker.is_file() else None
    if not (probe and probe.get("ready")):
        raise ValueError("Run /cc-codex:init successfully before dispatch.")


def task_new(state, session, title, source=None):
    records = task_records(state, migrate=True)
    (state / "tasks").mkdir(exist_ok=True)
    task = {"id": uuid.uuid4().hex,
            "number": max((t["number"] for t in records), default=0) + 1,
            "title": title, "brief": stdin_text(False, source) or title,
            "status": "planned", "thread_id": None, "updated": timestamp()}
    save(state / "tasks" / (task["id"] + ".json"), task)
    if session:
        try:
            navigation.remember(state.parent, session, task["id"])
        except (sqlite3.Error, OSError) as exc:
            raise ValueError(f"Task {task['id']} was saved. Retry task use to select it: {exc}") from exc
    return task_summary(task)


def task_run(root, state, args):
    require_ready(state)
    task = resolve_task(state, args.id)
    path = state / "tasks" / (task["id"] + ".json")
    if task["status"] == "running":
        raise ValueError("Inspect the interrupted run and checkpoint its actual state first.")
    thread = None if args.fresh else task["thread_id"]
    # A new thread starts from the brief, so the first run needs no assignment.
    assignment = stdin_text(required=bool(thread), source=args.input)
    prompt = assignment
    if not thread:
        previous = task.get("result")
        if isinstance(previous, dict):
            previous = json.dumps(previous, ensure_ascii=False)
        prompt = "\n\n".join(filter(None, [
            WORKER, "## Brief\n" + task["brief"],
            task.get("checkpoint") and "## Progress so far\n" + task["checkpoint"],
            previous and "## Last report\n" + previous,
            assignment and "## This run\n" + assignment]))
    model = args.model or task.get("model")
    effort = args.effort or task.get("effort")

    def persist(**changes):
        task.update(changes, updated=timestamp())
        save(path, task)

    persist(status="running", assignment=assignment or None, model=model, effort=effort,
            error=None)
    try:
        message = execute(root, prompt, model, effort, thread,
                          on_thread=lambda value: persist(thread_id=value),
                          schema=REPORT_SCHEMA)
    except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
        persist(status="blocked", error=str(exc) or "Interrupted")
        raise
    report = parse_report(message)
    persist(status="review", result=report)
    reply = {"id": task["id"], "ref": f"T{task['number']}", "status": task["status"],
             "report": report}
    changes = git_changes(root)
    if changes is not None:
        reply["git_status"] = changes
    if args.render:
        try:
            reply["screenshots"] = screenshots(root, state, args.render)
        except (OSError, ValueError) as exc:
            reply["render_error"] = str(exc)
    return reply


def task_checkpoint(state, args):
    task = resolve_task(state, args.id)
    task.update(status=args.status, checkpoint=stdin_text(source=args.input), error=None,
                updated=timestamp())
    save(state / "tasks" / (task["id"] + ".json"), task)
    return task_summary(task)


def project_list(root):
    rows = []
    for path in navigation.projects():
        rows.append({"project": path.name, "root": str(path), "current": path == root,
                     "initialized": (path / STATE / "project.json").is_file()})
    return rows


def resolve_root(args):
    if args.project:
        try:
            return Path(args.project).expanduser().resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"Project directory not found: {args.project}") from exc
    root = navigation.active_project(args.session)
    if getattr(args, "target", None):
        root = navigation.resolve_project(args.target)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", help="explicit project root (overrides session selection)")
    parser.add_argument("--session", help="Claude session ID for project and task selection")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("models", help="compact local Codex model catalog")
    status = commands.add_parser("status", help="read-only project and task status")
    status.add_argument("target", nargs="?")

    init = commands.add_parser("init", help="probe Codex and write project guidance")
    init.add_argument("--model")
    init.add_argument("--effort")

    project = commands.add_parser("project").add_subparsers(dest="action", required=True)
    project.add_parser("list")
    project.add_parser("use").add_argument("target")

    shot = commands.add_parser("render", help="screenshot a page for review (no Codex call)")
    shot.add_argument("page", help="file under the project root, or a URL")
    shot.add_argument("--width", type=int, action="append")
    shot.add_argument("--scheme", choices=render.SCHEMES, action="append")
    shot.add_argument("--height", type=int)

    body = "UTF-8 file holding the body ('-' reads stdin)"
    tasks = commands.add_parser("task").add_subparsers(dest="action", required=True)
    tasks.add_parser("list").add_argument("--all", action="store_true")
    tasks.add_parser("show").add_argument("id")
    tasks.add_parser("use").add_argument("id")
    new = tasks.add_parser("new")
    new.add_argument("title")
    new.add_argument("--input", help=body)
    checkpoint = tasks.add_parser("checkpoint")
    checkpoint.add_argument("id")
    checkpoint.add_argument("status", choices=STATUSES)
    checkpoint.add_argument("--input", help=body)
    run = tasks.add_parser("run")
    run.add_argument("id")
    run.add_argument("--model")
    run.add_argument("--effort")
    run.add_argument("--fresh", action="store_true", help="start a replacement Codex thread")
    run.add_argument("--input", help=body)
    run.add_argument("--render", metavar="PAGE",
                     help="screenshot this page after Codex finishes")

    args = parser.parse_args()
    if args.command == "models":
        return model_catalog()

    root = resolve_root(args)
    if args.command == "project" and args.action == "list":
        return project_list(root)

    state = root / STATE
    if state.is_symlink() or (state / "tasks").is_symlink():
        raise ValueError("Use project-local cc-codex state.")

    if args.command == "status":
        return project_status(root, args.session)

    if args.command == "project":
        if not args.session:
            raise ValueError("Pass --session <Claude session ID> before the command to save a selection.")
        if not (state / "project.json").is_file():
            raise ValueError("Project is not initialized. Run /cc-codex:init there first.")
        result = project_status(root, args.session)
        navigation.remember(root, args.session)
        return result

    if args.command == "init":
        state.mkdir(exist_ok=True)
        ignore = state / ".gitignore"
        if not ignore.exists():
            atomic_write(ignore, b"*\n")
        elif b"*" not in ignore.read_bytes().splitlines():
            raise ValueError("Local task directory must be gitignored before initialization.")
        with writer(state):
            result = initialize(root, state, args)
            task_records(state, migrate=True)
            navigation.remember(root, args.session)
            return {**result, "project": root.name, "root": str(root)}

    if not (state / "project.json").is_file():
        raise ValueError("Initialize this project with /cc-codex:init.")
    if args.command == "render":
        return {"screenshots": screenshots(root, state, args.page, args.width, args.scheme,
                                           args.height)}
    action = args.action

    with writer(state):
        if args.command == "init":
            result = initialize(root, state, args)
            task_records(state, migrate=True)
            navigation.remember(root, args.session)
            return {**result, "project": root.name, "root": str(root)}
        if action == "new":
            return task_new(state, args.session, args.title, args.input)
        if action == "use":
            task = resolve_task(state, args.id)
            navigation.remember(root, args.session, task["id"])
            return project_status(root, args.session)
        if action == "checkpoint":
            return task_checkpoint(state, args)
        if action == "run":
            return task_run(root, state, args)
        if action == "show":
            task = resolve_task(state, args.id)
            return {**task, "ref": f"T{task['number']}"}
        if action == "list":
            selected = navigation.selected_task(args.session, root)
            rows = [dict(task_summary(task), selected=task["id"] == selected)
                    for task in task_records(state) if args.all or task["status"] != "done"]
            return sorted(rows, key=lambda item: item["updated"], reverse=True)
        raise ValueError(f"Unknown task action: {action}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except KeyboardInterrupt:
        sys.exit("Interrupted")
    except (OSError, RuntimeError, ValueError, KeyError, sqlite3.Error) as error:
        sys.exit(str(error) or error.__class__.__name__)
