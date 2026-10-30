"""Synthetic source-bound charged diagnostics; no provider or cloud jobs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests"), str(ROOT / "tools")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.certification_tasks import (CertificationTaskPlan, CertificationTaskBridge, context,
    prepare_input, admitted_input, cell_source, reserve_dispatch, run_certification_task,
    validate_report, stdout_marker, research_observation, settle_result, run_cloud_task)
from qresearch.deployment_sources import build_manifest
from qresearch.engineering_tasks import EngineeringTaskError, EngineeringTaskBridge
from qresearch.engineering_receipts import ReceiptParseError
from qresearch.registry import Registry, RegistryError, BudgetExceeded, CorruptRegistry
import test_data_certification as fixture_data
from test_data_certification import ingestion, CATALOG, SID
import certification_tasks as cli


def manifest():
    return build_manifest({"qresearch/certification_tasks.py": (ROOT / "cloud/qresearch/certification_tasks.py").read_bytes()})


def raw_plan():
    fixture = fixture_data.DataCertificationTests
    raw = fixture.frozen_plan.to_dict()
    store = MemoryArtifactStore()
    source = ingestion(store)
    refs = fixture.base_refs
    return {"schema_version": 1, "task_kind": "data_certification", "scope": "engineering", "plan_id": "synthetic-certification",
        "project_id": 17, "source_manifest_hash": raw["source_manifest_hash"], "deployment_hash": content_hash(manifest()),
        "certification_plan": raw, "input_refs": {"liquidity": deepcopy(refs["liquidity_refs"]), "financial": deepcopy(refs["financial_refs"]),
        "membership": deepcopy(refs["membership_refs"]), "prices": deepcopy(refs["price_refs"]),
        "security_master": deepcopy(refs["security_master_refs"]), "corporate_actions": deepcopy(refs["corporate_action_refs"])},
        "source_binding": source.source_binding, "store_prefix": "synthetic/certification", "report_namespace": "synthetic/certification/task",
        "max_retries": 0, "capacity": {"required_bytes": 262144, "required_files": 3, "reserve_bytes": 8192, "reserve_files": 2}}


def plan(raw=None):
    return CertificationTaskPlan.from_dict(raw or raw_plan(), discovered_project_ids=[17], financial_catalog=CATALOG)


def authorize(registry, package):
    value = {"schema_version": 1, "round_id": "synthetic-certification-round", "project_id": 17,
        "allocation": "reserve", "limits": {"configurations": 1, "research": 1, "lean": 0},
        "final_test_enabled": False, "extra_spend_usd": 0}
    auth = deepcopy(value) | {"authority_kind": "explicit_human_user_message", "scope": "stage2_engineering_round",
        "global_limits_hash": content_hash(registry.limits), "request_text": "Synthetic explicit user-authorized certification diagnostic1/1/0"}
    digest = content_hash(auth)
    grant = value | {"authorization_ref": {"key": "engineering/rounds/user-authorizations/" + digest + ".json", "sha256": digest}}
    return registry.authorize_engineering_round(grant, [package], auth)


class CertificationTasksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_data.DataCertificationTests.setUpClass()

    def setUp(self):
        self.local = MemoryArtifactStore()
        self.registry = Registry(self.local, {kind: {"normal": 8, "reserve": 4, "total": 12} for kind in ("configurations", "research", "lean")})
        self.bridge = CertificationTaskBridge(self.registry, plan())
        authorize(self.registry, self.bridge.package)
        self.bridge.register(allocation="reserve")
        self.attempt = self.bridge.claim(allocation="reserve")
        self.admission = prepare_input(self.bridge, self.attempt, manifest())
        self.payload, self.deployment = self.admission["payload"], self.admission["deployment"]
        self.cloud = MemoryArtifactStore()
        self.cloud._data = dict(fixture_data.DataCertificationTests.base_store)
        self.ingest = ingestion(self.cloud)

    def bind(self, *, index=2):
        source = cell_source(self.payload, self.deployment)
        envelope = {"tool_name": "mcp__quantconnect__jupyter_read_cell", "arguments": {"projectId": 17, "index": index},
                    "result": {"structuredContent": {"cellType": "code", "source": source.splitlines(keepends=True)}}}
        return reserve_dispatch(self.bridge, self.attempt.attempt_id, envelope)

    def wrapper(self):
        return run_certification_task(self.payload, store=self.cloud, calendar=fixture_data.DataCertificationTests.calendar,
            ingestor=self.ingest, synthetic=True)

    def envelope(self, wrapper=None, *, index=2):
        marker = stdout_marker(wrapper or self.wrapper(), self.payload)
        return {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": index},
                "result": {"structuredContent": {"status": "ok", "success": True,
                    "outputs": [{"output_type": "stream", "name": "stdout", "text": marker + "\n"}]}}}

    def test_known_answer_predebit_worker_native_and_same_attempt_settlement(self):
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)
        self.assertTrue(self.bind()["should_execute"])
        native = self.envelope()
        final = settle_result(self.bridge, self.attempt.attempt_id, native)
        self.assertEqual(final.status, "completed")
        result = self.bridge.read_result(final)
        observation = result["cloud_report"]["evidence"]["observation"]
        self.assertEqual(observation["status"], "observations_passed")
        self.assertEqual(observation["counts"]["expected_member_cells"], 400)
        self.assertEqual(observation["counts"]["liquidity_record_count"], 201 * 21)
        self.assertFalse(observation["vendor_provenance_authenticated"])
        self.assertFalse(observation["full_historical_US200_certified"])
        self.assertFalse(observation["financial_vintage_certified"])
        self.assertFalse(result["financial_evidence"])
        for private in (SID[-1], "123456.78901", "88888.12345"):
            self.assertNotIn(private, str(self.local._data))
        before = deepcopy(self.local._data)
        self.assertEqual(settle_result(self.bridge, self.attempt.attempt_id, native).status, "completed")
        self.assertEqual(self.local._data, before)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)

    def test_unknown_native_outcome_never_redispatches_or_debits_again(self):
        first = self.bind()
        self.assertTrue(first["should_execute"])
        self.assertFalse(self.bind()["should_execute"])
        reused = self.bridge.claim(allocation="reserve")
        self.assertFalse(reused.should_execute)
        self.assertEqual(reused.attempt_id, self.attempt.attempt_id)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)

    def test_missing_evidence_is_completed_diagnostic_but_not_certification(self):
        raw = raw_plan()
        raw["input_refs"] = {name: [] for name in raw["input_refs"]}
        p = plan(raw)
        payload = deepcopy(self.payload)
        payload["plan"] = p.to_dict()
        payload["identity"].update(plan_hash=p.hash, config_id=content_hash({"engineering_task_schema_version": 1, "plan": p.to_dict()}), data_request_hash=p.request_hash)
        payload["report_key"] = p.to_dict()["report_namespace"] + "/reports/" + p.hash + "/research/" + self.attempt.attempt_id + ".json"
        wrapper = run_certification_task(payload, store=self.cloud, calendar=fixture_data.DataCertificationTests.calendar, ingestor=self.ingest, synthetic=True)
        self.assertEqual(wrapper["cloud_report"]["status"], "completed")
        observed = wrapper["cloud_report"]["evidence"]["observation"]
        self.assertEqual(observed["status"], "insufficient_evidence")
        self.assertFalse(observed["research_certified"])

    def test_unapproved_financial_fields_and_final_dates_are_rejected(self):
        raw = raw_plan()
        with self.assertRaises(ValueError):
            CertificationTaskPlan.from_dict(raw, discovered_project_ids=[17], financial_catalog={})
        for changes in ({"project_id": True}, {"project_id": 19}, {"max_retries": True}, {"max_retries": 1},
                        {"scope": "research"}, {"orders_enabled": True}, {"task_kind": "renamed"}, {"source_manifest_hash": "f" * 64}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                plan(raw_plan() | changes)
        raw["certification_plan"]["end_exclusive"] = "2024-01-02T00:00:00-05:00"
        with self.assertRaises(ValueError):
            plan(raw)

    def test_duplicate_refs_and_mutable_row_payload_cannot_enter_plan(self):
        raw = raw_plan()
        raw["input_refs"]["liquidity"] *= 2
        with self.assertRaises(ValueError):
            plan(raw)
        raw = raw_plan()
        raw["input_refs"]["liquidity"][0]["rows"] = [{"private": 123}]
        with self.assertRaises(ValueError):
            plan(raw)

    def test_plan_and_original_input_are_immutable(self):
        raw = raw_plan()
        p = plan(raw)
        original = p.hash
        raw["capacity"]["required_bytes"] += 1
        self.assertEqual(p.hash, original)
        self.assertEqual(admitted_input(self.bridge, self.attempt.attempt_id), self.admission)
        canonical = json.loads(canonical_json(self.payload))
        self.assertEqual(cell_source(canonical, self.deployment), cell_source(self.payload, self.deployment))
        with self.assertRaises(ValueError):
            prepare_input(self.bridge, self.attempt, build_manifest({"different.py": b"pass\n"}))

    def test_unauthorized_round_no_registration_and_no_debit(self):
        store = MemoryArtifactStore()
        registry = Registry(store, self.registry.limits)
        bridge = CertificationTaskBridge(registry, plan())
        before = deepcopy(store._data)
        with self.assertRaises(BudgetExceeded):
            bridge.register()
        self.assertEqual(store._data, before)
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 0)

    def test_generic_schema_downgrade_and_lean_bypass_are_rejected(self):
        for change in ({"task_kind": "generic"}, {"scope": "other"}, {"schema_version": True}):
            package = deepcopy(self.bridge.package)
            package["plan"].update(change)
            before = deepcopy(self.local._data)
            with self.assertRaises(ValueError):
                self.registry.register_config(package)
            self.assertEqual(self.local._data, before)
        with self.assertRaises(RegistryError):
            self.registry.begin_attempt(self.bridge.config_id, "lean", allocation="reserve", operation_key="certification-plan:" + self.bridge.plan.hash + ":research")
        with self.assertRaises(RegistryError):
            self.registry.begin_attempt(self.bridge.config_id, "research", allocation="reserve", operation_key="arbitrary")

    def test_read_source_and_execution_cell_are_bound_before_native_use(self):
        self.bind()
        before = deepcopy(self.local._data)
        for index in (1, True):
            envelope = self.envelope(index=index)
            with self.assertRaises(ValueError):
                settle_result(self.bridge, self.attempt.attempt_id, envelope)
        self.assertEqual(self.local._data, before)

    def test_free_success_without_dispatch_binding_is_rejected(self):
        before = deepcopy(self.local._data)
        with self.assertRaises((ValueError, FileNotFoundError)):
            settle_result(self.bridge, self.attempt.attempt_id, self.envelope())
        self.assertEqual(self.local._data, before)

    def test_native_error_is_settled_failed_keeps_spent_quota_and_private_text_cloud_only(self):
        self.bind()
        native = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 2},
            "result": {"content": [{"type": "text", "text": json.dumps({"output_type": "error", "ename": "ValueError",
                "evalue": "PRIVATE-ROW-VALUE", "traceback": ["PRIVATE-ROW-VALUE"]})}]}}
        final = settle_result(self.bridge, self.attempt.attempt_id, native)
        self.assertEqual(final.status, "failed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)
        self.assertNotIn("PRIVATE-ROW-VALUE", str(self.local._data))
        with self.assertRaises(RegistryError):
            self.bridge.claim(allocation="reserve", retry_of=self.attempt.attempt_id, reason="Forbidden retry")

    def test_report_approval_extra_rows_and_false_data_counts_are_rejected(self):
        wrapper = self.wrapper()
        for mutate in (lambda report: report.update(full_US200_coverage_certified=True),
                       lambda report: report["evidence"]["observation"].update(row_values_exported=True),
                       lambda report: report["evidence"]["observation"].update(rows=[1]),
                       lambda report: report["evidence"]["observation"]["counts"].update(formation_count=True),
                       lambda report: report["evidence"]["observation"]["counts"].update(price_missing_cells=1)):
            report = deepcopy(wrapper["cloud_report"])
            mutate(report)
            with self.assertRaises(ValueError):
                validate_report(report, self.bridge.plan, self.payload["identity"])

    def test_real_inputs_cannot_run_in_local_store_and_source_change_fails(self):
        with self.assertRaises(ValueError):
            run_certification_task(self.payload, store=self.cloud, calendar=fixture_data.DataCertificationTests.calendar, ingestor=self.ingest)
        changed = deepcopy(self.payload)
        changed["deployment_manifest"]["files"]["qresearch/certification_tasks.py"]["source_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            run_certification_task(changed, store=self.cloud, calendar=fixture_data.DataCertificationTests.calendar, ingestor=self.ingest, synthetic=True)

    def test_insufficient_capacity_or_live_receipt_cannot_be_faked_as_synthetic(self):
        raw = raw_plan()
        raw["capacity"]["required_bytes"] = 1
        with self.assertRaises(ValueError):
            plan(raw)
        wrapper = self.wrapper()
        report = deepcopy(wrapper["cloud_report"])
        report["evidence"]["observation"]["synthetic"] = False
        with self.assertRaises(ValueError):
            validate_report(report, self.bridge.plan, self.payload["identity"])

    def test_parser_does_not_accept_transport_or_compile_ack_as_execution(self):
        binding = self.bind()["binding"]
        for response in ({"success": True}, {"success": False, "errors": ["transport unavailable"]}, {"status": "compiled"}):
            envelope = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 2}, "result": response}
            with self.assertRaises(ValueError):
                research_observation(self.payload, self.deployment, envelope, dispatch_binding=binding)

    def test_historical_resolution_uses_admitted_package_not_current_config(self):
        bridge = cli.bridge_for_attempt(self.attempt.attempt_id, registry=self.registry)
        self.assertEqual(bridge.plan.hash, self.bridge.plan.hash)
        self.assertEqual(admitted_input(bridge, self.attempt.attempt_id), self.admission)

    def test_fixed_cloud_bootstrap_pins_development_frontier_before_security(self):
        calls = []
        class FakeQuantBook:
            def __init__(self):
                self.object_store = object()
                self.frontier = None
                calls.append("construct")
            def set_time_zone(self, name):
                calls.append(("timezone", name))
            def set_start_date(self, year, month, day):
                self.frontier = (year, month, day)
                calls.append(("frontier", self.frontier))
            def add_equity(self, name, resolution):
                if self.frontier is None or self.frontier[0] >= 2024:
                    raise AssertionError("Security bootstrap inherited a current/final frontier")
                calls.append(("security", name, resolution, self.frontier))
                return SimpleNamespace(exchange=SimpleNamespace(hours=object()))
        api = ModuleType("AlgorithmImports")
        api.Resolution = SimpleNamespace(DAILY="synthetic-daily")
        package = ModuleType("QuantConnect")
        package.__path__ = []
        research = ModuleType("QuantConnect.Research")
        research.QuantBook = FakeQuantBook
        for end, expected in (("2018-02-02T00:00:00-05:00", (2018, 2, 1)),
                              ("2024-01-01T00:00:00-05:00", (2023, 12, 31))):
            raw = raw_plan()
            raw["source_binding"]["synthetic"] = False
            raw["certification_plan"]["ingestion_namespace"] = content_hash(raw["source_binding"])
            raw["certification_plan"]["end_exclusive"] = end
            frozen = plan(raw)
            payload = deepcopy(self.payload)
            payload["plan"] = frozen.to_dict()
            payload["identity"].update(plan_hash=frozen.hash,
                config_id=content_hash({"engineering_task_schema_version": 1, "plan": frozen.to_dict()}),
                data_request_hash=frozen.request_hash)
            payload["report_key"] = frozen.to_dict()["report_namespace"] + "/reports/" + frozen.hash + "/research/" + self.attempt.attempt_id + ".json"
            calls.clear()
            with patch.dict(sys.modules, {"AlgorithmImports": api, "QuantConnect": package, "QuantConnect.Research": research}), \
                    patch("qresearch.certification_tasks.run_certification_task", return_value={"synthetic-bootstrap-only": True}) as worker:
                self.assertEqual(run_cloud_task(payload), {"synthetic-bootstrap-only": True})
            self.assertEqual(calls, ["construct", ("timezone", "America/New_York"), ("frontier", expected),
                                    ("security", "SPY", "synthetic-daily", expected)])
            self.assertEqual(worker.call_count, 1)

    def legacy_callbacks(self):
        wrapper = self.wrapper()
        external = "qc-research:17:" + self.attempt.attempt_id
        receipt = {"identity": self.payload["identity"], "identity_kind": "logical_research_execution_receipt",
            "accepted": True, "external_id": external, "status": "submitted", "deployment": self.deployment,
            "raw_receipt": {"accepted": True}}
        completion = {"platform": {"identity": dict(self.payload["identity"], external_id=external),
            "terminal": True, "status": "completed", "deployment": self.deployment, "raw_receipt": {"completed": True}}, **wrapper}
        return receipt, completion

    def test_legacy_public_and_base_callbacks_cannot_bypass_native_dispatch(self):
        receipt, completion = self.legacy_callbacks()
        for bound in (False, True):
            if bound:
                self.bind()
            before = deepcopy(self.local._data)
            for action in (
                lambda: self.bridge.record_submission(self.attempt, receipt),
                lambda: self.bridge.consume_completion(self.attempt, completion_source=lambda _: completion),
                lambda: EngineeringTaskBridge.record_submission(self.bridge, self.attempt, receipt),
                lambda: EngineeringTaskBridge.consume_completion(self.bridge, self.attempt, completion_source=lambda _: completion),
            ):
                with self.subTest(binding_exists=bound), self.assertRaises((ValueError, OSError)):
                    action()
                self.assertEqual(self.local._data, before)

    def test_generic_registry_cannot_manufacture_native_completion_or_failure(self):
        receipt, completion = self.legacy_callbacks()
        external = receipt["external_id"]
        fake = {"scope": "engineering", "identity": self.payload["identity"], "external_id": external,
                "cloud_report": completion["cloud_report"], "report_ref": completion["report_ref"],
                "platform_evidence_ref": {"key": "unproven/completion.json", "sha256": "f" * 64}, "financial_evidence": False}
        for bound in (False, True):
            if bound:
                self.bind()
            before = deepcopy(self.local._data)
            for action in (
                lambda: self.registry.complete(self.attempt, fake, external_id=external),
                lambda: self.registry.fail(self.attempt, {"platform_status": "runtime_error"}),
                lambda: self.registry.pending(self.attempt, external_id=external, details={}),
            ):
                with self.subTest(binding_exists=bound), self.assertRaises(RegistryError):
                    action()
                self.assertEqual(self.local._data, before)

    def test_after_real_native_proof_free_callbacks_cannot_replace_its_metadata(self):
        self.bind()
        native = self.envelope()
        final = settle_result(self.bridge, self.attempt.attempt_id, native)
        receipt, completion = self.legacy_callbacks()
        before = deepcopy(self.local._data)
        for action in (
            lambda: self.bridge.record_submission(final, receipt),
            lambda: self.bridge.consume_completion(final, completion_source=lambda _: completion),
            lambda: EngineeringTaskBridge.record_submission(self.bridge, final, receipt),
        ):
            with self.assertRaises((ValueError, OSError)):
                action()
            self.assertEqual(self.local._data, before)

    def test_native_proof_corruption_is_detected_on_registry_replay(self):
        self.bind()
        settle_result(self.bridge, self.attempt.attempt_id, self.envelope())
        key = "certification/native-receipts/" + self.attempt.attempt_id + ".json"
        proof = json.loads(self.local._data[key])
        proof["native_result_sha256"] = "f" * 64
        self.local._data[key] = canonical_json(proof)
        with self.assertRaises(CorruptRegistry):
            self.registry.snapshot()


if __name__ == "__main__":
    unittest.main()
