"""Precharged Research lifecycle and worker/parser chain, synthetic only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.collection import CollectionInterrupted
from qresearch.collection_tasks import CollectionTaskPlan, CollectionTaskBridge
from qresearch.collection_execution import run_collection_task, stdout_marker, collection_research_observation, context
from qresearch.engineering_tasks import EngineeringTaskError
from qresearch.registry import Registry, RegistryError
from qresearch.workflow import SubmissionRejected


CAT = {"dollar_volume": {"kind": "number", "role": "synthetic", "unit": "USD", "period_accessor": None}}


def manifest():
    path = ROOT / "cloud/qresearch/collection_tasks.py"
    return {"qresearch/collection_tasks.py": hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()}


def raw_plan():
    return {"schema_version": 1, "task_kind": "historical_collection", "scope": "engineering",
            "plan_id": "SYNTHETIC-TASK", "project_id": 17, "source_manifest_hash": "a" * 64,
            "deployment_hash": content_hash(manifest()), "report_namespace": "synthetic/collection", "max_retries": 1,
            "field_catalog": deepcopy(CAT), "collection_plan": {"schema_version": 1, "plan_id": "SYNTHETIC-SNAPSHOT",
            "scope": "engineering", "source": "quantconnect_fundamental_universe", "data_version": "SYNTHETIC-v1",
            "start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2018-01-05T00:00:00-05:00",
            "timezone": "America/New_York", "fields": ["dollar_volume"], "calendar_days_per_request": 1,
            "max_batch_records": 1, "max_records_per_window": 10, "source_manifest_hash": "a" * 64}}


def plan(raw=None):
    return CollectionTaskPlan.from_dict(raw or raw_plan(), discovered_project_ids=[17, 18], field_catalog=CAT)


class Source:
    def __init__(self):
        self.calls = 0

    def fetch(self, start, end, fields):
        self.calls += 1
        yield {"sid": "SYNTHETIC-ROW-SID", "snapshot_at": (start + pd.Timedelta(hours=9)).isoformat(),
               "values": {"dollar_volume": 0 if self.calls == 1 else None}}


class WorkerAdapter:
    def __init__(self, before=None):
        self.cloud, self.source, self.calls = MemoryArtifactStore(), Source(), 0
        self.before = before
        self.result = None

    def submit_research(self, payload, *, operation_key):
        if self.before:
            self.before()
        self.calls += 1
        payload = dict(payload, deployment_manifest=manifest())
        wrapper = run_collection_task(payload, field_catalog=CAT, store=self.cloud, source=self.source, synthetic=True)
        marker = stdout_marker(wrapper, payload=payload, field_catalog=CAT)
        envelope = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 0},
                    "result": {"structuredContent": {"status": "ok", "success": True,
                    "outputs": [{"output_type": "stream", "name": "stdout", "text": marker + "\n"}]}}}
        deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                      "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "f" * 64}
        self.result = collection_research_observation(payload, deployment, envelope, field_catalog=CAT)
        return self.result["submission"]


class CollectionTasksTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()
        self.registry = Registry(self.store, {key: {"normal": 8, "reserve": 2, "total": 10}
                                 for key in ("configurations", "research", "lean")})
        self.adapter = WorkerAdapter()
        self.bridge = CollectionTaskBridge(self.registry, plan(), adapter=self.adapter,
            completion_source=lambda _: self.adapter.result["completion"])
        self.bridge.register()

    def test_full_chain_debits_before_dispatch_waits_for_completion_and_reuses(self):
        self.adapter.before = lambda: self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)
        submitted = self.bridge.submit()
        self.assertEqual(submitted.status, "pending")
        self.assertEqual(self.adapter.source.calls, 2)
        self.assertEqual(self.bridge.submit().attempt_id, submitted.attempt_id)
        self.assertEqual(self.adapter.calls, 1)
        final = self.bridge.consume_completion(submitted)
        self.assertEqual(final.status, "completed")
        result = self.bridge.read_result(final)
        self.assertEqual(result["cloud_report"]["statistics"]["cache_only_source_fetch_calls"], 0)
        self.assertEqual(result["cloud_report"]["evidence"]["missing_values"], {"dollar_volume": 1})
        self.assertFalse(result["financial_evidence"])
        self.assertEqual(self.bridge.submit().status, "completed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)
        self.assertNotIn("SYNTHETIC-ROW-SID", str(self.store._data))
        self.assertNotIn('"records":', str(self.store._data))

    def test_worker_completed_cache_read_has_zero_new_source_calls(self):
        attempt = self.bridge.claim()
        payload = dict(self.bridge.payload(attempt), deployment_manifest=manifest())
        cloud, source = MemoryArtifactStore(), Source()
        first = run_collection_task(payload, field_catalog=CAT, store=cloud, source=source, synthetic=True)
        # Recover metadata after interruption without another source request or
        # changing the original first-pass provenance/immutable report.
        second = run_collection_task(payload, field_catalog=CAT, store=cloud, synthetic=True)
        self.assertEqual(first, second)
        self.assertEqual(source.calls, 2)
        self.assertEqual(first["cloud_report"]["statistics"]["source_fetch_calls"], 2)

    def test_cross_attempt_collection_reference_cannot_be_report_evidence(self):
        submitted = self.bridge.submit()
        changed = deepcopy(self.adapter.result["completion"])
        changed["cloud_report"]["evidence"]["collection_receipt_ref"]["key"] = "unrelated/another-attempt.json"
        changed["report_ref"]["sha256"] = content_hash(changed["cloud_report"])
        with self.assertRaises(EngineeringTaskError):
            self.bridge.consume_completion(submitted, completion_source=lambda _: changed)

    def test_invalid_plan_fields_project_source_and_catalog_fail_closed(self):
        bad = [{"scope": "research"}, {"project_id": True}, {"project_id": 19}, {"max_retries": True},
               {"max_retries": 3}, {"task_kind": "other"}, {"orders_enabled": True}, {"source_manifest_hash": "b" * 64}]
        for change in bad:
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                plan(raw_plan() | change)
        raw = raw_plan(); raw["field_catalog"]["dollar_volume"]["unit"] = "changed"
        with self.assertRaises(ValueError):
            plan(raw)
        raw = raw_plan(); raw["collection_plan"]["end_exclusive"] = "2024-01-02T00:00:00-05:00"
        with self.assertRaises(ValueError):
            plan(raw)

    def test_plan_and_collection_catalog_are_immutable(self):
        raw = raw_plan(); frozen = plan(raw); expected = frozen.hash
        raw["max_retries"] = 0
        copy = frozen.to_dict(); copy["field_catalog"]["dollar_volume"]["unit"] = "changed"
        self.assertEqual(frozen.hash, expected)
        with self.assertRaises(TypeError):
            CollectionTaskPlan({})

    def test_absent_adapter_does_not_debit_and_lean_is_rejected(self):
        bridge = CollectionTaskBridge(self.registry, plan())
        with self.assertRaises(EngineeringTaskError):
            bridge.submit()
        with self.assertRaises(EngineeringTaskError):
            self.bridge.submit("lean")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 0)

    def test_rejected_and_unknown_submissions_do_not_refund_or_leak_error_values(self):
        class Reject:
            def submit_research(self, *args, **kwargs):
                raise SubmissionRejected("SYNTHETIC-PRIVATE-VALUE")

        class Unknown:
            def submit_research(self, *args, **kwargs):
                raise RuntimeError("SYNTHETIC-PRIVATE-VALUE")

        self.bridge.adapter = Reject()
        failed = self.bridge.submit()
        self.assertEqual(failed.status, "failed")
        self.assertEqual(self.bridge.submit().attempt_id, failed.attempt_id)
        self.bridge.adapter = Unknown()
        unknown = self.bridge.submit(retry_of=failed.attempt_id, reason="explicit repair", allocation="reserve")
        self.assertEqual(unknown.status, "ambiguous")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 2)
        self.assertNotIn("SYNTHETIC-PRIVATE-VALUE", str(self.store._data))
        self.assertEqual(self.bridge.submit().attempt_id, unknown.attempt_id)

    def test_free_result_dictionary_cannot_finalize_and_wrong_attempt_cannot_be_read(self):
        submitted = self.bridge.submit()
        with self.assertRaises(EngineeringTaskError):
            self.bridge.consume_completion(submitted, completion_source={"completed": True})
        with self.assertRaises(RegistryError):
            self.bridge.read_result(submitted)
        with self.assertRaises(EngineeringTaskError):
            self.bridge.payload("0" * 32)

    def test_worker_requires_real_cloud_residency_and_pinned_source(self):
        attempt = self.bridge.claim(); payload = dict(self.bridge.payload(attempt), deployment_manifest=manifest())
        with self.assertRaises(EngineeringTaskError):
            run_collection_task(payload, field_catalog=CAT, store=MemoryArtifactStore(), source=Source())
        changed = deepcopy(payload); changed["deployment_manifest"]["qresearch/collection_tasks.py"] = "0" * 64
        with self.assertRaises(ValueError):
            run_collection_task(changed, field_catalog=CAT, store=MemoryArtifactStore(), source=Source(), synthetic=True)
        changed = deepcopy(payload); changed["identity"]["config_id"] = "0" * 64
        with self.assertRaises(ValueError):
            context(changed, field_catalog=CAT)

    def test_report_cannot_add_rows_claim_coverage_or_change_counts(self):
        submitted = self.bridge.submit()
        original = self.adapter.result["completion"]
        for mutate in (lambda r: r.update(records=[]), lambda r: r.update(actual_availability_verified=True),
                       lambda r: r["statistics"].update(record_count=True),
                       lambda r: r["statistics"].update(cache_only_source_fetch_calls=1),
                       lambda r: r["evidence"]["missing_values"].update(dollar_volume=99)):
            changed = deepcopy(original); mutate(changed["cloud_report"])
            with self.assertRaises((ValueError, TypeError)):
                self.bridge.consume_completion(submitted, completion_source=lambda _, c=changed: c)
        self.assertEqual(self.registry.snapshot()["attempts"][-1]["status"], "pending")
        self.assertEqual(self.bridge.consume_completion(submitted).status, "completed")

    def test_foreign_native_tool_project_marker_and_stdout_rejected(self):
        submitted = self.bridge.submit(); payload = self.bridge.payload(submitted)
        wrapper = {k: self.adapter.result["completion"][k] for k in ("cloud_report", "report_ref")}
        marker = stdout_marker(wrapper, payload=payload, field_catalog=CAT)
        deployment = self.adapter.result["submission"]["deployment"]
        base = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 0},
                "result": {"structuredContent": {"outputs": [{"output_type": "stream", "name": "stdout", "text": marker}]}}}
        for mutate in (lambda r: r.update(tool_name="other"), lambda r: r["arguments"].update(projectId=18),
                       lambda r: r["result"]["structuredContent"]["outputs"][0].update(text=marker + "\nSYNTHETIC-ROW"),
                       lambda r: r["result"]["structuredContent"]["outputs"][0].update(name="stderr")):
            changed = deepcopy(base); mutate(changed)
            with self.assertRaises((ValueError, TypeError)):
                collection_research_observation(payload, deployment, changed, field_catalog=CAT)


if __name__ == "__main__":
    unittest.main()
