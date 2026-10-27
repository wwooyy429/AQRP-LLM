"""WR-10 fixed LEAN-contract replays; synthetic clocks/objects only."""
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.collection import (CollectionError, CollectionInterrupted, HistoricalCollectionPlan,
                                 HistoricalSnapshotCollector)
from qresearch.historical_source import HistoricalSourceError, QuantConnectSnapshotSource


CATALOG = {"dollar_volume": {"kind": "number", "role": "synthetic_liquidity", "unit": "USD", "period_accessor": None}}


def ny(value):
    return pd.Timestamp(value, tz="America/New_York")


class ContractQB:
    """Replay the official (start, end] EndTime contract, not the desired one."""
    def __init__(self, stamps, frontier):
        self.stamps, self.time, self.calls = stamps, frontier, []
        self.universe_settings = NS()

    def set_time_zone(self, zone):
        if zone != "America/New_York":
            raise AssertionError("Explicit algorithm timezone required")

    def add_universe(self, selector):
        return "SYNTHETIC-WR10-UNIVERSE"

    def universe_history(self, universe, start, end, *, flatten):
        self.calls.append((start, end))
        if start.tzinfo is not None or end.tzinfo is not None or flatten is not False:
            raise AssertionError("Research API consumes naive algorithm-zone datetimes")
        accepted = [stamp for stamp in self.stamps if start < stamp <= end]
        index = pd.MultiIndex.from_tuples([(universe, stamp) for stamp in accepted], names=["symbol", "time"])
        return pd.Series([[NS(symbol=NS(id="SYNTHETIC-WR10-SID"), dollar_volume=0.)]
                          for stamp in accepted], index=index, dtype=object)


class WR10HistoryIntervalTests(unittest.TestCase):
    def source(self, qb):
        return QuantConnectSnapshotSource(qb, CATALOG, api=NS(Resolution=NS(DAILY="synthetic_daily")))

    def plan(self, start, end, *, days=1):
        return HistoricalCollectionPlan.from_dict({"schema_version": 1, "plan_id": "SYNTHETIC-WR10",
            "scope": "engineering", "source": "quantconnect_fundamental_universe", "data_version": "SYNTHETIC-fixed-v2",
            "start": start.isoformat(), "end_exclusive": end.isoformat(), "timezone": "America/New_York",
            "fields": list(CATALOG), "calendar_days_per_request": days, "max_batch_records": 2,
            "max_records_per_window": 20, "source_manifest_hash": "c" * 64}, field_catalog=CATALOG)

    def test_one_two_seven_day_contract_covers_start_and_excludes_end(self):
        for days in (1, 2, 7):
            with self.subTest(days=days):
                start, end = ny("2018-01-03"), ny("2018-01-03") + pd.DateOffset(days=days)
                all_days = pd.date_range(start - pd.DateOffset(days=1), end, freq="D")
                native = [stamp.tz_localize(None).to_pydatetime() for stamp in all_days]
                qb = ContractQB(native, end.tz_localize(None).to_pydatetime())
                rows = list(self.source(qb).fetch(start, end, CATALOG))
                self.assertEqual([row["snapshot_at"] for row in rows], [x.isoformat() for x in all_days[1:-1]])
                self.assertEqual(qb.calls, [(datetime(2018, 1, 2),
                    end.tz_localize(None).to_pydatetime() - timedelta(microseconds=1))])

    def test_contiguous_collector_windows_have_no_gap_duplicate_or_refetch(self):
        start, end = ny("2018-01-03"), ny("2018-01-08")
        stamps = pd.date_range(start - pd.DateOffset(days=1), end, freq="D")
        qb = ContractQB([x.tz_localize(None).to_pydatetime() for x in stamps], datetime(2018, 1, 8))
        store = MemoryArtifactStore()
        collector = HistoricalSnapshotCollector(store, self.source(qb), self.plan(start, end, days=2), synthetic=True)
        receipt = collector.collect()
        clocks = [row["snapshot_at"] for ref in receipt["window_refs"] for row in collector.read_window(ref)]
        self.assertEqual(clocks, [x.isoformat() for x in stamps[1:-1]])
        self.assertEqual(len(qb.calls), 3)
        replay = HistoricalSnapshotCollector(store, None, self.plan(start, end, days=2), synthetic=True).collect()
        self.assertEqual(replay["provider_calls"], 0)
        self.assertEqual(receipt["window_refs"], replay["window_refs"])
        self.assertEqual(len(qb.calls), 3)

    def test_spring_and_fall_dst_calendar_windows_preserve_actual_instants(self):
        for initial in ("2018-03-10", "2018-11-03"):
            for days in (1, 2, 7):
                with self.subTest(initial=initial, days=days):
                    start = ny(initial); end = start + pd.DateOffset(days=days)
                    stamps = pd.date_range(start - pd.DateOffset(days=1), end, freq="D")
                    qb = ContractQB([x.tz_localize(None).to_pydatetime() for x in stamps], end.tz_localize(None).to_pydatetime())
                    rows = list(self.source(qb).fetch(start, end, CATALOG))
                    self.assertEqual([x["snapshot_at"] for x in rows], [x.isoformat() for x in stamps[1:-1]])
                    self.assertEqual(qb.calls[0][0], (start - pd.DateOffset(days=1)).tz_localize(None).to_pydatetime())
                    expected_end = (end.tz_convert("UTC") - pd.Timedelta(microseconds=1)).tz_convert("America/New_York")
                    self.assertEqual(qb.calls[0][1], expected_end.tz_localize(None).to_pydatetime())

    def test_empty_window_completes_without_claiming_coverage(self):
        start, end = ny("2018-01-03"), ny("2018-01-04")
        qb = ContractQB([], datetime(2018, 1, 4))
        collector = HistoricalSnapshotCollector(MemoryArtifactStore(), self.source(qb), self.plan(start, end), synthetic=True)
        receipt = collector.collect()
        self.assertEqual(receipt["record_count"], 0)
        self.assertEqual(receipt["empty_windows"], 1)
        self.assertFalse(receipt["full_historical_US200_certified"])
        self.assertEqual(collector.read_window(receipt["window_refs"][0]), [])

    def test_final_boundary_never_requests_or_reads_final_timestamp(self):
        start, end = ny("2023-12-30"), ny("2024-01-01")
        stamps = [datetime(2023, 12, 29), datetime(2023, 12, 30), datetime(2023, 12, 31), datetime(2024, 1, 1)]
        qb = ContractQB(stamps, datetime(2024, 1, 1))
        collector = HistoricalSnapshotCollector(MemoryArtifactStore(), self.source(qb), self.plan(start, end), synthetic=True)
        receipt = collector.collect()
        rows = [row for ref in receipt["window_refs"] for row in collector.read_window(ref)]
        self.assertEqual([row["snapshot_at"] for row in rows], [start.isoformat(), ny("2023-12-31").isoformat()])
        self.assertTrue(all(right < datetime(2024, 1, 1) for _, right in qb.calls))
        self.assertFalse(receipt["actual_availability_certified"])

    def test_last_representable_microsecond_is_retained(self):
        start, end = ny("2018-01-03"), ny("2018-01-04")
        stamps = [datetime(2018, 1, 2, 23, 59, 59, 999999), datetime(2018, 1, 3),
                  datetime(2018, 1, 3, 23, 59, 59, 999999), datetime(2018, 1, 4)]
        qb = ContractQB(stamps, datetime(2018, 1, 4))
        rows = list(self.source(qb).fetch(start, end, CATALOG))
        self.assertEqual([row["snapshot_at"] for row in rows], [start.isoformat(), "2018-01-03T23:59:59.999999-05:00"])

    def test_broken_response_end_still_rejected_and_intent_not_auto_retried(self):
        class WrongQB(ContractQB):
            def universe_history(self, universe, start, end, *, flatten):
                self.calls.append((start, end))
                index = pd.MultiIndex.from_tuples([(universe, datetime(2018, 1, 4))], names=["symbol", "time"])
                return pd.Series([[NS(symbol=NS(id="SYNTHETIC"), dollar_volume=1.)]], index=index, dtype=object)

        start, end = ny("2018-01-03"), ny("2018-01-04")
        qb = WrongQB([], datetime(2018, 1, 4))
        collector = HistoricalSnapshotCollector(MemoryArtifactStore(), self.source(qb), self.plan(start, end), synthetic=True)
        with self.assertRaises(CollectionError):
            collector.collect()
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(len(qb.calls), 1)

    def test_requested_final_interval_rejected_before_native_call(self):
        qb = ContractQB([], datetime(2024, 1, 1))
        with self.assertRaises(HistoricalSourceError):
            list(self.source(qb).fetch(ny("2024-01-01"), ny("2024-01-02"), CATALOG))
        self.assertEqual(qb.calls, [])


if __name__ == "__main__":
    unittest.main()
