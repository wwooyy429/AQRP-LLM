"""Synthetic boundary/known-answer checks; never call a provider or real Registry."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stderr

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, content_hash, decode_events
from qresearch.terminal_receipt_tasks import (TerminalReceiptCollector, TerminalReadAuthority,
    PROJECTS, READ, LOGS, ORDERS)
from test_engineering_receipts import context, envelope, completed_tool, log_tools, report
from test_engineering_tasks import submission, completed
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.registry import Registry
import terminal_receipt_tasks as cli


def fixture(store=None, **overrides):
    payload, deployment = context("lean")
    authority = TerminalReadAuthority("1" * 32, 17, "native-backtest-id", "delivered_terminal_notification", "e" * 64)
    values = dict(payload=payload, deployment=deployment, backtest_id="native-backtest-id",
                  store=MemoryArtifactStore() if store is None else store, authority=authority, enabled=True)
    values.update(overrides)
    return TerminalReceiptCollector(**values)


def projects():
    return envelope("list_projects", {"page": 1}, {"success": True,
        "projects": [{"projectId": 17, "name": "SYNTHETIC ONLY", "language": "Py"}],
        "page": 1, "totalPages": 1, "nextPage": None})


def orders(**changes):
    native = {"success": True, "orders": [], "totalOrders": 0, "totalPages": 1}
    native.update(changes)
    return envelope("read_backtest_orders", {"projectId": 17, "backtestId": "native-backtest-id", "page": 1}, native)


def response(request, value):
    return {"command": "response", "attempt_id": "1" * 32,
            "correlation_id": request["correlation_id"], "tool_name": value["tool_name"],
            "arguments": value["arguments"], "result": value["result"]}


class TerminalReceiptTests(unittest.TestCase):
    def send(self, collector, value, receipts=None):
        request = collector.prepare()
        self.assertEqual(request["type"], "tool_request")
        self.assertEqual({key: request[key] for key in ("tool_name", "arguments")},
                         {key: value[key] for key in ("tool_name", "arguments")})
        if receipts is not None:
            receipts[content_hash(value)] = deepcopy(value)
        result = collector.accept_response(response(request, value))
        return request, result

    def completed(self, collector, pages=2, order_value=None):
        receipts = {}
        for value in [projects(), completed_tool(), *log_tools(collector.payload, pages=pages),
                      orders() if order_value is None else order_value]:
            _, result = self.send(collector, value, receipts)
        return receipts, result

    def test_default_off_does_not_touch_store_or_context(self):
        class Forbidden:
            def __getattribute__(self, name):
                raise AssertionError("Off collector touched external input")
        collector = TerminalReceiptCollector(Forbidden(), store=Forbidden())
        self.assertEqual(collector.prepare()["action"], "dispatch_disabled")
        self.assertEqual(collector.accept_response(None)["action"], "dispatch_disabled")
        self.assertEqual(collector.command({"command": "settle"})["action"], "dispatch_disabled")

    def test_read_authority_is_exact_typed_bound_and_not_directory_status(self):
        for basis in ("directory_completed", "elapsed_grace", "transport_completed_reads", ""):
            with self.assertRaises(ValueError):
                TerminalReadAuthority("1" * 32, 17, "native-backtest-id", basis, "a" * 64)
        with self.assertRaises(ValueError):
            fixture(authority={"basis": "delivered_terminal_notification"})
        with self.assertRaises(ValueError):
            fixture(authority=TerminalReadAuthority("2" * 32, 17, "native-backtest-id", "historical_user_reference", "e" * 64))
        with self.assertRaises(ValueError):
            TerminalReadAuthority("1" * 32, True, "native-backtest-id", "delivered_terminal_notification", "e" * 64)
        class Derived(TerminalReadAuthority):
            pass
        with self.assertRaises(ValueError):
            fixture(authority=Derived("1" * 32, 17, "native-backtest-id", "delivered_terminal_notification", "e" * 64))

    def test_known_answer_full_chain_and_no_raw_panels_or_chunks_in_journal(self):
        collector = fixture()
        receipts, status = self.completed(collector)
        self.assertEqual(status["action"], "ready_for_reconciliation")
        observed = collector.reconcile(receipts.__getitem__)
        self.assertTrue(observed["same_attempt_settlement_ready"])
        self.assertEqual(observed["completion"]["cloud_report"], report(collector.payload)["cloud_report"])
        self.assertEqual(observed["zero_order_evidence"]["orders_count"], 0)
        saved = b"".join(collector.store._data.values()).decode()
        self.assertNotIn("SENSITIVE_FINANCIAL_SENTINEL", saved)
        # The exact query is permitted metadata; the encoded report chunks are not.
        native_line = log_tools(collector.payload)[0]["result"]["structuredContent"]["logs"][0]
        self.assertNotIn(native_line.split()[-1], saved)
        self.assertNotIn('"logs":', saved)
        kinds = [row["event"]["kind"] for row in decode_events(collector.store.read_bytes(collector.stream))]
        self.assertEqual(kinds.count("reserved"), 5)  # discover, terminal, 2 logs, orders

    def test_unknown_reserved_response_is_never_reemitted_after_restart(self):
        collector = fixture(); request = collector.prepare()
        reopened = fixture(store=collector.store)
        self.assertEqual(reopened.prepare()["action"], "reserved_response_unknown")
        self.assertEqual(reopened.accept_response(response(request, projects()))["action"], "ready_for_next_request")
        self.assertEqual(reopened.prepare()["tool_name"], READ)

    def test_same_response_replay_idempotent_conflict_and_wrong_correlation_rejected(self):
        collector = fixture(); request = collector.prepare(); message = response(request, projects())
        bad = dict(message, correlation_id="2" * 32)
        with self.assertRaises(ValueError):collector.accept_response(bad)
        result = collector.accept_response(message)
        before = collector.store.read_bytes(collector.stream)
        self.assertEqual(collector.accept_response(message), result)
        self.assertEqual(before, collector.store.read_bytes(collector.stream))
        changed = deepcopy(message); changed["result"]["structuredContent"]["nextPage"] = 2
        with self.assertRaises(ValueError):collector.accept_response(changed)

    def test_boolean_argument_alias_does_not_match_integer_page(self):
        collector = fixture(); request = collector.prepare(); value = projects()
        value["arguments"]["page"] = True
        with self.assertRaises(ValueError):collector.accept_response(response(request, value))
        self.assertEqual(collector.status()["action"], "reserved_response_unknown")
        self.assertEqual(collector.accept_response(response(request, projects()))["action"], "ready_for_next_request")

    def test_project_absent_duplicate_or_malformed_page_permanently_stops_chain(self):
        for change in (lambda n:n.update(page=True), lambda n:n.update(projects=[]),
                       lambda n:n["projects"].append(deepcopy(n["projects"][0]))):
            collector = fixture(); value = projects(); change(value["result"]["structuredContent"])
            value["result"]["content"][0]["text"] = json.dumps(value["result"]["structuredContent"])
            _, status = self.send(collector, value)
            self.assertEqual(status["action"], "attention_required")
            self.assertFalse(collector.prepare()["should_execute"])

    def test_nonterminal_invalid_clock_and_boolean_progress_are_rejected(self):
        for changed in ({"status": "In Progress...", "completed": False, "progress": 0.4},
                        {"progress": True}, {"error": False}, {"projectId": True}):
            collector = fixture(); self.send(collector, projects())
            _, status = self.send(collector, completed_tool(**changed))
            self.assertEqual(status["action"], "attention_required")

    def test_zero_order_requires_native_count_and_empty_rows_not_missing_stat(self):
        for native in ({"totalOrders": False}, {"totalOrders": 1}, {"orders": [{"private": "ORDER_ROW_SENTINEL"}]},
                       {"totalPages": 2}, {"totalOrders": None}):
            collector = fixture(); receipts, status = self.completed(collector, order_value=orders(**native))
            self.assertEqual(status["action"], "attention_required")
            self.assertNotIn("ORDER_ROW_SENTINEL", b"".join(collector.store._data.values()).decode())
            with self.assertRaises(ValueError):collector.reconcile(receipts.__getitem__)

    def test_exact_query_and_maximum_eight_log_pages_enforced(self):
        collector = fixture(max_log_pages=2)
        self.send(collector, projects());self.send(collector, completed_tool())
        value = log_tools(collector.payload, pages=3)[0]
        _, status = self.send(collector, value)
        self.assertEqual(status["action"], "attention_required")
        with self.assertRaises(ValueError):fixture(max_log_pages=True)
        with self.assertRaises(ValueError):fixture(max_log_pages=9)

    def test_duplicate_chunk_across_pages_and_incomplete_final_page_stop(self):
        for duplicate in (True, False):
            collector = fixture(); self.send(collector, projects());self.send(collector, completed_tool())
            values = log_tools(collector.payload, pages=2)
            first = values[0]["result"]["structuredContent"]["logs"][0]
            native = values[1]["result"]["structuredContent"]
            if duplicate:native["logs"].append(first)
            else:native["logs"].pop()
            values[1]["result"]["content"][0]["text"] = json.dumps(native)
            self.send(collector, values[0]);_, status = self.send(collector, values[1])
            self.assertEqual(status["action"], "attention_required")

    def test_rehydration_must_return_the_original_exact_envelope(self):
        collector = fixture(); receipts, _ = self.completed(collector)
        def changed(key):
            value = deepcopy(receipts[key]);value["arguments"]["projectId"] = 99;return value
        with self.assertRaises(ValueError):collector.reconcile(changed)
        self.assertEqual(collector.status()["action"], "ready_for_reconciliation")

    def test_mutating_caller_payload_after_construction_does_not_retarget(self):
        payload, deployment = context("lean");collector = fixture(payload=payload, deployment=deployment)
        payload["identity"]["project_id"] = 99;deployment["input_hash"] = "0" * 64
        collector.payload["identity"]["project_id"] = 98
        collector.binding["identity"]["project_id"] = 97
        collector.deployment["input_hash"] = "0" * 64
        self.send(collector, projects())
        self.assertEqual(collector.prepare()["arguments"]["projectId"], 17)
        changed = fixture(store=collector.store, authority=TerminalReadAuthority("1" * 32, 17, "native-backtest-id", "historical_user_reference", "e" * 64))
        with self.assertRaises(ValueError):changed.status()

    def test_existing_bridge_same_attempt_settlement_is_idempotent_no_extra_debit(self):
        payload, deployment = context("research")
        store = MemoryArtifactStore()
        registry = Registry(store, {kind: {"total": 10, "normal": 8, "reserve": 2}
                                  for kind in ("configurations", "research", "lean")})
        plan = EngineeringTaskPlan.from_dict(payload["plan"], discovered_project_ids=[17])
        bridge = EngineeringTaskBridge(registry, plan)
        bridge.register()
        research = bridge.claim("research")
        research_payload = bridge.payload(research)
        bridge.record_submission(research, submission(research_payload))
        bridge.consume_completion(research, completion_source=lambda _: completed(research_payload))
        lean = bridge.claim("lean"); lean_payload = bridge.payload(lean)
        receipt = submission(lean_payload); receipt["external_id"] = "native-backtest-id"
        receipt["raw_receipt"]["backtestId"] = "native-backtest-id"
        bridge.record_submission(lean, receipt)
        authority = TerminalReadAuthority(lean.attempt_id, 17, "native-backtest-id", "delivered_terminal_notification", "e" * 64)
        collector = TerminalReceiptCollector(lean_payload, deployment, "native-backtest-id", store=store,
                                             authority=authority, enabled=True)
        receipts = {}
        native_responses = [projects(), completed_tool(), *log_tools(lean_payload, pages=2), orders()]
        for value in native_responses:
            request = collector.prepare();receipts[content_hash(value)] = deepcopy(value)
            message = response(request, value);message["attempt_id"] = lean.attempt_id
            collector.accept_response(message)
        usage = registry.snapshot()["usage"]
        self.assertEqual(collector.settle(bridge, receipts.__getitem__).status, "completed")
        journal = store.read_bytes(registry.JOURNAL)
        self.assertEqual(collector.settle(bridge, receipts.__getitem__).status, "completed")
        self.assertEqual(store.read_bytes(registry.JOURNAL), journal)
        self.assertEqual(registry.snapshot()["usage"], usage)
        with self.assertRaises(ValueError):collector.settle(object(), receipts.__getitem__)

    def test_concurrent_reservation_has_one_emission(self):
        store = MemoryArtifactStore()
        with ThreadPoolExecutor(max_workers=6) as pool:
            values = list(pool.map(lambda _:fixture(store=store).prepare(), range(18)))
        self.assertEqual(sum(value["type"] == "tool_request" for value in values), 1)

    def test_native_runtime_failure_is_reconcilable_without_success_logs_or_orders(self):
        collector = fixture();receipts = {}
        self.send(collector, projects(), receipts)
        _, status = self.send(collector, completed_tool(status="Runtime Error", progress=0.2, completed=True, error="PRIVATE_ERROR_SENTINEL"), receipts)
        self.assertEqual(status["action"], "ready_for_reconciliation")
        reconciled = collector.reconcile(receipts.__getitem__)
        self.assertEqual(reconciled["completion"]["platform"]["status"], "failed")
        self.assertIsNone(reconciled["zero_order_evidence"])
        self.assertEqual(reconciled["evidence_collection"], {"native_terminal_collected": True,
            "engineering_logs_collected": False, "independent_zero_orders_collected": False,
            "success_receipt_chain_complete": False})
        self.assertFalse(collector.prepare()["should_execute"])
        self.assertNotIn("PRIVATE_ERROR_SENTINEL", b"".join(collector.store._data.values()).decode())

    def test_native_error_carrier_is_settleable_but_unconfirmed_transport_error_is_not(self):
        for errors, marker in ((["The backtest ended with a runtime error.", "PRIVATE_DIAGNOSTIC"], True),
                               (["Connection timed out"], False)):
            collector = fixture();receipts = {};self.send(collector, projects(), receipts)
            value = envelope("read_backtest", {"projectId": 17, "backtestId": "native-backtest-id"},
                             {"success": False, "errors": errors})
            value["result"]["isError"] = True
            _, status = self.send(collector, value, receipts)
            if marker:
                self.assertEqual(status["action"], "ready_for_reconciliation")
                result = collector.reconcile(receipts.__getitem__)
                self.assertEqual(result["completion"]["platform"]["status"], "runtime_error")
                self.assertFalse(result["evidence_collection"]["success_receipt_chain_complete"])
            else:
                self.assertEqual(status["action"], "attention_required")
                with self.assertRaises(ValueError):collector.reconcile(receipts.__getitem__)

    def test_proven_native_failure_settles_existing_attempt_once_without_order_query(self):
        from test_task_followup import fixture as pending_fixture
        store, registry, bridge, attempt, _ = pending_fixture()
        payload = bridge.payload(attempt)
        deployment = {"source_manifest_hash": "a" * 64, "deployment_hash": "b" * 64, "input_hash": "f" * 64}
        bid = "actual-synthetic-backtest-id"
        grant = TerminalReadAuthority(attempt, 17, bid, "delivered_terminal_notification", "e" * 64)
        collector = TerminalReceiptCollector(payload, deployment, bid, store=store, authority=grant, enabled=True)
        failed = envelope("read_backtest", {"projectId": 17, "backtestId": bid}, {"success": False,
            "errors": ["The backtest ended with a runtime error.", "SYNTHETIC_INITIALIZE_FAILURE"]})
        failed["result"]["isError"] = True
        receipts = {}
        usage = registry.snapshot()["usage"]
        for value in (projects(), failed):
            request = collector.prepare();receipts[content_hash(value)] = deepcopy(value)
            message = response(request, value);message["attempt_id"] = attempt
            collector.accept_response(message)
        self.assertEqual(collector.status()["action"], "ready_for_reconciliation")
        self.assertEqual(collector.settle(bridge, receipts.__getitem__).status, "failed")
        after = store.read_bytes(registry.JOURNAL)
        self.assertEqual(collector.settle(bridge, receipts.__getitem__).status, "failed")
        self.assertEqual(after, store.read_bytes(registry.JOURNAL))
        self.assertEqual(usage, registry.snapshot()["usage"])

    def test_cli_off_does_not_accept_grants_or_unrestricted_requests(self):
        incoming = io.StringIO('{"command":"wake","authority":{"basis":"delivered_terminal_notification"}}\n{"command":"wake"}\n')
        outgoing = io.StringIO();self.assertEqual(cli.main(["serve"], input_stream=incoming, output_stream=outgoing), 0)
        values = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual(values[0]["action"], "attention_required")
        self.assertEqual(values[1]["action"], "dispatch_disabled")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):cli.main(["status", "--enable-dispatch"])
        completed = subprocess.run([sys.executable, "-B", str(ROOT/"tools/terminal_receipt_tasks.py"), "status"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["action"], "dispatch_disabled")


if __name__ == "__main__":
    unittest.main()
