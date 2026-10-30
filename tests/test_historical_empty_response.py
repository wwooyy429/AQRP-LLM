"""Known empty sentinel and rejected near-misses; synthetic provider only."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.collection import CollectionError, CollectionInterrupted, HistoricalCollectionPlan, HistoricalSnapshotCollector
from qresearch.historical_source import HistoricalSourceError, QuantConnectSnapshotSource
from test_historical_source import CATALOG, FakeQB, native, response, ts


class HistoricalEmptyResponseTests(unittest.TestCase):
    def plan(self, start="2018-01-01", end="2018-01-02"):
        return HistoricalCollectionPlan.from_dict(dict(schema_version=1, plan_id="SYNTHETIC-EMPTY-RESPONSE",
            scope="engineering", source="quantconnect_fundamental_universe", data_version="synthetic-v1",
            start=ts(start).isoformat(), end_exclusive=ts(end).isoformat(), timezone="America/New_York",
            fields=list(CATALOG), calendar_days_per_request=1, max_batch_records=10,
            max_records_per_window=20, source_manifest_hash="a" * 64), field_catalog=CATALOG)

    def source(self, qb):
        return QuantConnectSnapshotSource(qb, CATALOG, api=NS(Resolution=NS(DAILY="synthetic_daily")))

    def assert_uncertified(self, receipt, source):
        for name in ("full_historical_US200_certified", "actual_availability_certified", "research_certified"):
            self.assertIs(receipt[name], False)
        for name in ("full_historical_US200_certified", "actual_availability_certified",
                     "vendor_revision_certified", "financial_field_coverage_certified"):
            self.assertIs(source.provenance()[name], False)

    def test_ordinary_zero_by_zero_sentinels_are_empty_observations(self):
        fixtures = [pd.DataFrame(), pd.DataFrame(index=pd.Index([], dtype=object), columns=pd.Index([], dtype=object)),
            pd.DataFrame(index=pd.RangeIndex(0), columns=pd.RangeIndex(0))]
        for data in fixtures:
            with self.subTest(index_type=type(data.index).__name__):
                qb, store = FakeQB(data), MemoryArtifactStore()
                source = self.source(qb)
                collector = HistoricalSnapshotCollector(store, source, self.plan(), synthetic=True)
                receipt = collector.collect()
                self.assertEqual(receipt["record_count"], 0)
                self.assertEqual(receipt["empty_windows"], 1)
                self.assertEqual(receipt["provider_calls"], 1)
                self.assertEqual(collector.read_window(receipt["window_refs"][0]), [])
                self.assertEqual(source.history_call_count, 1)
                self.assertEqual(len(qb.calls), 1)
                self.assert_uncertified(receipt, source)

    def test_empty_window_is_immutable_cache_and_cache_only_reuses_without_call(self):
        qb, store, plan = FakeQB(pd.DataFrame()), MemoryArtifactStore(), self.plan()
        source = self.source(qb)
        first = HistoricalSnapshotCollector(store, source, plan, synthetic=True).collect()
        before = deepcopy(store._data)
        reader = HistoricalSnapshotCollector(store, None, plan, synthetic=True)
        second = reader.collect()
        self.assertEqual(second["provider_calls"], 0)
        self.assertEqual(second["reused_windows"], 1)
        self.assertEqual(second["empty_windows"], 1)
        self.assertEqual(first["window_refs"], second["window_refs"])
        self.assertEqual(reader.read_window(second["window_refs"][0]), [])
        self.assertEqual(store._data, before)
        self.assertEqual(source.history_call_count, 1)
        self.assertEqual(len(qb.calls), 1)

    def test_weekday_empty_observation_does_not_certify_coverage(self):
        qb, store = FakeQB(pd.DataFrame()), MemoryArtifactStore()
        source = self.source(qb)
        receipt = HistoricalSnapshotCollector(store, source, self.plan("2018-01-03", "2018-01-04"), synthetic=True).collect()
        self.assertEqual(receipt["empty_windows"], 1)
        self.assertEqual(receipt["record_count"], 0)
        self.assert_uncertified(receipt, source)
        self.assertNotIn("expected_session_count", receipt)
        self.assertNotIn("coverage_certified", receipt)

    def test_empty_first_window_does_not_skip_following_series(self):
        class SplitQB(FakeQB):
            def universe_history(inner, universe, start, end, *, flatten):
                inner.calls.append((universe, start, end, flatten))
                return pd.DataFrame() if len(inner.calls) == 1 else response([native()], "2018-01-02")
        qb, store = SplitQB(), MemoryArtifactStore()
        source = self.source(qb)
        collector = HistoricalSnapshotCollector(store, source, self.plan("2018-01-01", "2018-01-03"), synthetic=True)
        receipt = collector.collect()
        self.assertEqual(receipt["window_count"], 2)
        self.assertEqual(receipt["empty_windows"], 1)
        self.assertEqual(receipt["record_count"], 1)
        self.assertEqual(receipt["provider_calls"], 2)
        self.assertEqual(collector.read_window(receipt["window_refs"][0]), [])
        self.assertEqual(len(collector.read_window(receipt["window_refs"][1])), 1)
        self.assertEqual(source.history_call_count, 2)
        self.assert_uncertified(receipt, source)

    def test_nonempty_or_unknown_dataframe_shapes_remain_rejected_and_redacted(self):
        frames = [pd.DataFrame({"LICENSED-COLUMN": ["LICENSED-VALUE"]}),
            pd.DataFrame(columns=["LICENSED-COLUMN"]), pd.DataFrame(index=["LICENSED-INDEX"]),
            pd.DataFrame(index=pd.Index([], name="LICENSED-INDEX-NAME")),
            pd.DataFrame(columns=pd.Index([], name="LICENSED-COLUMN-NAME")),
            pd.DataFrame(index=pd.MultiIndex.from_tuples([], names=["symbol", "time"])),
            pd.DataFrame(columns=pd.MultiIndex.from_tuples([], names=["LICENSED-COLUMN", "other"])),
            pd.DataFrame(index=pd.DatetimeIndex([])), pd.DataFrame(index=pd.CategoricalIndex([]))]
        class UnknownFrame(pd.DataFrame):
            pass
        frames.append(UnknownFrame())
        for data in frames:
            with self.subTest(shape=data.shape, index_type=type(data.index).__name__):
                qb, store = FakeQB(data), MemoryArtifactStore()
                source = self.source(qb)
                collector = HistoricalSnapshotCollector(store, source, self.plan(), synthetic=True)
                with self.assertRaises(CollectionError) as caught:
                    collector.collect()
                message = str(caught.exception)
                self.assertNotIn("LICENSED", message)
                diagnostic = json.loads(message.split("; diagnostic=", 1)[1])
                self.assertEqual(diagnostic["stage"], "response_contract")
                self.assertEqual(diagnostic["response_kind"], "dataframe")
                self.assertFalse(any("/windows/" in key for key in store._data))
                with self.assertRaises(CollectionInterrupted):
                    collector.collect()
                self.assertEqual(source.history_call_count, 1)

    def test_series_contract_stays_strict_including_empty_series(self):
        invalid = [pd.Series(dtype=object), pd.Series([], index=pd.Index([], name="time"), dtype=object),
            pd.Series([], index=pd.MultiIndex.from_tuples([], names=["symbol", "wrong"]), dtype=object),
            pd.Series([], index=pd.MultiIndex.from_tuples([], names=["a", "b", "c"]), dtype=object)]
        for data in invalid:
            with self.subTest(index_type=type(data.index).__name__), self.assertRaises(HistoricalSourceError):
                list(self.source(FakeQB(data)).fetch(ts("2018-01-01"), ts("2018-01-02"), CATALOG))
        valid = pd.Series([], index=pd.MultiIndex.from_tuples([], names=["symbol", "time"]), dtype=object)
        self.assertEqual(list(self.source(FakeQB(valid)).fetch(ts("2018-01-01"), ts("2018-01-02"), CATALOG)), [])


if __name__ == "__main__":
    unittest.main()
