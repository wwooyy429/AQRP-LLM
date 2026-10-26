"""Synthetic observed-coverage tests; no provider or external submission."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.audits import COVERAGE_ISSUER, verify_evidence
from qresearch.contracts import DataRequest, RECORD_COLUMNS
from qresearch.coverage import (CoverageIntegrityError, audit_registered_coverage,
                                produce_engineering_coverage)
from test_pipeline import complete_study, registered_package


def stamp(value):
    return pd.Timestamp(value, tz="America/New_York")


def raw_reference(store, data, suffix="input"):
    rows = [[row.sid, row.field, row.event_time.isoformat(), row.available_time.isoformat(),
             row.value, row.revision] for row in data.itertuples(index=False)]
    payload = json.dumps(rows, allow_nan=True, separators=(",", ":")).encode()
    key = "synthetic-input/" + suffix + "/" + sha256(payload).hexdigest() + ".json"
    store.write_once(key, payload)
    return {"key": key, "sha256": sha256(payload).hexdigest()}


def fixture():
    request = DataRequest("US Equities", ("close", "volume"), ("A", "B"),
        stamp("2018-01-01"), stamp("2019-01-01"), "fixture-2018-v1", "a" * 64)
    decisions = (stamp("2018-01-03 09:00"), stamp("2018-01-04 09:00"))
    events = {decisions[0]: stamp("2018-01-02 16:00"), decisions[1]: stamp("2018-01-03 16:00")}
    rows = [[sid, field, event, event, 431.25 + index, "original-v1"]
            for index, (sid, field, event) in enumerate(
                (sid, field, event) for sid in request.sids for field in request.fields for event in events.values())]
    return {"request": request, "records": pd.DataFrame(rows, columns=RECORD_COLUMNS),
        "decisions": decisions, "sids": request.sids,
        "policies": {name: "exact_session" for name in request.fields},
        "expected_events": events,
        "membership": pd.DataFrame(True, index=decisions, columns=request.sids),
        "provenance": {"data_version": request.data_version,
            "availability": "modeled LEAN end_time; not actual historical vendor receipt"},
        "subject_hash": "b" * 64, "source_hash": "c" * 64, "synthetic": True}


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()
        self.args = fixture()

    def run_report(self, *, data=None, **changes):
        args = dict(self.args)
        args.update(changes)
        if data is not None:
            args["records"] = data
        args["source_refs"] = [raw_reference(self.store, args["records"])]
        return produce_engineering_coverage(self.store, **args)

    def verify(self, result, scope="engineering", passed=True):
        return verify_evidence(self.store, result["audit_evidence"],
            subject_hash=self.args["subject_hash"], source_hash=self.args["source_hash"],
            issuer=COVERAGE_ISSUER, required_checks=("complete_formation_coverage", "execution_plan_bound"),
            scope=scope, require_passed=passed)

    def test_complete_fixture_counts_are_not_production_certification_or_value_export(self):
        result = self.run_report()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["observations"]["record_count"], 8)
        self.assertEqual(result["observations"]["expected_member_field_cells"], 8)
        self.assertEqual(result["observations"]["available_member_field_cells"], 8)
        self.assertFalse(result["research_certified"])
        self.assertFalse(result["financial_evidence"])
        self.assertNotIn("431.25", json.dumps(result))
        self.assertIn(b"431.25", self.store.read_bytes(result["raw_snapshot_ref"]["key"]))
        self.assertEqual(json.loads(self.store.read_bytes(result["provenance_ref"]["key"])),
                         self.args["provenance"])
        self.verify(result)
        with self.assertRaises(ValueError):
            self.verify(result, scope="research")

    def test_missing_active_cell_is_counted_and_rejected_without_backfill(self):
        result = self.run_report(data=self.args["records"].iloc[1:].copy())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["observations"]["missing_member_field_cells"], 1)
        self.assertFalse(result["checks"]["complete_formation_coverage"])
        with self.assertRaises(ValueError):
            self.verify(result)
        self.verify(result, passed=False)

    def test_historical_membership_masks_that_rows_own_cross_section(self):
        members = self.args["membership"].copy()
        members.iloc[0, 0] = False
        result = self.run_report(data=self.args["records"].iloc[1:].copy(), membership=members)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["observations"]["expected_member_field_cells"], 6)
        self.assertEqual(result["observations"]["available_member_field_cells"], 6)
        self.assertFalse(result["research_certified"])

    def test_duplicate_and_ambiguous_vintage_failures_are_observed(self):
        for same_revision in (True, False):
            data = self.args["records"].copy()
            extra = data.iloc[[0]].copy()
            if not same_revision:
                extra["revision"] = "other-vintage"
            data = pd.concat([data, extra], ignore_index=True)
            with self.subTest(same_revision=same_revision):
                result = self.run_report(data=data)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["observations"]["ambiguous_simultaneous_vintage_rows"], 1)
                self.assertEqual(result["observations"]["duplicate_vintage_rows"], int(same_revision))

    def test_nonfinite_and_boolean_records_cannot_pass_observed_coverage(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(kind=type(value).__name__, value=str(value)):
                data = self.args["records"].astype(object)
                data.at[0, "value"] = value
                result = self.run_report(data=data)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["observations"]["invalid_numeric_rows"], 1)
                self.assertFalse(result["checks"]["finite_real_observations"])
                json.dumps(result, allow_nan=False)

    def test_late_availability_leaves_a_missing_cell_and_later_revision_does_not_rewrite_earlier(self):
        data = self.args["records"].copy()
        data.at[0, "available_time"] = stamp("2018-01-03 10:00")
        result = self.run_report(data=data)
        self.assertEqual(result["observations"]["missing_member_field_cells"], 1)
        self.assertEqual(result["status"], "failed")
        extra = self.args["records"].iloc[[0]].copy()
        extra["available_time"] = stamp("2018-01-04 10:00")
        extra["revision"] = "later-known-revision"
        extra["value"] = 999999.0
        result = self.run_report(data=pd.concat([self.args["records"], extra], ignore_index=True))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["observations"]["available_member_field_cells"], 8)
        self.assertNotIn("999999.0", json.dumps(result))

    def test_source_hash_mismatch_and_metadata_instead_of_raw_rows_are_rejected(self):
        ref = raw_reference(self.store, self.args["records"])
        ref["sha256"] = "0" * 64
        with self.assertRaises(CoverageIntegrityError):
            produce_engineering_coverage(self.store, **self.args, source_refs=[ref])
        payload = canonical_json({"certified": True})
        self.store.write_once("synthetic-input/not-records.json", payload)
        ref = {"key": "synthetic-input/not-records.json", "sha256": sha256(payload).hexdigest()}
        with self.assertRaises(CoverageIntegrityError):
            produce_engineering_coverage(self.store, **self.args, source_refs=[ref])

    def test_different_source_rows_or_absent_refs_cannot_back_supplied_records(self):
        changed = self.args["records"].copy()
        changed.at[0, "value"] += 100
        ref = raw_reference(self.store, changed)
        result = produce_engineering_coverage(self.store, **self.args, source_refs=[ref])
        self.assertFalse(result["checks"]["source_payloads_match_records"])
        self.assertEqual(result["status"], "failed")
        result = produce_engineering_coverage(self.store, **self.args)
        self.assertEqual(result["status"], "failed")
        with self.assertRaises(CoverageIntegrityError):
            produce_engineering_coverage(self.store, **self.args, source_refs=[ref, ref])

    def test_future_naive_or_invalid_timestamp_inputs_are_rejected_before_snapshot_storage(self):
        for field, value in (("event_time", stamp("2024-01-01")),
                             ("available_time", stamp("2024-01-01")),
                             ("event_time", pd.Timestamp("2018-01-02 16:00")),
                             ("available_time", pd.NaT)):
            data = self.args["records"].astype(object)
            data.at[0, field] = value
            before = set(self.store._data)
            with self.subTest(field=field, value=str(value)), self.assertRaises(CoverageIntegrityError):
                produce_engineering_coverage(self.store, **(self.args | {"records": data}))
            self.assertEqual(set(self.store._data), before)
        changed = (stamp("2024-01-02 09:00"), stamp("2024-01-03 09:00"))
        with self.assertRaises(CoverageIntegrityError):
            produce_engineering_coverage(self.store, **(self.args | {"decisions": changed}))

    def test_forged_provenance_flags_cannot_escalate_engineering_scope(self):
        claimed = self.args["provenance"] | {"certified": True,
            "actual_availability_verified": True, "historical_universe_coverage": True}
        result = self.run_report(provenance=claimed)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["scope"], "engineering")
        self.assertFalse(result["research_certified"])
        self.assertEqual(len(result["research_certification_gaps"]), 4)
        with self.assertRaises(ValueError):
            self.verify(result, scope="research")

    def test_bound_report_prevents_changed_plan_or_flipped_failed_check(self):
        result = self.run_report(data=self.args["records"].iloc[1:].copy())
        evidence = deepcopy(result["audit_evidence"])
        for check in evidence["checks"]:
            check["passed"] = True
        result["audit_evidence"] = evidence
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify(result)
        first = self.run_report()
        members = self.args["membership"].copy()
        members.iloc[0, 0] = False
        second = self.run_report(membership=members)
        self.assertNotEqual(first["plan_hash"], second["plan_hash"])
        self.assertNotEqual(first["report_ref"], second["report_ref"])

    def test_real_store_boundary_and_explicit_synthetic_classification(self):
        with self.assertRaises(CoverageIntegrityError):
            produce_engineering_coverage(self.store, **(self.args | {"synthetic": False}))
        with self.assertRaises(CoverageIntegrityError):
            produce_engineering_coverage(self.store, **(self.args | {"synthetic": "false"}))
        self.store.residency = "quantconnect_cloud"  # Synthetic SDK-boundary stand-in only.
        result = self.run_report(synthetic=False)
        self.assertEqual(result["status"], "passed")

    def test_explicit_new_york_schedule_can_cross_dst_without_invented_sessions(self):
        decisions = (stamp("2018-03-12 09:00"), stamp("2018-03-13 09:00"))
        expected = {decisions[0]: stamp("2018-03-09 16:00"), decisions[1]: stamp("2018-03-12 16:00")}
        old_to_new = dict(zip(self.args["expected_events"].values(), expected.values()))
        data = self.args["records"].copy()
        data["event_time"] = data.event_time.map(old_to_new)
        data["available_time"] = data.event_time
        # UTC input timestamps must resolve to the same NY sessions.
        data["event_time"] = data.event_time.dt.tz_convert("UTC")
        data["available_time"] = data.available_time.dt.tz_convert("UTC")
        result = self.run_report(data=data, decisions=decisions, expected_events=expected,
            membership=pd.DataFrame(True, index=decisions, columns=self.args["sids"]))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["observations"]["missing_member_field_cells"], 0)

    def test_registered_production_report_remains_failed_and_verifier_compatible(self):
        self.store.residency = "quantconnect_cloud"  # No external provider was contacted.
        study = complete_study(purpose="research")
        package = registered_package(study, self.store)
        document = study.to_dict()
        binding = document["data_binding"]
        request = replace(self.args["request"], fields=("close",),
            data_version=binding["data_version"], universe_hash=binding["universe_hash"])
        data = self.args["records"][self.args["records"].field == "close"].copy()
        args = {key: value for key, value in self.args.items()
                if key not in {"synthetic", "subject_hash", "source_hash", "request", "records", "provenance", "policies"}}
        args.update(request=request, records=data, policies={"close": "exact_session"},
            provenance={"data_version": binding["data_version"], "certified": True},
            source_hash=binding["code_hash"], source_refs=[raw_reference(self.store, data)],
            study=study, registered_configuration=package, field_catalog=["close"],
            operator_catalog=["positive_session_lag", "multiply"])
        result = audit_registered_coverage(self.store, **args)
        self.assertEqual(result["status"], "not_certified")
        self.assertFalse(result["research_certified"])
        required = ("historical_universe_coverage", "actual_availability_verified",
                    "source_revision_pinned", "development_only", "execution_plan_bound")
        evidence = verify_evidence(self.store, result["audit_evidence"], subject_hash=content_hash(package),
            source_hash=binding["code_hash"], issuer=COVERAGE_ISSUER, required_checks=required,
            scope="research", require_passed=False)
        self.assertFalse(evidence.passed)
        with self.assertRaises(ValueError):
            verify_evidence(self.store, result["audit_evidence"], subject_hash=content_hash(package),
                source_hash=binding["code_hash"], issuer=COVERAGE_ISSUER, required_checks=required, scope="research")
        changed = dict(args, source_hash="e" * 64)
        with self.assertRaises(CoverageIntegrityError):
            audit_registered_coverage(self.store, **changed)
        unregistered = deepcopy(package)
        unregistered["campaign_hash"] = "f" * 64
        with self.assertRaises(ValueError):
            audit_registered_coverage(self.store, **(args | {"registered_configuration": unregistered}))


if __name__ == "__main__":
    unittest.main()
