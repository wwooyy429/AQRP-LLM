"""Exercise actual v2 grant/new-cycle admission of strict schema3 joint plans.

All stores, observations and histories here are synthetic; no real Registry or
QuantConnect connection is opened. The tests cover the operator grant path that
direct Bridge fixture tests alone do not exercise.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.registry import Registry, RegistryError
from test_budget_cycles import documents, normal_round_documents
from test_budget_revision_cli import budget_fixture
import test_engineering_storage as storage_fixtures


def context():
    budget = budget_fixture()
    budget["limits"]["full_configurations"] = 13
    budget["allocations"]["full_configurations"] = {"normal": 8, "reserve": 5, "total": 13}
    budget["usage"].update(configuration_budget_charges=13, configuration_reserve_used=5,
                           research_execution_attempts=16, research_reserve_used=8)
    store = MemoryArtifactStore()
    registry = Registry(store, budget)
    cycle, authority = documents(registry)
    registry.authorize_configuration_cycle(cycle, authority)
    return store, registry, budget


def storage_package(directory):
    _, _, _, payload, _, _ = storage_fixtures.StorageRepairWorkerTests().fixture(directory)
    raw = deepcopy(payload["plan"])
    raw["max_retries"] = {"research": 0, "lean": 0}
    frozen = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=(17,))
    return {"engineering_task_schema_version": 1, "plan": frozen.to_dict()}


class RegistryStorageAdmissionTests(unittest.TestCase):
    def test_v3_full_new_cycle_grant_register_claim_path_is_concurrent_once_only(self):
        with tempfile.TemporaryDirectory() as directory:
            package = storage_package(directory)
        store, registry, baseline = context()
        grant, authority = normal_round_documents(registry)
        before_usage = registry.snapshot()["usage"]
        registry.authorize_engineering_round(grant, [package], authority)
        self.assertEqual(registry.snapshot()["usage"], before_usage)
        plan = Registry._joint_engineering_plan(package)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.to_dict()["schema_version"], 3)
        task = EngineeringTaskBridge(registry, plan)
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: task.register(allocation="normal"), range(8)))
        self.assertEqual(len(set(ids)), 1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            attempts = list(pool.map(lambda _: task.claim("research", allocation="normal"), range(8)))
        self.assertEqual(sum(a.should_execute for a in attempts), 1)
        self.assertEqual(len({a.attempt_id for a in attempts}), 1)
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 14)
        self.assertEqual(registry.configuration_cycle_snapshot()["usage"]["total"], 1)
        self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 17)
        self.assertEqual(registry.snapshot()["usage"]["lean"]["total"], 2)
        before = dict(store._data)
        with self.assertRaises(RegistryError):
            registry.begin_attempt(task.config_id, "research", operation_key="arbitrary")
        with self.assertRaises(RegistryError):
            registry.begin_attempt(task.config_id, "lean", allocation="normal",
                                   operation_key="engineering-plan:" + plan.hash + ":lean")
        self.assertEqual(store._data, before)
        registry.fail(attempts[0], "SYNTHETIC actual runtime failure")
        before = dict(store._data)
        with self.assertRaises(RegistryError):
            registry.begin_attempt(task.config_id, "research", operation_key=attempts[0].operation_key,
                                   retry_of=attempts[0].attempt_id, reason="SYNTHETIC forbidden retry")
        self.assertEqual(store._data, before)
        registry.close_engineering_round(grant["round_id"], "SYNTHETIC zero-retry stop")
        self.assertEqual(registry.engineering_rounds_snapshot()[grant["round_id"]]["usage"],
                         {"configurations": 1, "research": 1, "lean": 0})
        self.assertEqual(Registry(store, baseline).snapshot(), registry.snapshot())

    def test_v3_malformed_storage_policy_cannot_bind_or_register_before_any_charge(self):
        with tempfile.TemporaryDirectory() as directory:
            original = storage_package(directory)
        for mutation in (lambda p: p["storage_policy"].update(price_cache_mode="fetch"),
                         lambda p: p["storage_policy"].update(extra="unrestricted"),
                         lambda p: p.pop("storage_policy"),
                         lambda p: p["collection_probe"]["collection_plan"].update(source_manifest_hash="0" * 64)):
            store, registry, _ = context()
            package = deepcopy(original)
            mutation(package["plan"])
            grant, authority = normal_round_documents(registry)
            before = dict(store._data)
            with self.assertRaises(ValueError):
                registry.authorize_engineering_round(grant, [package], authority)
            self.assertEqual(store._data, before)
            with self.assertRaises(ValueError):
                registry.register_config(package)
            self.assertEqual(store._data, before)


if __name__ == "__main__":
    unittest.main()
