"""Real CLI processes against private synthetic stores, never a live transport.

These checks exercise the documented script and module entrypoints in addition
to the canonical import API. They establish software behavior only.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import FilesystemArtifactStore, decode_events
import test_task_followup as synthetic_fixture


ENTRYPOINTS = ("canonical_import", "script", "module")
PROJECTS = "mcp__quantconnect__list_projects"
HISTORY = "mcp__quantconnect__list_backtests"
ATTEMPT = "1" * 32

FACTORY_SOURCE = '''"""Private synthetic CLI fixture, with no connector client."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from followup_host import FollowupHost, TransportAuthority
from qresearch.artifacts import FilesystemArtifactStore, MemoryArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController

Path(os.environ["WR29_IMPORT_MARKER"]).write_text("imported", encoding="utf-8")

def _controller(store):
    limits = {kind: {"total": 10, "normal": 8, "reserve": 2}
              for kind in ("configurations", "research", "lean")}
    return TaskFollowupController(Registry(store, limits),
        {"schema_version": 1, "notification_grace_seconds": 1800, "max_history_pages": 3})

def build():
    store = FilesystemArtifactStore(os.environ["WR29_SYNTHETIC_STORE"],
                                    data_classification="synthetic")
    controller = _controller(store)
    attempt = os.environ["WR29_ATTEMPT"]
    authority = TransportAuthority("synthetic-cli-test", frozenset({attempt}),
                                   frozenset({attempt}))
    host = FollowupHost(controller, enabled=True, authority=authority,
                       clock=lambda: datetime(9999, 1, 1, tzinfo=timezone.utc))
    Path(os.environ["WR29_TYPE_MARKER"]).write_text(json.dumps({
        "host": type(host).__module__, "authority": type(authority).__module__}),
        encoding="utf-8")
    return host

def disabled():
    return FollowupHost()

def invalid():
    return {"enabled": True}

def incompatible():
    class HostSubclass(FollowupHost):
        pass
    return HostSubclass(_controller(MemoryArtifactStore()), enabled=True,
                        authority=TransportAuthority("synthetic-incompatible"))

def invalid_authority():
    return FollowupHost(_controller(MemoryArtifactStore()), enabled=True, authority=object())
'''


class FollowupHostEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.store_path = self.directory / "private-synthetic-store"
        self.import_marker = self.directory / "factory-imported"
        self.type_marker = self.directory / "factory-types.json"
        (self.directory / "wr29_synthetic_factory.py").write_text(FACTORY_SOURCE, encoding="utf-8")
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=os.pathsep.join((str(self.directory), str(ROOT / "tools"), str(ROOT / "cloud"))),
            WR29_IMPORT_MARKER=str(self.import_marker), WR29_TYPE_MARKER=str(self.type_marker),
            WR29_SYNTHETIC_STORE=str(self.store_path), WR29_ATTEMPT=ATTEMPT)

    def command(self, entrypoint, arguments):
        if entrypoint == "canonical_import":
            prefix = ["-c", "import followup_host; raise SystemExit(followup_host.main())"]
        elif entrypoint == "script":
            prefix = [str(ROOT / "tools" / "followup_host.py")]
        else:
            self.assertEqual(entrypoint, "module")
            prefix = ["-m", "followup_host"]
        return [sys.executable, "-B", *prefix, *arguments]

    def invoke(self, entrypoint, arguments, messages=()):
        return subprocess.run(self.command(entrypoint, arguments),
            input="".join(json.dumps(message) + "\n" for message in messages),
            text=True, capture_output=True, cwd=self.directory, env=self.environment, timeout=30)

    def successful(self, entrypoint, arguments, messages=()):
        result = self.invoke(entrypoint, arguments, messages)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return [json.loads(line) for line in result.stdout.splitlines()]

    @staticmethod
    def enabled(command="serve", factory="build", attempt=None):
        arguments = [command, "--enable-dispatch", "--host-factory", "wr29_synthetic_factory:" + factory]
        if attempt is not None:
            arguments.extend(("--attempt", attempt))
        return arguments

    def seed_pending(self, submitted, *, register=False):
        # The pre-existing fixture creates an accepted pending attempt entirely
        # in MemoryArtifactStore. Only its synthetic bytes enter this temp root.
        with patch.object(synthetic_fixture, "SUBMITTED", submitted):
            memory, registry, _, attempt, controller = synthetic_fixture.fixture()
        if register:
            controller.register(attempt)
        self.store = FilesystemArtifactStore(self.store_path, data_classification="synthetic")
        for key, value in memory._data.items():
            self.store.write_once(key, value)
        self.environment["WR29_ATTEMPT"] = attempt
        self.journal_key = registry.JOURNAL
        self.journal_before = self.store.read_bytes(self.journal_key)
        return attempt

    def assert_journal_unchanged(self):
        self.assertEqual(self.store.read_bytes(self.journal_key), self.journal_before)

    def test_valid_canonical_factory_is_accepted_by_all_three_entrypoints(self):
        for entrypoint in ENTRYPOINTS:
            with self.subTest(entrypoint=entrypoint):
                self.assertEqual(self.successful(entrypoint, self.enabled()), [])
                self.assertEqual(json.loads(self.type_marker.read_text(encoding="utf-8")),
                                 {"host": "followup_host", "authority": "followup_host"})

    def test_default_off_never_imports_factory_or_opens_store(self):
        for entrypoint in ENTRYPOINTS:
            with self.subTest(entrypoint=entrypoint):
                plan = self.successful(entrypoint,
                    ["plan", "--attempt", ATTEMPT, "--host-factory", "wr29_synthetic_factory:build"])
                serve = self.successful(entrypoint,
                    ["serve", "--host-factory", "wr29_synthetic_factory:build"],
                    [{"command": command, "attempt_id": ATTEMPT}
                     for command in ("wake", "register", "sync", "status")])
                self.assertEqual([item["action"] for item in plan + serve], ["dispatch_disabled"] * 5)
                self.assertFalse(self.import_marker.exists())
                self.assertFalse(self.store_path.exists())

    def test_disabled_invalid_and_incompatible_factories_remain_rejected(self):
        for entrypoint in ENTRYPOINTS:
            for factory in ("disabled", "invalid", "incompatible"):
                with self.subTest(entrypoint=entrypoint, factory=factory):
                    result = self.invoke(entrypoint, self.enabled(factory=factory))
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("factory must return an explicitly enabled FollowupHost", result.stderr)
                    self.assertFalse(self.store_path.exists())
            with self.subTest(entrypoint=entrypoint, factory="invalid_authority"):
                result = self.invoke(entrypoint, self.enabled(factory="invalid_authority"))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("trusted_controller_and_authority_required", result.stderr)
                self.assertFalse(self.store_path.exists())

    def test_cli_gate_and_no_clock_override_remain_enforced(self):
        for entrypoint in ENTRYPOINTS:
            for arguments in (["serve", "--enable-dispatch"],
                              ["serve", "--enable-dispatch", "--host-factory", "bad-factory"],
                              ["serve", "--now", "9999-01-01T00:00:00+00:00"]):
                with self.subTest(entrypoint=entrypoint, arguments=arguments):
                    result = self.invoke(entrypoint, arguments)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertFalse(self.import_marker.exists())
                    self.assertFalse(self.store_path.exists())

    def test_pending_plan_and_serve_use_real_utc_instead_of_future_factory_clock(self):
        attempt = self.seed_pending(datetime.now(timezone.utc) - timedelta(minutes=5), register=True)
        watch_stream = "engineering/followup/" + attempt + "/events.jsonl"
        watch_before = self.store.read_bytes(watch_stream)
        for entrypoint in ENTRYPOINTS:
            with self.subTest(entrypoint=entrypoint):
                plan = self.successful(entrypoint, self.enabled("plan", attempt=attempt))
                serve = self.successful(entrypoint, self.enabled(),
                    [{"command": command, "attempt_id": attempt}
                     for command in ("status", "wake")])
                self.assertEqual([item["type"] for item in plan + serve], ["status"] * 3)
                self.assertEqual([item["action"] for item in plan + serve], ["wait_for_delivery"] * 3)
                self.assertFalse(self.store.exists("engineering/followup-host/" + attempt + "/events.jsonl"))
                self.assertEqual(self.store.read_bytes(watch_stream), watch_before)
                self.assert_journal_unchanged()

    def test_discovery_response_and_unknown_restart_work_across_real_processes(self):
        attempt = self.seed_pending(datetime.now(timezone.utc) - timedelta(hours=2))
        wake = {"command": "wake", "attempt_id": attempt}
        before = datetime.now(timezone.utc)
        first = self.successful("script", self.enabled(), [wake])[0]
        after = datetime.now(timezone.utc)
        self.assertEqual(first["type"], "tool_request")
        self.assertEqual((first["tool_name"], first["arguments"]), (PROJECTS, {"page": 1}))
        stream = "engineering/followup-host/" + attempt + "/events.jsonl"
        first_events = decode_events(self.store.read_bytes(stream))
        reserved_at = datetime.fromisoformat(first_events[-1]["event"]["reserved_at"])
        self.assertEqual(reserved_at.tzinfo, timezone.utc)
        self.assertLessEqual(before, reserved_at)
        self.assertLessEqual(reserved_at, after)
        unknown = self.successful("module", self.enabled(), [wake])[0]
        self.assertEqual(unknown["failure_code"], "reserved_response_unknown")
        self.assertEqual(decode_events(self.store.read_bytes(stream)), first_events)
        response = {"command": "response", **{key: first[key] for key in
                    ("attempt_id", "correlation_id", "tool_name", "arguments")},
                    "result": {"success": True, "projects": [{"projectId": 17, "name": "SYNTHETIC"}],
                               "page": 1, "nextPage": None, "totalPages": 1}}
        observed = self.successful("canonical_import", self.enabled(), [response, wake])
        self.assertEqual(observed[0]["action"], "projects_observed")
        second = observed[1]
        self.assertEqual(second["type"], "tool_request")
        self.assertEqual((second["tool_name"], second["arguments"]),
                         (HISTORY, {"projectId": 17, "page": 1}))
        self.assertNotEqual(first["correlation_id"], second["correlation_id"])
        for entrypoint in ENTRYPOINTS:
            with self.subTest(entrypoint=entrypoint):
                plan = self.successful(entrypoint, self.enabled("plan", attempt=attempt))[0]
                restarted = self.successful(entrypoint, self.enabled(), [wake])[0]
                self.assertEqual(plan["failure_code"], "reserved_response_unknown")
                self.assertEqual(restarted["failure_code"], "reserved_response_unknown")
        reservations = [item["event"] for item in decode_events(self.store.read_bytes(stream))
                        if item["event"]["kind"] == "reserved"]
        self.assertEqual([event["tool_name"] for event in reservations], [PROJECTS, HISTORY])
        self.assert_journal_unchanged()


if __name__ == "__main__":
    unittest.main()
