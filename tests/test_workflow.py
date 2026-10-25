"""Synthetic workflow lifecycle and crash-window checks; no cloud execution."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.audits import make_evidence
from qresearch.registry import BudgetExceeded, Registry
from qresearch.workflow import WorkflowController, WorkflowError, SubmissionRejected
from test_persistence import budget_fixture
from test_study import fixture_study, fixture_trading
from qresearch.study import StudySpec


def identity_fixture():
    return dict(zip(("code_hash", "data_hash", "universe_hash", "label_hash",
                     "factor_set_hash", "model_hash", "trading_hash"),
                    (str(i) * 64 for i in range(1, 8))),
                data_end_exclusive="2023-12-31T23:00:00-05:00")


def campaign_fixture():
    identity = identity_fixture()
    return {"schema_version": 1, "phase": "factor", "scope": "engineering",
            "fixed_model_hash": identity["model_hash"], "fixed_trading_hash": identity["trading_hash"],
            "audit_issuers": ["synthetic-fixed-checker"],
            "required_audit_checks": {"formula_timing": ["causal"], "data_coverage": ["complete"]},
            "max_candidates": 2, "max_research_retries": 1, "max_lean_retries": 0,
            "decision_rules": {"research": [{"field": "statistics.sample_count", "op": ">=", "value": 3}],
                               "lean": [{"field": "checks.parity", "op": "==", "value": True}]}}


class FakeAdapter:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.receipt_status = "submitted"
        self.before_submit = None

    def submit_research(self, payload, *, operation_key):
        if self.before_submit:
            self.before_submit()
        self.calls.append(deepcopy(payload))
        if self.failure:
            raise self.failure
        return {"external_id": "synthetic-job-" + str(len(self.calls)), "status": self.receipt_status}

    submit_backtest = submit_research


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.store, self.adapter = MemoryArtifactStore(), FakeAdapter()
        self.registry = Registry(self.store, budget_fixture())
        self.controller = self.make_controller()
        self.identity = identity_fixture()
        self.config_id = self.controller.register({"scope": "engineering", "synthetic": True}, self.identity)

    def make_controller(self, campaign=None):
        return WorkflowController(self.registry, self.adapter, campaign=campaign or campaign_fixture())

    def evidence(self, name, passed=True, **overrides):
        evidence = make_evidence(self.store, subject_hash=self.config_id,
            source_hash=self.identity["code_hash"], issuer="synthetic-fixed-checker",
            checks={name: passed}, scope="engineering").to_dict()
        return dict(evidence, **overrides)

    def ready(self):
        self.controller.audit(self.config_id, self.evidence("causal"))
        self.controller.data_ready(self.config_id, self.evidence("complete"))

    def result(self, stage="research", status="completed", **overrides):
        call = next(x for x in reversed(self.adapter.calls) if x["_workflow"]["stage"] == stage)
        meta = deepcopy(call["_workflow"])
        meta.pop("identity")
        state = self.controller.status(self.config_id)
        return dict(meta, external_id=state["attempts"][stage]["external_id"], terminal=True,
                    status=status, statistics={"sample_count": 3}, checks={"parity": True}, **overrides)

    def finish_research(self):
        self.ready()
        self.controller.submit(self.config_id, "research", {"fixture": "bounded-plan"})
        result = self.result()
        self.controller.consume_result(self.config_id, "research", result["external_id"], result)
        self.controller.decide(self.config_id, "research")

    def test_audits_require_trusted_source_subject_and_named_checks(self):
        for raw in (True, self.evidence("causal", issuer_kind="llm"),
                    self.evidence("causal", subject_hash="0" * 64), self.evidence("unrelated")):
            with self.subTest(raw=raw), self.assertRaises((WorkflowError, ValueError)):
                self.controller.audit(self.config_id, raw)
        self.assertEqual(self.controller.status(self.config_id)["status"], "registered")
        blocked = self.controller.audit(self.config_id, self.evidence("causal", passed=False))
        self.assertEqual(blocked["status"], "blocked")
        archived = self.controller.archive(self.config_id)
        self.assertEqual(archived["archive"]["verdict"], "insufficient_evidence")
        with self.assertRaises(WorkflowError):
            self.controller.freeze(self.config_id)

    def test_stage_order_and_final_data_are_denied_without_new_charge(self):
        with self.assertRaises(WorkflowError):
            self.controller.submit(self.config_id, "research", {})
        with self.assertRaises(WorkflowError):
            self.controller.submit(self.config_id, "final", {})
        changed = dict(self.identity, data_end_exclusive="2024-01-02T00:00:00-05:00")
        with self.assertRaises(WorkflowError):
            self.controller.register({"synthetic": True}, changed)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 6)

    def test_audit_reference_integrity_checked_before_advancing(self):
        evidence = self.evidence("causal")
        self.store._data[evidence["evidence_refs"][0]["key"]] = b"synthetic corruption"
        with self.assertRaises((WorkflowError, ValueError)):
            self.controller.audit(self.config_id, evidence)
        self.assertEqual(self.controller.status(self.config_id)["status"], "registered")

    def test_audit_outcome_tampering_cannot_overrule_failed_observation(self):
        evidence = self.evidence("causal", passed=False)
        evidence["checks"][0]["passed"] = True
        with self.assertRaises(ValueError):
            self.controller.audit(self.config_id, evidence)
        self.assertEqual(self.controller.status(self.config_id)["status"], "registered")
        observed_failure = self.evidence("causal", passed=False)
        self.assertEqual(self.controller.audit(self.config_id, observed_failure)["status"], "blocked")

    def test_omitting_observed_failure_cannot_make_audit_pass(self):
        evidence = make_evidence(self.store, subject_hash=self.config_id,
            source_hash=self.identity["code_hash"], issuer="synthetic-fixed-checker",
            checks={"causal": True, "additional_failed_check": False}, scope="engineering").to_dict()
        evidence["checks"] = [check for check in evidence["checks"] if check["name"] == "causal"]
        with self.assertRaises(ValueError):
            self.controller.audit(self.config_id, evidence)
        self.assertEqual(self.controller.status(self.config_id)["status"], "registered")

    def production_controller(self):
        document = fixture_study("research")
        document["trading_spec"] = fixture_trading()
        study = StudySpec.from_dict(document, field_catalog=["close"], require_trading=True)
        frozen = study.to_dict()
        components, binding = frozen["component_hashes"], frozen["data_binding"]
        identity = {"code_hash": binding["code_hash"], "data_hash": content_hash(binding),
                    "universe_hash": binding["universe_hash"], "label_hash": components["label"],
                    "factor_set_hash": content_hash(components["factors"]), "model_hash": components["model"],
                    "trading_hash": components["trading"], "data_end_exclusive": frozen["development"]["end_exclusive"]}
        campaign = campaign_fixture()
        campaign.update(scope="research", fixed_model_hash=identity["model_hash"], fixed_trading_hash=identity["trading_hash"])
        controller = WorkflowController(self.registry, self.adapter, campaign=campaign, field_catalog=["close"])
        return controller, frozen, identity

    def test_research_registration_rejects_arbitrary_json_and_unbound_components(self):
        controller, study, identity = self.production_controller()
        before = self.registry.snapshot()["usage"]["configurations"]["total"]
        with self.assertRaises((WorkflowError, ValueError)):
            controller.register({"approved": True}, identity)
        for field in ("data_hash", "code_hash", "universe_hash", "label_hash", "factor_set_hash"):
            with self.subTest(field=field), self.assertRaises(WorkflowError):
                controller.register(study, dict(identity, **{field: "0" * 64}))
        with self.assertRaises(WorkflowError):
            controller.register(study, dict(identity, data_end_exclusive="2020-01-01T00:00:00-05:00"))
        with self.assertRaises(WorkflowError):
            controller.register(study, dict(identity, model_parameters={"alpha": 0}))
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], before)
        registered = controller.register(study, identity)
        self.assertEqual(controller.status(registered)["status"], "registered")

    def test_research_dispatch_without_certified_adapter_fails_closed_before_budget(self):
        controller, study, identity = self.production_controller()
        registered = controller.register(study, identity)
        before = self.registry.snapshot()["usage"]["research"]["total"]
        with self.assertRaisesRegex(WorkflowError, "dispatch is disabled"):
            controller.submit(registered, "research", {"end_date": "2026-10-23", "model_parameters": {"alpha": 0}})
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], before)
        self.assertEqual(self.adapter.calls, [])

    def test_research_registration_requires_trusted_field_catalog(self):
        controller, study, identity = self.production_controller()
        without_catalog = WorkflowController(self.registry, self.adapter, campaign=controller.campaign)
        with self.assertRaisesRegex(WorkflowError, "trusted field catalog"):
            without_catalog.register(study, identity)

    def test_receipt_is_not_completion_and_duplicate_submit_is_free(self):
        self.ready()
        self.adapter.receipt_status = "completed"
        state = self.controller.submit(self.config_id, "research", {"fixture": "bounded-plan"})
        self.assertEqual(state["status"], "research_submitted")
        with self.assertRaises(WorkflowError):
            self.controller.decide(self.config_id, "research")
        self.controller.submit(self.config_id, "research", {"fixture": "bounded-plan"})
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)

    def test_budget_is_durable_before_adapter_and_confirmed_failure_not_refunded(self):
        self.ready()
        self.adapter.before_submit = lambda: self.assertEqual(
            self.registry.snapshot()["usage"]["research"]["total"], 7)
        self.adapter.failure = SubmissionRejected("synthetic confirmed rejection")
        state = self.controller.submit(self.config_id, "research", {})
        self.assertEqual(state["status"], "research_failed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)
        self.controller.submit(self.config_id, "research", {})
        self.assertEqual(len(self.adapter.calls), 1)

    def test_timeout_is_ambiguous_and_restart_does_not_resubmit(self):
        self.ready()
        self.adapter.failure = TimeoutError("synthetic unknown remote outcome")
        state = self.controller.submit(self.config_id, "research", {})
        self.assertEqual(state["status"], "research_ambiguous")
        reopened = self.make_controller()
        reopened.submit(self.config_id, "research", {})
        self.assertEqual(len(self.adapter.calls), 1)
        with self.assertRaises(WorkflowError):
            reopened.archive(self.config_id)

    def test_crash_after_admission_cannot_submit_again(self):
        class SimulatedProcessDeath(BaseException):
            pass
        self.ready()
        self.adapter.failure = SimulatedProcessDeath()
        with self.assertRaises(SimulatedProcessDeath):
            self.controller.submit(self.config_id, "research", {})
        reopened = self.make_controller()
        state = reopened.submit(self.config_id, "research", {})
        self.assertEqual(state["status"], "research_claimed")
        self.assertEqual(len(self.adapter.calls), 1)

    def test_claim_journal_gap_recovered_from_registry(self):
        self.ready()
        append = self.store.append_event
        def interrupted_append(stream, event):
            if event.get("to") == "research_claimed":
                raise OSError("Synthetic crash after Registry debit before workflow claim")
            return append(stream, event)
        with patch.object(self.store, "append_event", side_effect=interrupted_append):
            with self.assertRaises(OSError):
                self.controller.submit(self.config_id, "research", {})
        state = self.make_controller().submit(self.config_id, "research", {})
        self.assertEqual(state["status"], "research_claimed")
        self.assertEqual(self.adapter.calls, [])

    def test_completed_registry_gap_recovers_without_repeating_remote_work(self):
        self.ready()
        self.controller.submit(self.config_id, "research", {})
        result = self.result()
        append = self.store.append_event
        def interrupted_append(stream, event):
            if event.get("to") == "research_completed":
                raise OSError("Synthetic crash after Registry completion")
            return append(stream, event)
        with patch.object(self.store, "append_event", side_effect=interrupted_append):
            with self.assertRaises(OSError):
                self.controller.consume_result(self.config_id, "research", result["external_id"], result)
        reopened = self.make_controller()
        self.assertEqual(reopened.status(self.config_id)["status"], "research_completed")
        reopened.submit(self.config_id, "research", {})
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)

    def test_wrong_result_id_and_nonterminal_success_rejected(self):
        self.ready()
        self.controller.submit(self.config_id, "research", {})
        result = self.result()
        wrong = dict(result, external_id="different-job")
        with self.assertRaises(WorkflowError):
            self.controller.consume_result(self.config_id, "research", wrong["external_id"], wrong)
        for wrong in (dict(result, terminal=False), dict(result, status="compiled"),
                      dict(result, config_id="0" * 64), dict(result, identity_hash="0" * 64)):
            with self.subTest(wrong=wrong), self.assertRaises(WorkflowError):
                self.controller.consume_result(self.config_id, "research", result["external_id"], wrong)
        self.assertEqual(self.controller.status(self.config_id)["status"], "research_submitted")

    def test_full_fixed_pipeline_archives_then_freezes_without_running_final(self):
        self.finish_research()
        self.controller.submit(self.config_id, "lean", {"fixture": "same-frozen-protocol"})
        result = self.result("lean")
        self.controller.consume_result(self.config_id, "lean", result["external_id"], result)
        self.assertEqual(self.controller.decide(self.config_id, "lean")["status"], "lean_passed")
        self.controller.archive(self.config_id)
        frozen = self.controller.freeze(self.config_id)
        packet = json.loads(self.store.read_bytes(frozen["freeze"]["key"]))
        self.assertFalse(packet["final_execution_enabled"])
        self.assertTrue(packet["independent_executor_required"])
        self.assertEqual(self.controller.freeze(self.config_id), frozen)
        self.assertEqual(self.registry.snapshot()["usage"]["lean"]["total"], 1)

    def test_predicate_uses_preregistered_numeric_values_not_provided_accept_flag(self):
        self.ready()
        self.controller.submit(self.config_id, "research", {})
        result = self.result()
        result["statistics"]["sample_count"] = 2
        result["accepted"] = True
        self.controller.consume_result(self.config_id, "research", result["external_id"], result)
        self.assertEqual(self.controller.decide(self.config_id, "research")["status"], "research_rejected")
        with self.assertRaises(WorkflowError):
            self.controller.submit(self.config_id, "lean", {})

    def test_missing_metric_is_archived_as_insufficient_not_zero_or_success(self):
        self.ready()
        self.controller.submit(self.config_id, "research", {})
        result = self.result()
        result["statistics"] = {}
        self.controller.consume_result(self.config_id, "research", result["external_id"], result)
        self.controller.decide(self.config_id, "research")
        self.assertEqual(self.controller.archive(self.config_id)["archive"]["verdict"], "insufficient_evidence")

    def test_retries_are_explicit_bounded_and_cannot_change_payload(self):
        self.ready()
        self.adapter.failure = SubmissionRejected("synthetic repairable failure")
        state = self.controller.submit(self.config_id, "research", {"fixture": 1})
        first_id = state["attempts"]["research"]["attempt_id"]
        with self.assertRaises(WorkflowError):
            self.controller.submit(self.config_id, "research", {"fixture": 2}, allocation="reserve", retry_of=first_id, reason="repair")
        state = self.controller.submit(self.config_id, "research", {"fixture": 1}, allocation="reserve", retry_of=first_id, reason="bounded repair")
        self.assertEqual(len(self.adapter.calls), 2)
        second_id = state["attempts"]["research"]["attempt_id"]
        with self.assertRaises(WorkflowError):
            self.controller.submit(self.config_id, "research", {"fixture": 1}, allocation="reserve", retry_of=second_id, reason="excess repair")
        self.assertEqual(self.controller.status(self.config_id)["status"], "blocked")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 8)

    def test_concurrent_submit_has_one_adapter_call_and_one_charge(self):
        self.ready()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.controller.submit(self.config_id, "research", {}), range(8)))
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)

    def test_fixed_phase_and_candidate_count_are_enforced(self):
        with self.assertRaises(WorkflowError):
            self.controller.register({"synthetic": True}, dict(self.identity, model_hash="0" * 64))
        self.controller.register({"synthetic": True, "candidate": 2}, self.identity)
        with self.assertRaises(WorkflowError):
            self.controller.register({"synthetic": True, "candidate": 3}, self.identity)
        usage = self.registry.snapshot()["usage"]["configurations"]["total"]
        same = self.controller.register({"scope": "engineering", "synthetic": True}, self.identity)
        self.assertEqual(same, self.config_id)
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], usage)

    def test_budget_exhaustion_stops_without_adapter_call(self):
        self.ready()
        # Exhaust the synthetic registry normally instead of modifying usage.
        other = self.registry.register_config({"synthetic": "budget-consumer"})
        for i in range(8):
            attempt = self.registry.begin_attempt(other, "research", operation_key="budget-" + str(i))
            self.registry.fail(attempt, "synthetic")
        with self.assertRaises(BudgetExceeded):
            self.controller.submit(self.config_id, "research", {})
        self.assertEqual(self.controller.status(self.config_id)["status"], "blocked")
        self.assertEqual(self.adapter.calls, [])


if __name__ == "__main__":
    unittest.main()
