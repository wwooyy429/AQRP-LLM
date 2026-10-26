"""Synthetic mixed engineering-task admission; no remote calls or real ledger."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import multiprocessing
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import FilesystemArtifactStore, MemoryArtifactStore, content_hash
from qresearch.collection_tasks import CollectionTaskPlan
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskError, EngineeringTaskPlan
from qresearch.registry import BudgetExceeded, Registry, RegistryError
from test_engineering_tasks import raw_plan


LIMITS = {"configurations": {"total": 12, "normal": 8, "reserve": 4},
          "research": {"total": 20, "normal": 12, "reserve": 8},
          "lean": {"total": 16, "normal": 8, "reserve": 8}}
CATALOG = {"dollar_volume": {"kind": "number", "role": "synthetic_observation", "unit": "USD", "period_accessor": None}}


def collection_document(name="synthetic-collection", project=102, retries=1):
    return {"schema_version": 1, "task_kind": "historical_collection", "scope": "engineering",
            "plan_id": name, "project_id": project, "source_manifest_hash": "a" * 64,
            "deployment_hash": "b" * 64, "field_catalog": deepcopy(CATALOG),
            "collection_plan": {"schema_version": 1, "plan_id": "synthetic-snapshot", "scope": "engineering",
                "source": "quantconnect_fundamental_universe", "data_version": "synthetic-v1",
                "start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2018-01-04T00:00:00-05:00",
                "timezone": "America/New_York", "fields": list(CATALOG), "calendar_days_per_request": 1,
                "max_batch_records": 2, "max_records_per_window": 10, "source_manifest_hash": "a" * 64},
            "report_namespace": "synthetic/collection", "max_retries": retries}


def collection_package(name="synthetic-collection", project=102, retries=1):
    plan = CollectionTaskPlan.from_dict(collection_document(name, project, retries),
                                      discovered_project_ids=[project], field_catalog=CATALOG)
    return {"engineering_task_schema_version": 1, "plan": plan.to_dict()}


def legacy_package(name="synthetic-legacy", project=101):
    document = raw_plan()
    document.update(plan_id=name, project_id=project)
    plan = EngineeringTaskPlan.from_dict(document, discovered_project_ids=[project])
    return {"engineering_task_schema_version": 1, "plan": plan.to_dict()}


def operation(package):
    return "collection-plan:" + content_hash(package["plan"]) + ":research"


def process_mixed_contender(directory, package, kind, retry, barrier, queue):
    """Spawn-compatible native process; never imports or opens the real ledger."""
    try:
        registry = Registry(FilesystemArtifactStore(directory), LIMITS)
        barrier.wait(20)
        try:
            if kind == "configurations":
                registry.register_config(package)
            else:
                collection = package["plan"].get("task_kind") == "historical_collection"
                attempt = registry.begin_attempt(content_hash(package), "research",
                    operation_key=operation(package) if collection else "legacy",
                    retry_of=retry, reason="synthetic process repair" if retry else None)
                if not attempt.should_execute:
                    queue.put("unexpected_reuse")
                    return
            queue.put("admitted")
        except BudgetExceeded:
            queue.put("rejected" if kind != "project" else "unexpected_budget_rejection")
        except RegistryError as exc:
            queue.put("rejected" if kind == "project" and str(exc).startswith("Unresolved engineering work")
                      else "unexpected_registry_error:" + type(exc).__name__ + ":" + str(exc))
    except Exception as exc:
        queue.put("unexpected:" + type(exc).__name__ + ":" + str(exc))


class CollectionAdmissionTests(unittest.TestCase):
    def registry(self, store=None, limits=None):
        return Registry(store or MemoryArtifactStore(), limits or LIMITS)

    def test_legacy_and_collection_configuration_charge_share_domain_cap(self):
        registry = self.registry()
        old, new = legacy_package(), collection_package()
        self.assertEqual(registry.register_config(old), content_hash(old))
        self.assertEqual(registry.register_config(new, allocation="reserve"), content_hash(new))
        self.assertEqual(registry.register_config(new), content_hash(new))
        with self.assertRaises(BudgetExceeded):
            registry.register_config(collection_package("third", 103))
        with self.assertRaises(BudgetExceeded):
            registry.register_config(legacy_package("fourth", 104))
        self.assertEqual(registry.snapshot()["usage"]["configurations"], {"total": 2, "normal": 1, "reserve": 1})

    def test_mixed_execution_cap_counts_failures_across_allocations_and_projects(self):
        registry = self.registry()
        old, new = legacy_package(), collection_package()
        old_id, new_id = registry.register_config(old), registry.register_config(new)
        first = registry.begin_attempt(old_id, "research", operation_key="legacy")
        registry.fail(first, "synthetic failure remains charged")
        second = registry.begin_attempt(new_id, "research", operation_key=operation(new), allocation="reserve")
        registry.fail(second, "synthetic collection failure remains charged")
        with self.assertRaises(BudgetExceeded):
            registry.begin_attempt(old_id, "research", operation_key="legacy", retry_of=first.attempt_id, reason="repair")
        self.assertEqual(registry.begin_attempt(new_id, "research", operation_key=operation(new)).attempt_id, second.attempt_id)
        self.assertEqual(registry.snapshot()["usage"]["research"], {"total": 2, "normal": 1, "reserve": 1})

    def test_old_unresolved_work_blocks_collection_registration_before_configuration_charge(self):
        for status in ("started", "pending", "ambiguous"):
            with self.subTest(status=status):
                registry = self.registry()
                old_id = registry.register_config(legacy_package(project=101))
                attempt = registry.begin_attempt(old_id, "lean", operation_key="legacy-lean")
                if status == "pending":
                    registry.pending(attempt, external_id="synthetic-backtest")
                elif status == "ambiguous":
                    registry.ambiguous(attempt, reason="synthetic unknown")
                new = collection_package(project=101)
                before = deepcopy(registry.snapshot())
                with self.assertRaises(RegistryError):
                    registry.register_config(new)
                with self.assertRaises(RegistryError):
                    registry.check_engineering_admission(new, "configurations")
                self.assertEqual(registry.snapshot(), before)

    def test_collection_unresolved_work_blocks_old_bridge_and_direct_begin(self):
        registry = self.registry()
        old, new = legacy_package(project=101), collection_package(project=101)
        old_id, new_id = registry.register_config(old), registry.register_config(new)
        attempt = registry.begin_attempt(new_id, "research", operation_key=operation(new))
        registry.pending(attempt, external_id="synthetic-research")
        plan = EngineeringTaskPlan.from_dict(old["plan"], discovered_project_ids=[101])
        bridge = EngineeringTaskBridge(registry, plan)
        before = deepcopy(registry.snapshot())
        with self.assertRaises(EngineeringTaskError):
            bridge.claim("research")
        with self.assertRaises(RegistryError):
            registry.begin_attempt(old_id, "research", operation_key="direct-bypass")
        self.assertEqual(registry.snapshot(), before)

    def test_both_pre_registered_task_types_share_same_project_open_guard(self):
        registry = self.registry()
        old, new = legacy_package(project=101), collection_package(project=101)
        old_id, new_id = registry.register_config(old), registry.register_config(new)
        attempt = registry.begin_attempt(old_id, "lean", operation_key="legacy-lean")
        registry.pending(attempt, external_id="synthetic-backtest")
        with self.assertRaises(RegistryError):
            registry.begin_attempt(new_id, "research", operation_key=operation(new))
        self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 0)

    def test_different_projects_may_claim_but_remain_under_shared_domain_limit(self):
        registry = self.registry()
        old, new = legacy_package(project=101), collection_package(project=102)
        old_id = registry.register_config(old)
        old_attempt = registry.begin_attempt(old_id, "lean", operation_key="legacy-lean")
        registry.pending(old_attempt, external_id="synthetic-backtest")
        new_id = registry.register_config(new)
        new_attempt = registry.begin_attempt(new_id, "research", operation_key=operation(new))
        self.assertTrue(new_attempt.should_execute)
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 2)

    def test_direct_begin_rejects_collection_stage_and_operation_overrides_without_charge(self):
        registry = self.registry()
        package = collection_package()
        config = registry.register_config(package)
        before = deepcopy(registry.snapshot())
        for stage, op in (("lean", operation(package)), ("research", "default"), ("research", "renamed-operation")):
            with self.subTest(stage=stage, operation=op), self.assertRaises(RegistryError):
                registry.begin_attempt(config, stage, operation_key=op)
        with self.assertRaises(RegistryError):
            registry.check_engineering_admission(package, "lean")
        self.assertEqual(registry.snapshot(), before)

    def test_direct_retry_bound_cannot_be_bypassed_with_a_new_operation(self):
        registry = self.registry()
        package = collection_package(retries=0)
        config = registry.register_config(package)
        first = registry.begin_attempt(config, "research", operation_key=operation(package))
        registry.fail(first, "synthetic failure")
        before = deepcopy(registry.snapshot())
        self.assertEqual(registry.begin_attempt(config, "research", operation_key=operation(package)).attempt_id, first.attempt_id)
        with self.assertRaisesRegex(RegistryError, "retry bound"):
            registry.begin_attempt(config, "research", operation_key=operation(package), retry_of=first.attempt_id, reason="explicit repair")
        with self.assertRaises(RegistryError):
            registry.begin_attempt(config, "research", operation_key="changed", retry_of=first.attempt_id, reason="renamed retry")
        self.assertEqual(registry.snapshot(), before)

    def test_explicit_retry_is_charged_once_and_restart_does_not_refund(self):
        store = MemoryArtifactStore(); registry = self.registry(store)
        package = collection_package(retries=1); config = registry.register_config(package)
        first = registry.begin_attempt(config, "research", operation_key=operation(package))
        registry.fail(first, "synthetic failure")
        second = registry.begin_attempt(config, "research", operation_key=operation(package), retry_of=first.attempt_id,
                                        reason="explicit synthetic repair", allocation="reserve")
        registry.fail(second, "second synthetic failure")
        restarted = self.registry(store)
        with self.assertRaisesRegex(RegistryError, "retry bound"):
            restarted.begin_attempt(config, "research", operation_key=operation(package), retry_of=second.attempt_id, reason="third")
        self.assertEqual(restarted.snapshot(), registry.snapshot())
        self.assertEqual(restarted.snapshot()["usage"]["research"], {"total": 2, "normal": 1, "reserve": 1})

    def test_completed_and_ambiguous_collection_reuse_remains_free(self):
        for status in ("completed", "ambiguous"):
            with self.subTest(status=status):
                registry = self.registry(); package = collection_package(); config = registry.register_config(package)
                first = registry.begin_attempt(config, "research", operation_key=operation(package))
                if status == "completed":
                    registry.complete(first, {"synthetic_metadata": True})
                else:
                    registry.ambiguous(first, reason="synthetic outcome unknown")
                before = deepcopy(registry.snapshot())
                again = registry.begin_attempt(config, "research", operation_key=operation(package))
                self.assertFalse(again.should_execute)
                self.assertEqual(again.attempt_id, first.attempt_id)
                self.assertEqual(registry.snapshot(), before)

    def test_reserved_collection_shape_cannot_drop_or_change_marker_kind_or_scope(self):
        package = collection_package()
        changes = []
        for marker in (None, True, 0, 2):
            changed = deepcopy(package)
            if marker is None:
                del changed["engineering_task_schema_version"]
            else:
                changed["engineering_task_schema_version"] = marker
            changes.append(changed)
        for field, value in (("task_kind", None), ("task_kind", "generic"), ("scope", "research")):
            changed = deepcopy(package)
            if value is None:
                del changed["plan"][field]
            else:
                changed["plan"][field] = value
            changes.append(changed)
        changed = deepcopy(package);del changed["engineering_task_schema_version"];changed["plan"]["scope"] = "generic";changes.append(changed)
        registry = self.registry()
        for changed in changes:
            with self.subTest(keys=sorted(changed)), self.assertRaises(ValueError):
                registry.register_config(changed)
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 0)

    def test_frozen_collection_shape_validation_runs_in_direct_registry_entry(self):
        for field, value in (("max_retries", True), ("project_id", True), ("source_manifest_hash", "wrong"),
                             ("field_catalog", {}), ("collection_plan", {})):
            registry = self.registry(); package = collection_package();package["plan"][field] = value
            with self.subTest(field=field), self.assertRaises((ValueError, TypeError)):
                registry.register_config(package)
            self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 0)

    def test_direct_registry_rejects_unfrozen_plan_before_charging_its_unusable_identity(self):
        registry = self.registry()
        package = collection_package()
        package["plan"]["collection_plan"]["start"] = "2018-01-03T05:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "already frozen canonical plan"):
            registry.register_config(package)
        with self.assertRaisesRegex(ValueError, "already frozen canonical plan"):
            registry.check_engineering_admission(package, "configurations")
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 0)

    def test_global_budget_still_applies_before_second_engineering_research(self):
        limits = deepcopy(LIMITS); limits["research"] = {"total": 1, "normal": 1, "reserve": 0}
        registry = self.registry(limits=limits); old, new = legacy_package(), collection_package()
        old_id, new_id = registry.register_config(old), registry.register_config(new)
        registry.fail(registry.begin_attempt(old_id, "research", operation_key="legacy"), "synthetic")
        with self.assertRaises(BudgetExceeded):
            registry.begin_attempt(new_id, "research", operation_key=operation(new))
        self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 1)

    def race(self, kind, disk):
        with tempfile.TemporaryDirectory(prefix="aqrp-collection-admission-") as directory:
            store = FilesystemArtifactStore(directory) if disk else MemoryArtifactStore()
            registry = self.registry(store)
            old = legacy_package(project=101); new = collection_package(project=101 if kind == "project" else 102)
            if kind == "configurations":
                registry.register_config(legacy_package("used", 103))
            else:
                old_id, new_id = registry.register_config(old), registry.register_config(new)
                if kind == "research":
                    first = registry.begin_attempt(old_id, "research", operation_key="legacy")
                    registry.fail(first, "used first slot")
            barrier = threading.Barrier(2)
            def worker(package):
                local = self.registry(FilesystemArtifactStore(directory)) if disk else registry
                barrier.wait(10)
                try:
                    if kind == "configurations":
                        local.register_config(package)
                    else:
                        collection = package is new
                        op = operation(package) if collection else "legacy"
                        config = content_hash(package)
                        attempt = local.begin_attempt(config, "research", operation_key=op,
                            retry_of=first.attempt_id if kind == "research" and not collection else None,
                            reason="synthetic repair" if kind == "research" and not collection else None)
                        if not attempt.should_execute:
                            return "unexpected_reuse"
                    return "admitted"
                except BudgetExceeded:
                    if kind == "project":
                        raise
                    return "rejected"
                except RegistryError as exc:
                    if kind != "project" or not str(exc).startswith("Unresolved engineering work"):
                        raise
                    return "rejected"
            with ThreadPoolExecutor(max_workers=2) as executor:
                answers = list(executor.map(worker, (old, new)))
            self.assertCountEqual(answers, ["admitted", "rejected"])
            resource = "research" if kind == "project" else kind
            self.assertEqual(registry.snapshot()["usage"][resource]["total"], 1 if kind == "project" else 2)
            reopened = self.registry(FilesystemArtifactStore(directory)) if disk else self.registry(store)
            self.assertEqual(reopened.snapshot(), registry.snapshot())

    def test_mixed_configuration_race_memory(self): self.race("configurations", False)
    def test_mixed_configuration_race_separate_filesystem_instances(self): self.race("configurations", True)
    def test_mixed_research_race_memory(self): self.race("research", False)
    def test_mixed_research_race_separate_filesystem_instances(self): self.race("research", True)
    def test_mixed_same_project_claim_race_memory(self): self.race("project", False)
    def test_mixed_same_project_claim_race_separate_filesystem_instances(self): self.race("project", True)

    def process_race(self, kind):
        with tempfile.TemporaryDirectory(prefix="aqrp-collection-process-") as directory:
            registry = self.registry(FilesystemArtifactStore(directory))
            old = legacy_package(project=101)
            new = collection_package(project=101 if kind == "project" else 102)
            retry = None
            if kind == "configurations":
                registry.register_config(legacy_package("used", 103))
            else:
                old_id = registry.register_config(old)
                registry.register_config(new)
                if kind == "research":
                    attempt = registry.begin_attempt(old_id, "research", operation_key="legacy")
                    registry.fail(attempt, "synthetic first slot remains charged")
                    retry = attempt.attempt_id
            context = multiprocessing.get_context("spawn")
            barrier, queue = context.Barrier(2), context.Queue()
            workers = [context.Process(target=process_mixed_contender,
                args=(directory, package, kind, retry if index == 0 else None, barrier, queue))
                for index, package in enumerate((old, new))]
            try:
                for worker in workers:
                    worker.start()
                answers = [queue.get(timeout=50) for _ in workers]
                for worker in workers:
                    worker.join(10)
                    self.assertEqual(worker.exitcode, 0)
            finally:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                    worker.join()
                queue.close()
                queue.join_thread()
            self.assertCountEqual(answers, ["admitted", "rejected"])
            resource = "research" if kind == "project" else kind
            snapshot = registry.snapshot()
            self.assertEqual(snapshot["usage"][resource]["total"], 1 if kind == "project" else 2)
            self.assertEqual(self.registry(FilesystemArtifactStore(directory)).snapshot(), snapshot)

    def test_mixed_configuration_native_process_race(self): self.process_race("configurations")
    def test_mixed_research_native_process_race(self): self.process_race("research")
    def test_mixed_same_project_native_process_race(self): self.process_race("project")


if __name__ == "__main__":
    unittest.main()
