"""Synthetic engineering tests. No market data or economic claim."""
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import unittest
import pandas as pd
from qresearch.contracts import DataRequest, NY, RECORD_COLUMNS
from qresearch.cache import SharedDataCache, CacheMiss, merge_requests
from qresearch.point_in_time import causal_window
from qresearch.universe import select_liquid_universe


def ts(day, hour=16):
    return datetime(2018, 1, day, hour, tzinfo=NY)


class FixtureProvider:
    def __init__(self):
        self.calls = 0
        self.requests = []
        self.provenance = {"synthetic": True}

    def fetch(self, request):
        self.calls += 1
        self.requests.append(request)
        return pd.DataFrame([[sid, field, ts(2), ts(2, 18), 10., "v1"]
                             for sid in request.sids for field in request.fields], columns=RECORD_COLUMNS)


class DataPipelineTests(unittest.TestCase):
    def request(self, **changes):
        arguments = dict(dataset="ohlcv", fields=("close",), sids=("A", "B"),
                         start=ts(1, 0), end=ts(10, 0), data_version="synthetic-v1", universe_hash="fixture")
        arguments.update(changes)
        return DataRequest(**arguments)

    def test_shared_batch_cache_and_concurrent_reuse(self):
        from qresearch.artifacts import MemoryArtifactStore
        provider = FixtureProvider()
        cache = SharedDataCache(MemoryArtifactStore(), provider)
        with ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _: cache.prefetch(self.request()), range(4)))
        self.assertEqual(provider.calls, 1)
        a, b = cache.read(self.request()), cache.read(self.request(fields=("close",), sids=("B", "A")))
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(provider.calls, 1)
        cache.prefetch(self.request(data_version="synthetic-v2"))
        self.assertEqual(provider.calls, 2)

    def test_reader_miss_does_not_fetch(self):
        from qresearch.artifacts import MemoryArtifactStore
        provider = FixtureProvider()
        with self.assertRaises(CacheMiss):
            SharedDataCache(MemoryArtifactStore(), provider).read(self.request())
        self.assertEqual(provider.calls, 0)

    def test_new_field_fetches_only_missing_field(self):
        from qresearch.artifacts import MemoryArtifactStore
        provider = FixtureProvider()
        cache = SharedDataCache(MemoryArtifactStore(), provider)
        cache.prefetch(self.request())
        cache.prefetch(self.request(fields=("close", "volume")))
        self.assertEqual(provider.requests[-1].fields, ("volume",))
        self.assertEqual(len(cache.read(self.request())), 2)

    def test_empty_history_is_a_valid_cached_missing_panel(self):
        from qresearch.artifacts import MemoryArtifactStore
        class EmptyProvider:
            def fetch(self, request):
                return pd.DataFrame(columns=RECORD_COLUMNS)
        cache = SharedDataCache(MemoryArtifactStore(), EmptyProvider())
        cache.prefetch(self.request())
        self.assertTrue(cache.read(self.request()).empty)

    def test_failed_fetch_is_not_retried_by_adding_a_field(self):
        from qresearch.artifacts import MemoryArtifactStore
        class FailingProvider(FixtureProvider):
            def fetch(self, request):
                self.calls += 1
                raise ConnectionError("synthetic unresolved fetch")
        provider = FailingProvider()
        cache = SharedDataCache(MemoryArtifactStore(), provider)
        with self.assertRaises(ConnectionError):
            cache.prefetch(self.request())
        with self.assertRaises(RuntimeError):
            cache.prefetch(self.request(fields=("close", "volume")))
        self.assertEqual(provider.calls, 1)

    def test_request_plan_merges_fields_symbols_and_periods(self):
        merged = merge_requests([self.request(), self.request(fields=("open",), sids=("C",))])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].fields, ("close", "open"))
        self.assertEqual(merged[0].sids, ("A", "B", "C"))

    def test_holdout_and_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            self.request(end=datetime(2024, 1, 2, tzinfo=NY))
        with self.assertRaises(ValueError):
            self.request(fields=("label_return",))
        with self.assertRaises(ValueError):
            self.request(start=datetime(2018, 1, 1))

    def test_each_historical_row_uses_own_vintage(self):
        records = pd.DataFrame([
            ["A", "fundamental", ts(1), ts(2, 18), 10., "v1"],
            ["A", "fundamental", ts(1), ts(4, 18), 99., "v2"],
            ["A", "close", ts(2), ts(2, 18), 20., "v1"],
            ["A", "close", ts(4), ts(4, 18), 40., "v1"]], columns=RECORD_COLUMNS)
        times = [ts(3, 9), ts(4, 9), ts(5, 9)]
        expected = pd.Series([ts(2), ts(3), ts(4)], index=times)
        window = causal_window(records, times, ("A",), {"fundamental": "latest_available", "close": "exact_session"},
                               expected, {"fundamental": "30d"})
        self.assertEqual(list(window.matrices["fundamental"].A), [10., 10., 99.])
        self.assertTrue(pd.isna(window.matrices["close"].A.iloc[1]))
        self.assertEqual(window.matrices["close"].A.iloc[-1], 40.)

    def test_missing_session_not_compressed_and_no_financial_filter(self):
        sessions = [ts(2), ts(3), ts(4)]
        rows = []
        for sid, value in [("A", 50.), ("B", 40.), ("C", 100.), ("ETF", 1000.)]:
            for session in sessions:
                if sid == "C" and session == sessions[1]:
                    continue
                rows.append([sid, session, session, value, "etf" if sid == "ETF" else "common_stock", True])
        frame = pd.DataFrame(rows, columns=["sid", "session", "available_at", "dollar_volume", "instrument_type", "listed"])
        selected = select_liquid_universe(frame, ts(5, 9), sessions, size=2, lookback=3)
        self.assertEqual(selected, ("A", "B"))
        with self.assertRaises(ValueError):
            select_liquid_universe(frame, ts(5, 9), sessions, size=3, lookback=3)


if __name__ == "__main__":
    unittest.main()
