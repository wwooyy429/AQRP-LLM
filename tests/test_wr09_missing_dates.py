"""WR-09 native-shaped date regressions; no SDK or real-data execution."""
from datetime import date, datetime
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.collection import CollectionIntegrityError, HistoricalCollectionPlan, HistoricalSnapshotCollector
from qresearch.historical_source import QuantConnectSnapshotSource, _scalar


DATE_PATHS = ("financial_statements.file_date.value",
              "financial_statements.period_ending_date.value")
CATALOG = {path: {"kind": "date", "role": "synthetic_filing_metadata",
                  "unit": "ISO_date", "period_accessor": "value"} for path in DATE_PATHS}


class NativeDateField:
    """Synthetic MultiPeriodField contract: HasValue concerns default period.

    Value may validly fall back to another period even when HasValue is false.
    With no period containing a value, the SDK DateTime NoValue is datetime.min.
    """
    def __init__(self, default=None, fallback=None):
        self.has_value = default is not None
        self.value = default if default is not None else fallback if fallback is not None else datetime.min


class NativeDateQB:
    def __init__(self, file_date, period_end):
        self.time = datetime(2018, 1, 4)
        self.universe_settings = NS()
        self.calls = 0
        self.object = NS(symbol=NS(id="SYNTHETIC-DATE-SID"), financial_statements=NS(
            file_date=file_date, period_ending_date=period_end))

    def set_time_zone(self, zone):
        if zone != "America/New_York":
            raise AssertionError("Explicit NY interpretation required")

    def add_universe(self, selector):
        return "SYNTHETIC-DATE-UNIVERSE"

    def universe_history(self, universe, start, end, *, flatten):
        self.calls += 1
        if flatten is not False:
            raise AssertionError("Native-shaped Series required")
        # The WR-09 fixture is deliberately inside both request conventions;
        # WR-10 tests separately own request-boundary behavior.
        index = pd.MultiIndex.from_tuples([(universe, datetime(2018, 1, 3, 9))],
                                          names=["symbol", "time"])
        return pd.Series([[self.object]], index=index, dtype=object)


class WR09MissingDateTests(unittest.TestCase):
    def collect(self, file_date, period_end):
        qb = NativeDateQB(file_date, period_end)
        source = QuantConnectSnapshotSource(qb, CATALOG, api=NS(Resolution=NS(DAILY="synthetic_daily")))
        raw = {"schema_version": 1, "plan_id": "SYNTHETIC-WR09", "scope": "engineering",
               "source": "quantconnect_fundamental_universe", "data_version": "SYNTHETIC-v1",
               "start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2018-01-04T00:00:00-05:00",
               "timezone": "America/New_York", "fields": list(DATE_PATHS),
               "calendar_days_per_request": 1, "max_batch_records": 1,
               "max_records_per_window": 10, "source_manifest_hash": "a" * 64}
        plan = HistoricalCollectionPlan.from_dict(raw, field_catalog=CATALOG)
        collector = HistoricalSnapshotCollector(MemoryArtifactStore(), source, plan, synthetic=True)
        receipt = collector.collect()
        rows = collector.read_window(receipt["window_refs"][0])
        return qb, collector, receipt, rows

    def test_exact_sdk_default_datetime_and_date_are_missing(self):
        for value in (datetime.min, date.min, pd.Timestamp(datetime.min), "0001-01-01"):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(_scalar(value, "date"))

    def test_existing_missing_variants_and_legitimate_dates(self):
        for value in (None, pd.NaT, pd.NA, float("nan")):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(_scalar(value, "date"))
        for value, expected in ((datetime(2017, 12, 31), "2017-12-31"),
                                (date(2017, 12, 31), "2017-12-31"),
                                ("2017-12-31", "2017-12-31"),
                                (date(1, 1, 2), "0001-01-02")):
            with self.subTest(value=value):
                self.assertEqual(_scalar(value, "date"), expected)
        self.assertEqual(_scalar(0, "number"), 0)

    def test_all_periods_missing_cache_nulls_and_counts_each_field(self):
        qb, collector, receipt, rows = self.collect(NativeDateField(), NativeDateField())
        self.assertEqual(len(rows), 1)
        for path in DATE_PATHS:
            with self.subTest(path=path):
                self.assertIsNone(rows[0]["values"][path])
                self.assertEqual(receipt["missing_values"][path], 1)
        self.assertFalse(receipt["actual_availability_certified"])
        replay = collector.collect()
        self.assertEqual(qb.calls, 1)
        self.assertEqual(receipt["window_refs"], replay["window_refs"])
        self.assertEqual(replay["missing_values"], receipt["missing_values"])

    def test_valid_fallback_is_not_deleted_by_default_has_value_false(self):
        file_date = NativeDateField(fallback=datetime(2017, 12, 29))
        period_end = NativeDateField(fallback=datetime(2017, 9, 30))
        self.assertFalse(file_date.has_value)
        self.assertFalse(period_end.has_value)
        _, _, receipt, rows = self.collect(file_date, period_end)
        self.assertEqual(rows[0]["values"], {DATE_PATHS[0]: "2017-12-29", DATE_PATHS[1]: "2017-09-30"})
        self.assertEqual(receipt["missing_values"], {path: 0 for path in DATE_PATHS})

    def test_normal_and_missing_fields_have_independent_gap_counts(self):
        _, _, receipt, rows = self.collect(NativeDateField(datetime(2017, 12, 29)), NativeDateField())
        self.assertEqual(rows[0]["values"][DATE_PATHS[0]], "2017-12-29")
        self.assertIsNone(rows[0]["values"][DATE_PATHS[1]])
        self.assertEqual(receipt["missing_values"], {DATE_PATHS[0]: 0, DATE_PATHS[1]: 1})

    def test_legacy_completed_sentinel_cache_is_rejected_without_overwrite_or_refetch(self):
        qb, collector, receipt, _ = self.collect(NativeDateField(), NativeDateField())
        store = collector.store
        reference = receipt["window_refs"][0]
        manifest = json.loads(store.read_bytes(reference["key"]))
        payload = json.loads(store.read_bytes(manifest["batches"][0]["key"]))
        # Reconstruct the old writer's valid format/content hashes, including
        # its incorrect zero missing counts. This is synthetic legacy data.
        payload["records"][0]["values"] = {path: "0001-01-01" for path in DATE_PATHS}
        digest = content_hash(payload)
        key = "historical-snapshots/v1/objects/" + digest + ".json"
        store.write_once(key, canonical_json(payload))
        manifest["batches"] = [{"key": key, "sha256": digest}]
        manifest["missing_values"] = {path: 0 for path in DATE_PATHS}
        old_bytes = canonical_json(manifest)
        store._data[reference["key"]] = old_bytes
        old_ref = {"key": reference["key"], "sha256": content_hash(manifest)}
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window(old_ref)
        with self.assertRaises(CollectionIntegrityError):
            collector.collect()
        self.assertEqual(qb.calls, 1)
        self.assertEqual(store.read_bytes(reference["key"]), old_bytes)


if __name__ == "__main__":
    unittest.main()
