"""Native-shaped synthetic responses only; no SDK/provider/network access."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.collection import HistoricalCollectionPlan, HistoricalSnapshotCollector
from qresearch.historical_source import (HistoricalSourceError, QuantConnectSnapshotSource,
                                         observed_liquidity_record)
from qresearch.ingestion import HistoricalBatchIngestor, MissingPITEvidence


ROOT = Path(__file__).resolve().parents[1]


def ts(value):
    return pd.Timestamp(value, tz="America/New_York")


def definition(kind):
    return {"kind": kind, "role": "synthetic_observation", "unit": "synthetic", "period_accessor": None}


CATALOG = {"dollar_volume": definition("number"), "has_fundamental_data": definition("boolean"),
           "time": definition("text"), "financial_statements.file_date.value": definition("date"),
           "security_reference.security_type": definition("text"),
           "security_reference.common_share_sub_type": definition("text"),
           "security_reference.is_depositary_receipt": definition("boolean"),
           "security_reference.share_class_status": definition("text"),
           "company_reference.is_reit": definition("boolean")}


def native(sid="SYNTHETIC-SID", **changes):
    return NS(symbol=NS(id=sid), dollar_volume=100, has_fundamental_data=False,
              time=datetime(2018, 1, 2), financial_statements=NS(file_date=NS(value=datetime(2017, 12, 31))),
              security_reference=NS(security_type="ST00000001", common_share_sub_type=None,
                  is_depositary_receipt=False, share_class_status="I"),
              company_reference=NS(is_reit=False), **changes)


def response(objects, stamp="2018-01-03"):
    return pd.Series([objects], index=pd.MultiIndex.from_tuples(
        [("SYNTHETIC-UNIVERSE", pd.Timestamp(stamp))], names=["symbol", "time"]), dtype=object)


class FakeQB:
    def __init__(self, data=None):
        self.time = datetime(2018, 1, 4)
        self.universe_settings = NS(resolution=None)
        self.data = response([native()]) if data is None else data
        self.calls, self.selectors, self.zones = [], [], []

    def set_time_zone(self, zone):
        self.zones.append(zone)

    def add_universe(self, selector):
        self.selectors.append(selector)
        return "SYNTHETIC-HISTORY-UNIVERSE"

    def universe_history(self, universe, start, end, *, flatten):
        self.calls.append((universe, start, end, flatten))
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


class HistoricalSourceTests(unittest.TestCase):
    def source(self, qb=None, catalog=None, **kwargs):
        return QuantConnectSnapshotSource(qb or FakeQB(), catalog or CATALOG,
            api=NS(Resolution=NS(DAILY="synthetic_daily")), **kwargs)

    def fetch(self, source, catalog=None):
        return list(source.fetch(ts("2018-01-03"), ts("2018-01-04"), catalog or CATALOG))

    def test_single_bulk_call_preserves_no_financial_coverage_and_permanent_sid(self):
        a, b = native(), native("OTHER-SID")
        b.symbol.value = "CURRENT-TICKER-IGNORED"
        b.dollar_volume, b.has_fundamental_data = 0, True
        qb = FakeQB(response([a, b]))
        source = self.source(qb)
        rows = self.fetch(source)
        self.assertEqual([row["sid"] for row in rows], ["SYNTHETIC-SID", "OTHER-SID"])
        self.assertFalse(rows[0]["values"]["has_fundamental_data"])
        self.assertEqual(rows[1]["values"]["dollar_volume"], 0)
        self.assertEqual(rows[0]["values"]["time"], "2018-01-02T00:00:00")
        self.assertEqual(rows[0]["values"]["financial_statements.file_date.value"], "2017-12-31")
        self.assertEqual(rows[0]["snapshot_at"], "2018-01-03T00:00:00-05:00")
        self.assertEqual(len(qb.calls), 1)
        self.assertEqual(qb.calls[0][1:], (datetime(2018, 1, 2),
                                        datetime(2018, 1, 4) - timedelta(microseconds=1), False))
        self.assertEqual(qb.selectors[0]([a, b]), [a.symbol, b.symbol])
        self.assertFalse(source.provenance()["actual_availability_certified"])

    def test_missing_properties_and_nan_stay_missing(self):
        item = native()
        del item.financial_statements
        item.dollar_volume, item.has_fundamental_data = np.nan, np.bool_(False)
        row = self.fetch(self.source(FakeQB(response([item]))))[0]
        self.assertIsNone(row["values"]["dollar_volume"])
        self.assertIsNone(row["values"]["financial_statements.file_date.value"])
        self.assertIs(row["values"]["has_fundamental_data"], False)

    def test_empty_series_is_not_certification(self):
        empty = pd.Series([], index=pd.MultiIndex.from_tuples([], names=["symbol", "time"]), dtype=object)
        source = self.source(FakeQB(empty))
        self.assertEqual(self.fetch(source), [])
        self.assertFalse(source.provenance()["full_historical_US200_certified"])

    def test_intervals_final_frontier_and_projection_rejected_before_history(self):
        cases = [("2018-01-03", ts("2018-01-04"), CATALOG),
                 (ts("2018-01-01"), ts("2018-01-09"), CATALOG),
                 (ts("2024-01-01"), ts("2024-01-02"), CATALOG),
                 (ts("2018-01-03 01:00"), ts("2018-01-04"), CATALOG),
                 (ts("2018-01-03"), ts("2018-01-04"), {"unrestricted": definition("number")})]
        changed = deepcopy(CATALOG)
        changed["dollar_volume"]["unit"] = "changed"
        cases.append((ts("2018-01-03"), ts("2018-01-04"), changed))
        for start, end, catalog in cases:
            with self.subTest(start=start, end=end, catalog=catalog):
                qb = FakeQB()
                with self.assertRaises((HistoricalSourceError, ValueError)):
                    list(self.source(qb).fetch(start, end, catalog))
                self.assertEqual(qb.calls, [])
        for frontier in (datetime(2018, 1, 3), datetime(2024, 1, 2), pd.NaT):
            qb = FakeQB()
            qb.time = frontier
            with self.assertRaises(HistoricalSourceError):
                self.fetch(self.source(qb))
            self.assertEqual(qb.calls, [])

    def test_malformed_response_and_outside_or_duplicate_snapshots_rejected(self):
        duplicate = pd.concat([response([native()]), response([native("B")])])
        bad = [pd.DataFrame(columns=["unknown"]), pd.Series([[]]), response([native()], "2018-01-04"),
               response([native()], "2018-01-02"), duplicate, response("not-list"),
               response([native(), native()]), response([NS(symbol="TICKER")])]
        for data in bad:
            with self.subTest(data_type=type(data).__name__):
                with self.assertRaises(HistoricalSourceError):
                    self.fetch(self.source(FakeQB(data)))

    def test_scalar_type_errors_and_retired_property_fail_closed_without_native_values(self):
        for name, value in (("dollar_volume", True), ("dollar_volume", np.inf),
                            ("has_fundamental_data", 2), ("time", 42)):
            item = native()
            setattr(item, name, value)
            with self.subTest(name=name, value=value):
                with self.assertRaises(HistoricalSourceError):
                    self.fetch(self.source(FakeQB(response([item]))))

        class Retired:
            symbol = NS(id="SYNTHETIC")

            @property
            def dollar_volume(self):
                raise RuntimeError("LICENSED-ROW-SECRET")

        with self.assertRaises(HistoricalSourceError) as caught:
            self.fetch(self.source(FakeQB(response([Retired()]))))
        self.assertNotIn("LICENSED-ROW-SECRET", str(caught.exception))

    def test_wrong_mixed_or_changed_universe_identity_rejected(self):
        mixed = pd.concat([response([native()]), response([native("B")], "2018-01-04")])
        mixed.index = pd.MultiIndex.from_tuples([
            ("SYNTHETIC-UNIVERSE", pd.Timestamp("2018-01-03")),
            ("DIFFERENT-UNIVERSE", pd.Timestamp("2018-01-04"))], names=["symbol", "time"])
        qb = FakeQB(mixed)
        qb.time = datetime(2018, 1, 5)
        with self.assertRaises(HistoricalSourceError):
            list(self.source(qb).fetch(ts("2018-01-03"), ts("2018-01-05"), CATALOG))
        qb = FakeQB()
        source = self.source(qb)
        self.fetch(source)
        qb.data.index = pd.MultiIndex.from_tuples([("DIFFERENT-UNIVERSE", pd.Timestamp("2018-01-03"))], names=["symbol", "time"])
        with self.assertRaises(HistoricalSourceError):
            self.fetch(source)
        qb = FakeQB()
        qb.add_universe = lambda selector: NS(symbol="EXPECTED-UNIVERSE")
        with self.assertRaises(HistoricalSourceError):
            self.fetch(self.source(qb))

    def test_native_request_error_is_redacted(self):
        with self.assertRaises(HistoricalSourceError) as caught:
            self.fetch(self.source(FakeQB(RuntimeError("LICENSED-ROW-SECRET"))))
        self.assertNotIn("LICENSED-ROW-SECRET", str(caught.exception))

    def test_same_display_universe_different_native_id_cannot_alias(self):
        class NativeSymbol:
            def __init__(self, sid):
                self.id = sid

            def __str__(self):
                return "SAME-UNIVERSE-NAME"

        expected, different = NativeSymbol("EXPECTED-SID"), NativeSymbol("OTHER-SID")
        qb = FakeQB()
        qb.add_universe = lambda selector: NS(symbol=expected)
        qb.data.index = pd.MultiIndex.from_tuples([(different, pd.Timestamp("2018-01-03"))], names=["symbol", "time"])
        with self.assertRaises(HistoricalSourceError):
            self.fetch(self.source(qb))
        qb.data.index = pd.MultiIndex.from_tuples([(expected, pd.Timestamp("2018-01-03"))], names=["symbol", "time"])
        source = self.source(qb)
        self.assertEqual(len(self.fetch(source)), 1)
        qb.data.index = pd.MultiIndex.from_tuples([(different, pd.Timestamp("2018-01-03"))], names=["symbol", "time"])
        with self.assertRaises(HistoricalSourceError):
            self.fetch(source)

    def test_calls_and_universe_reused_and_snapshot_bound_enforced(self):
        qb = FakeQB(response([native(), native("B")]))
        with self.assertRaises(HistoricalSourceError):
            self.fetch(self.source(qb, max_records_per_snapshot=1))
        for limit in (True, 0, 100001):
            with self.assertRaises(HistoricalSourceError):
                self.source(max_records_per_snapshot=limit)
        qb = FakeQB()
        source = self.source(qb)
        self.fetch(source); self.fetch(source)
        self.assertEqual(source.history_call_count, 2)
        self.assertEqual(len(qb.selectors), 1)

    def test_dst_uses_local_midnights_and_aware_response_preserves_instant(self):
        qb = FakeQB(response([native()], "2018-03-11T05:00:00+00:00"))
        qb.time = datetime(2018, 3, 12)
        row = list(self.source(qb).fetch(ts("2018-03-11"), ts("2018-03-12"), CATALOG))[0]
        self.assertEqual(row["snapshot_at"], "2018-03-11T00:00:00-05:00")
        self.assertEqual(qb.calls[0][1:3], (datetime(2018, 3, 10),
                                         datetime(2018, 3, 12) - timedelta(microseconds=1)))

    def test_collection_ingestion_chain_reuses_and_unknown_timing_cannot_rank(self):
        raw = {"schema_version": 1, "plan_id": "SYNTHETIC", "scope": "engineering",
               "source": "quantconnect_fundamental_universe", "data_version": "SYNTHETIC-v1",
               "start": ts("2018-01-03").isoformat(), "end_exclusive": ts("2018-01-04").isoformat(),
               "timezone": "America/New_York", "fields": list(CATALOG), "calendar_days_per_request": 1,
               "max_batch_records": 10, "max_records_per_window": 20, "source_manifest_hash": "a" * 64}
        plan, store, source = HistoricalCollectionPlan.from_dict(raw, field_catalog=CATALOG), MemoryArtifactStore(), self.source()
        collector = HistoricalSnapshotCollector(store, source, plan, synthetic=True)
        first, second = collector.collect(), collector.collect()
        self.assertEqual(source.history_call_count, 1)
        self.assertEqual(first["window_refs"], second["window_refs"])
        row = collector.read_window(first["window_refs"][0])[0]
        projected = observed_liquidity_record(row, session_close=ts("2018-01-02 16:00"))
        self.assertEqual(projected["instrument_type"], "common_stock")
        self.assertTrue(projected["listed"])  # I has no fundamental coverage; not excluded.
        self.assertTrue(projected["source_revision"].startswith("observed_snapshot:"))
        ingestor = HistoricalBatchIngestor(store, source="synthetic-observation-not-vendor-revision",
            data_version="SYNTHETIC-v1", origin="historical_declared_fixture", synthetic=True)
        receipt = ingestor.ingest("liquidity", [projected], partition="synthetic-window")
        self.assertEqual(receipt["gaps"]["actual_availability_unverified"], 1)
        with self.assertRaises(MissingPITEvidence):
            ingestor.liquidity_rows_asof(receipt["batch_ref"], ts("2018-01-03 09:00"), [ts("2018-01-02 16:00")])

    def test_classification_is_conservative_and_no_session_inference(self):
        row = self.fetch(self.source())[0]
        values = row["values"]
        for field, value, expected in (("security_reference.is_depositary_receipt", True, "adr"),
                                      ("company_reference.is_reit", True, "reit_common"),
                                      ("security_reference.common_share_sub_type", "Closed-End Fund", "closed_end_fund"),
                                      ("security_reference.common_share_sub_type", "Unfamiliar", None),
                                      ("security_reference.security_type", "UNKNOWN", None)):
            changed = deepcopy(row)
            changed["values"][field] = value
            self.assertEqual(observed_liquidity_record(changed, session_close=ts("2018-01-02 16:00"))["instrument_type"], expected)
        with self.assertRaises(HistoricalSourceError):
            observed_liquidity_record(row, session_close=ts("2018-01-03 16:00"))
        with self.assertRaises(HistoricalSourceError):
            observed_liquidity_record(row, session_close="2018-01-02 16:00")


if __name__ == "__main__":
    unittest.main()
