import io
import json
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

    def command(self, *args, body=""):
        stream = io.TextIOWrapper(io.BytesIO(body.encode("utf-8")))
        with patch.object(sys, "argv", ["bridge", "--project", str(self.root), *args]), \
                patch.object(sys, "stdin", stream):
            return bridge.main()

    def initialize(self):
        def probe(root, prompt, model, effort, probe):
            challenge, = root.glob(".cc-codex/probe-*/input.txt")
            value = challenge.read_bytes()
            challenge.with_name("output.txt").write_bytes(value)
            return value.decode()

        with patch.object(bridge, "execute", probe):
            self.command("init")

    def test_existing_instructions_survive_repeated_init(self):
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

    def test_failed_recheck_blocks_dispatch_and_preserves_tasks(self):
        self.initialize()
        task = self.command("new", "A", body="acceptance A")["id"]
        with patch.object(bridge, "execute", return_value="claimed success"):
            with self.assertRaisesRegex(ValueError, "did not create"):
                self.command("init")
            with self.assertRaisesRegex(ValueError, "before dispatch"):
                self.command("run", task, body="implement")
        self.assertEqual(self.command("show", task)["brief"], "acceptance A")

    def test_switching_tasks_resumes_exact_thread_and_keeps_reviews(self):
        self.initialize()
        a = self.command("new", "A", body="persist theme")["id"]
        b = self.command("new", "B", body="fix login")["id"]
        def worker(root, prompt, model, effort, thread, on_thread):
            on_thread(thread or str(uuid.uuid4()))
            return "ready for review"

        with patch.object(bridge, "execute", side_effect=worker) as dispatch:
            self.command("run", a, "--model", "selected", "--effort", "high", body="implement A")
            first = self.command("show", a)
            self.command("run", b, body="implement B")
            second = self.command("show", b)
            self.assertNotEqual(first["thread_id"], second["thread_id"])
            self.command("run", a, body="adjust contrast")
            self.assertEqual(dispatch.call_args.args[1:], (
                "adjust contrast", "selected", "high", first["thread_id"]))
            self.assertEqual(self.command("show", b), second)
        self.command("checkpoint", a, "done", body="reviewed contrast")
        self.assertEqual([row["id"] for row in self.command("list")], [b])
        self.assertEqual(len(self.command("list", "--all")), 2)

    def test_interrupted_run_requires_reconciliation_before_fresh_thread(self):
        self.initialize()
        task = self.command("new", "theme", body="persist preference")["id"]
        thread_id = str(uuid.uuid4())
        def interrupt(root, prompt, model, effort, thread, on_thread):
            on_thread(thread_id)
            raise SystemExit(99)  # Simulates loss of the parent after thread.started.

        with patch.object(bridge, "execute", side_effect=interrupt):
            with self.assertRaises(SystemExit):
                self.command("run", task, body="implement")
        self.assertEqual(self.command("show", task)["thread_id"], thread_id)
        with self.assertRaisesRegex(ValueError, "interrupted"):
            self.command("run", task, body="implement")
        self.command("checkpoint", task, "planned", body="storage exists, UI is pending")
        with patch.object(bridge, "execute", return_value="fixed") as dispatch:
            self.command("run", task, "--fresh", body="finish UI")
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


if __name__ == "__main__":
    unittest.main()
