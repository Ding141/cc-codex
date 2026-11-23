import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins/cc-codex/scripts"
sys.path.insert(0, str(SCRIPTS))
import bridge
import codex_cli


class ProjectTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        home = patch.dict(os.environ, CC_CODEX_HOME=str(self.root / "user-data"))
        home.start()
        self.addCleanup(home.stop)

    def command(self, *args, body=""):
        return self.cli("--project", str(self.root), *args, body=body)

    def cli(self, *args, body=""):
        stream = io.TextIOWrapper(io.BytesIO(body.encode("utf-8")))
        with patch.object(sys, "argv", ["bridge", *args]), \
                patch.object(sys, "stdin", stream):
            return bridge.main()

    def initialize(self, root=None):
        def probe(root, prompt, model, effort, probe):
            challenge, = root.glob(".cc-codex/probe-*/input.txt")
            value = challenge.read_bytes()
            challenge.with_name("output.txt").write_bytes(value)
            return value.decode()

        with patch.object(bridge, "execute", probe):
            self.cli("--project", str(root or self.root), "init")

    def test_initialize_creates_state_and_keeps_existing_instructions(self):
        agents = self.root / "AGENTS.md"
        original = "已有规则\r\n".encode()
        agents.write_bytes(original)
        self.initialize()
        first = agents.read_bytes()
        self.assertTrue(first.startswith(original))
        self.assertIn("@AGENTS.md", (self.root / "CLAUDE.md").read_text())
        self.initialize()
        self.assertEqual(agents.read_bytes(), first)
        self.assertFalse(list(self.root.glob(".cc-codex/probe-*")))
        self.assertEqual((self.root / ".cc-codex/.gitignore").read_text(), "*\n")
        self.assertTrue(self.command("status")["ready"])

    def test_failed_recheck_blocks_dispatch_and_preserves_tasks(self):
        self.initialize()
        task = self.command("task", "new", "A", body="acceptance A")["id"]
        with patch.object(bridge, "execute", return_value="claimed success"):
            with self.assertRaisesRegex(ValueError, "did not create"):
                self.command("init")
            with self.assertRaisesRegex(ValueError, "before dispatch"):
                self.command("task", "run", task, body="implement")
        self.assertEqual(self.command("task", "show", task)["brief"], "acceptance A")
        self.assertFalse(self.command("status")["ready"])

    def test_switching_tasks_resumes_exact_thread_and_keeps_reviews(self):
        self.initialize()
        a = self.command("task", "new", "A", body="persist theme")["id"]
        b = self.command("task", "new", "B", body="fix login")["id"]

        def worker(root, prompt, model, effort, thread, on_thread, **options):
            on_thread(thread or str(uuid.uuid4()))
            return "ready for review"

        with patch.object(bridge, "execute", side_effect=worker) as dispatch:
            self.command("task", "run", a, "--model", "selected", "--effort", "high", body="implement A")
            first = self.command("task", "show", a)
            self.command("task", "run", b, body="implement B")
            second = self.command("task", "show", b)
            self.assertNotEqual(first["thread_id"], second["thread_id"])
            self.command("task", "run", a, body="adjust contrast")
            self.assertEqual(dispatch.call_args.args[1:], (
                "adjust contrast", "selected", "high", first["thread_id"]))
            self.assertEqual(self.command("task", "show", b), second)
        self.command("task", "checkpoint", a, "done", body="reviewed contrast")
        self.assertEqual([row["id"] for row in self.command("task", "list")], [b])
        self.assertEqual(len(self.command("task", "list", "--all")), 2)

    def test_interrupted_run_requires_reconciliation_before_fresh_thread(self):
        self.initialize()
        task = self.command("task", "new", "theme", body="persist preference")["id"]
        thread_id = str(uuid.uuid4())

        def interrupt(root, prompt, model, effort, thread, on_thread, **options):
            on_thread(thread_id)
            raise SystemExit(99)  # Simulates loss of the parent after thread.started.

        with patch.object(bridge, "execute", side_effect=interrupt):
            with self.assertRaises(SystemExit):
                self.command("task", "run", task, body="implement")
        self.assertEqual(self.command("task", "show", task)["thread_id"], thread_id)
        with self.assertRaisesRegex(ValueError, "interrupted"):
            self.command("task", "run", task, body="implement")
        self.command("task", "checkpoint", task, "planned", body="storage exists, UI is pending")
        with patch.object(bridge, "execute", return_value="fixed") as dispatch:
            self.command("task", "run", task, "--fresh", body="finish UI")
            self.assertIsNone(dispatch.call_args.args[4])
            self.assertIn("storage exists", dispatch.call_args.args[1])

    def test_jsonl_adapter_consumes_only_final_reply_and_checks_exit(self):
        session = str(uuid.uuid4())
        worker = self.root / "worker.py"
        events = [{"type": "thread.started", "thread_id": session},
                  {"type": "item.completed", "item": {"type": "command_execution"}},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
                  {"type": "turn.completed"}]
        worker.write_text("import sys\nsys.stdin.buffer.read()\n" +
                          "\n".join(f"print({json.dumps(e)!r})" for e in events), encoding="utf-8")
        ids = []
        with patch.object(codex_cli, "launcher", return_value=[sys.executable, str(worker)]):
            result = codex_cli.execute(self.root, "中文", on_thread=ids.append)
            self.assertEqual((ids, result), ([session], "done"))
            with worker.open("a") as out:
                out.write("\nsys.exit(17)\n")
            with self.assertRaisesRegex(RuntimeError, "exit 17"):
                codex_cli.execute(self.root, "retry")

    def test_project_switch_preserves_each_session_selection_and_dispatch_root(self):
        other = self.root / "网站 后台"
        other.mkdir()
        self.initialize()
        self.initialize(other)
        one = lambda *args, **kw: self.cli("--session", "one", *args, **kw)
        two = lambda *args, **kw: self.cli("--session", "two", *args, **kw)
        for window in (one, two):
            window("project", "use", str(self.root))
        a = one("task", "new", "theme")
        c = two("task", "new", "login")
        self.assertEqual((a["ref"], c["ref"]), ("T1", "T2"))
        one("project", "use", other.name)
        b = one("task", "new", "dashboard")
        self.assertEqual(b["ref"], "T1")
        self.assertEqual(one("status", self.root.name)["selected"]["id"], a["id"])
        self.assertEqual(one("status")["root"], str(other))
        self.assertEqual(two("status")["selected"]["id"], c["id"])
        with patch.object(bridge, "execute", return_value="implemented B") as dispatch:
            one("task", "run", "T1", body="implement it")
            self.assertEqual(dispatch.call_args.args[0], other)
            self.assertIn("dashboard", dispatch.call_args.args[1])
        one("project", "use", str(self.root))
        self.assertEqual(one("status")["selected"]["status"], "planned")
        self.assertEqual(one("status")["selected"]["id"], a["id"])
        self.assertEqual(one("task", "use", "T2")["selected"]["id"], c["id"])

    def test_legacy_task_refs_persist_across_new_tasks_and_updates(self):
        self.initialize()
        old = self.command("task", "new", "old", body="legacy brief")
        path = self.root / bridge.STATE / "tasks" / (old["id"] + ".json")
        data = bridge.read(path)
        del data["number"]
        bridge.save(path, data)
        self.assertEqual(self.command("task", "list")[0]["ref"], "T1")
        self.assertNotIn("number", bridge.read(path))  # Viewing legacy records is read-only.
        self.assertEqual(self.command("task", "new", "next", body="new brief")["ref"], "T2")
        self.command("task", "checkpoint", "T1", "done", body="checked")
        self.assertEqual(self.command("task", "show", "T1")["id"], old["id"])
        self.assertEqual([t["ref"] for t in self.command("task", "list")], ["T2"])
        self.assertEqual(len(self.command("task", "list", "--all")), 2)

    def test_failed_switch_and_duplicate_names_preserve_selection(self):
        roots = [self.root / group / "site" for group in ("first", "second")]
        for root in roots:
            root.mkdir(parents=True)
            self.initialize(root)
        session = ("--session", "demo")
        self.cli(*session, "project", "use", str(roots[0]))
        for target in ("site", str(self.root), "unknown"):
            with self.assertRaises(ValueError):
                self.cli(*session, "project", "use", target)
        self.assertEqual(self.cli(*session, "status")["root"], str(roots[0]))
        self.assertEqual(sum(p["current"] for p in self.cli(*session, "project", "list")), 1)

    def test_navigation_snapshot_is_read_only_and_never_dispatches(self):
        with patch.object(bridge, "execute", side_effect=AssertionError("unwanted dispatch")):
            self.assertFalse(self.command("status")["initialized"])
            self.assertEqual(self.command("project", "list"), [])
            self.assertEqual(list(self.root.iterdir()), [])
        self.initialize()
        with patch.object(bridge, "execute", side_effect=AssertionError("unwanted dispatch")):
            task = self.command("--session", "a", "task", "new", "plan only")
            self.command("--session", "b", "task", "use", task["ref"])
            self.assertEqual(self.command("--session", "b", "status")["selected"]["status"], "planned")
            self.assertIsNone(self.command("--session", "new-window", "status")["selected"])

    def test_brief_file_starts_worker_thread_and_report_is_structured(self):
        self.initialize()
        brief = self.root / ".cc-codex" / "brief.md"
        brief.write_text("目标：深色模式\n验收：刷新后保留", encoding="utf-8")
        task = self.command("task", "new", "dark mode", "--input", str(brief))
        report = {"outcome": "done", "summary": "ok", "changed_files": ["a.css"], "checks": [],
                  "criteria": [{"criterion": "刷新后保留", "status": "met", "evidence": "test"}],
                  "open_questions": []}
        calls = []

        def worker(root, prompt, model, effort, thread, on_thread, schema=None):
            calls.append((prompt, thread, schema))
            on_thread(thread or str(uuid.uuid4()))
            return json.dumps(report, ensure_ascii=False)

        with patch.object(bridge, "execute", side_effect=worker):
            first = self.command("task", "run", task["ref"])  # No assignment on a new thread.
            self.assertEqual(first["report"], report)
            prompt, thread, schema = calls[-1]
            self.assertIsNone(thread)
            self.assertTrue(prompt.startswith(bridge.WORKER))
            self.assertIn("刷新后保留", prompt)
            self.assertEqual(schema, bridge.REPORT_SCHEMA)
            self.assertTrue(schema.is_file())
            with self.assertRaisesRegex(ValueError, "Expected a UTF-8 body"):
                self.command("task", "run", task["ref"])  # A resumed thread needs new work.
            fix = self.root / ".cc-codex" / "fix.md"
            fix.write_text("提高对比度", encoding="utf-8")
            self.command("task", "run", task["ref"], "--input", str(fix))
            self.assertEqual(calls[-1][0], "提高对比度")
        self.assertEqual(self.command("task", "show", task["ref"])["result"], report)
        with patch.object(bridge, "execute", return_value="plain text"):
            self.command("task", "run", task["ref"], "--fresh")
        self.assertEqual(self.command("task", "show", task["ref"])["result"], {"raw": "plain text"})
        with self.assertRaisesRegex(ValueError, "Cannot read --input"):
            self.command("task", "checkpoint", task["ref"], "done", "--input", str(self.root / "missing"))

    def test_render_uses_browser_outside_codex_and_never_fails_the_run(self):
        self.initialize()
        (self.root / "index.html").write_text("<p>hi</p>", encoding="utf-8")
        launched = []

        def browser(args, **kw):
            launched.append(args)
            shot = next(a for a in args if a.startswith("--screenshot="))[len("--screenshot="):]
            Path(shot).write_bytes(b"png")

        with patch.object(bridge.render, "browser", return_value="chrome"), \
                patch.object(bridge.render.subprocess, "run", side_effect=browser):
            shots = self.command("render", "index.html", "--width", "390")["screenshots"]
        self.assertEqual([(s["width"], s["scheme"]) for s in shots], [(390, "light"), (390, "dark")])
        self.assertTrue(all(Path(s["path"]).is_file() for s in shots))
        self.assertFalse(any("--single-process" in a or "--no-sandbox" in a for a in launched[0]))
        task = self.command("task", "new", "page", body="build page")["ref"]
        with patch.object(bridge, "execute", return_value="{}"), \
                patch.object(bridge.render, "browser", side_effect=ValueError("No Chrome")):
            result = self.command("task", "run", task, "--render", "index.html")
        self.assertEqual((result["status"], result["render_error"]), ("review", "No Chrome"))

    def test_schema_flag_reaches_codex(self):
        worker = self.root / "argv.py"
        log = self.root / "argv.json"
        session = str(uuid.uuid4())
        worker.write_text(
            "import json, sys\nsys.stdin.buffer.read()\n"
            f"open({str(log)!r}, 'w').write(json.dumps(sys.argv))\n"
            f"print(json.dumps({{'type': 'thread.started', 'thread_id': {session!r}}}))\n"
            "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{}'}}))\n"
            "print(json.dumps({'type': 'turn.completed'}))\n", encoding="utf-8")
        with patch.object(codex_cli, "launcher", return_value=[sys.executable, str(worker)]):
            codex_cli.execute(self.root, "x", schema=bridge.REPORT_SCHEMA, thread=session)
        argv = json.loads(log.read_text())
        self.assertEqual(argv[argv.index("--output-schema") + 1], str(bridge.REPORT_SCHEMA))
        self.assertLess(argv.index("--output-schema"), argv.index("resume"))


if __name__ == "__main__":
    unittest.main()
