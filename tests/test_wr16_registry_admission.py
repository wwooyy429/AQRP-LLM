"""Synthetic direct-Registry joint admission; no cloud or market calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskError, EngineeringTaskPlan
from qresearch.engineering_receipts import research_observation
from qresearch.registry import Registry, RegistryError
from qresearch.artifacts import FilesystemArtifactStore
from test_phase2_joint_boundaries import joint_document, synthetic_registry, wrapper
from test_engineering_receipts import research_tool


def context(retries=0):
    store, registry = synthetic_registry()
    raw = joint_document()
    raw["max_retries"] = {"research": retries, "lean": retries}
    plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])
    bridge = EngineeringTaskBridge(registry, plan)
    bridge.register()
    return store, registry, bridge


def finish_research(bridge):
    attempt = bridge.claim("research")
    payload = bridge.payload(attempt)
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                  "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "f" * 64}
    observed = research_observation(payload, deployment, research_tool(payload, wrapper(payload)))
    bridge.record_submission(attempt, observed["submission"])
    bridge.consume_completion(attempt, completion_source=lambda _: observed["completion"])
    return attempt


class WR16RegistryAdmissionTests(unittest.TestCase):
    def reject_without_write(self, store, registry, action):
        before, saved = registry.snapshot(), dict(store._data)
        with self.assertRaises(RegistryError):
            action()
        self.assertEqual(registry.snapshot(), before)
        self.assertEqual(store._data, saved)

    def test_direct_wrong_operation_cannot_charge_or_return_another_claim(self):
        for stage, operation in (("research", "default"), ("research", "unregistered"),
                                 ("lean", "unregistered")):
            with self.subTest(stage=stage, operation=operation):
                store, registry, bridge = context()
                self.reject_without_write(store, registry, lambda: registry.begin_attempt(
                    bridge.config_id, stage, operation_key=operation))
        store, registry, bridge = context()
        bridge.claim("research")
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(
            bridge.config_id, "research", operation_key="different-while-pending"))

    def test_direct_lean_requires_verified_same_plan_research(self):
        for state in ("absent", "failed", "generic_completed", "wrong_identity_completed"):
            with self.subTest(state=state):
                store, registry, bridge = context()
                if state != "absent":
                    attempt = bridge.claim("research")
                    if state == "failed":
                        registry.fail(attempt, "Synthetic observed failure")
                    elif state == "generic_completed":
                        registry.complete(attempt, {"synthetic_unverified_result": True})
                    else:
                        payload = bridge.payload(attempt)
                        report = wrapper(payload)
                        report["cloud_report"]["identity"]["attempt_id"] = "0" * 32
                        registry.complete(attempt, {"cloud_report": report["cloud_report"]})
                self.reject_without_write(store, registry, lambda: registry.begin_attempt(
                    bridge.config_id, "lean", operation_key=bridge._operation("lean")))

    def test_zero_retries_rejected_at_direct_transaction_before_debit(self):
        store, registry, bridge = context()
        first = bridge.claim("research")
        registry.fail(first, "Synthetic observed failure")
        with self.assertRaises(EngineeringTaskError):
            bridge.claim("research", retry_of=first.attempt_id, reason="Synthetic repair")
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(
            bridge.config_id, "research", operation_key=bridge._operation("research"),
            retry_of=first.attempt_id, reason="Synthetic repair"))
        reused = registry.begin_attempt(bridge.config_id, "research", operation_key=first.operation_key)
        self.assertFalse(reused.should_execute)
        self.assertEqual(reused.attempt_id, first.attempt_id)

    def test_legal_single_retry_and_concurrent_idempotent_reuse(self):
        store, registry, bridge = context(retries=1)
        first = bridge.claim("research")
        registry.fail(first, "Synthetic observed failure")
        second = registry.begin_attempt(bridge.config_id, "research", operation_key=first.operation_key,
            retry_of=first.attempt_id, reason="Synthetic admitted repair")
        self.assertTrue(second.should_execute)
        self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 2)
        before, saved = registry.snapshot(), dict(store._data)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: registry.begin_attempt(bridge.config_id, "research",
                operation_key=first.operation_key), range(16)))
        self.assertTrue(all(not attempt.should_execute and attempt.attempt_id == second.attempt_id for attempt in results))
        self.assertEqual(registry.snapshot(), before)
        self.assertEqual(store._data, saved)

    def test_completed_native_shaped_result_enables_one_direct_lean(self):
        store, registry, bridge = context()
        research = finish_research(bridge)
        lean = registry.begin_attempt(bridge.config_id, "lean", operation_key=bridge._operation("lean"))
        self.assertTrue(lean.should_execute)
        self.assertEqual(bridge.payload(lean)["research_resolution"], registry.read_result(research)["cloud_report"]["resolution"])
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 1)
        self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 1)
        self.assertEqual(registry.snapshot()["usage"]["lean"]["total"], 1)
        before, saved = registry.snapshot(), dict(store._data)
        repeated = registry.begin_attempt(bridge.config_id, "lean", operation_key=lean.operation_key)
        self.assertEqual(repeated.attempt_id, lean.attempt_id)
        self.assertFalse(repeated.should_execute)
        self.assertEqual(registry.snapshot(), before)
        self.assertEqual(store._data, saved)

    def test_lean_zero_retry_bound_is_stage_specific_and_not_a_second_charge(self):
        store, registry, bridge = context()
        finish_research(bridge)
        first = bridge.claim("lean")
        registry.fail(first, "Synthetic observed Lean failure")
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(
            bridge.config_id, "lean", operation_key=first.operation_key,
            retry_of=first.attempt_id, reason="Synthetic forbidden repair"))

    def test_completed_status_without_checked_reference_or_correct_report_is_not_dependency(self):
        for mutation in ("missing_completion", "wrong_stage"):
            with self.subTest(mutation=mutation):
                store, registry, bridge = context()
                attempt = bridge.claim("research")
                payload = bridge.payload(attempt)
                report = wrapper(payload)
                if mutation == "wrong_stage":
                    report["cloud_report"]["identity"]["stage"] = "lean"
                identity = deepcopy(payload["identity"])
                result = {"scope": "engineering", "identity": identity,
                    "external_id": "qc-research:17:" + attempt.attempt_id,
                    "cloud_report": report["cloud_report"], "report_ref": report["report_ref"],
                    "platform_evidence_ref": {"key": "engineering/evidence/" + attempt.attempt_id + "/completion/" + "a" * 64 + ".json", "sha256": "a" * 64},
                    "financial_evidence": False}
                registry.complete(attempt, result)
                self.reject_without_write(store, registry, lambda: registry.begin_attempt(
                    bridge.config_id, "lean", operation_key=bridge._operation("lean")))

    def test_filesystem_parent_completion_and_direct_lean_do_not_reenter_registry_lock(self):
        with tempfile.TemporaryDirectory(prefix="aqrp-wr16-") as directory:
            store = FilesystemArtifactStore(directory, data_classification="synthetic", lock_timeout=0.25)
            limits = {key: {"total": 10, "normal": 10, "reserve": 0}
                      for key in ("configurations", "research", "lean")}
            registry = Registry(store, limits)
            raw = joint_document()
            raw["max_retries"] = {"research": 0, "lean": 0}
            bridge = EngineeringTaskBridge(registry, EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17]))
            bridge.register()
            completed = finish_research(bridge)
            lean = registry.begin_attempt(bridge.config_id, "lean", operation_key=bridge._operation("lean"))
            self.assertTrue(lean.should_execute)
            self.assertEqual(bridge.payload(lean)["research_resolution"], registry.read_result(completed)["cloud_report"]["resolution"])
            self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 1)
            self.assertEqual(registry.snapshot()["usage"]["lean"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
