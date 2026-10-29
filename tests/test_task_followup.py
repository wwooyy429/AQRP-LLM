"""Known-answer, concurrency and boundary tests; synthetic metadata only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, decode_events
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController, TaskFollowupError, validate_policy
from test_engineering_tasks import raw_plan, submission, completed


POLICY = {"schema_version": 1, "notification_grace_seconds": 1800, "max_history_pages": 3}
SUBMITTED = datetime(2026, 10, 29, 10, tzinfo=timezone.utc)
DEADLINE = SUBMITTED + timedelta(minutes=30)


def fixture():
    store = MemoryArtifactStore()
    with patch("qresearch.registry.datetime") as clock:
        clock.now.return_value = SUBMITTED
        registry = Registry(store, {kind: {"total": 10, "normal": 8, "reserve": 2}
                                   for kind in ("configurations", "research", "lean")})
        plan = EngineeringTaskPlan.from_dict(raw_plan(), discovered_project_ids=(17,))
        bridge = EngineeringTaskBridge(registry, plan)
        bridge.register()
        research = bridge.claim("research")
        payload = bridge.payload(research)
        bridge.record_submission(research, submission(payload))
        bridge.consume_completion(research, completion_source=lambda _: completed(payload))
        lean = bridge.claim("lean")
        payload = bridge.payload(lean)
        bridge.record_submission(lean, submission(payload))
    return store, registry, bridge, lean.attempt_id, TaskFollowupController(registry, POLICY)


def history(backtest="actual-synthetic-backtest-id", status="Completed.", progress=1, page=1,
            total=1, entries=None, success=True):
    native = {"success": success, "backtests": entries if entries is not None else [
        {"backtestId": backtest, "status": status, "progress": progress,
         "name": "synthetic", "created": "2026-10-29 10:00:00", "snapshotId": 1,
         "tradeableDates": 2, "netProfit": 12345.67891}], "totalPages": total}
    if not success:
        native.pop("backtests"); native["errors"] = ["SYNTHETIC server unavailable"]
    return {"tool_name": "mcp__quantconnect__list_backtests", "arguments": {"projectId": 17, "page": page},
            "result": {"structuredContent": deepcopy(native),
                       "content": [{"type": "text", "text": json.dumps(native)}], "isError": False}}


def mutate_native(envelope, edit):
    native = envelope["result"]["structuredContent"]
    edit(native)
    envelope["result"]["content"][0]["text"] = json.dumps(native)
    return envelope


def reseal_synthetic_watch(store, controller, attempt, edit):
    """Tamper metadata while retaining a valid hash chain for boundary tests."""
    key = controller._stream(attempt)
    events = [deepcopy(item["event"]) for item in decode_events(store.read_bytes(key))]
    edit(events)
    replacement = MemoryArtifactStore()
    for event in events:
        replacement.append_event(key, event)
    store._data[key] = replacement.read_bytes(key)


class TaskFollowupTests(unittest.TestCase):
    def test_policy_validation_is_pure_and_returns_a_defensive_copy(self):
        supplied = deepcopy(POLICY)
        copied = validate_policy(supplied)
        self.assertEqual(copied, POLICY)
        self.assertIsNot(copied, supplied)
        supplied["max_history_pages"] = 99
        self.assertEqual(copied["max_history_pages"], 3)
        with self.assertRaises(TaskFollowupError): validate_policy(supplied)

    def reserve(self, controller, attempt, now=DEADLINE):
        return controller.next_action(attempt, now=now, discovered_project_ids=(17,))

    def test_exact_30_minute_deadline_comes_from_original_journal_not_restart(self):
        store, reg, bridge, attempt, controller = fixture()
        before = store.read_bytes(reg.JOURNAL)
        initial = controller.register(attempt)
        self.assertEqual(initial["submitted_at"], "2026-10-29T10:00:00+00:00")
        self.assertEqual(initial["deadline"], "2026-10-29T10:30:00+00:00")
        reopened = TaskFollowupController(reg, POLICY)
        wait = reopened.next_action(attempt, now=DEADLINE - timedelta(microseconds=1))
        self.assertEqual(wait["action"], "wait_for_delivery")
        self.assertFalse(wait["should_execute"])
        ready = self.reserve(reopened, attempt)
        self.assertTrue(ready["should_execute"])
        self.assertEqual(ready["tool_request"], {"tool_name": "mcp__quantconnect__list_backtests",
            "arguments": {"projectId": 17, "page": 1}})
        self.assertEqual(store.read_bytes(reg.JOURNAL), before)
        reservation = decode_events(store.read_bytes(controller._stream(attempt)))[-1]["event"]
        self.assertEqual(reservation["reserved_at"], "2026-10-29T10:30:00+00:00")

    def test_reserved_clocks_reject_early_naive_missing_and_non_UTC_tampering(self):
        invalid = ["2026-10-29T10:29:59.999999+00:00", "2026-10-29T10:30:00",
                   "2026-10-29T18:30:00+08:00", None]
        for clock in invalid:
            with self.subTest(clock=clock):
                store, reg, bridge, attempt, controller = fixture()
                self.reserve(controller, attempt)
                def edit(events):
                    if clock is None:
                        events[-1].pop("reserved_at")
                    else:
                        events[-1]["reserved_at"] = clock
                reseal_synthetic_watch(store, controller, attempt, edit)
                with self.assertRaises(TaskFollowupError): controller.status(attempt)

    def test_history_page_reservations_reject_clock_rollback_at_dispatch_and_replay(self):
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt, DEADLINE + timedelta(seconds=10))
        controller.record_history(attempt, history(backtest="other", total=3))
        before = store.read_bytes(controller._stream(attempt))
        with self.assertRaises(TaskFollowupError):
            self.reserve(controller, attempt, DEADLINE + timedelta(seconds=5))
        self.assertEqual(store.read_bytes(controller._stream(attempt)), before)
        self.reserve(controller, attempt, DEADLINE + timedelta(seconds=20))
        reseal_synthetic_watch(store, controller, attempt,
            lambda events: events[-1].update(reserved_at=(DEADLINE + timedelta(seconds=5)).isoformat()))
        with self.assertRaises(TaskFollowupError): controller.status(attempt)

    def test_completed_read_reservation_UTC_clock_is_auditable_and_not_backdated(self):
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt, DEADLINE + timedelta(seconds=10))
        controller.record_history(attempt, history())
        ready = self.reserve(controller, attempt, DEADLINE + timedelta(seconds=20))
        self.assertEqual(ready["action"], "read_completed_backtest")
        event = decode_events(store.read_bytes(controller._stream(attempt)))[-1]["event"]
        self.assertEqual(event["reserved_at"], (DEADLINE + timedelta(seconds=20)).isoformat())
        reseal_synthetic_watch(store, controller, attempt,
            lambda events: events[-1].update(reserved_at=(DEADLINE + timedelta(seconds=5)).isoformat()))
        with self.assertRaises(TaskFollowupError): controller.status(attempt)

    def test_concurrent_one_reservation_then_unknown_response_never_redispatches(self):
        store, reg, bridge, attempt, controller = fixture()
        before = reg.snapshot()["usage"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            calls = list(pool.map(lambda _: self.reserve(controller, attempt), range(16)))
        self.assertEqual(sum(item["should_execute"] for item in calls), 1)
        self.assertTrue(all(item["action"] == "attention_required" for item in calls if not item["should_execute"]))
        restarted = TaskFollowupController(reg, POLICY)
        unknown = self.reserve(restarted, attempt, DEADLINE + timedelta(days=1))
        self.assertEqual(unknown["status"], "attention_required")
        self.assertFalse(unknown["should_execute"])
        self.assertEqual(reg.snapshot()["usage"], before)

    def test_native_terminal_proof_allows_one_bound_completed_read_but_does_not_settle(self):
        store, reg, bridge, attempt, controller = fixture()
        journal = store.read_bytes(reg.JOURNAL)
        self.reserve(controller, attempt)
        observed = controller.record_history(attempt, history())
        self.assertFalse(observed["should_execute"])
        ready = self.reserve(controller, attempt)
        self.assertTrue(ready["should_execute"])
        self.assertEqual(ready["action"], "read_completed_backtest")
        self.assertEqual(ready["tool_request"]["arguments"], {"projectId": 17, "backtestId": "actual-synthetic-backtest-id"})
        self.assertFalse(self.reserve(controller, attempt)["should_execute"])
        self.assertEqual(bridge._record(attempt)["status"], "pending")
        self.assertEqual(store.read_bytes(reg.JOURNAL), journal)
        watch = store.read_bytes(controller._stream(attempt))
        self.assertNotIn(b"12345.67891", watch)
        self.assertNotIn(b"netProfit", watch)

    def test_runtime_error_is_terminal_evidence_not_a_success_or_new_attempt(self):
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt)
        controller.record_history(attempt, history(status="Runtime Error", progress=0.1))
        ready = self.reserve(controller, attempt)
        self.assertEqual(ready["action"], "read_completed_backtest")
        self.assertEqual(bridge._record(attempt)["status"], "pending")

    def test_still_running_or_queued_is_attention_not_periodic_polling(self):
        for state in ("In Queue...", "In Progress..."):
            with self.subTest(state=state):
                store, reg, bridge, attempt, controller = fixture()
                self.reserve(controller, attempt)
                controller.record_history(attempt, history(status=state, progress=0.8))
                for delta in (timedelta(), timedelta(days=1)):
                    result = self.reserve(controller, attempt, DEADLINE + delta)
                    self.assertEqual(result["action"], "attention_required")
                    self.assertFalse(result["should_execute"])
                self.assertEqual(len(reg.snapshot()["attempts"]), 2)

    def test_known_pagination_is_bounded_to_three_pages_without_new_budget(self):
        store, reg, bridge, attempt, controller = fixture()
        before = reg.snapshot()["usage"]
        for page in (1, 2, 3):
            ready = self.reserve(controller, attempt)
            self.assertEqual(ready["tool_request"]["arguments"]["page"], page)
            controller.record_history(attempt, history(backtest="other-" + str(page), page=page, total=8))
        result = self.reserve(controller, attempt)
        self.assertEqual(result["action"], "attention_required")
        self.assertFalse(result["should_execute"])
        self.assertEqual(reg.snapshot()["usage"], before)

    def test_end_of_directory_or_unknown_pagination_has_no_speculative_next_page(self):
        for missing_total in (False, True):
            with self.subTest(missing_total=missing_total):
                store, reg, bridge, attempt, controller = fixture()
                self.reserve(controller, attempt)
                tool = history(backtest="other", total=1)
                if missing_total:
                    mutate_native(tool, lambda value: value.pop("totalPages"))
                controller.record_history(attempt, tool)
                self.assertEqual(self.reserve(controller, attempt)["action"], "attention_required")

    def test_native_failure_has_no_terminal_authority_and_original_response_is_idempotent(self):
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt)
        tool = history(success=False)
        controller.record_history(attempt, tool)
        data = store.read_bytes(controller._stream(attempt))
        controller.record_history(attempt, tool)
        self.assertEqual(data, store.read_bytes(controller._stream(attempt)))
        self.assertEqual(self.reserve(controller, attempt)["action"], "attention_required")
        self.assertNotIn(b"SYNTHETIC server unavailable", data)

    def test_invalid_typed_states_duplicates_and_foreign_project_are_rejected(self):
        changes = [lambda e: e["arguments"].update(projectId=18),
                   lambda e: e["arguments"].update(page=True),
                   lambda e: mutate_native(e, lambda n: n["backtests"][0].update(status=True)),
                   lambda e: mutate_native(e, lambda n: n["backtests"][0].update(progress=True)),
                   lambda e: mutate_native(e, lambda n: n["backtests"][0].update(progress=0.9)),
                   lambda e: mutate_native(e, lambda n: n["backtests"].append(deepcopy(n["backtests"][0]))),
                   lambda e: mutate_native(e, lambda n: n["backtests"][0].update(rows=[1])),
                   lambda e: mutate_native(e, lambda n: n.update(totalPages=False))]
        for change in changes:
            with self.subTest(change=change):
                store, reg, bridge, attempt, controller = fixture()
                self.reserve(controller, attempt)
                tool = history(); change(tool)
                before = store.read_bytes(controller._stream(attempt))
                with self.assertRaises((TaskFollowupError, ValueError)):
                    controller.record_history(attempt, tool)
                self.assertEqual(store.read_bytes(controller._stream(attempt)), before)
                self.assertEqual(self.reserve(controller, attempt)["action"], "attention_required")

    def test_carrier_disagreement_and_conflicting_replays_are_rejected(self):
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt)
        bad = history(); bad["result"]["content"][0]["text"] = json.dumps({"success": False})
        with self.assertRaises(TaskFollowupError): controller.record_history(attempt, bad)
        good = history(); controller.record_history(attempt, good)
        changed = history(status="Runtime Error", progress=0.2)
        with self.assertRaises(TaskFollowupError): controller.record_history(attempt, changed)

    def test_wrong_tool_unreserved_page_and_absent_listing_cannot_dispatch(self):
        store, reg, bridge, attempt, controller = fixture()
        controller.register(attempt)
        before = store.read_bytes(controller._stream(attempt))
        with self.assertRaises(TaskFollowupError): controller.record_history(attempt, history())
        missing = controller.next_action(attempt, now=DEADLINE, discovered_project_ids=())
        self.assertEqual(missing["action"], "list_projects")
        self.assertEqual(missing["reason"], "trusted_project_listing_required")
        self.assertFalse(missing["should_execute"])
        self.assertIsNone(missing["tool_request"])
        with self.assertRaises(TaskFollowupError): controller.next_action(attempt, now=DEADLINE, discovered_project_ids=(18,))
        with self.assertRaises(TaskFollowupError): controller.next_action(attempt, now=DEADLINE, discovered_project_ids=(True,))
        self.assertEqual(store.read_bytes(controller._stream(attempt)), before)

    def test_missing_listing_after_timeout_never_creates_watch_or_reserves(self):
        store, reg, bridge, attempt, controller = fixture()
        before = dict(store._data)
        result = controller.next_action(attempt, now=DEADLINE)
        self.assertEqual(result["action"], "list_projects")
        self.assertFalse(result["should_execute"])
        self.assertEqual(store._data, before)
        self.assertEqual(controller.next_action(attempt, now=SUBMITTED)["action"], "wait_for_delivery")

    def test_register_status_sync_do_not_dispatch_or_reset_deadline(self):
        store, reg, bridge, attempt, controller = fixture()
        self.assertEqual(controller.status(attempt)["action"], "register_watch")
        self.assertFalse(store.exists(controller._stream(attempt)))
        controller.sync(attempt)
        self.assertFalse(store.exists(controller._stream(attempt)))
        initial = controller.register(attempt)
        data = store.read_bytes(controller._stream(attempt))
        self.assertEqual(initial["deadline"], controller.register(attempt)["deadline"])
        controller.status(attempt); controller.sync(attempt)
        self.assertEqual(data, store.read_bytes(controller._stream(attempt)))

    def test_only_registry_terminal_finishes_existing_watch_once_and_never_backfills_old(self):
        for create_watch in (False, True):
            with self.subTest(create_watch=create_watch):
                store, reg, bridge, attempt, controller = fixture()
                if create_watch: controller.register(attempt)
                payload = bridge.payload(attempt)
                bridge.consume_completion(attempt, completion_source=lambda _: completed(payload))
                before = store.read_bytes(reg.JOURNAL)
                result = controller.sync(attempt)
                self.assertEqual(result["action"], "finished")
                self.assertEqual(result["status"], "completed")
                self.assertEqual(controller.next_action(attempt, now=None)["action"], "finished")
                self.assertEqual(store.exists(controller._stream(attempt)), create_watch)
                if create_watch:
                    events = decode_events(store.read_bytes(controller._stream(attempt)))
                    self.assertEqual([x["event"]["kind"] for x in events], ["registered", "registry_finished"])
                    data = store.read_bytes(controller._stream(attempt)); controller.sync(attempt)
                    self.assertEqual(data, store.read_bytes(controller._stream(attempt)))
                self.assertEqual(store.read_bytes(reg.JOURNAL), before)

    def test_readonly_status_exposes_unknown_dispatch_attention(self):
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt)
        data = store.read_bytes(controller._stream(attempt))
        self.assertEqual(controller.status(attempt)["action"], "attention_required")
        self.assertEqual(store.read_bytes(controller._stream(attempt)), data)
        controller.record_history(attempt, history())
        self.reserve(controller, attempt)
        self.assertEqual(controller.status(attempt)["action"], "attention_required")

    def test_later_duplicate_pending_timestamp_cannot_reset_original_deadline(self):
        store, reg, bridge, attempt, controller = fixture()
        original = next(x["event"] for x in decode_events(store.read_bytes(reg.JOURNAL))
                        if x["event"].get("kind") == "pending" and x["event"].get("attempt_id") == attempt)
        with patch("qresearch.registry.datetime") as clock:
            clock.now.return_value = SUBMITTED + timedelta(days=1)
            reg._append({k: v for k, v in original.items() if k != "recorded_at"})
        self.assertEqual(controller.register(attempt)["deadline"], DEADLINE.isoformat())
        self.assertTrue(self.reserve(controller, attempt)["should_execute"])

    def test_policy_clock_and_unaccepted_attempt_rejected(self):
        store, reg, bridge, attempt, controller = fixture()
        for key in POLICY:
            for value in (True, 1.0, -1):
                policy = deepcopy(POLICY); policy[key] = value
                with self.assertRaises(TaskFollowupError): TaskFollowupController(reg, policy)
        policy = deepcopy(POLICY); policy["extra"] = 1
        with self.assertRaises(TaskFollowupError): TaskFollowupController(reg, policy)
        for clock in (None, True, 42.0, "2026-10-29", SUBMITTED.replace(tzinfo=None), SUBMITTED - timedelta(seconds=1)):
            with self.subTest(clock=clock), self.assertRaises(TaskFollowupError):
                controller.next_action(attempt, now=clock)
        research = next(x["attempt_id"] for x in reg.snapshot()["attempts"] if x["stage"] == "research")
        with self.assertRaises(TaskFollowupError): controller.register(research)
        with self.assertRaises(TaskFollowupError): controller.register("f" * 32)

    def test_unknown_pagination_change_and_nonfinite_metadata_fail_closed(self):
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt)
        controller.record_history(attempt, history(backtest="other", total=2))
        self.reserve(controller, attempt)
        with self.assertRaises(TaskFollowupError): controller.record_history(attempt, history(page=2, total=3))
        self.assertEqual(self.reserve(controller, attempt)["action"], "attention_required")
        store, reg, bridge, attempt, controller = fixture()
        self.reserve(controller, attempt)
        tool = history(); mutate_native(tool, lambda n: n["backtests"][0].update(progress=float("nan")))
        with self.assertRaises((ValueError, TaskFollowupError)): controller.record_history(attempt, tool)


if __name__ == "__main__": unittest.main()
