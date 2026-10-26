"""Synthetic task receipts and in-memory accounting; no QC requests."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge, EngineeringTaskError
from qresearch.registry import Registry, BudgetExceeded
from qresearch.workflow import SubmissionRejected


def raw_plan():
    return {"schema_version": 1, "plan_id": "stage2-engineering-v1", "scope": "engineering", "project_id": 17,
            "source_manifest_hash": "a" * 64, "deployment_hash": "b" * 64, "request_mode": "symbol_resolution",
            "request_template": {"dataset": "US Equities", "fields": ["close", "volume"],
                "start": "2018-01-01T00:00:00-05:00", "end": "2019-01-01T00:00:00-05:00",
                "data_version": "synthetic-engine-v1", "universe_hash": "c" * 64,
                "normalization": "raw", "timezone": "America/New_York"},
            "symbol_resolution": {"tickers": ["AAPL", "MSFT"], "as_of": "2019-01-01T00:00:00-05:00",
                                  "method": "QuantBook.add_equity/as-of fixed fixture"},
            "observation_window": {"start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2019-01-01T00:00:00-05:00"},
            "required_checks": {"research": ["nonempty_history", "second_prefetch_no_history"],
                                "lean": ["data_received", "orders_zero", "corporate_action_received"]},
            "max_retries": {"research": 1, "lean": 1}, "report_namespace": "engineering/v2",
            "orders_enabled": False, "financial_metrics_enabled": False, "economic_factor": None, "economic_model": None}


def resolution():
    refs = {"resolved_registry_ref": {"key": "synthetic/registry.json", "sha256": "d" * 64},
            "resolved_request_ref": {"key": "synthetic/request.json", "sha256": "e" * 64}}
    return dict(refs, resolved_registry_hash="d" * 64, resolved_request_hash="e" * 64,
                resolution_artifact_hash=content_hash(refs), tickers=["AAPL", "MSFT"], ticker_count=2,
                permanent_sid_count=2, method="QuantBook.add_equity/as-of fixed fixture")


def submission(payload):
    identity = payload["identity"]
    external = ("qc-research:" + str(identity["project_id"]) + ":" + identity["attempt_id"]
                if identity["stage"] == "research" else "actual-synthetic-backtest-id")
    return {"identity": identity, "identity_kind": payload["external_identity_kind"], "external_id": external,
            "accepted": True, "status": "completed", "deployment": {
                "source_manifest_hash": identity["source_manifest_hash"], "deployment_hash": identity["deployment_hash"],
            "input_hash": "f" * 64}, "raw_receipt": {"success": True, "backtestId": external} if identity["stage"] == "lean" else {"success": True, "id": external}}


def completed(payload):
    receipt = submission(payload)
    identity = payload["identity"]
    report = {"schema_version": 1, "identity": identity, "status": "completed", "terminal": True,
              "checks": {name: True for name in payload["plan"]["required_checks"][identity["stage"]]},
              "statistics": {"record_count": 42, "history_calls_second": 0} if identity["stage"] == "research" else {
                  "data_event_count": 32, "orders_submitted": 0, "runtime_error_count": 0, "dividend_event_count": 2},
              "resolution": resolution(), "market_values_exported": False, "economic_factor_tested": False,
              "final_data_accessed": False, "full_US200_coverage_certified": False, "actual_availability_verified": False}
    return {"platform": {"identity": dict(identity, external_id=receipt["external_id"]), "status": "completed",
                         "terminal": True, "deployment": receipt["deployment"], "raw_receipt": {"completed": True}},
            "cloud_report": report, "report_ref": {"key": payload["report_key"], "sha256": content_hash(report)}}


class Adapter:
    def __init__(self):
        self.calls = []
        self.before_submit = None
        self.error = None

    def submit_research(self, payload, *, operation_key):
        if self.before_submit:
            self.before_submit()
        self.calls.append(deepcopy(payload))
        if self.error:
            raise self.error
        return submission(payload)

    submit_backtest = submit_research


class EngineeringTasksTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()
        self.limits = {key: {"total": 10, "normal": 8, "reserve": 2} for key in ("configurations", "research", "lean")}
        self.registry = Registry(self.store, self.limits)
        self.plan = EngineeringTaskPlan.from_dict(raw_plan(), discovered_project_ids=[17, 18])
        self.adapter = Adapter()
        self.bridge = EngineeringTaskBridge(self.registry, self.plan, adapter=self.adapter, completion_source=completed)
        self.bridge.register()

    def research_done(self):
        attempt = self.bridge.submit("research")
        return self.bridge.consume_completion(attempt)

    def test_plan_rejects_future_economic_and_unlisted_project_overrides(self):
        edits = [lambda p: p.update(project_id=19), lambda p: p.update(project_id=True),
                 lambda p: p.update(scope="research"), lambda p: p.update(orders_enabled=True),
                 lambda p: p.update(economic_model="ridge"), lambda p: p.update(unregistered_override=True),
                 lambda p: p["request_template"].update(end="2024-01-02T00:00:00-05:00"),
                 lambda p: p["request_template"].update(start="2018-12-01T00:00:00-05:00"),
                 lambda p: p["symbol_resolution"].update(tickers=["SPY", "MSFT"]),
                 lambda p: p["symbol_resolution"].update(as_of="2026-01-01T00:00:00-05:00")]
        for edit in edits:
            raw = raw_plan()
            edit(raw)
            with self.subTest(raw=raw), self.assertRaises((EngineeringTaskError, ValueError)):
                EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])

    def test_plan_is_frozen_and_semantic_changes_have_new_hash(self):
        with self.assertRaises(TypeError):
            EngineeringTaskPlan(b"{}")
        raw = raw_plan()
        plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])
        raw["source_manifest_hash"] = "0" * 64
        exported = plan.to_dict()
        exported["request_template"]["data_version"] = "tampered"
        self.assertEqual(plan.hash, self.plan.hash)
        changed = raw_plan()
        changed["source_manifest_hash"] = "1" * 64
        other = EngineeringTaskPlan.from_dict(changed, discovered_project_ids=[17])
        self.assertNotEqual(plan.hash, other.hash)
        self.assertEqual(self.bridge.register(), self.bridge.config_id)
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], 1)

    def test_debit_precedes_adapter_and_receipt_completed_only_means_pending(self):
        self.adapter.before_submit = lambda: self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)
        attempt = self.bridge.submit("research")
        self.assertEqual(attempt.status, "pending")
        self.assertFalse(attempt.should_execute)
        with self.assertRaises(Exception):
            self.bridge.read_result(attempt)
        repeated = self.bridge.submit("research")
        self.assertEqual(repeated.attempt_id, attempt.attempt_id)
        self.assertEqual(len(self.adapter.calls), 1)

    def test_terminal_requires_trusted_reader_platform_and_cloud_report(self):
        attempt = self.bridge.submit("research")
        for free in ({"status": "completed"}, {}, True):
            with self.subTest(free=free), self.assertRaises(EngineeringTaskError):
                self.bridge.consume_completion(attempt, completion_source=free)
        for mutate in (lambda x: x["platform"].update(terminal=False),
                       lambda x: x["platform"].update(status="compiled"),
                       lambda x: x.pop("cloud_report"),
                       lambda x: x["report_ref"].update(sha256="0" * 64)):
            def read(payload):
                result = completed(payload)
                mutate(result)
                return result
            with self.assertRaises(EngineeringTaskError):
                self.bridge.consume_completion(attempt, completion_source=read)
        self.assertEqual(self.bridge._record(attempt)["status"], "pending")

    def test_all_terminal_identity_components_and_input_must_match(self):
        attempt = self.bridge.submit("research")
        identity = self.bridge.payload(attempt)["identity"]
        for key in list(identity) + ["external_id", "input_hash"]:
            def wrong(payload):
                value = completed(payload)
                target = value["platform"]["deployment"] if key == "input_hash" else value["platform"]["identity"]
                target[key] = "wrong"
                return value
            with self.subTest(key=key), self.assertRaises(EngineeringTaskError):
                self.bridge.consume_completion(attempt, completion_source=wrong)
        self.assertEqual(self.bridge.consume_completion(attempt).status, "completed")

    def test_completed_result_reused_after_restart_without_callback(self):
        attempt = self.research_done()
        restarted = EngineeringTaskBridge(Registry(self.store, self.limits), self.plan, adapter=self.adapter,
                                         completion_source=lambda _: self.fail("Completed result must not be read again remotely"))
        self.assertEqual(restarted.submit("research").attempt_id, attempt.attempt_id)
        self.assertEqual(restarted.consume_completion(attempt).status, "completed")
        self.assertFalse(restarted.read_result(attempt)["financial_evidence"])
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)

    def test_lean_depends_on_research_and_inherits_resolution_without_overrides(self):
        with self.assertRaises(EngineeringTaskError):
            self.bridge.submit("lean")
        self.assertEqual(self.registry.snapshot()["usage"]["lean"]["total"], 0)
        self.research_done()
        lean = self.bridge.submit("lean")
        payload = self.adapter.calls[-1]
        self.assertEqual(payload["research_resolution"], resolution())
        self.assertEqual(self.bridge.consume_completion(lean).status, "completed")
        self.assertEqual(self.registry.snapshot()["usage"]["lean"]["total"], 1)

    def test_changed_resolution_and_false_coverage_certification_rejected(self):
        self.research_done()
        lean = self.bridge.submit("lean")
        for field in ("resolved_request_hash", "resolved_registry_hash", "full_US200_coverage_certified", "actual_availability_verified"):
            def wrong(payload):
                result = completed(payload)
                report = result["cloud_report"]
                if field in report:
                    report[field] = True
                else:
                    report["resolution"][field] = "1" * 64
                result["report_ref"]["sha256"] = content_hash(report)
                return result
            with self.subTest(field=field), self.assertRaises(EngineeringTaskError):
                self.bridge.consume_completion(lean, completion_source=wrong)

    def test_counts_are_observed_and_corporate_actions_cannot_be_boolean_only(self):
        self.research_done()
        lean = self.bridge.submit("lean")
        def no_dividend(payload):
            result = completed(payload)
            result["cloud_report"]["statistics"]["dividend_event_count"] = 0
            result["report_ref"]["sha256"] = content_hash(result["cloud_report"])
            return result
        self.assertEqual(self.bridge.consume_completion(lean, completion_source=no_dividend).status, "failed")
        self.assertEqual(self.registry.snapshot()["usage"]["lean"]["total"], 1)

    def test_known_rejection_retry_is_explicit_charged_and_bounded(self):
        self.adapter.error = SubmissionRejected("synthetic observed rejection")
        first = self.bridge.submit("research")
        self.assertEqual(first.status, "failed")
        self.assertEqual(self.bridge.submit("research").attempt_id, first.attempt_id)
        with self.assertRaises(Exception):
            self.bridge.submit("research", retry_of=first.attempt_id)
        second = self.bridge.submit("research", retry_of=first.attempt_id, reason="explicit repair", allocation="reserve")
        self.assertEqual(second.status, "failed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 2)
        with self.assertRaises(EngineeringTaskError):
            self.bridge.submit("research", retry_of=second.attempt_id, reason="unbounded retry")

    def test_timeout_stays_ambiguous_and_cannot_be_bypassed_by_new_plan_name(self):
        self.adapter.error = TimeoutError("remote state unknown")
        first = self.bridge.submit("research")
        self.assertEqual(first.status, "ambiguous")
        self.assertEqual(self.bridge.submit("research").attempt_id, first.attempt_id)
        changed = raw_plan()
        changed["plan_id"] = "cosmetic-new-name"
        other = EngineeringTaskBridge(self.registry, EngineeringTaskPlan.from_dict(changed, discovered_project_ids=[17]), adapter=self.adapter)
        other.register()
        with self.assertRaises(EngineeringTaskError):
            other.submit("research")
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)

    def test_ambiguous_acknowledgement_does_not_become_pending_but_final_can_reconcile(self):
        self.adapter.error = TimeoutError("synthetic unknown")
        first = self.bridge.submit("research")
        receipt = submission(self.bridge.payload(first))
        self.assertEqual(self.bridge.record_submission(first, receipt).status, "ambiguous")
        self.assertEqual(self.bridge.consume_completion(first).status, "completed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)

    def test_pending_lean_prevents_another_plan_from_overwriting_project_inputs(self):
        self.research_done()
        self.bridge.submit("lean")
        changed = raw_plan()
        changed["plan_id"] = "another-plan"
        other = EngineeringTaskBridge(self.registry, EngineeringTaskPlan.from_dict(changed, discovered_project_ids=[17]), adapter=self.adapter)
        other.register()
        with self.assertRaises(EngineeringTaskError):
            other.submit("research")
        self.assertEqual(len(self.adapter.calls), 2)

    def test_wrong_submission_binding_or_fake_research_job_id_fails_closed(self):
        attempt = self.bridge.claim("research")
        for key in ("identity", "external_id", "deployment"):
            value = submission(self.bridge.payload(attempt))
            if key == "identity":
                value[key]["source_manifest_hash"] = "0" * 64
            elif key == "deployment":
                value[key]["input_hash"] = "not-a-hash"
            else:
                value[key] = "fabricated-platform-job"
            with self.subTest(key=key), self.assertRaises(EngineeringTaskError):
                self.bridge.record_submission(attempt, value)

    def test_platform_failure_retains_evidence_and_never_refunds(self):
        attempt = self.bridge.submit("research")
        def failed(payload):
            result = completed(payload)
            result["platform"]["status"] = "runtime_error"
            result.pop("cloud_report")
            result.pop("report_ref")
            return result
        self.assertEqual(self.bridge.consume_completion(attempt, completion_source=failed).status, "failed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)
        self.assertTrue(any(key.startswith("engineering/evidence/") for key in self.store._data))

    def test_compile_receipt_cannot_create_a_pending_backtest(self):
        self.research_done()
        lean = self.bridge.claim("lean")
        receipt = submission(self.bridge.payload(lean))
        receipt["raw_receipt"] = {"success": True, "compileId": "compiled-only"}
        with self.assertRaises(EngineeringTaskError):
            self.bridge.record_submission(lean, receipt)
        self.assertEqual(self.bridge._record(lean)["status"], "started")

    def test_invalid_adapter_and_missing_ledger_admission_do_not_execute(self):
        bad = EngineeringTaskBridge(self.registry, self.plan, adapter=object())
        with self.assertRaises(EngineeringTaskError):
            bad.submit("research")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 0)
        limits = {key: {"total": 1, "normal": 1, "reserve": 0} for key in ("configurations", "research", "lean")}
        limits["research"] = {"total": 0, "normal": 0, "reserve": 0}
        empty = Registry(MemoryArtifactStore(), limits)
        blocked = EngineeringTaskBridge(empty, self.plan, adapter=self.adapter)
        blocked.register()
        with self.assertRaises(BudgetExceeded):
            blocked.submit("research")
        self.assertEqual(len(self.adapter.calls), 0)

    def test_market_performance_or_row_arrays_are_not_engineering_statistics(self):
        attempt = self.bridge.submit("research")
        for value in (0.12, [1, 2, 3], True):
            def bad(payload):
                result = completed(payload)
                result["cloud_report"]["statistics"]["invalid_market_value"] = value
                result["report_ref"]["sha256"] = content_hash(result["cloud_report"])
                return result
            with self.subTest(value=value), self.assertRaises(EngineeringTaskError):
                self.bridge.consume_completion(attempt, completion_source=bad)

    def test_unsafe_completion_fields_are_rejected_before_any_local_evidence_write(self):
        attempt = self.bridge.submit("research")
        mutations = [
            lambda v: v.update(rows=[["A", 123.45]]),
            lambda v: v["cloud_report"].update(rows=[["A", 123.45]]),
            lambda v: v["cloud_report"].update(evidence={"rows": [[123.45]]}),
            lambda v: v["cloud_report"].update(evidence={"coverage_certification_gaps": ["unregistered table"]}),
            lambda v: v["cloud_report"].update(evidence={"lean_engine_version": "version\n123.45"}),
            lambda v: v["cloud_report"]["statistics"].update(close=123),
            lambda v: v["platform"]["raw_receipt"].update(rows=[["A", 123.45]]),
            lambda v: v["platform"]["raw_receipt"].update(nested={"Values": [123.45]}),
            lambda v: v["platform"]["raw_receipt"].update(unknown_numeric_array=[123.45]),
            lambda v: v["platform"].update(dataframe=[[123.45]]),
            lambda v: v["cloud_report"]["resolution"].update(values=[123.45]),
        ]
        before = dict(self.store._data)
        for mutate in mutations:
            def unsafe(payload):
                result = completed(payload)
                mutate(result)
                result["report_ref"]["sha256"] = content_hash(result["cloud_report"])
                return result
            with self.subTest(mutation=mutate), self.assertRaises(EngineeringTaskError):
                self.bridge.consume_completion(attempt, completion_source=unsafe)
            self.assertEqual(self.store._data, before)

    def test_unsafe_submission_receipt_is_not_written_locally(self):
        attempt = self.bridge.claim("research")
        raw = submission(self.bridge.payload(attempt))
        raw["raw_receipt"]["nested"] = {"panel": [["A", 123.45]]}
        before = dict(self.store._data)
        with self.assertRaises(EngineeringTaskError):
            self.bridge.record_submission(attempt, raw)
        self.assertEqual(self.store._data, before)

    def test_safe_failure_report_and_fixed_evidence_are_preserved(self):
        from qresearch.coverage import RESEARCH_GAPS
        attempt = self.bridge.submit("research")
        def legitimate_failure(payload):
            result = completed(payload)
            report = result["cloud_report"]
            report["status"] = "failed"
            report["checks"]["nonempty_history"] = False
            report["statistics"]["record_count"] = 0
            report["evidence"] = {
                "coverage_report_ref": {"key": "synthetic/coverage.json", "sha256": "1" * 64},
                "cache_payload_refs": [{"key": "synthetic/cache.json", "sha256": "2" * 64}],
                "coverage_certification_gaps": list(RESEARCH_GAPS), "lean_engine_version": "synthetic-2.5.0",
                "vendor_revision_known": False,
            }
            result["platform"]["raw_receipt"]["warnings"] = {"module.py": ["synthetic metadata-only warning"]}
            result["report_ref"]["sha256"] = content_hash(report)
            return result
        final = self.bridge.consume_completion(attempt, completion_source=legitimate_failure)
        self.assertEqual(final.status, "failed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)
        saved = [value for key, value in self.store._data.items() if "/completion/" in key]
        self.assertEqual(len(saved), 1)
        self.assertIn(b'"coverage_report_ref"', saved[0])
        self.assertIn(b'"status":"failed"', saved[0])


if __name__ == "__main__":
    unittest.main()
