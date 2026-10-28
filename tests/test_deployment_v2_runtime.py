"""Versioned worker/receipt integration, invented data and temporary stores only.

No provider, QC connector, authoritative Registry or reserved date is accessed.
The manifests and expected observations below are independent known answers.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
import qresearch.engineering_data as worker
import qresearch.engineering_receipts as receipts
from qresearch.deployment_observation import validate_observation_binding
from qresearch.engineering_tasks import (EngineeringTaskBridge, EngineeringTaskPlan,
    EngineeringTaskError, submission_protocol)
from qresearch.registry import Registry
from qresearch.collection_tasks import CollectionTaskBridge, CollectionTaskPlan
from qresearch.collection_execution import run_collection_task, stdout_marker, collection_research_observation
import test_engineering_data as receiver_fixture
import test_engineering_receipts as native_fixture
from test_wr13_annotations import ToyQuantBook
from test_collection_tasks import raw_plan as collection_plan, CAT, Source

POLICY = "utf8_sig_universal_newlines_terminal_lf_v1"
SOURCE = b"SYNTHETIC = True\n"


def manifest(sources):
    return {"schema_version": 2, "source_identity_policy": POLICY, "files": {
        name: {"source_sha256": sha256(raw).hexdigest(),
               "canonical_sha256": sha256(raw.rstrip(b"\n") + b"\n").hexdigest(),
               "terminal_lf_count": len(raw) - len(raw.rstrip(b"\n"))}
        for name, raw in sources.items()}}


def observation(deployment, count=1, normalized=0, mode="worker_terminal_lf"):
    return {"schema_version": 1, "source_identity_policy": POLICY,
            "deployment_hash": content_hash(deployment), "verification_mode": mode,
            "declared_file_count": count, "verified_file_count": count,
            "eof_normalized_file_count": normalized,
            "original_source_identity_match": normalized == 0, "canonical_sources_verified": True}


def synthetic_registry():
    store = MemoryArtifactStore()
    return store, Registry(store, {name: {"normal": 8, "reserve": 2, "total": 10}
        for name in ("configurations", "research", "lean")})


def admit(store, payload, *, collection=False):
    attempt = payload["identity"]["attempt_id"]
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode("utf-8")) + "\n"
    deployment = {name: payload["identity"][name] for name in ("source_manifest_hash", "deployment_hash")}
    deployment["input_hash"] = sha256(text.encode()).hexdigest()
    admission = {"payload": payload, "deployment": deployment,
        "input_path": ("audit/collection_task_inputs/" if collection else "audit/task_inputs/") + attempt + ".py",
        "cloud_input_path": "_collection_task_input.py" if collection else "_engineering_task_input.py"}
    prefix = "collection" if collection else "engineering"
    store.write_once(prefix + "/admitted-inputs/" + attempt + ".json", canonical_json(admission))
    return admission


class VersionedRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = {"a.py": SOURCE, "q/b.py": b"OTHER = 2"}
        for name, raw in self.sources.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.manifest = manifest(self.sources)
        self.hash = content_hash(self.manifest)

    def test_worker_observation_reconstructs_frozen_manifest_and_counts_exactly(self):
        (self.root / "a.py").write_bytes(SOURCE + b"\n")
        expected = observation(self.manifest, count=2, normalized=1)
        reads = []
        original = Path.read_bytes
        def read_once(path):
            reads.append(path)
            return original(path)
        with patch.object(Path, "read_bytes", read_once):
            actual = worker.verify_deployment_observation(self.manifest, self.hash,
                source_root=self.root, worker_diagnostics=True)
        self.assertEqual(actual, expected)
        self.assertEqual(len(reads), 2)
        self.assertEqual(len(set(reads)), 2)
        self.assertEqual(worker.verify_deployment(self.manifest, self.hash, source_root=self.root), self.hash)
        self.assertNotIn("q/b.py", json.dumps(actual))

    def test_project_original_mode_rejects_eof_change_accepted_by_worker(self):
        expected = observation(self.manifest, count=2, mode="project_original_source")
        self.assertEqual(worker.verify_deployment_observation(self.manifest, self.hash,
            source_root=self.root, require_source_bytes=True), expected)
        (self.root / "a.py").write_bytes(SOURCE + b"\n")
        with self.assertRaises(worker.DeploymentVerificationError) as caught:
            worker.verify_deployment_observation(self.manifest, self.hash,
                source_root=self.root, require_source_bytes=True)
        self.assertEqual(caught.exception.diagnostics["failure_kind"], "source_hash_mismatch")

    def test_body_import_comment_indentation_and_value_changes_still_reject(self):
        for changed in (b"import sys\n" + SOURCE, SOURCE + b"# added comment\n",
                SOURCE.replace(b"True", b"False"), b"if True:\n    " + SOURCE,
                SOURCE.replace(b" = ", b"  = ")):
            (self.root / "a.py").write_bytes(changed)
            with self.subTest(source=changed), self.assertRaises(worker.DeploymentVerificationError) as caught:
                worker.verify_deployment_observation(self.manifest, self.hash,
                    source_root=self.root, worker_diagnostics=True)
            self.assertEqual(caught.exception.diagnostics["failure_kind"], "source_hash_mismatch")

    def test_legacy_eof_difference_keeps_strict_schema2_diagnostic(self):
        legacy = {"a.py": sha256(SOURCE).hexdigest()}
        self.assertIsNone(worker.verify_deployment_observation(legacy, content_hash(legacy), source_root=self.root))
        (self.root / "a.py").write_bytes(SOURCE + b"\n")
        with self.assertRaises(worker.DeploymentVerificationError) as caught:
            worker.verify_deployment_observation(legacy, content_hash(legacy),
                source_root=self.root, worker_diagnostics=True)
        diagnostic = caught.exception.diagnostics
        self.assertEqual(diagnostic["schema_version"], 2)
        self.assertEqual(diagnostic["failure_kind"], "source_hash_mismatch")
        self.assertEqual(diagnostic["expected_sha256"], sha256(SOURCE).hexdigest())
        self.assertEqual(diagnostic["observed_sha256"], sha256(SOURCE + b"\n").hexdigest())
        self.assertIn("worker_observation", diagnostic)

    def test_observation_binding_refuses_missing_forged_counts_hash_and_project_mode(self):
        evidence = {"deployment_verification": observation(self.manifest, count=2)}
        validate_observation_binding(evidence, self.manifest, self.hash)
        mutations = [lambda value: value.pop("deployment_verification"),
            lambda value: value["deployment_verification"].update(schema_version=True),
            lambda value: value["deployment_verification"].update(source_identity_policy="unapproved"),
            lambda value: value["deployment_verification"].update(deployment_hash="0" * 64),
            lambda value: value["deployment_verification"].update(declared_file_count=1, verified_file_count=1),
            lambda value: value["deployment_verification"].update(verified_file_count=1),
            lambda value: value["deployment_verification"].update(eof_normalized_file_count=True),
            lambda value: value["deployment_verification"].update(eof_normalized_file_count=1),
            lambda value: value["deployment_verification"].update(canonical_sources_verified=False),
            lambda value: value["deployment_verification"].update(verification_mode="project_original_source"),
            lambda value: value["deployment_verification"].update(extra="SYNTHETIC-SECRET")]
        for mutation in mutations:
            changed = deepcopy(evidence)
            mutation(changed)
            with self.subTest(evidence=changed), self.assertRaises(ValueError):
                validate_observation_binding(changed, self.manifest, self.hash)
        legacy = {"a.py": sha256(SOURCE).hexdigest()}
        validate_observation_binding({}, legacy, content_hash(legacy))
        with self.assertRaises(ValueError):
            validate_observation_binding(evidence, legacy, content_hash(legacy))
        with self.assertRaises(ValueError):
            validate_observation_binding(evidence, self.manifest, "f" * 64)


class VersionedEngineeringWorkerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = receiver_fixture.EngineeringDataTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.fixture.manifest = manifest({"receiver.py": self.fixture.code.encode()})
        raw = self.fixture.plan.to_dict()
        raw["deployment_hash"] = content_hash(self.fixture.manifest)
        self.fixture.plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])
        (self.root / "receiver.py").write_bytes(self.fixture.code.encode() + b"\n")

    def test_context_opt_in_and_both_worker_reports_preserve_policy_evidence(self):
        payload = self.fixture.payload("research")
        expected = observation(self.fixture.manifest, normalized=1)
        self.assertEqual(len(worker._context(payload, "research", source_root=self.root)), 3)
        observed = worker._context(payload, "research", source_root=self.root, with_observation=True)
        self.assertEqual(len(observed), 4)
        self.assertEqual(observed[3], expected)
        original = worker._context
        with patch.object(worker, "_context", side_effect=lambda data, stage, **kwargs:
                original(data, stage, source_root=self.root, **kwargs)):
            research = worker.run_research_task(payload, api=receiver_fixture.FAKE_API,
                quantbook_factory=ToyQuantBook)
        self.assertEqual(research["cloud_report"]["evidence"]["deployment_verification"], expected)
        self.assertEqual(research["report_ref"]["sha256"], content_hash(research["cloud_report"]))
        algorithm = self.fixture.init_receiver()
        self.fixture.receive_all(algorithm)
        lean = worker.finish_receiver(algorithm)
        self.assertEqual(lean["cloud_report"]["status"], "completed")
        self.assertEqual(lean["cloud_report"]["evidence"]["deployment_verification"], expected)
        self.assertFalse(lean["cloud_report"]["market_values_exported"])
        self.assertFalse(lean["cloud_report"]["full_US200_coverage_certified"])
        self.assertFalse(lean["cloud_report"]["actual_availability_verified"])


class VersionedNativeRejectionTests(unittest.TestCase):
    def fixture(self):
        store, registry = synthetic_registry()
        deployment_manifest = manifest({"stub.py": SOURCE})
        raw = deepcopy(native_fixture.context("research")[0]["plan"])
        raw["deployment_hash"] = content_hash(deployment_manifest)
        plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])
        bridge = EngineeringTaskBridge(registry, plan)
        bridge.register()
        attempt = bridge.claim("research")
        payload = dict(bridge.payload(attempt), deployment_manifest=deployment_manifest)
        result = native_fixture.report(payload)
        result["cloud_report"]["evidence"]["deployment_verification"] = observation(deployment_manifest)
        result["report_ref"]["sha256"] = content_hash(result["cloud_report"])
        deployment = admit(store, payload)["deployment"]
        parsed = receipts.research_observation(payload, deployment, native_fixture.research_tool(payload, result))
        bridge.record_submission(attempt, parsed["submission"])
        bridge.consume_completion(attempt, completion_source=lambda _: parsed["completion"])
        lean = bridge.claim("lean")
        payload = dict(bridge.payload(lean), deployment_manifest=deployment_manifest)
        admission = admit(store, payload)
        deployment = admission["deployment"]
        store.write_once("engineering/submission-protocol/" + lean.attempt_id + ".json",
            canonical_json(submission_protocol(payload, deployment)))
        return store, registry, plan, lean, admission

    def test_v2_file_map_eligibility_uses_inner_sources_and_exact_generated_input(self):
        _, _, _, _, admission = self.fixture()
        for name, eligible in (("stub.py", True), ("_engineering_task_input.py", True),
                ("files.py", False), ("schema_version.py", False), ("unknown.py", False)):
            tool = native_fixture.envelope("create_backtest", {"projectId": 17},
                {"success": False, "errors": {name: ["1:2 SYNTHETIC-DIAGNOSTIC"]}})
            result = receipts.backtest_rejection(admission["payload"], admission["deployment"], tool)
            self.assertIs(result["raw_receipt"]["settlement_eligible"], eligible)
            self.assertNotIn("SYNTHETIC-DIAGNOSTIC", json.dumps(result))

    def test_fresh_bridge_recovers_v2_original_admission_without_new_source_or_charge(self):
        store, registry, plan, attempt, admission = self.fixture()
        tool = native_fixture.envelope("create_backtest", {"projectId": 17},
            {"success": False, "errors": {"stub.py": ["1:2 SYNTHETIC-DIAGNOSTIC"]}})
        receipt = receipts.backtest_rejection(admission["payload"], admission["deployment"], tool)
        before = registry.snapshot()["usage"]
        key = "engineering/admitted-inputs/" + attempt.attempt_id + ".json"
        original = store.read_bytes(key)
        recovered = EngineeringTaskBridge(registry, plan)
        with patch.object(worker, "verify_deployment_observation", side_effect=AssertionError("No live sources")):
            self.assertEqual(recovered.record_rejection(attempt, receipt).status, "failed")
            self.assertEqual(recovered.record_rejection(attempt, receipt).status, "failed")
        self.assertEqual(store.read_bytes(key), original)
        self.assertEqual(registry.snapshot()["usage"], before)
        self.assertEqual(json.loads(original)["payload"]["deployment_manifest"]["schema_version"], 2)

    def test_engineering_binding_requires_original_admission_and_complete_worker_summary(self):
        store, registry, plan, _, _ = self.fixture()
        bridge = EngineeringTaskBridge(registry, plan)
        report = bridge._research_result()["cloud_report"]
        attempt = report["identity"]["attempt_id"]
        payload = bridge.payload(attempt)
        key = "engineering/admitted-inputs/" + attempt + ".json"
        for mode in ("missing-summary", "wrong-count", "wrong-hash", "project-mode"):
            changed = deepcopy(report)
            summary = changed["evidence"]["deployment_verification"]
            if mode == "missing-summary":
                changed["evidence"].pop("deployment_verification")
            elif mode == "wrong-count":
                summary.update(declared_file_count=2, verified_file_count=2)
            elif mode == "wrong-hash":
                summary["deployment_hash"] = "0" * 64
            else:
                summary["verification_mode"] = "project_original_source"
            before = dict(store._data)
            with self.subTest(mode=mode), self.assertRaises(EngineeringTaskError):
                bridge._cloud_report(changed, payload)
            self.assertEqual(store._data, before)
        store._data.pop(key)
        with self.assertRaises(EngineeringTaskError):
            bridge._cloud_report(report, payload)


class VersionedCollectionWorkerTests(unittest.TestCase):
    def test_synthetic_collection_worker_native_parser_and_cache_replay_keep_v2_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "stub.py").write_bytes(SOURCE + b"\n")
            deployment_manifest = manifest({"stub.py": SOURCE})
            raw = collection_plan()
            raw["deployment_hash"] = content_hash(deployment_manifest)
            plan = CollectionTaskPlan.from_dict(raw, discovered_project_ids=[17], field_catalog=CAT)
            local, registry = synthetic_registry()
            bridge = CollectionTaskBridge(registry, plan)
            bridge.register()
            attempt = bridge.claim()
            payload = dict(bridge.payload(attempt), deployment_manifest=deployment_manifest)
            admission = admit(local, payload, collection=True)
            cloud, source = MemoryArtifactStore(), Source()
            expected = observation(deployment_manifest, normalized=1)
            result = run_collection_task(payload, field_catalog=CAT, store=cloud, source=source,
                synthetic=True, source_root=root)
            self.assertEqual(result["cloud_report"]["evidence"]["deployment_verification"], expected)
            self.assertEqual(run_collection_task(payload, field_catalog=CAT, store=cloud,
                synthetic=True, source_root=root), result)
            self.assertEqual(source.calls, 2)
            marker = stdout_marker(result, payload=payload, field_catalog=CAT)
            tool = native_fixture.envelope("jupyter_execute_cell", {"projectId": 17, "index": 0},
                {"status": "ok", "outputs": [{"output_type": "stream", "name": "stdout", "text": marker + "\n"}]})
            deployment = admission["deployment"]
            before = registry.snapshot()["usage"]
            parsed = collection_research_observation(payload, deployment, tool, field_catalog=CAT)
            bridge.record_submission(attempt, parsed["submission"])
            self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: parsed["completion"]).status,
                "completed")
            self.assertEqual(registry.snapshot()["usage"], before)
            self.assertNotIn("SYNTHETIC-ROW-SID", str(local._data))
            for mode in ("missing-summary", "wrong-count", "wrong-hash", "project-mode"):
                changed = deepcopy(result["cloud_report"])
                summary = changed["evidence"]["deployment_verification"]
                if mode == "missing-summary":
                    changed["evidence"].pop("deployment_verification")
                elif mode == "wrong-count":
                    summary.update(declared_file_count=2, verified_file_count=2)
                elif mode == "wrong-hash":
                    summary["deployment_hash"] = "0" * 64
                else:
                    summary.update(verification_mode="project_original_source", eof_normalized_file_count=0,
                        original_source_identity_match=True)
                before = dict(local._data)
                with self.subTest(mode=mode), self.assertRaises(EngineeringTaskError):
                    bridge._cloud_report(changed, payload)
                self.assertEqual(local._data, before)
            local._data.pop("collection/admitted-inputs/" + attempt.attempt_id + ".json")
            with self.assertRaises(EngineeringTaskError):
                bridge._cloud_report(result["cloud_report"], payload)


if __name__ == "__main__":
    unittest.main()
