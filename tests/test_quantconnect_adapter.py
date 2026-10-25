"""Synthetic SDK-boundary tests, containing no licensed market observations."""
from datetime import datetime, time
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import ArtifactConflict, decode_events
from qresearch.contracts import DataRequest, NY
from qresearch.quantconnect import (ExchangeCalendar, ObjectStoreArtifactStore,
                                  QuantConnectHistoryProvider)


class FakeObjectStore:
    def __init__(self):
        self.data = {}
        self.saves = 0
        self.reject = False

    def contains_key(self, key):
        return key in self.data

    def read_bytes(self, key):
        return self.data[key]

    def save_bytes(self, key, data):
        if self.reject:
            return False
        self.data[key] = bytes(data)
        self.saves += 1
        return True


class FakeHours:
    # Explicit artificial exchange fixture: only these sessions exist.
    def __init__(self):
        self.closes = {
            datetime(2018, 3, 9): datetime(2018, 3, 9, 16),
            datetime(2018, 3, 12): datetime(2018, 3, 12, 16),
            datetime(2018, 3, 13): datetime(2018, 3, 13, 13),
            datetime(2018, 3, 14): datetime(2018, 3, 14, 16),
            datetime(2018, 3, 15): datetime(2018, 3, 15, 16),
        }

    def is_date_open(self, day):
        return day in self.closes

    def get_next_trading_day(self, day):
        return min(d for d in self.closes if d > day)

    def get_previous_trading_day(self, day):
        return max(d for d in self.closes if d < day)

    def get_next_market_close(self, moment, extended):
        return min(d for d in self.closes.values() if d >= moment)


class FakeSymbol:
    def __init__(self, sid, ticker):
        self.id, self.value = sid, ticker

    def __str__(self):
        return self.value


class FakeBook:
    def __init__(self, symbols, history):
        self.settings = SimpleNamespace(daily_precise_end_time=False)
        self.time = datetime(2018, 3, 14)
        self.securities = {symbol: SimpleNamespace(exchange=SimpleNamespace(hours=FakeHours()))
                           for symbol in symbols}
        self.return_history = history
        self.calls = []

    def set_time_zone(self, value):
        self.timezone = value

    def history(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.return_history


API = SimpleNamespace(Resolution=SimpleNamespace(DAILY="daily"),
                      DataNormalizationMode=SimpleNamespace(RAW="raw"))


class ObjectStoreTests(unittest.TestCase):
    def test_readonly_and_explicit_single_producer(self):
        raw = FakeObjectStore()
        with self.assertRaises(ValueError):
            ObjectStoreArtifactStore(raw, "research", read_only=False)
        readonly = ObjectStoreArtifactStore(raw, "research")
        with self.assertRaises(PermissionError):
            readonly.write_once("a", b"a")
        with self.assertRaises(FileNotFoundError):
            readonly.read_bytes("missing")

    def test_immutable_reuse_conflict_and_path_validation(self):
        raw = FakeObjectStore()
        store = ObjectStoreArtifactStore(raw, "research", read_only=False, single_producer=True)
        self.assertTrue(store.write_once("cache/a", b"a"))
        self.assertFalse(store.write_once("cache/a", b"a"))
        self.assertEqual(raw.saves, 1)
        with self.assertRaises(ArtifactConflict):
            store.write_once("cache/a", b"different")
        with self.assertRaises(ValueError):
            store.exists("../other")

    def test_append_chain_and_rejected_save(self):
        raw = FakeObjectStore()
        store = ObjectStoreArtifactStore(raw, "research", read_only=False, single_producer=True)
        store.append_event("events.jsonl", {"state": "reserved"})
        store.append_event("events.jsonl", {"state": "complete"})
        self.assertEqual(len(decode_events(store.read_bytes("events.jsonl"))), 2)
        raw.reject = True
        with self.assertRaises(IOError):
            store.write_once("rejected", b"x")


class CalendarTests(unittest.TestCase):
    def test_exchange_days_dst_and_early_close(self):
        calendar = ExchangeCalendar(FakeHours())
        rows = calendar.decisions(datetime(2018, 3, 12, tzinfo=NY),
                                  datetime(2018, 3, 15, tzinfo=NY))
        self.assertEqual(list(rows.formation_at.dt.hour), [9, 9, 9])
        self.assertEqual(rows.iloc[0].session_close.date().isoformat(), "2018-03-09")
        self.assertEqual(rows.iloc[0].session_close.utcoffset().total_seconds(), -5 * 3600)
        self.assertEqual(rows.iloc[0].formation_at.utcoffset().total_seconds(), -4 * 3600)
        self.assertEqual(rows.iloc[2].session_close.hour, 13)

    def test_final_calendar_blocked(self):
        with self.assertRaises(ValueError):
            ExchangeCalendar(FakeHours()).decisions(datetime(2023, 1, 1, tzinfo=NY),
                                                     datetime(2024, 2, 1, tzinfo=NY))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = FakeSymbol("SID-A", "AAA"), FakeSymbol("SID-B", "BBB")
        index = pd.MultiIndex.from_tuples([(self.a, datetime(2018, 3, 12, 16)),
                                          (self.b, datetime(2018, 3, 13, 13))],
                                         names=["symbol", "time"])
        self.frame = pd.DataFrame({"close": [10., 20.], "volume": [50., 70.]}, index=index)
        self.qb = FakeBook([self.a, self.b], self.frame)
        self.provider = QuantConnectHistoryProvider(self.qb,
                    {"SID-A": self.a, "SID-B": self.b}, "fixture-v1", API)

    def request(self, **changes):
        args = dict(dataset="us_equity_daily", fields=("close", "volume"),
                    sids=("SID-A", "SID-B"), start=datetime(2018, 3, 12, tzinfo=NY),
                    end=datetime(2018, 3, 14, tzinfo=NY), data_version="fixture-v1",
                    universe_hash="fixture-universe")
        args.update(changes)
        return DataRequest(**args)

    def test_one_batched_call_raw_no_fill_and_assumed_availability(self):
        rows = self.provider.fetch(self.request())
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(self.qb.calls), 1)
        self.assertEqual(len(self.qb.calls[0][0][0]), 2)
        self.assertEqual(self.qb.calls[0][1], {"fill_forward": False,
                         "extended_market_hours": False, "data_normalization_mode": "raw"})
        self.assertTrue(self.qb.settings.daily_precise_end_time)
        self.assertIsNone(self.provider.provenance["historical_vendor_available_at"])
        self.assertEqual(self.provider.provenance["coverage_status"], "not_certified")
        self.assertEqual(self.provider.fetch_call_count, 1)

    def test_unapproved_fields_versions_and_symbols_fail_before_io(self):
        for changes in ({"fields": ("net_income",)}, {"normalization": "adjusted"},
                        {"data_version": "v2"}, {"sids": ("SID-C",)},
                        {"dataset": "fundamentals"}):
            with self.assertRaises(ValueError):
                self.provider.fetch(self.request(**changes))
        self.assertEqual(len(self.qb.calls), 0)

    def test_midnight_daily_bar_rejected(self):
        self.qb.return_history = self.frame.iloc[[0]].copy()
        self.qb.return_history.index = pd.MultiIndex.from_tuples([
            (self.a, datetime(2018, 3, 13))], names=["symbol", "time"])
        with self.assertRaisesRegex(ValueError, "end_time"):
            self.provider.fetch(self.request())

    def test_frontier_before_request_end_rejected_before_io(self):
        self.qb.time = datetime(2018, 3, 12)
        with self.assertRaisesRegex(ValueError, "frontier"):
            self.provider.fetch(self.request())
        self.assertEqual(self.provider.fetch_call_count, 0)
        self.assertEqual(self.qb.calls, [])

    def test_current_or_final_frontier_rejected_before_io(self):
        self.qb.time = datetime(2026, 10, 26)
        with self.assertRaisesRegex(ValueError, "frontier"):
            self.provider.fetch(self.request())
        self.assertEqual(self.provider.fetch_call_count, 0)
        self.assertEqual(self.qb.calls, [])

    def test_symbol_mapping_requires_permanent_sid(self):
        with self.assertRaises(ValueError):
            QuantConnectHistoryProvider(self.qb, {"AAA": self.a}, "fixture-v1", API)


if __name__ == "__main__":
    unittest.main()
