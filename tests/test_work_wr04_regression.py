"""Synthetic WR-04 admission regressions; never contact a platform.

The two contenders deliberately finish the old read-only preflight together.
A correct mutation grants one new slot and rejects the other with no debit.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import multiprocessing
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
from qresearch.artifacts import FilesystemArtifactStore, MemoryArtifactStore
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import BudgetExceeded, Registry
from qresearch.workflow import SubmissionRejected
from stage2 import _limits
from test_engineering_tasks import Adapter, completed, raw_plan


LIMITS = {
    "configurations": {"total": 12, "normal": 8, "reserve": 4},
    "research": {"total": 20, "normal": 12, "reserve": 8},
    "lean": {"total": 16, "normal": 8, "reserve": 8},
}


def plan_document(name, project):
    document = raw_plan()
    document.update(plan_id=name, project_id=project)
    return document


def make_bridge(registry, document, adapter=None):
    return EngineeringTaskBridge(registry,
        EngineeringTaskPlan.from_dict(document, discovered_project_ids=[document["project_id"]]),
        adapter=adapter, completion_source=completed)


def compete(registry, document, kind, retry, barrier):
    bridge = make_bridge(registry, document)
    _limits(bridge, kind)
    barrier.wait(15)
    try:
        if kind == "configurations":
            bridge.register()
        else:
            attempt = bridge.claim(kind, retry_of=retry,
                reason="synthetic repair" if retry else None,
                allocation="reserve" if retry else "normal")
            if not attempt.should_execute:
                return "unexpected_reuse"
        return "admitted"
    except BudgetExceeded:
        return "rejected"


def process_contender(root, document, kind, retry, barrier, queue):
    try:
        registry = Registry(FilesystemArtifactStore(root), LIMITS)
        queue.put(compete(registry, document, kind, retry, barrier))
    except Exception as exc:
        queue.put("unexpected:" + type(exc).__name__ + ":" + str(exc))


class EngineeringAtomicAdmissionTests(unittest.TestCase):
    def race(self, kind, surface):
        with tempfile.TemporaryDirectory(prefix="aqrp-wr04-") as directory:
            filesystem = surface != "memory_threads"
            registry = Registry(FilesystemArtifactStore(directory) if filesystem else MemoryArtifactStore(), LIMITS)
            documents = [plan_document("contender-a", 101), plan_document("contender-b", 102)]
            retries = [None, None]
            if kind == "configurations":
                make_bridge(registry, plan_document("used", 103)).register()
            else:
                bridges = [make_bridge(registry, doc, Adapter()) for doc in documents]
                for bridge in bridges:
                    bridge.register()
                    if kind == "lean":
                        research = bridge.submit("research")
                        bridge.consume_completion(research)
                first = bridges[0].claim(kind)
                registry.fail(first, "synthetic failure remains charged")
                retries[0] = first.attempt_id
            if surface == "processes":
                context = multiprocessing.get_context("spawn")
                barrier, queue = context.Barrier(2), context.Queue()
                workers = [context.Process(target=process_contender,
                    args=(directory, doc, kind, retry, barrier, queue))
                    for doc, retry in zip(documents, retries)]
                try:
                    for worker in workers:
                        worker.start()
                    answers = [queue.get(timeout=40) for _ in workers]
                    for worker in workers:
                        worker.join(5)
                        self.assertEqual(worker.exitcode, 0)
                finally:
                    for worker in workers:
                        if worker.is_alive():
                            worker.terminate()
                        worker.join()
                    queue.close()
                    queue.join_thread()
            else:
                barrier = threading.Barrier(2)
                def worker(pair):
                    doc, retry = pair
                    other = Registry(FilesystemArtifactStore(directory), LIMITS) if filesystem else registry
                    return compete(other, doc, kind, retry, barrier)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    answers = list(executor.map(worker, zip(documents, retries)))
            self.assertCountEqual(answers, ["admitted", "rejected"])
            snapshot = registry.snapshot()
            self.assertEqual(snapshot["usage"][kind]["total"], 2)
            restarted = Registry(FilesystemArtifactStore(directory), LIMITS) if filesystem else Registry(registry.store, LIMITS)
            self.assertEqual(restarted.snapshot(), snapshot)

    def test_configuration_memory_threads(self): self.race("configurations", "memory_threads")
    def test_research_memory_threads(self): self.race("research", "memory_threads")
    def test_lean_memory_threads(self): self.race("lean", "memory_threads")
    def test_configuration_separate_disk_store_threads(self): self.race("configurations", "disk_threads")
    def test_research_separate_disk_store_threads(self): self.race("research", "disk_threads")
    def test_lean_separate_disk_store_threads(self): self.race("lean", "disk_threads")
    def test_configuration_native_processes(self): self.race("configurations", "processes")
    def test_research_native_processes(self): self.race("research", "processes")
    def test_lean_native_processes(self): self.race("lean", "processes")

    def test_direct_registry_and_bridge_registration_share_cap(self):
        registry = Registry(MemoryArtifactStore(), LIMITS)
        bridges = [make_bridge(registry, plan_document(str(i), 101 + i)) for i in range(3)]
        registry.register_config(bridges[0].package)
        bridges[1].register(allocation="reserve")
        with self.assertRaises(BudgetExceeded): bridges[2].register()
        with self.assertRaises(BudgetExceeded): registry.register_config(bridges[2].package)
        self.assertEqual(bridges[0].register(), bridges[0].config_id)
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 2)

    def test_direct_registry_attempts_cannot_bypass_round_cap(self):
        registry = Registry(MemoryArtifactStore(), LIMITS)
        bridge = make_bridge(registry, plan_document("direct", 101))
        bridge.register()
        for operation in ("first", "different-operation"):
            attempt = registry.begin_attempt(bridge.config_id, "research", operation_key=operation)
            registry.fail(attempt, "no refund")
        with self.assertRaises(BudgetExceeded): bridge.claim("research")
        with self.assertRaises(BudgetExceeded):
            registry.begin_attempt(bridge.config_id, "research", operation_key="third-operation")
        self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 2)

    def test_submit_rejects_before_adapter_and_failed_reuse_does_not_charge(self):
        store = MemoryArtifactStore()
        registry = Registry(store, LIMITS)
        adapter = Adapter()
        adapter.error = SubmissionRejected("synthetic refusal")
        bridge = make_bridge(registry, plan_document("failed", 101), adapter)
        bridge.register()
        first = bridge.submit("research")
        second = bridge.submit("research", retry_of=first.attempt_id, reason="repair", allocation="reserve")
        self.assertEqual(len(adapter.calls), 2)
        restarted = make_bridge(Registry(store, LIMITS), plan_document("failed", 101), adapter)
        self.assertEqual(restarted.submit("research").attempt_id, second.attempt_id)
        other = make_bridge(registry, plan_document("renamed", 102), adapter)
        other.register()
        with self.assertRaises(BudgetExceeded): other.submit("research")
        self.assertEqual(len(adapter.calls), 2)
        self.assertEqual(registry.snapshot()["usage"]["research"], {"total": 2, "normal": 1, "reserve": 1})

    def test_completed_and_unknown_reuse_at_full_round_limit(self):
        registry = Registry(MemoryArtifactStore(), LIMITS)
        first_adapter, unknown_adapter = Adapter(), Adapter()
        first = make_bridge(registry, plan_document("completed", 101), first_adapter)
        second = make_bridge(registry, plan_document("unknown", 102), unknown_adapter)
        first.register(); second.register()
        done = first.consume_completion(first.submit("research"))
        unknown_adapter.error = TimeoutError("synthetic unknown outcome")
        unknown = second.submit("research")
        before = deepcopy(registry.snapshot())
        for bridge, attempt in ((first, done), (second, unknown)):
            self.assertFalse(bridge.submit("research").should_execute)
            self.assertEqual(bridge.submit("research").attempt_id, attempt.attempt_id)
        self.assertEqual(len(first_adapter.calls), 1)
        self.assertEqual(len(unknown_adapter.calls), 1)
        self.assertEqual(registry.snapshot(), before)

    def test_global_cap_still_limits_an_engineering_admission(self):
        usage = {"configurations": {"total": 11, "normal": 8, "reserve": 3}}
        registry = Registry(MemoryArtifactStore(), LIMITS, usage=usage)
        first = make_bridge(registry, plan_document("last-global-slot", 101))
        second = make_bridge(registry, plan_document("global-exhausted", 102))
        first.register(allocation="reserve")
        with self.assertRaises(BudgetExceeded): second.register(allocation="reserve")
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 12)

    def test_registry_rejects_missing_changed_or_noninteger_engineering_marker(self):
        registry = Registry(MemoryArtifactStore(), LIMITS)
        package = make_bridge(registry, plan_document("marked", 101)).package
        for marker in (None, 0, 2, True, "1"):
            modified = deepcopy(package)
            if marker is None:
                modified.pop("engineering_task_schema_version")
            else:
                modified["engineering_task_schema_version"] = marker
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                registry.register_config(modified)
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
