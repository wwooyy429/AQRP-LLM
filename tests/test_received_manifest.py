"""Known-answer received/cache equality tests using synthetic OHLCV only."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import canonical_json
from qresearch.cache import _encode
from qresearch.contracts import DataRequest, NY, RECORD_COLUMNS, validate_records
from qresearch.received_manifest import build_received_manifest


def fixture():
    request = DataRequest("US Equities", ("open", "high", "low", "close", "volume"),
        ("SYNTHETIC-A", "SYNTHETIC-B"), datetime(2018, 1, 1, tzinfo=NY),
        datetime(2019, 1, 1, tzinfo=NY), "synthetic-raw-v1", "synthetic-universe")
    rows = []
    for sid in request.sids:
        for day in (2, 3):
            stamp = pd.Timestamp(datetime(2018, 1, day, 16, tzinfo=NY))
            for i, field in enumerate(request.fields):
                rows.append([sid, field, stamp, stamp, float(day * 10 + i), request.data_version])
    cached = validate_records(pd.DataFrame(rows, columns=RECORD_COLUMNS), request)
    window = {"start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2018-01-04T00:00:00-05:00"}
    actual = [[r.sid, r.field, r.event_time.isoformat(), r.available_time.isoformat(), float(r.value), r.revision]
              for r in cached.itertuples(index=False) if r.event_time.day == 3]
    return actual, cached, request, window, references(cached, request)


def references(cached, request):
    normalized = validate_records(cached, request)
    result = []
    for field in request.fields:
        digest = sha256(_encode(normalized[normalized.field == field])).hexdigest()
        result.append({"key": "feature-cache/v1/objects/" + digest + ".json", "sha256": digest})
    return result


class ReceivedManifestTests(unittest.TestCase):
    def test_known_answer_matches_subset_and_stores_no_rows_or_values(self):
        actual, cached, request, window, refs = fixture()
        expected = sorted(actual, key=lambda r: (r[0], r[1], r[2], r[3], r[5]))
        expected_hash = sha256(canonical_json(expected)).hexdigest()
        manifest, metadata = build_received_manifest(actual, cached, request, window, refs)
        self.assertEqual(metadata, {"schema_version": 1, "encoding": "cached_row_reference_v1", "record_count": 10,
            "rowset_sha256": expected_hash, "manifest_sha256": sha256(canonical_json(manifest)).hexdigest(),
            "cache_reference_count": 5, "new_row_objects": False})
        self.assertEqual(manifest["actual_rowset_sha256"], manifest["cached_rowset_sha256"])
        self.assertEqual(manifest["actual_rowset_sha256"], expected_hash)
        self.assertEqual(manifest["request"], request.identity())
        self.assertEqual(manifest["request_hash"], request.key)
        self.assertEqual(manifest["columns"], list(RECORD_COLUMNS))
        self.assertEqual(manifest["observation_window"], window)
        self.assertFalse(manifest["row_values_stored"])
        self.assertEqual(set(manifest), {"schema_version", "encoding", "request", "request_hash", "columns",
            "observation_window", "record_count", "actual_rowset_sha256", "cached_rowset_sha256", "source_refs", "row_values_stored"})
        self.assertNotIn("rows", manifest)
        self.assertNotIn("value", manifest)

    def test_sorting_input_orders_does_not_change_identity_or_mutate_inputs(self):
        actual, cached, request, window, refs = fixture()
        old_actual, old_cached, old_refs = deepcopy(actual), cached.copy(deep=True), deepcopy(refs)
        a = build_received_manifest(actual, cached, request, window, refs)
        b = build_received_manifest(list(reversed(actual)), cached.iloc[::-1], request, window, list(reversed(refs)))
        self.assertEqual(a, b)
        self.assertEqual(actual, old_actual); self.assertEqual(refs, old_refs)
        pd.testing.assert_frame_equal(cached, old_cached)

    def test_native_integral_values_match_the_same_exact_cached_numeric_values(self):
        actual, cached, request, window, refs = fixture()
        actual[0][4] = int(actual[0][4])
        self.assertEqual(build_received_manifest(actual, cached, request, window, refs)[1]["record_count"], 10)

    def test_value_difference_in_any_price_or_volume_fails(self):
        for field in ("open", "high", "low", "close", "volume"):
            actual, cached, request, window, refs = fixture()
            next(r for r in actual if r[1] == field)[4] += 0.01
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "frozen verified cache"):
                build_received_manifest(actual, cached, request, window, refs)

    def test_missing_extra_and_duplicate_actual_rows_fail(self):
        for mode in ("missing", "extra", "duplicate", "empty"):
            actual, cached, request, window, refs = fixture()
            if mode == "missing": actual.pop()
            elif mode == "duplicate": actual.append(deepcopy(actual[0]))
            elif mode == "extra":
                row = deepcopy(actual[0]); row[2] = row[3] = "2018-01-03T16:01:00-05:00"; actual.append(row)
            else: actual.clear()
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                build_received_manifest(actual, cached, request, window, refs)

    def test_availability_and_revision_must_match_exactly(self):
        for column, value in ((3, "2018-01-03T16:00:01-05:00"), (5, "synthetic-other-vintage")):
            actual, cached, request, window, refs = fixture(); actual[0][column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                build_received_manifest(actual, cached, request, window, refs)

    def test_naive_missing_future_outside_and_impossible_clocks_fail(self):
        for column, value in ((2, "2018-01-03T16:00:00"), (3, "NaT"),
                              (2, "2024-01-01T16:00:00-05:00"), (2, "2018-01-02T16:00:00-05:00"),
                              (3, "2018-01-03T15:59:59-05:00"), (2, None)):
            actual, cached, request, window, refs = fixture(); actual[0][column] = value
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                build_received_manifest(actual, cached, request, window, refs)

    def test_equivalent_aware_timezones_are_canonicalized_to_NY(self):
        actual, cached, request, window, refs = fixture()
        expected = build_received_manifest(actual, cached, request, window, refs)
        for row in actual:
            row[2] = pd.Timestamp(row[2]).tz_convert("UTC").isoformat()
            row[3] = pd.Timestamp(row[3]).tz_convert("UTC").isoformat()
        self.assertEqual(build_received_manifest(actual, cached, request, window, refs), expected)

    def test_nonnative_nonfinite_and_inexact_integer_values_never_get_coerced(self):
        for value in (True, "123.45 LICENSED", None, float("nan"), float("inf"), 2**53 + 1):
            actual, cached, request, window, refs = fixture(); actual[0][4] = value
            with self.subTest(value=type(value)), self.assertRaises(ValueError) as caught:
                build_received_manifest(actual, cached, request, window, refs)
            self.assertNotIn("LICENSED", str(caught.exception))

    def test_cached_bad_data_is_rejected_even_outside_observation_interval(self):
        for mode in ("duplicate", "bad_value", "naive_time", "extra_column", "wrong_revision"):
            actual, cached, request, window, refs = fixture()
            if mode == "duplicate": cached = pd.concat([cached, cached.iloc[:1]], ignore_index=True)
            elif mode == "bad_value": cached.loc[0, "value"] = float("inf")
            elif mode == "naive_time":
                cached["event_time"] = cached["event_time"].astype(object)
                cached.loc[0, "event_time"] = pd.Timestamp("2018-01-02T16:00:00")
            elif mode == "extra_column": cached["future_return"] = 1
            else: cached.loc[0, "revision"] = "synthetic-other-vintage"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                build_received_manifest(actual, cached, request, window, refs)

    def test_different_cached_values_cannot_be_hidden_behind_new_matching_cache_refs(self):
        actual, cached, request, window, _ = fixture()
        cached.loc[cached.event_time.dt.day == 3, "value"] += 1
        with self.assertRaises(ValueError):
            build_received_manifest(actual, cached, request, window, references(cached, request))

    def test_five_unique_canonical_references_are_required(self):
        for mode in ("missing", "extra", "duplicate", "unknown", "bad_hash", "path_hash_mismatch", "traversal"):
            actual, cached, request, window, refs = fixture()
            if mode == "missing": refs.pop()
            elif mode == "extra": refs.append({"key": "feature-cache/v1/objects/" + "a" * 64 + ".json", "sha256": "a" * 64})
            elif mode == "duplicate": refs[-1] = deepcopy(refs[0])
            elif mode == "unknown": refs[0]["rows"] = ["LICENSED"]
            elif mode == "bad_hash": refs[0]["sha256"] = "A" * 64
            elif mode == "path_hash_mismatch": refs[0]["sha256"] = "0" * 64
            else: refs[0]["key"] = "../private.json"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                build_received_manifest(actual, cached, request, window, refs)

    def test_well_formed_but_unrelated_payload_reference_is_rejected(self):
        actual, cached, request, window, refs = fixture()
        refs[0] = {"key": "feature-cache/v1/objects/" + "0" * 64 + ".json", "sha256": "0" * 64}
        with self.assertRaises(ValueError): build_received_manifest(actual, cached, request, window, refs)

    def test_window_and_request_cannot_expand_to_final_data_or_partial_year_refs(self):
        for new_window in ({"start": "2017-12-31T00:00:00-05:00", "end_exclusive": "2018-01-04T00:00:00-05:00"},
                           {"start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2024-01-02T00:00:00-05:00"},
                           {"start": "2018-01-03", "end_exclusive": "2018-01-04"},
                           {"start": "2018-01-04T00:00:00-05:00", "end_exclusive": "2018-01-03T00:00:00-05:00"}):
            actual, cached, request, _, refs = fixture()
            with self.subTest(window=new_window), self.assertRaises(ValueError):
                build_received_manifest(actual, cached, request, new_window, refs)
        actual, cached, request, window, refs = fixture()
        partial = DataRequest(request.dataset, request.fields, request.sids,
            datetime(2018, 1, 2, tzinfo=NY), request.end, request.data_version, request.universe_hash)
        with self.assertRaises(ValueError): build_received_manifest(actual, cached, partial, window, refs)


if __name__ == "__main__":
    unittest.main()
