"""Synthetic end-to-end boundaries for the explicit storage-repair protocol."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests"), str(ROOT / "tools")]
from qresearch.artifacts import canonical_json, content_hash
from qresearch.collection import HistoricalCollectionPlan
from qresearch.collection_storage import processing_contract_sha256
from qresearch.engineering_storage import (encode_compressed_json, decode_compressed_json,
    validate_capacity_observation)
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge, validate_joint_report
from qresearch.storage_capacity import check_capacity, StorageCapacityError
import qresearch.engineering_data as worker
from test_phase2_joint_plan import JointWorkerTests, joint_raw, CATALOG
from test_wr13_annotations import registry


def occurrence_raw():
    raw = joint_raw()
    raw["collection_probe"]["collection_plan"].update(schema_version=2, observation_policy="retain_source_occurrences")
    return raw


def repair_policy(legacy, identity, receipt_ref):
    processing = processing_contract_sha256()
    return {"schema_version": 1, "price_cache_mode": "cache_only", "lean_record_encoding": "zlib_json_v1",
        "capacity": {stage: {"required_bytes": 65536, "required_files": 8,
                             "reserve_bytes": 8192, "reserve_files": 2} for stage in ("research", "lean")},
        "collection_cache": {"schema_version": 1, "mode": "reuse_verified_legacy_only",
            "processing_contract_sha256": processing, "legacy": {"plan_identity": legacy.identity(),
                "plan_hash": legacy.hash, "source_manifest_hash": legacy.to_dict()["source_manifest_hash"],
                "processing_contract_sha256": processing, "receipt_ref": receipt_ref, "receipt_identity": identity}}}


class StorageRepairWorkerTests(unittest.TestCase):
    def fixture(self, directory):
        # Seed an older successful synthetic source once, as a distinct task.
        with patch("test_phase2_joint_plan.joint_raw", side_effect=occurrence_raw):
            prior = JointWorkerTests().build(directory)
        old_wrapper = JointWorkerTests().run_worker(prior)
        root, _, _, _, _, old_payload, api, qb = prior
        raw = deepcopy(old_payload["plan"])
        old_probe = raw["collection_probe"]
        legacy = HistoricalCollectionPlan.from_dict(old_probe["collection_plan"], field_catalog=old_probe["field_catalog"])
        raw.update(schema_version=3, plan_id="synthetic-storage-repair", report_namespace="engineering/synthetic-repair",
                   source_manifest_hash="b" * 64)
        raw["collection_probe"]["collection_plan"].update(plan_id="another-label", source_manifest_hash="b" * 64)
        raw["storage_policy"] = repair_policy(legacy, old_payload["identity"],
            old_wrapper["cloud_report"]["evidence"]["collection_probe"]["receipt_ref"])
        plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=(17,), probe_field_catalog=CATALOG)
        _, reg = registry()
        bridge = EngineeringTaskBridge(reg, plan); bridge.register()
        attempt = bridge.claim("research")
        payload = dict(bridge.payload(attempt), deployment_manifest=old_payload["deployment_manifest"])
        capacity = check_capacity({"max_size_bytes": 10**7, "max_files": 1000,
                                  "used_size_bytes": 1234, "used_files": 100}, **raw["storage_policy"]["capacity"]["research"])
        return root, qb, api, payload, capacity, old_wrapper

    def execute(self, root, qb, api, payload, capacity):
        original = worker._context
        with patch.object(worker, "_context", side_effect=lambda value, stage, **kw: original(value, stage, source_root=root, **kw)), \
             patch.object(worker.ObjectStoreArtifactStore, "preflight_capacity", return_value=capacity):
            return worker.run_research_task(payload, api=api, quantbook_factory=lambda: qb)

    def test_verified_legacy_run_has_no_new_source_or_row_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            root, qb, api, payload, capacity, prior = self.fixture(directory)
            source_calls = qb.universe_calls
            with patch.object(qb, "history", side_effect=AssertionError("Unexpected historical fetch")):
                result = self.execute(root, qb, api, payload, capacity)
            report = result["cloud_report"]
            self.assertEqual(qb.universe_calls, source_calls)
            self.assertTrue(all(report["checks"].values()))
            self.assertEqual(report["statistics"]["history_calls_first"], 0)
            reuse = report["evidence"]["collection_storage"]
            self.assertEqual(reuse["verified_window_count"], 40)
            self.assertFalse(reuse["new_row_objects"])
            self.assertEqual(reuse["origin_receipt_ref"], prior["cloud_report"]["evidence"]["collection_probe"]["receipt_ref"])
            validate_joint_report(report, payload["plan"])
            forged = deepcopy(report); forged["evidence"]["collection_storage"]["storage_plan_hash"] = "0" * 64
            with self.assertRaises(ValueError): validate_joint_report(forged, payload["plan"])

    def test_capacity_failure_precedes_resolution_writes_and_any_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root, qb, api, payload, _, _ = self.fixture(directory)
            original = worker._context
            with patch.object(worker, "_context", side_effect=lambda value, stage, **kw: original(value, stage, source_root=root, **kw)), \
                 patch.object(worker.ObjectStoreArtifactStore, "preflight_capacity", side_effect=StorageCapacityError("byte_capacity_insufficient")), \
                 patch.object(worker, "_resolution", side_effect=AssertionError("Write before preflight")), \
                 patch.object(qb, "history", side_effect=AssertionError("Fetch before preflight")):
                with self.assertRaises(StorageCapacityError):
                    worker.run_research_task(payload, api=api, quantbook_factory=lambda: qb)

    def test_plan_rejects_refresh_unbounded_capacity_and_unknown_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, _, payload, _, _ = self.fixture(directory)
            for edit in (lambda p: p.update(extra="row"), lambda p: p.update(price_cache_mode="fetch"),
                         lambda p: p["capacity"]["research"].update(required_bytes=True),
                         lambda p: p["capacity"]["lean"].update(required_bytes=10**12)):
                raw = deepcopy(payload["plan"]); edit(raw["storage_policy"])
                with self.assertRaises(ValueError): EngineeringTaskPlan.from_dict(raw, discovered_project_ids=(17,))


class CompressionBoundaryTests(unittest.TestCase):
    def test_roundtrip_byte_identity_and_corruption_trailing_stream_rejected(self):
        value = {"synthetic": [dict(field="example", number=i) for i in range(1000)]}
        stored, metadata = encode_compressed_json(value)
        self.assertEqual(decode_compressed_json(stored, metadata), value)
        self.assertLess(metadata["stored_bytes"], metadata["uncompressed_bytes"])
        for bad in (stored[:-1], stored + zlib.compress(b"{}"), stored[:5] + b"bad" + stored[8:]):
            with self.assertRaises(ValueError): decode_compressed_json(bad, metadata)
        altered = deepcopy(metadata); altered["uncompressed_bytes"] = 2**21
        with self.assertRaises(ValueError): decode_compressed_json(stored, altered, max_raw_bytes=10)

    def test_compressed_key_obeys_native_single_extension_contract(self):
        # Public LEAN LocalObjectStore path contract; not a cloud-binary claim.
        native = re.compile(r"^\.?[a-zA-Z0-9\\/_#\-\$= ]+\.?[a-zA-Z0-9]*$")
        self.assertIsNotNone(native.fullmatch("engineering/received/" + "a" * 64 + ".zlib"))
        self.assertIsNone(native.fullmatch("engineering/received/" + "a" * 64 + ".json.zlib"))

    def test_capacity_observation_cannot_forge_arithmetic_or_boolean_counts(self):
        observation = check_capacity({"max_size_bytes": 100, "max_files": 10,
                                      "used_size_bytes": 50, "used_files": 2}, 20, 1, reserve_bytes=10, reserve_files=1)
        validate_capacity_observation(observation)
        for key in ("used_size_bytes", "remaining_bytes_after_reservation"):
            bad = deepcopy(observation); bad[key] = True
            with self.assertRaises(ValueError): validate_capacity_observation(bad)

    def test_mutable_cycle_projection_cannot_invalidate_its_own_frozen_source(self):
        import collection_task_cli as controller
        budget = json.loads((ROOT / "config/budget.json").read_bytes())
        with patch.object(controller, "source_manifest", return_value={"source_files": {"config/budget.json": "ignored"}}), \
             patch.object(controller, "read_json", side_effect=lambda path: deepcopy(budget)):
            before = controller.execution_source_manifest()
            budget["usage"]["configuration_budget_charges"] += 1
            budget["configuration_cycle"] = {"usage": {"total": 1}, "state_hash": "1" * 64}
            self.assertEqual(controller.execution_source_manifest(), before)
            budget["limits"]["full_configurations"] += 1
            self.assertNotEqual(controller.execution_source_manifest(), before)


if __name__ == "__main__": unittest.main()
