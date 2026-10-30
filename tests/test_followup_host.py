"""Host acceptance checks with production controller and private synthetic stores.

No connector, provider, Research execution, LEAN submission or real Registry is
used. These are software checks, not independent review or financial evidence.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
import followup_host as host_module
from followup_host import FollowupHost, TransportAuthority, ReadGrant, PROJECTS, HISTORY, READ
from qresearch.artifacts import FilesystemArtifactStore, canonical_json, decode_events
from qresearch.engineering_receipts import backtest_observation
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController
from test_task_followup import fixture, history, POLICY, SUBMITTED, DEADLINE
from test_engineering_tasks import completed, submission
from test_engineering_receipts import envelope, completed_tool, log_tools

LIMITS = {kind: {"total": 10, "normal": 8, "reserve": 2} for kind in ("configurations", "research", "lean")}


def projects(ids=(17,)):
    return envelope("list_projects", {"page": 1}, {"success": True, "projects": [
        {"projectId": project, "name": "SYNTHETIC_PRIVATE_PROJECT", "language": "Py"} for project in ids],
        "page": 1, "nextPage": None, "totalPages": 1})


def response(request, native):
    return {"command": "response", **{key: request[key] for key in ("attempt_id", "correlation_id", "tool_name", "arguments")},
            "result": native["result"]}


def make_host(controller, attempt, *, now=DEADLINE, read=False, discover=True, history_allowed=True, mode="chat_connector"):
    grants = (ReadGrant(attempt, 17, "actual-synthetic-backtest-id", "delivered_terminal_notification", "a" * 64),) if read else ()
    authority = TransportAuthority("synthetic-test-transport", frozenset({attempt}) if discover else frozenset(),
                                   frozenset({attempt}) if history_allowed else frozenset(), mode, grants)
    return FollowupHost(controller, enabled=True, authority=authority, clock=lambda: now)


class FollowupHostTests(unittest.TestCase):
    def discover(self, host, attempt):
        request = host.prepare(attempt)
        self.assertEqual({key: request[key] for key in ("tool_name", "arguments")},
                         {"tool_name": PROJECTS, "arguments": {"page": 1}})
        self.assertEqual(host.accept_response(response(request, projects()))["action"], "projects_observed")
        return request

    def test_default_disabled_never_reads_or_locks_even_supplied_controller(self):
        class ForbiddenController:
            @property
            def store(self):
                raise AssertionError("disabled host accessed store")
        host = FollowupHost(ForbiddenController())
        for command in ("wake", "register", "sync", "status"):
            self.assertEqual(host.command({"command": command, "attempt_id": "1" * 32})["action"], "dispatch_disabled")

    def test_discovery_has_separate_authority_and_unique_durable_reservation(self):
        store, reg, bridge, attempt, controller = fixture()
        before = reg.snapshot()
        host = make_host(controller, attempt)
        request = host.prepare(attempt)
        events = [item["event"] for item in decode_events(store.read_bytes(host._stream(attempt)))]
        self.assertEqual([event["kind"] for event in events], ["bound", "reserved"])
        self.assertEqual(events[-1]["correlation_id"], request["correlation_id"])
        self.assertFalse(store.exists(controller._stream(attempt)))
        self.assertEqual(host.prepare(attempt)["failure_code"], "reserved_response_unknown")
        reopened = make_host(TaskFollowupController(reg, POLICY), attempt)
        self.assertEqual(reopened.prepare(attempt)["action"], "attention_required")
        self.assertEqual(reopened.command({"command": "status", "attempt_id": attempt})["failure_code"], "reserved_response_unknown")
        reopened.accept_response(response(request, projects()))
        next_request = reopened.prepare(attempt)
        self.assertEqual(next_request["tool_name"], HISTORY)
        self.assertEqual(next_request["arguments"], {"projectId": 17, "page": 1})
        watch = [item["event"]["kind"] for item in decode_events(store.read_bytes(controller._stream(attempt)))]
        self.assertEqual(watch, ["registered", "history_reserved"])
        self.assertEqual(reg.snapshot(), before)

    def test_controller_false_action_does_not_authorize_discovery(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt, discover=False)
        result = host.prepare(attempt)
        self.assertEqual(result["failure_code"], "discovery_not_authorized")
        self.assertFalse(store.exists(controller._stream(attempt)))
        self.assertFalse(any(item["event"]["kind"] == "reserved" for item in decode_events(store.read_bytes(host._stream(attempt)))))

    def test_original_pending_clock_and_register_sync_status_cannot_dispatch(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt, now=DEADLINE - timedelta(microseconds=1))
        for command in ("status", "sync", "register"):
            self.assertEqual(host.command({"command": command, "attempt_id": attempt})["type"], "status")
        self.assertEqual(host.prepare(attempt)["action"], "wait_for_delivery")
        self.assertFalse(store.exists(host._stream(attempt)))
        self.assertEqual(controller.status(attempt)["deadline"], DEADLINE.isoformat())

    def test_threaded_wake_uses_shared_lock_and_only_one_emission(self):
        store, reg, bridge, attempt, controller = fixture()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: make_host(controller, attempt).prepare(attempt), range(24)))
        self.assertEqual(sum(item["type"] == "tool_request" for item in outcomes), 1)

    def test_filesystem_instances_and_processes_share_at_most_once_reservation(self):
        memory, reg, bridge, attempt, controller = fixture()
        with tempfile.TemporaryDirectory() as temp:
            store = FilesystemArtifactStore(temp, data_classification="synthetic")
            for key, value in memory._data.items():
                store.write_once(key, value)
            code = ("import sys,json;sys.path[:0]=sys.argv[1:4];"
                    "from test_followup_host import *;"
                    "s=FilesystemArtifactStore(sys.argv[4],data_classification='synthetic');"
                    "r=Registry(s,LIMITS);c=TaskFollowupController(r,POLICY);"
                    "print(json.dumps(make_host(c,sys.argv[5]).prepare(sys.argv[5])))")
            args = [sys.executable, "-B", "-c", code, str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests"), temp, attempt]
            processes = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            outputs = []
            for process in processes:
                out, err = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, err)
                outputs.append(json.loads(out))
            self.assertEqual(sum(item["type"] == "tool_request" for item in outputs), 1)

    def test_crash_after_host_reservation_and_stdout_failure_never_reemit(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        append = host._append
        def crash_after_append(attempt, event):
            append(attempt, event)
            if event["kind"] == "reserved":
                raise IOError("SYNTHETIC crash after persistence")
        with patch.object(host, "_append", side_effect=crash_after_append), self.assertRaises(IOError):
            host.prepare(attempt)
        self.assertEqual(make_host(controller, attempt).prepare(attempt)["failure_code"], "reserved_response_unknown")
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        class LostStdout(io.StringIO):
            def write(self, value):
                raise IOError("lost stdout")
        with self.assertRaises(IOError):
            host_module.serve(host, io.StringIO(json.dumps({"command": "wake", "attempt_id": attempt}) + "\n"), LostStdout())
        self.assertEqual(make_host(controller, attempt).prepare(attempt)["failure_code"], "reserved_response_unknown")

    def test_crash_between_controller_and_host_reservation_cannot_reconstruct_request(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        self.discover(host, attempt)
        append = host._append
        def crash_before_host_append(attempt, event):
            if event["kind"] == "reserved":
                raise IOError("SYNTHETIC crash between reservations")
            append(attempt, event)
        with patch.object(host, "_append", side_effect=crash_before_host_append), self.assertRaises(IOError):
            host.prepare(attempt)
        self.assertEqual(make_host(controller, attempt).prepare(attempt)["action"], "attention_required")
        self.assertEqual(controller.status(attempt)["action"], "attention_required")

    def test_client_execution_lost_response_is_never_retried(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        class Client:
            calls = []
            def call_tool(self, name, arguments):
                self.calls.append((name, arguments))
                raise IOError("SYNTHETIC dispatched then lost response")
        client = Client()
        self.assertEqual(host.run_once(attempt, client)["action"], "attention_required")
        self.assertEqual(host.run_once(attempt, client)["action"], "attention_required")
        self.assertEqual(client.calls, [(PROJECTS, {"page": 1})])

    def test_watch_registration_failure_does_not_dispatch_history_or_lose_identity(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        self.discover(host, attempt)
        append = store.append_event
        def fail_watch(key, value):
            if key.startswith("engineering/followup/"):
                raise IOError("SYNTHETIC sensitive path")
            return append(key, value)
        with patch.object(store, "append_event", side_effect=fail_watch):
            result = host.prepare(attempt)
        self.assertEqual(result["failure_code"], "watch_registration_failed")
        self.assertNotIn("SYNTHETIC sensitive path", json.dumps(result))
        reservations = [e["event"] for e in decode_events(store.read_bytes(host._stream(attempt))) if e["event"]["kind"] == "reserved"]
        self.assertEqual([e["tool_name"] for e in reservations], [PROJECTS])
        self.assertEqual(bridge._record(attempt)["external_id"], "actual-synthetic-backtest-id")

    def test_pagination_conflict_queued_unknown_and_three_page_bound_stop(self):
        for scenario in ("conflict", "queued", "unknown", "absent"):
            with self.subTest(scenario=scenario):
                store, reg, bridge, attempt, controller = fixture()
                host = make_host(controller, attempt, read=True)
                self.discover(host, attempt)
                request = host.prepare(attempt)
                if scenario == "queued":
                    native = history(status="In Queue...", progress=0)
                elif scenario == "unknown":
                    native = history(); native["result"] = {"success": True, "rows": [["PRIVATE_ROW"]]}
                else:
                    native = history(backtest="other", total=4)
                host.accept_response(response(request, native))
                if scenario == "conflict":
                    request = host.prepare(attempt)
                    outcome = host.accept_response(response(request, history(backtest="other", page=2, total=3)))
                    self.assertEqual(outcome["failure_code"], "invalid_native_response")
                elif scenario == "absent":
                    for page in (2, 3):
                        request = host.prepare(attempt)
                        self.assertEqual(request["arguments"]["page"], page)
                        host.accept_response(response(request, history(backtest="other", page=page, total=4)))
                self.assertEqual(host.prepare(attempt)["action"], "attention_required")
                self.assertEqual(bridge._record(attempt)["status"], "pending")
                self.assertNotIn(b"PRIVATE_ROW", store.read_bytes(host._stream(attempt)))

    def test_completed_history_never_overrides_chat_connector_read_restriction(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        self.discover(host, attempt)
        request = host.prepare(attempt)
        host.accept_response(response(request, history()))
        result = host.prepare(attempt)
        self.assertEqual(result["failure_code"], "completed_read_not_authorized")
        watch = [item["event"]["kind"] for item in decode_events(store.read_bytes(controller._stream(attempt)))]
        self.assertNotIn("completed_read_reserved", watch)
        bad = ReadGrant(attempt, 17, "actual-synthetic-backtest-id", "transport_completed_reads", "b" * 64)
        authority = TransportAuthority("chat", frozenset(), frozenset(), "chat_connector", (bad,))
        self.assertFalse(authority.permits_read(FollowupHost._identity(controller.status(attempt))))

    def test_permitted_read_returns_parser_handoff_and_late_native_parser_can_settle(self):
        store, reg, bridge, attempt, controller = fixture()
        usage = reg.snapshot()["usage"]
        host = make_host(controller, attempt, read=True)
        self.discover(host, attempt)
        request = host.prepare(attempt)
        host.accept_response(response(request, history()))
        request = host.prepare(attempt)
        self.assertEqual(request["tool_name"], READ)
        native = completed_tool(backtestId="actual-synthetic-backtest-id")
        native["arguments"]["backtestId"] = "actual-synthetic-backtest-id"
        result = host.accept_response(response(request, native))
        self.assertEqual(result["action"], "awaiting_native_receipt")
        self.assertEqual(result["receipt_parser"], "tools/stage2.py backtest-result")
        self.assertEqual(host.prepare(attempt)["action"], "awaiting_native_receipt")
        self.assertEqual(bridge._record(attempt)["status"], "pending")
        payload = bridge.payload(attempt)
        wrapper = {key: completed(payload)[key] for key in ("cloud_report", "report_ref")}
        logs = log_tools(payload, wrapper)
        for log in logs:
            log["arguments"]["backtestId"] = "actual-synthetic-backtest-id"
        parsed = backtest_observation(payload, submission(payload)["deployment"], "actual-synthetic-backtest-id", native, logs)
        self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: parsed).status, "completed")
        self.assertEqual(host.command({"command": "sync", "attempt_id": attempt})["action"], "finished")
        self.assertEqual(host.prepare(attempt)["action"], "finished")
        self.assertEqual(reg.snapshot()["usage"], usage)
        for data in (store.read_bytes(host._stream(attempt)), store.read_bytes(controller._stream(attempt))):
            self.assertNotIn(b"SENSITIVE_FINANCIAL_SENTINEL", data)
            self.assertNotIn(b"SYNTHETIC_PRIVATE_PROJECT", data)

    def test_old_terminal_attempt_does_not_acquire_watch_or_host_stream(self):
        store, reg, bridge, attempt, controller = fixture()
        bridge.consume_completion(attempt, completion_source=lambda payload: completed(payload))
        host = make_host(controller, attempt)
        before = dict(store._data)
        self.assertEqual(host.prepare(attempt)["action"], "finished")
        self.assertEqual(host.command({"command": "sync", "attempt_id": attempt})["action"], "finished")
        self.assertEqual(store._data, before)

    def test_response_exact_binding_rejects_wrong_tool_arguments_types_correlation_and_fields(self):
        for mutate in (lambda m: m.update(tool_name="mcp__quantconnect__create_backtest"),
                       lambda m: m["arguments"].update(page=True),
                       lambda m: m["arguments"].update(projectId=17),
                       lambda m: m.update(correlation_id="f" * 32),
                       lambda m: m.update(now=DEADLINE.isoformat())):
            with self.subTest(mutate=mutate):
                store, reg, bridge, attempt, controller = fixture()
                host = make_host(controller, attempt)
                request = host.prepare(attempt)
                message = response(request, projects()); message["arguments"] = deepcopy(message["arguments"])
                mutate(message)
                message["result"] = {"success": True, "rows": [["DO_NOT_STORE_RAW_ROW"]]}
                self.assertEqual(host.accept_response(message)["failure_code"], "response_binding_rejected")
                audit = store.read_bytes(host._stream(attempt))
                host.accept_response(message)
                self.assertEqual(store.read_bytes(host._stream(attempt)), audit)
                self.assertNotIn(b"DO_NOT_STORE_RAW_ROW", audit)
                self.assertEqual(host.prepare(attempt)["action"], "attention_required")

    def test_identical_response_replay_idempotent_and_conflict_requires_attention(self):
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        request = host.prepare(attempt)
        message = response(request, projects())
        host.accept_response(message)
        before = store.read_bytes(host._stream(attempt))
        self.assertEqual(host.accept_response(message)["action"], "projects_observed")
        self.assertEqual(store.read_bytes(host._stream(attempt)), before)
        self.assertEqual(host.accept_response(response(request, projects((17, 18))))["failure_code"], "response_conflict")

    def test_cli_private_cwd_default_off_unknown_factory_never_loaded_and_no_now_override(self):
        script = ROOT / "tools/followup_host.py"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); (path / "private-marker").write_text("synthetic", encoding="utf-8")
            args = [sys.executable, "-B", str(script)]
            completed_run = subprocess.run(args + ["plan", "--attempt", "1" * 32, "--host-factory", "never_import_this:factory"],
                                           cwd=path, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(completed_run.stdout)["action"], "dispatch_disabled")
            lines = [json.dumps({"command": command, "attempt_id": "1" * 32}) for command in ("wake", "register", "sync", "status")]
            completed_run = subprocess.run(args + ["serve"], input="\n".join(lines) + "\n", cwd=path, capture_output=True, text=True, check=True)
            self.assertEqual([json.loads(line)["action"] for line in completed_run.stdout.splitlines()], ["dispatch_disabled"] * 4)
            self.assertEqual([item.name for item in path.iterdir()], ["private-marker"])
            for extra in (["--now", DEADLINE.isoformat()], ["--enable-dispatch"]):
                rejected = subprocess.run(args + ["plan", "--attempt", "1" * 32] + extra, cwd=path, capture_output=True, text=True)
                self.assertNotEqual(rejected.returncode, 0)

    def test_stdio_rejects_duplicate_keys_nonfinite_oversize_unterminated_and_proposal_grants(self):
        values = ['{"command":"wake","command":"status","attempt_id":"' + "1" * 32 + '"}\n',
                  '{"command":"wake","attempt_id":"' + "1" * 32 + '","now":NaN}\n',
                  json.dumps({"command": "wake", "attempt_id": "1" * 32, "grant": True}) + "\n",
                  '{"command":"wake"}', "x" * (host_module.MAX_LINE + 1) + "\n"]
        for value in values:
            with self.subTest(value=value[:80]):
                output = io.StringIO()
                host_module.serve(FollowupHost(), io.StringIO(value), output)
                result = json.loads(output.getvalue())
                self.assertEqual(result["failure_code"], "invalid_message_or_store_state")
                self.assertNotIn("NaN", output.getvalue())

    def test_utf8_byte_limit_and_direct_response_size_limit(self):
        value = json.dumps({"command": "wake", "attempt_id": "1" * 32,
                            "padding": "界" * (host_module.MAX_LINE // 2)}, ensure_ascii=False) + "\n"
        output = io.StringIO()
        class Probe:
            calls = 0
            def command(self, message):
                self.calls += 1
                raise AssertionError("oversize UTF-8 input reached host command")
        probe = Probe()
        host_module.serve(probe, io.StringIO(value), output)
        self.assertEqual(probe.calls, 0)
        self.assertEqual(json.loads(output.getvalue())["failure_code"], "invalid_message_or_store_state")
        store, reg, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        request = host.prepare(attempt)
        message = response(request, projects())
        message["result"] = {"success": True, "rows": ["界" * (host_module.MAX_LINE // 2)]}
        before = store.read_bytes(host._stream(attempt))
        self.assertEqual(host.accept_response(message)["failure_code"], "response_too_large")
        self.assertEqual(store.read_bytes(host._stream(attempt)), before)
        self.assertNotIn("界".encode(), store.read_bytes(host._stream(attempt)))


if __name__ == "__main__":
    unittest.main()
