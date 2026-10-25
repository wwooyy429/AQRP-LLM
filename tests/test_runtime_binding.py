"""Adversarial authorization tests, using only synthetic in-memory fixtures.

The cloud residency flag and fixed-program reports are SDK-boundary fixtures.
They are not market coverage certificates or independent profitability tests.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.audits import COVERAGE_ISSUER, FORMULA_ISSUER, make_evidence
from qresearch.cache import SharedDataCache
from qresearch.contracts import DataRequest
from qresearch.factors import FactorSpec
from qresearch.runtime import ResearchEngine
from test_data_pipeline import FixtureProvider, ts
from test_pipeline import complete_study, registered_package


FORMULA_CHECKS = ("validated_study_contract", "source_hash_matches_binding",
                  "restricted_factor_compilation", "development_only")
COVERAGE_CHECKS = ("historical_universe_coverage", "actual_availability_verified",
                   "source_revision_pinned", "development_only", "execution_plan_bound")


class RecordingCache(SharedDataCache):
    reads = 0

    def read(self, request, allow_fetch=False):
        self.reads += 1
        return super().read(request, allow_fetch=allow_fetch)


def declared_plan(request, decisions, sids, policies, events, membership):
    """Independent literal construction of the fixed, reviewed plan schema."""
    columns = sorted(sids)
    member = {"index": [value.isoformat() for value in decisions], "columns": columns,
              "data": membership.reindex(columns=columns).to_numpy(dtype=bool).tolist()}
    return {"schema_version": 1, "request": request.identity(),
            "decisions": [value.isoformat() for value in decisions], "sids": columns,
            "policies": dict(policies), "max_age": {},
            "expected_events": [[value.isoformat(), events[value].isoformat()] for value in decisions],
            "membership_hash": content_hash(member)}


def observed_report(store, *, subject, source, issuer, names, plan=None, passed=True):
    """Synthetic fixed-producer fixture with observations in immutable bytes."""
    checks = {name: passed for name in names}
    report = {"subject_hash": subject, "source_hash": source, "issuer": issuer,
              "scope": "research", "checks": checks}
    if plan is not None:
        report.update(execution_plan=deepcopy(plan), plan_hash=content_hash(plan))
    report_hash = content_hash(report)
    key = "test-evidence/" + report_hash + ".json"
    store.write_once(key, canonical_json(report))
    return {"schema_version": 1, "audit_id": report_hash, "issuer": issuer,
            "issuer_kind": "fixed_program", "created_at": "2026-10-26T00:00:00Z",
            "subject_hash": subject, "source_hash": source, "scope": "research",
            "checks": [{"name": name, "passed": value, "evidence_hash": report_hash}
                       for name, value in sorted(checks.items())],
            "evidence_refs": [{"key": key, "sha256": report_hash}]}


class RuntimeBindingTests(unittest.TestCase):
    def setUp(self):
        self.store, self.provider = MemoryArtifactStore(), FixtureProvider()
        self.store.residency = "quantconnect_cloud"
        self.cache = RecordingCache(self.store, self.provider)
        self.study = complete_study(purpose="research")
        self.document = self.study.to_dict()
        self.package = registered_package(self.study, self.store)
        self.subject = content_hash(self.package)
        binding = self.document["data_binding"]
        self.request = DataRequest("US Equities", ("close",), ("A", "B"), ts(1, 0), ts(10, 0),
                                   binding["data_version"], binding["universe_hash"])
        self.cache.prefetch(self.request)
        self.decisions = (ts(3, 9), ts(4, 9))
        self.sids, self.policies = ("A", "B"), {"close": "exact_session"}
        self.events = {ts(3, 9): ts(2), ts(4, 9): ts(3)}
        self.membership = pd.DataFrame(True, index=self.decisions, columns=self.sids)
        self.plan = declared_plan(self.request, self.decisions, self.sids, self.policies,
                                  self.events, self.membership)
        source = binding["code_hash"]
        self.approval = {"execution_plan": self.plan, "plan_hash": content_hash(self.plan),
                         "audit_evidence": {
                             "formula_timing": observed_report(self.store, subject=self.subject, source=source,
                                 issuer=FORMULA_ISSUER, names=FORMULA_CHECKS),
                             "data_coverage": observed_report(self.store, subject=self.subject, source=source,
                                 issuer=COVERAGE_ISSUER, names=COVERAGE_CHECKS, plan=self.plan)}}

    def engine(self, **changes):
        parameters = {"code_version": self.document["data_binding"]["code_hash"],
                      "research_approval": self.approval, "study": self.study,
                      "registered_configuration": self.package, "field_catalog": ["close"],
                      "operator_catalog": ["positive_session_lag", "multiply"]}
        parameters.update(changes)
        return ResearchEngine(self.cache, **parameters)

    def compute(self, engine=None, **changes):
        parameters = {"specs": self.study.factor_specs, "request": self.request,
                      "decisions": self.decisions, "sids": self.sids, "policies": self.policies,
                      "expected_events": self.events, "membership": self.membership}
        parameters.update(changes)
        return (engine or self.engine()).evaluate(**parameters)

    def test_registered_exact_plan_has_positive_control_and_stable_cache_reuse(self):
        first = self.compute()
        self.assertEqual(first["values"]["columns"], ["fixture_factor"])
        self.assertEqual(first["values"]["data"], [[10.0], [10.0]])
        self.assertEqual(first["identity"]["registered_authorization"]["registered_configuration_hash"], self.subject)
        self.assertEqual(self.cache.reads, 1)
        repeated = deepcopy(self.approval)
        # A new envelope time does not change its actual observations or the
        # authorized computation. Reuse depends on immutable report identities.
        repeated["audit_evidence"]["formula_timing"]["created_at"] = "2026-10-26T00:01:00Z"
        second = self.compute(self.engine(research_approval=repeated))
        self.assertEqual(first, second)
        self.assertEqual(self.cache.reads, 1)
        self.assertEqual(self.provider.calls, 1)

    def test_A_audits_cannot_authorize_B_factor_even_with_relabelled_approval(self):
        raw_b = self.study.factor_specs[0].to_dict()
        raw_b["factor_id"] = "candidate_b"
        raw_b["formula"] = {"op": "multiply", "args": [2, {"op": "field", "name": "close"}]}
        raw_b["allowed_operators"] = ["multiply"]
        factor_b = FactorSpec.from_dict(raw_b, field_catalog=["close"])
        approval_b = deepcopy(self.approval)
        approval_b.update(formula_timing_audit_passed=True, coverage_audit_passed=True,
                          study_hash=self.study.configuration_hash, factor_hashes=[factor_b.configuration_hash],
                          data_version=self.request.data_version, universe_hash=self.request.universe_hash)
        with self.assertRaisesRegex(ValueError, "Actual factors differ"):
            self.compute(self.engine(research_approval=approval_b), specs=[factor_b])
        self.assertEqual(self.cache.reads, 0)

    def test_A_audits_cannot_authorize_B_data_version_or_universe(self):
        for request_b in (replace(self.request, data_version="synthetic-data-B"),
                          replace(self.request, universe_hash=content_hash({"universe": "B"}))):
            approval_b = deepcopy(self.approval)
            approval_b.update(data_version=request_b.data_version, universe_hash=request_b.universe_hash)
            with self.subTest(request=request_b), self.assertRaisesRegex(ValueError, "Actual data request differs"):
                self.compute(self.engine(research_approval=approval_b), request=request_b)
        self.assertEqual(self.cache.reads, 0)

    def test_missing_study_registration_or_trusted_catalogs_fail_before_read(self):
        for parameters in ({"study": None}, {"registered_configuration": None}, {"field_catalog": None},
                           {"operator_catalog": None}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                self.compute(self.engine(**parameters))
        altered = deepcopy(self.package)
        altered["identity"]["model_hash"] = "0" * 64
        with self.assertRaises(ValueError):
            self.compute(self.engine(registered_configuration=altered))
        self.assertEqual(self.cache.reads, 0)

    def test_unregistered_package_cannot_be_authorized_by_valid_looking_evidence(self):
        unregistered = deepcopy(self.package)
        unregistered["campaign_hash"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "already exist"):
            self.compute(self.engine(registered_configuration=unregistered))
        self.assertEqual(self.cache.reads, 0)

    def test_boolean_approval_and_free_plan_dictionary_are_not_authority(self):
        only_bits = {"formula_timing_audit_passed": True, "coverage_audit_passed": True}
        with self.assertRaises(ValueError):
            self.compute(self.engine(research_approval=only_bits))
        only_bits.update(execution_plan=self.plan, plan_hash=content_hash(self.plan))
        with self.assertRaisesRegex(ValueError, "Both fixed-program audits"):
            self.compute(self.engine(research_approval=only_bits))
        self.assertEqual(self.cache.reads, 0)

    def test_coverage_without_certified_plan_is_not_a_market_pass(self):
        ordinary = deepcopy(self.approval)
        ordinary["audit_evidence"]["data_coverage"] = make_evidence(self.store, subject_hash=self.subject,
            source_hash=self.document["data_binding"]["code_hash"], issuer=COVERAGE_ISSUER,
            checks={name: True for name in COVERAGE_CHECKS}, scope="research").to_dict()
        with self.assertRaisesRegex(ValueError, "does not certify"):
            self.compute(self.engine(research_approval=ordinary))
        self.assertEqual(self.cache.reads, 0)

    def test_actual_interval_and_membership_require_the_same_observed_plan(self):
        request_b = replace(self.request, end=ts(9, 0))
        plan_b = declared_plan(request_b, self.decisions, self.sids, self.policies, self.events, self.membership)
        approval_b = deepcopy(self.approval)
        approval_b.update(execution_plan=plan_b, plan_hash=content_hash(plan_b))
        with self.assertRaisesRegex(ValueError, "does not certify"):
            self.compute(self.engine(research_approval=approval_b), request=request_b)
        members_b = self.membership.copy()
        members_b.iloc[-1, -1] = False
        plan_b = declared_plan(self.request, self.decisions, self.sids, self.policies, self.events, members_b)
        approval_b = deepcopy(self.approval)
        approval_b.update(execution_plan=plan_b, plan_hash=content_hash(plan_b))
        with self.assertRaisesRegex(ValueError, "does not certify"):
            self.compute(self.engine(research_approval=approval_b), membership=members_b)
        self.assertEqual(self.cache.reads, 0)

    def test_invented_subject_or_failed_report_cannot_be_relabelled(self):
        for purpose in ("formula_timing", "data_coverage"):
            forged = deepcopy(self.approval)
            forged["audit_evidence"][purpose]["subject_hash"] = self.study.configuration_hash
            with self.subTest(purpose=purpose), self.assertRaises(ValueError):
                self.compute(self.engine(research_approval=forged))
        forged = deepcopy(self.approval)
        failed = observed_report(self.store, subject=self.subject,
            source=self.document["data_binding"]["code_hash"], issuer=COVERAGE_ISSUER,
            names=COVERAGE_CHECKS, plan=self.plan, passed=False)
        for check in failed["checks"]:
            check["passed"] = True
        forged["audit_evidence"]["data_coverage"] = failed
        with self.assertRaisesRegex(ValueError, "differs from its observed report"):
            self.compute(self.engine(research_approval=forged))
        self.assertEqual(self.cache.reads, 0)

    def test_code_model_label_fields_and_normalization_cannot_drift(self):
        with self.assertRaisesRegex(ValueError, "Implementation differs"):
            self.compute(self.engine(code_version="0" * 64))
        for field in ("fixed_model_hash", "label_contract_hash", "preregistered_comparison_hash"):
            approval = deepcopy(self.approval)
            approval[field] = "0" * 64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "annotation conflicts"):
                self.compute(self.engine(research_approval=approval))
        for request in (replace(self.request, fields=("close", "volume")),
                        replace(self.request, normalization="adjusted")):
            with self.assertRaisesRegex(ValueError, "Actual data request differs"):
                self.compute(request=request)
        with self.assertRaisesRegex(ValueError, "development interval"):
            self.compute(decisions=[pd.Timestamp("2024-01-01 09:00", tz="America/New_York")])
        self.assertEqual(self.cache.reads, 0)


if __name__ == "__main__":
    unittest.main()
