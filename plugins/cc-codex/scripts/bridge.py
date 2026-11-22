"""Project initialization, dispatch and resumable task records for cc-codex."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import tempfile
import uuid

from codex_cli import execute, model_catalog
import navigation


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
BEGIN = b"<!-- cc-codex:begin -->"
END = b"<!-- cc-codex:end -->"
STATE = ".cc-codex"


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
        for name in ("input.txt", "output.txt"):
            (probe / name).unlink(missing_ok=True)
        probe.rmdir()


@contextmanager
def writer(state):
    # One Codex writer at a time per worktree. OS releases locks on process exit.
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
    if path.is_symlink():
        raise ValueError(f"Inspect linked instructions manually: {path}")
    old = path.read_bytes() if path.exists() else b""
    old.decode("utf-8-sig")  # Preserve hand-written bytes; reject incompatible encodings.
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
    readiness = state / "project.json"
    save(readiness, {"ready": False})
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
    # Probe in the same working root and sandbox used by ordinary tasks.
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
    result = {"ready": True, "checked": timestamp(), "probe_model": args.model or "CLI default",
              "probe_effort": args.effort or "CLI default"}
    save(readiness, result)
    return result


def stdin_text():
    body = sys.stdin.buffer.read().decode("utf-8-sig").strip()
    if not body:
        raise ValueError("Expected a UTF-8 task brief or checkpoint on stdin.")
    return body


def task_records(state, migrate=False):
    """Give pre-0.2 records deterministic numbers; persist them under the writer lock."""
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
    return {"ref": f"T{task['number']}", **{key: task[key] for key in ("id", "title", "status", "updated")}}


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
    return {"project": root.name, "root": str(root), "initialized": marker.is_file(),
            "last_probe": read(marker) if marker.is_file() else None, "selected": details,
            "other_open_tasks": [task_summary(t) for t in records if t["id"] != selected and t["status"] != "done"]}


def task_command(root, state, args):
    folder = state / "tasks"
    if args.command == "new":
        records = task_records(state, migrate=True)
        folder.mkdir(exist_ok=True)
        task = {"id": uuid.uuid4().hex, "number": max((t["number"] for t in records), default=0) + 1,
                "title": args.title, "brief": args.title if args.title_only else stdin_text(),
                "status": "planned", "thread_id": None}
    else:
        task = resolve_task(state, args.id)
    path = folder / (task["id"] + ".json")

    def persist(**changes):
        task.update(changes, updated=timestamp())
        save(path, task)

    if args.command == "show":
        return {**task, "ref": f"T{task['number']}"}
    if args.command == "new":
        persist()
        if args.session:
            try:
                navigation.remember(root, args.session, task["id"])
            except (sqlite3.Error, OSError) as exc:
                raise ValueError(f"Task {task['id']} was saved. Retry task use to select it: {exc}") from exc
    elif args.command == "checkpoint":
        persist(status=args.status, checkpoint=stdin_text())
    else:
        if not read(state / "project.json")["ready"]:
            raise ValueError("Run /cc-codex:init successfully before dispatch.")
        if task["status"] == "running":
            raise ValueError("Inspect the interrupted run and checkpoint its actual state first.")
        assignment = stdin_text()
        thread = None if args.fresh else task["thread_id"]
        prompt = assignment
        if not thread:
            prompt = "\n".join(filter(None, [task["brief"], task.get("checkpoint"),
                                            task.get("result"), assignment]))
        model = args.model or task.get("model")
        effort = args.effort or task.get("effort")
        persist(status="running", assignment=assignment, model=model, effort=effort)
        try:
            result = execute(root, prompt, model, effort, thread,
                             on_thread=lambda value: persist(thread_id=value))
        except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
            persist(status="blocked", error=str(exc) or "Interrupted")
            raise
        persist(status="review", result=result, error=None)
        return {"id": task["id"], "status": task["status"], "result": result}
    return task_summary(task)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="explicit project root (overrides session selection)")
    parser.add_argument("--session", help="Claude session ID for project and task selection")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("models", help="compact local Codex model catalog")
    status = commands.add_parser("status")
    status.add_argument("target", nargs="?")
    project = commands.add_parser("project").add_subparsers(dest="action", required=True)
    project.add_parser("list")
    project.add_parser("use").add_argument("target")
    tasks = commands.add_parser("task").add_subparsers(dest="action", required=True)
    tasks.add_parser("list").add_argument("--all", action="store_true")
    tasks.add_parser("use").add_argument("id")
    tasks.add_parser("new").add_argument("title")
    init = commands.add_parser("init")
    new = commands.add_parser("new")
    new.add_argument("title")
    listing = commands.add_parser("list")
    listing.add_argument("--all", action="store_true")
    show = commands.add_parser("show")
    run = commands.add_parser("run")
    checkpoint = commands.add_parser("checkpoint")
    for command in (show, run, checkpoint):
        command.add_argument("id")
    for command in (init, run):
        command.add_argument("--model")
        command.add_argument("--effort")
    run.add_argument("--fresh", action="store_true", help="start a replacement Codex thread")
    checkpoint.add_argument("status", choices=["planned", "review", "blocked", "done"])
    args = parser.parse_args()
    if args.command == "models":
        return model_catalog()
    root = Path(args.project).resolve(strict=True) if args.project else navigation.active_project(args.session)
    if args.command == "project" and args.action == "list":
        return [{"project": p.name, "root": str(p), "current": p == root} for p in navigation.projects()]
    if getattr(args, "target", None):
        root = navigation.resolve_project(args.target)
    state = root / STATE
    if state.is_symlink() or (state / "tasks").is_symlink():
        raise ValueError("Use project-local cc-codex state.")
    if args.command == "status":
        return project_status(root, args.session)
    if args.command in ("project", "task") and args.action != "list" and not args.session:
        raise ValueError("Pass --session <Claude session ID> before the command to save a selection.")
    if args.command == "init":
        state.mkdir(exist_ok=True)
        ignore = state / ".gitignore"
        if not ignore.exists():
            atomic_write(ignore, b"*\n")
        elif b"*" not in ignore.read_bytes().splitlines():
            raise ValueError("Local task directory must be gitignored before initialization.")
    elif not (state / "project.json").is_file():
        raise ValueError("Initialize this project with /cc-codex:init.")
    if args.command == "project":
        result = project_status(root, args.session)
        navigation.remember(root, args.session)
        return result
    args.title_only = args.command == "task" and args.action == "new"
    if args.command == "task":
        if args.action == "use":
            task = resolve_task(state, args.id)
            navigation.remember(root, args.session, task["id"])
            return project_status(root, args.session)
        args.command = args.action
    if args.command == "list":
        selected = navigation.selected_task(args.session, root)
        rows = [dict(task_summary(task), selected=task["id"] == selected)
                for task in task_records(state) if args.all or task["status"] != "done"]
        return sorted(rows, key=lambda item: item["updated"], reverse=True)
    if args.command == "show":
        return task_command(root, state, args)
    with writer(state):
        if args.command == "init":
            result = initialize(root, state, args)
            task_records(state, migrate=True)
            navigation.remember(root, args.session)
            return result
        return task_command(root, state, args)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except (OSError, RuntimeError, ValueError, KeyError, sqlite3.Error) as error:
        sys.exit(str(error))
