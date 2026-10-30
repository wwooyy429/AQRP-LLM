"""WR-18 synthetic submission/completion binding at shared LEAN admission."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import FilesystemArtifactStore, MemoryArtifactStore, canonical_json, content_hash
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan, EngineeringTaskError
from qresearch.engineering_receipts import research_observation
from qresearch.registry import Registry, RegistryError
from test_phase2_joint_boundaries import joint_document, wrapper
from test_engineering_receipts import research_tool


def fixture(store=None, submit=True):
    store = MemoryArtifactStore() if store is None else store
    limits = {name: {"total": count, "normal": count, "reserve": 0}
              for name, count in (("configurations", 12), ("research", 20), ("lean", 16))}
    registry = Registry(store, limits)
    bridge = EngineeringTaskBridge(registry, EngineeringTaskPlan.from_dict(joint_document(), discovered_project_ids=[17]))
    bridge.register()
    attempt = bridge.claim("research")
    payload = bridge.payload(attempt)
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                  "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "d" * 64}
    observed = research_observation(payload, deployment, research_tool(payload, wrapper(payload)))
    if submit:
        bridge.record_submission(attempt, observed["submission"])
    return store, registry, bridge, attempt, payload, observed


def complete_direct(item, completion=None):
    store, registry, bridge, attempt, payload, observed = item
    completion = deepcopy(observed["completion"]) if completion is None else completion
    reference = bridge._save(attempt.attempt_id, "completion", completion)
    external = observed["submission"]["external_id"]
    result = {"scope": "engineering", "identity": payload["identity"], "external_id": external,
              "cloud_report": completion["cloud_report"], "report_ref": completion["report_ref"],
              "platform_evidence_ref": reference, "financial_evidence": False}
    registry.complete(attempt, result, external_id=external)
    return completion


def memory_bytes(store):
    return dict(store._data)


class WR18CompletionDependencyTests(unittest.TestCase):
    def assert_denied_without_write(self, item):
        store, registry, bridge, _, _, _ = item
        before, saved = registry.snapshot(), memory_bytes(store)
        with self.assertRaises(RegistryError):
            registry.begin_attempt(bridge.config_id, "lean", operation_key=bridge._operation("lean"))
        self.assertEqual(registry.snapshot(), before)
        self.assertEqual(memory_bytes(store), saved)

    def test_matching_bridge_completion_and_direct_completion_each_allow_one_lean(self):
        for direct in (False, True):
            with self.subTest(direct=direct):
                item = fixture()
                _, registry, bridge, attempt, _, observed = item
                if direct:
                    complete_direct(item)
                else:
                    self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: observed["completion"]).status, "completed")
                lean = registry.begin_attempt(bridge.config_id, "lean", operation_key=bridge._operation("lean"))
                self.assertTrue(lean.should_execute)
                before = registry.snapshot()
                reused = registry.begin_attempt(bridge.config_id, "lean", operation_key=lean.operation_key)
                self.assertFalse(reused.should_execute)
                self.assertEqual(registry.snapshot(), before)

    def test_every_completion_deployment_component_must_match_original_submission(self):
        for name in ("input_hash", "source_manifest_hash", "deployment_hash"):
            with self.subTest(component=name):
                item = fixture()
                completion = deepcopy(item[-1]["completion"])
                completion["platform"]["deployment"][name] = "e" * 64
                complete_direct(item, completion)
                self.assert_denied_without_write(item)

    def test_empty_completion_receipt_cannot_be_completed_dependency(self):
        item = fixture()
        completion = deepcopy(item[-1]["completion"])
        completion["platform"]["raw_receipt"] = {}
        complete_direct(item, completion)
        self.assert_denied_without_write(item)

    def test_absent_submission_cannot_be_completed_dependency(self):
        item = fixture(submit=False)
        complete_direct(item)
        self.assert_denied_without_write(item)

    def test_missing_original_submission_evidence_cannot_be_completed_dependency(self):
        item = fixture()
        store, _, bridge, attempt, _, _ = item
        summary = __import__("json").loads(store.read_bytes(bridge._submission_key(attempt.attempt_id)))
        del store._data[summary["receipt_ref"]["key"]]
        complete_direct(item)
        self.assert_denied_without_write(item)

    def test_rehashed_invalid_original_submission_is_not_a_checked_submission(self):
        for mutation in ("unaccepted", "empty_raw", "wrong_identity", "wrong_external", "wrong_input"):
            with self.subTest(mutation=mutation):
                item = fixture()
                store, _, bridge, attempt, _, observed = item
                receipt = deepcopy(observed["submission"])
                if mutation == "unaccepted":
                    receipt["accepted"] = False
                elif mutation == "empty_raw":
                    receipt["raw_receipt"] = {}
                elif mutation == "wrong_identity":
                    receipt["identity"]["attempt_id"] = "0" * 32
                elif mutation == "wrong_external":
                    receipt["external_id"] = "qc-research:17:" + "0" * 32
                else:
                    receipt["deployment"]["input_hash"] = "e" * 64
                reference = bridge._save(attempt.attempt_id, "submission", receipt)
                summary = __import__("json").loads(store.read_bytes(bridge._submission_key(attempt.attempt_id)))
                summary["receipt_ref"] = reference
                store._data[bridge._submission_key(attempt.attempt_id)] = canonical_json(summary)
                complete_direct(item)
                self.assert_denied_without_write(item)

    def test_summary_identity_external_and_input_tampering_are_rejected(self):
        for mutation in ("identity", "external", "input", "kind"):
            with self.subTest(mutation=mutation):
                item = fixture()
                store, _, bridge, attempt, _, _ = item
                key = bridge._submission_key(attempt.attempt_id)
                summary = __import__("json").loads(store.read_bytes(key))
                if mutation == "identity":
                    summary["identity"]["source_manifest_hash"] = "0" * 64
                elif mutation == "external":
                    summary["external_id"] = "qc-research:17:" + "0" * 32
                elif mutation == "input":
                    summary["deployment"]["input_hash"] = "0" * 64
                else:
                    summary["identity_kind"] = "quantconnect_backtest_id"
                store._data[key] = canonical_json(summary)
                complete_direct(item)
                self.assert_denied_without_write(item)

    def test_completion_identity_status_and_ref_mismatches_are_rejected(self):
        for mutation in ("external", "identity", "status", "report_ref"):
            with self.subTest(mutation=mutation):
                item = fixture()
                completion = deepcopy(item[-1]["completion"])
                if mutation == "external":
                    completion["platform"]["identity"]["external_id"] = "qc-research:17:" + "0" * 32
                elif mutation == "identity":
                    completion["platform"]["identity"]["source_manifest_hash"] = "0" * 64
                elif mutation == "status":
                    completion["platform"]["status"] = "compiled"
                else:
                    completion["report_ref"]["sha256"] = "0" * 64
                complete_direct(item, completion)
                self.assert_denied_without_write(item)

    def test_bridge_and_shared_registry_reject_the_three_original_invalid_paths(self):
        for mutation in ("input_hash", "empty_raw", "no_submission"):
            with self.subTest(mutation=mutation):
                item = fixture(submit=mutation != "no_submission")
                _, registry, bridge, attempt, _, observed = item
                completion = deepcopy(observed["completion"])
                if mutation == "input_hash":
                    completion["platform"]["deployment"]["input_hash"] = "e" * 64
                elif mutation == "empty_raw":
                    completion["platform"]["raw_receipt"] = {}
                before = registry.snapshot()
                with self.assertRaises(EngineeringTaskError):
                    bridge.consume_completion(attempt, completion_source=lambda _: completion)
                self.assertEqual(registry.snapshot(), before)
                complete_direct(item, completion)
                self.assert_denied_without_write(item)

    def test_filesystem_matching_dependency_does_not_reenter_transaction_lock(self):
        with tempfile.TemporaryDirectory(prefix="aqrp-wr18-") as directory:
            store = FilesystemArtifactStore(directory, data_classification="synthetic", lock_timeout=0.25)
            item = fixture(store=store)
            _, registry, bridge, attempt, _, observed = item
            self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: observed["completion"]).status, "completed")
            lean = registry.begin_attempt(bridge.config_id, "lean", operation_key=bridge._operation("lean"))
            self.assertTrue(lean.should_execute)
            self.assertEqual(registry.snapshot()["usage"]["lean"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
