"""WR-21 known-answer settlement gates, using disposable synthetic ledgers."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import canonical_json
from qresearch.engineering_tasks import EngineeringTaskError
from qresearch.registry import RegistryError
import qresearch.engineering_receipts as receipts
import stage2 as cli
from test_engineering_receipts import context, envelope, research_tool
from test_native_research_failure import bind, error_tool, read_cell
from test_wr17_engineering_recovery import SyntheticFixture


class WR21ResearchDispatchTests(unittest.TestCase):
    def assert_rejected_unchanged(self, fixture, tool):
        before = fixture.registry.snapshot()
        saved = dict(fixture.store._data)
        with self.assertRaises((EngineeringTaskError, receipts.ReceiptParseError, ValueError)):
            fixture.command("research-result", attempt=fixture.attempt, tool=tool)
        self.assertEqual(fixture.registry.snapshot(), before)
        self.assertEqual(fixture.store._data, saved)
        self.assertEqual(fixture.bridge._record(fixture.attempt)["status"], "started")
        with self.assertRaises((EngineeringTaskError, RegistryError)):
            fixture.bridge.claim("lean")
        self.assertEqual(fixture.registry.snapshot(), before)
        self.assertEqual(fixture.store._data, saved)

    def test_new_entry_without_dispatch_rejects_success_before_all_writes(self):
        for version in (1, 2):
            for index in (0, 999):
                with self.subTest(version=version, index=index), SyntheticFixture(version) as fixture:
                    self.assertTrue(fixture.store.exists("engineering/research-entry-protocol/" + fixture.attempt + ".json"))
                    self.assertFalse(fixture.store.exists("engineering/research-dispatch/" + fixture.attempt + ".json"))
                    tool = fixture.research_observation()
                    tool["arguments"]["index"] = index
                    self.assert_rejected_unchanged(fixture, tool)

    def test_new_entry_without_dispatch_rejects_native_failure(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                self.assert_rejected_unchanged(fixture, error_tool())

    def test_valid_binding_success_is_completed_replayable_and_unlocks_lean(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                permit = fixture.command("research-dispatch", attempt=fixture.attempt,
                    tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=23))
                self.assertTrue(permit["should_execute"])
                tool = fixture.research_observation()
                tool["arguments"]["index"] = 23
                before_usage = fixture.registry.snapshot()["usage"]
                result = fixture.command("research-result", attempt=fixture.attempt, tool=tool)
                self.assertEqual(result["status"], "completed")
                after = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                self.assertEqual(fixture.command("research-result", attempt=fixture.attempt, tool=tool)["status"], "completed")
                self.assertEqual(fixture.registry.snapshot(), after)
                self.assertEqual(fixture.store._data, saved)
                self.assertEqual(after["usage"], before_usage)
                self.assertEqual(fixture.bridge.claim("lean").status, "started")

    def test_bound_success_wrong_cell_index_rejects_without_downstream_admission(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                fixture.command("research-dispatch", attempt=fixture.attempt,
                    tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=23))
                for wrong in (0, 999, True):
                    with self.subTest(index=wrong):
                        tool = fixture.research_observation()
                        tool["arguments"]["index"] = wrong
                        self.assert_rejected_unchanged(fixture, tool)

    def test_invalid_or_missing_original_entry_and_dispatch_reject_both_terminal_shapes(self):
        for mode in ("entry-invalid", "entry-missing", "dispatch-invalid", "dispatch-noncanonical", "dispatch-missing"):
            for terminal in ("success", "failure"):
                with self.subTest(mode=mode, terminal=terminal), SyntheticFixture(2) as fixture:
                    fixture.command("research-dispatch", attempt=fixture.attempt,
                        tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=0))
                    entry = "engineering/research-entry-protocol/" + fixture.attempt + ".json"
                    dispatch = "engineering/research-dispatch/" + fixture.attempt + ".json"
                    if mode == "entry-invalid":
                        fixture.store._data[entry] = canonical_json({})
                    elif mode == "entry-missing":
                        del fixture.store._data[entry]
                    elif mode == "dispatch-invalid":
                        value = json.loads(fixture.store.read_bytes(dispatch))
                        value["deployment"]["input_hash"] = "0" * 64
                        fixture.store._data[dispatch] = canonical_json(value)
                    elif mode == "dispatch-noncanonical":
                        fixture.store._data[dispatch] += b"\n"
                    else:
                        del fixture.store._data[dispatch]
                    tool = fixture.research_observation() if terminal == "success" else error_tool(index=0)
                    self.assert_rejected_unchanged(fixture, tool)

    def test_explicit_legacy_admission_without_protocol_preserves_success_only(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                # Only this isolated fixture models a pre-entry-protocol task.
                # Historical admissions had four fields, not today's atomic
                # inline protocol identity. Removing a sidecar alone is not old.
                fixture.admission.pop("research_entry_protocol")
                fixture.store._data["engineering/admitted-inputs/" + fixture.attempt + ".json"] = canonical_json(fixture.admission)
                del fixture.store._data["engineering/research-entry-protocol/" + fixture.attempt + ".json"]
                self.assertFalse(fixture.store.exists("engineering/research-dispatch/" + fixture.attempt + ".json"))
                before = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                with self.assertRaises(receipts.ReceiptParseError):
                    fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)
                result = fixture.command("research-result", attempt=fixture.attempt, tool=fixture.research_observation())
                self.assertEqual(result["status"], "completed")
                self.assertEqual(fixture.registry.snapshot()["usage"], before["usage"])

    def test_new_success_and_failure_parser_require_an_original_binding(self):
        payload, deployment = context("research")
        for tool in (research_tool(payload), error_tool()):
            with self.subTest(tool=tool["arguments"]), self.assertRaises(receipts.ReceiptParseError):
                receipts.research_observation(payload, deployment, tool, dispatch_required=True)
        bound = bind(payload, deployment, index=0)
        success = receipts.research_observation(payload, deployment, research_tool(payload),
            dispatch_binding=bound, dispatch_required=True)
        self.assertEqual(success["completion"]["platform"]["status"], "completed")
        self.assertEqual(receipts.research_observation(payload, deployment, error_tool(index=0),
            dispatch_binding=bound, dispatch_required=True)["completion"]["platform"]["status"], "runtime_error")
        for invalid in (None, 0, 1, "true", {}):
            with self.subTest(required=invalid), self.assertRaises(receipts.ReceiptParseError):
                receipts.research_observation(payload, deployment, research_tool(payload), dispatch_required=invalid)

    def test_completed_new_success_cannot_replay_after_dispatch_removed(self):
        with SyntheticFixture(2) as fixture:
            fixture.command("research-dispatch", attempt=fixture.attempt,
                tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=0))
            tool = fixture.research_observation()
            self.assertEqual(fixture.command("research-result", attempt=fixture.attempt, tool=tool)["status"], "completed")
            del fixture.store._data["engineering/research-dispatch/" + fixture.attempt + ".json"]
            before, saved = fixture.registry.snapshot(), dict(fixture.store._data)
            with self.assertRaises(EngineeringTaskError):
                fixture.command("research-result", attempt=fixture.attempt, tool=tool)
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)

    def test_failed_new_execution_cannot_replay_after_dispatch_removed(self):
        with SyntheticFixture(2) as fixture:
            fixture.command("research-dispatch", attempt=fixture.attempt,
                tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=0))
            tool = error_tool(index=0)
            self.assertEqual(fixture.command("research-result", attempt=fixture.attempt, tool=tool)["status"], "failed")
            del fixture.store._data["engineering/research-dispatch/" + fixture.attempt + ".json"]
            before, saved = fixture.registry.snapshot(), dict(fixture.store._data)
            with self.assertRaises(EngineeringTaskError):
                fixture.command("research-result", attempt=fixture.attempt, tool=tool)
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)

    def test_success_native_cell_metadata_matches_dispatch_when_present(self):
        payload, deployment = context("research")
        binding = bind(payload, deployment, index=0)
        for field in ("index", "cell_index"):
            for index in (0, 999, True):
                with self.subTest(field=field, index=index):
                    native = deepcopy(research_tool(payload)["result"]["structuredContent"])
                    native[field] = index
                    tool = envelope("jupyter_execute_cell", {"projectId": 17, "index": 0}, native)
                    if type(index) is int and index == 0:
                        result = receipts.research_observation(payload, deployment, tool,
                            dispatch_binding=binding, dispatch_required=True)
                        self.assertEqual(result["completion"]["platform"]["status"], "completed")
                    else:
                        with self.assertRaises(receipts.ReceiptParseError):
                            receipts.research_observation(payload, deployment, tool,
                                dispatch_binding=binding, dispatch_required=True)


if __name__ == "__main__":
    unittest.main()
