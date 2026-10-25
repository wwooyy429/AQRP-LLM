"""Independent synthetic checks for complete-study identity and audit provenance."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.factors import FactorValidationError
from qresearch.labels import LabelProtocol, LabelValidationError
from qresearch.models import ModelSpec, ModelValidationError
from qresearch.study import AuditEvidence, StudySpec, StudyValidationError, validate_trading_spec


def fixture_study(purpose="engineering_fixture"):
    """No proposed market factor: this document is a synthetic contract fixture."""
    model = {"schema_version": 1, "model_id": "fixture-identity", "model_family": "identity",
             "features": ["candidate_score"], "target_kind": "net_return",
             "preprocessing": {"standardize": False, "constant_feature_policy": "unit_scale"},
             "hyperparameters": {"coefficient": 1.0}, "trainable_parameters": [], "purpose": purpose}
    label = {"schema_version": 1, "protocol_id": "fixture-label", "target_kind": "net_return",
             "price_basis": "actual_fill", "currency": "USD", "normalization": "raw",
             "corporate_action_policy": "reject_non_cash_actions", "denominator": "entry_notional",
             "zero_cost_reason": "Synthetic execution fixture only", "purpose": purpose}
    factor = {"schema_version": 1, "factor_id": "fixture_factor",
              "economic_hypothesis": {"mechanism": "合成工程检查，不作经济结论", "expected_direction": 1,
                                       "prediction_horizon_sessions": 1,
                                       "applicable_regimes": ["synthetic"], "failure_conditions": ["invalid fixture"]},
              "formula": {"op": "positive_session_lag", "arg": {"op": "field", "name": "close"}, "periods": 1},
              "allowed_fields": ["close"], "allowed_operators": ["positive_session_lag"], "parameters": {}}
    model_hash = ModelSpec.from_dict(model).configuration_hash
    document = {"schema_version": 1, "study_id": "engineering-contract-fixture", "purpose": purpose,
                "synthetic": purpose == "engineering_fixture", "timezone": "America/New_York", "research_phase": "factor",
                "factor_specs": [factor], "model_spec": model, "label_spec": label,
                "data_binding": {"data_version": "synthetic-v1", "universe_hash": content_hash(["A", "B"]),
                                 "code_hash": content_hash({"code": "synthetic fixture"})},
                "feature_bindings": {"candidate_score": "fixture_factor"}, "fixed_model_hash": model_hash,
                "development": {"start": "2018-03-01", "end_exclusive": "2019-01-01"},
                "final_evaluation": {"execution_enabled": False}}
    if purpose == "research":
        acceptance = {"logic": "all", "metrics": [{"name": "fixture_metric", "operator": "gte", "value": 0,
                                                    "min_observations": 3, "scope": "validation"}]}
        document["preregistered_acceptance"] = acceptance
        document["rolling_validation"] = {"first_training_year": 2010, "training_years": 8,
                                           "validation_years": 1, "step_years": 1, "rounds": 6}
        factor["availability_contract"] = {"rule": "Use actual historical available_time"}
        factor["label_entry_exit_contract"] = {"label_protocol_hash": LabelProtocol.from_dict(label).configuration_hash}
        factor["baseline_and_incrementality_test"] = {"protocol": "synthetic metadata fixture, no execution"}
        factor["fixed_model_binding"] = {"model_hash": model_hash}
        factor["preregistered_acceptance"] = {"acceptance_hash": content_hash(acceptance)}
    return document


def fixture_trading():
    costs = {name: {"model": "constant", "parameters": {"value": 0}, "unit": "USD",
                    "zero_cost_reason": "Synthetic fixture only"}
             for name in ("commission", "spread", "slippage", "impact", "borrow")}
    return {"schema_version": 1, "capital": 1000, "account_type": "synthetic_cash",
            "position_construction": {"rule": "synthetic equal weights"}, "rebalance_rule": "synthetic trigger",
            "entry_rule": "supplied synthetic entry", "exit_rule": "supplied synthetic exit",
            "costs": costs, "fills": {"order_type": "synthetic", "participation_cap": 0.1,
            "stale_data_policy": "reject", "partial_fill_policy": "reject",
            "corporate_action_and_delisting_rules": "reject unresolved events"},
            "risk": {"gross_exposure": 1.0, "net_exposure": 1.0, "single_security": 0.5,
                     "issuer": 0.5, "sector": 1.0, "beta": {"min": -1, "max": 1}, "drawdown": 0.1},
            "stress_tests": [{"scenario_id": "synthetic timing check"}], "orders_enabled": False}


def fixture_audit(passed=True):
    payload = {"check": "synthetic-only", "outcome": passed}
    evidence_hash = content_hash(payload)
    document = {"schema_version": 1, "audit_id": "fixture-audit", "issuer": "fixed-formula-auditor-v1",
                "issuer_kind": "fixed_program", "created_at": "2026-10-26T00:00:00Z",
                "subject_hash": content_hash({"study": "fixture"}), "source_hash": content_hash({"program": "fixture"}),
                "checks": [{"name": "synthetic consistency", "passed": passed, "evidence_hash": evidence_hash}],
                "evidence_refs": [{"key": "evidence/fixture.json", "sha256": evidence_hash}], "scope": "engineering"}
    return document, payload


def parse_audit(document):
    return AuditEvidence.from_dict(document, expected_subject_hash=content_hash({"study": "fixture"}),
                                   expected_source_hash=content_hash({"program": "fixture"}),
                                   allowed_issuers={"fixed-formula-auditor-v1"})


class StudyTests(unittest.TestCase):
    def test_canonical_roundtrip_matches_registry_hash_even_with_chinese(self):
        spec = StudySpec.from_dict(fixture_study(), field_catalog=["close"])
        self.assertEqual(spec.configuration_hash, content_hash(spec.to_dict()))
        self.assertEqual(spec.configuration_hash, sha256(spec.canonical_json.encode("utf-8")).hexdigest())
        self.assertEqual(spec.configuration_hash, StudySpec.from_dict(spec.to_dict(), field_catalog=["close"]).configuration_hash)
        self.assertEqual(spec.hash, spec.study_hash)
        self.assertEqual(spec.to_dict()["development"]["start"], "2018-03-01T00:00:00-05:00")

    def test_semantic_model_label_or_factor_change_requires_new_identity(self):
        original = fixture_study()
        first = StudySpec.from_dict(original, field_catalog=["close"])
        changed = deepcopy(original)
        changed["factor_specs"][0]["economic_hypothesis"]["expected_direction"] = -1
        self.assertNotEqual(first.hash, StudySpec.from_dict(changed, field_catalog=["close"]).hash)
        changed = deepcopy(original)
        changed["model_spec"]["hyperparameters"]["coefficient"] = -1
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(changed, field_catalog=["close"])
        changed["fixed_model_hash"] = ModelSpec.from_dict(changed["model_spec"]).configuration_hash
        self.assertNotEqual(first.hash, StudySpec.from_dict(changed, field_catalog=["close"]).hash)

    def test_unknown_fields_and_empty_or_unapproved_catalog_rejected(self):
        for change in ({"unknown": 1}, {"timezone": "UTC"}, {"schema_version": True}):
            document = fixture_study() | change
            with self.subTest(change=change), self.assertRaises(StudyValidationError):
                StudySpec.from_dict(document, field_catalog=["close"])
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(fixture_study(), field_catalog=[])
        with self.assertRaises(FactorValidationError):
            StudySpec.from_dict(fixture_study(), field_catalog=["volume"])
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(fixture_study(), field_catalog=["close"], operator_catalog=["add"])

    def test_final_access_and_exposure_relabeling_rejected(self):
        variants = [{"execution_enabled": True}, {"execution_enabled": False, "feedback_to_research_for_changes": True},
                    {"execution_enabled": False, "whole_window_is_untouched_independent_holdout": True}]
        for final in variants:
            document = fixture_study() | {"final_evaluation": final}
            with self.subTest(final=final), self.assertRaises(StudyValidationError):
                StudySpec.from_dict(document, field_catalog=["close"])
        document = fixture_study()
        document["development"]["end_exclusive"] = "2024-01-02"
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(document, field_catalog=["close"])

    def test_label_metadata_and_unbound_features_rejected(self):
        for feature in ("future_return", "formation_at", "sid", "label", "entry_price"):
            document = fixture_study()
            document["model_spec"]["features"] = [feature]
            document["fixed_model_hash"] = content_hash({"changed": feature})
            with self.subTest(feature=feature), self.assertRaises((StudyValidationError, ModelValidationError)):
                StudySpec.from_dict(document, field_catalog=["close"])
        document = fixture_study()
        document["feature_bindings"]["candidate_score"] = "absent_factor"
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(document, field_catalog=["close"])

    def test_engineering_cannot_masquerade_as_research(self):
        document = fixture_study()
        document["synthetic"] = False
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(document, field_catalog=["close"])
        document = fixture_study()
        document["model_spec"]["purpose"] = "research"
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(document, field_catalog=["close"])

    def test_research_bindings_acceptance_and_rolling_are_explicit(self):
        document = fixture_study("research")
        valid = StudySpec.from_dict(document, field_catalog=["close"])
        self.assertEqual(valid.to_dict()["purpose"], "research")
        for field in ("preregistered_acceptance", "rolling_validation"):
            broken = deepcopy(document)
            del broken[field]
            with self.subTest(field=field), self.assertRaises(StudyValidationError):
                StudySpec.from_dict(broken, field_catalog=["close"])
        broken = deepcopy(document)
        broken["preregistered_acceptance"]["metrics"][0]["scope"] = "final_test"
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(broken, field_catalog=["close"])

    def test_templates_and_missing_trading_are_not_executable(self):
        document = fixture_study()
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(document, field_catalog=["close"], require_trading=True)
        document["model_spec"] = json.loads((Path(__file__).resolve().parents[1] / "templates/model_spec.json").read_text(encoding="utf-8"))
        with self.assertRaises(ModelValidationError):
            StudySpec.from_dict(document, field_catalog=["close"])
        document = fixture_study()
        document["trading_spec"] = fixture_trading()
        self.assertIsNotNone(StudySpec.from_dict(document, field_catalog=["close"], require_trading=True).to_dict()["component_hashes"]["trading"])

    def test_costs_fills_and_risk_have_no_implicit_defaults(self):
        for mutation in (lambda x: x["costs"].pop("impact"),
                         lambda x: x["costs"]["commission"].pop("zero_cost_reason"),
                         lambda x: x["fills"].update(participation_cap=0),
                         lambda x: x["risk"].update(drawdown=None),
                         lambda x: x.update(stress_tests=[])):
            document = fixture_trading()
            mutation(document)
            with self.assertRaises(StudyValidationError):
                validate_trading_spec(document, purpose="engineering_fixture")


class EvidenceTests(unittest.TestCase):
    def test_named_evidence_resolves_and_failed_checks_are_retained(self):
        for passed in (True, False):
            document, payload = fixture_audit(passed)
            evidence = parse_audit(document)
            self.assertEqual(evidence.passed, passed)
            self.assertEqual(evidence.hash, content_hash(evidence.to_dict()))
            self.assertEqual(evidence.hash, sha256(evidence.canonical_json.encode("utf-8")).hexdigest())
            store = MemoryArtifactStore()
            store.write_once("evidence/fixture.json", canonical_json(payload))
            self.assertIs(evidence.verify_references(store), evidence)
            if passed:
                self.assertIs(evidence.require_passed(), evidence)
            else:
                with self.assertRaises(StudyValidationError):
                    evidence.require_passed()

    def test_boolean_approval_and_llm_self_attestation_rejected(self):
        for raw in (True, {"passed": True}):
            with self.assertRaises(StudyValidationError):
                parse_audit(raw)
        document, _ = fixture_audit()
        for change in ({"issuer_kind": "llm"}, {"issuer": "untrusted-program"}, {"source_hash": "0" * 64},
                       {"subject_hash": "0" * 64}, {"schema_version": True}):
            with self.subTest(change=change), self.assertRaises(StudyValidationError):
                parse_audit(document | change)
        with self.assertRaises(StudyValidationError):
            AuditEvidence.from_dict(document)

    def test_unreferenced_and_corrupt_evidence_is_rejected(self):
        document, _ = fixture_audit()
        broken = deepcopy(document)
        broken["checks"][0]["evidence_hash"] = "0" * 64
        with self.assertRaises(StudyValidationError):
            parse_audit(broken)
        broken = deepcopy(document)
        broken["evidence_refs"][0]["key"] = "../escape.json"
        with self.assertRaises(ValueError):
            parse_audit(broken)
        evidence = parse_audit(document)
        store = MemoryArtifactStore()
        store.write_once("evidence/fixture.json", b"corrupted synthetic evidence")
        with self.assertRaises(StudyValidationError):
            evidence.verify_references(store)


if __name__ == "__main__":
    unittest.main()
