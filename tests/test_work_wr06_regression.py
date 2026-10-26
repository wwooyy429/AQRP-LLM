"""WR-06 developer regressions; equivalent instants are not new data.

All prices, members and executions here are synthetic engineering fixtures.
These checks do not authorize a market execution or financial acceptance.
"""
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.cache import SharedDataCache
from qresearch.contracts import DataRequest, NY, PITWindow, RECORD_COLUMNS
from qresearch.pipeline import evaluate_registered_study
from qresearch.point_in_time import causal_window
from qresearch.runtime import ResearchEngine, execution_plan_identity
from qresearch.study import StudySpec
from test_pipeline import complete_study, roundtrip_rows


class TimezoneCompatibilityTests(unittest.TestCase):
    def setUp(self):
        # The string constructor is intentionally pandas' common pytz route;
        # no caller-side ZoneInfo workaround should be needed.
        self.times = pd.DatetimeIndex([
            pd.Timestamp("2018-03-09 09:00", tz="America/New_York"),
            pd.Timestamp("2018-03-12 09:00", tz="America/New_York")])
        self.events = {
            self.times[0]: pd.Timestamp("2018-03-08 16:00", tz="America/New_York"),
            self.times[1]: pd.Timestamp("2018-03-09 16:00", tz="America/New_York")}
        self.members = pd.DataFrame([[True, False], [True, True]],
                                    index=self.times, columns=["A", "B"])
        self.records = pd.DataFrame([
            [sid, "close", event, event, float(i + 1), "v1"]
            for event in self.events.values() for i, sid in enumerate(("A", "B"))],
            columns=RECORD_COLUMNS)
        self.request = DataRequest("synthetic", ("close",), ("A", "B"),
            pd.Timestamp("2018-01-01", tz=NY), pd.Timestamp("2019-01-01", tz=NY),
            "wr06-synthetic", "synthetic-members")

    def window(self, members=None, times=None):
        return causal_window(self.records, self.times if times is None else times,
            ("A", "B"), {"close": "exact_session"}, self.events,
            membership=self.members if members is None else members)

    def identity(self, members=None, times=None):
        return execution_plan_identity(self.request, self.times if times is None else times,
            ("A", "B"), {"close": "exact_session"}, self.events,
            membership=self.members if members is None else members)

    def test_common_pandas_new_york_members_are_accepted_without_adapter(self):
        original = self.members.copy(deep=True)
        result = self.window()
        self.assertEqual(list(result.matrices["close"].A), [1., 1.])
        self.assertIs(result.universe_membership.index.tz, NY)
        pd.testing.assert_frame_equal(self.members, original)

    def test_pytz_zoneinfo_utc_have_one_plan_identity_across_spring_dst(self):
        expected = self.identity()
        for zone in ("America/New_York", ZoneInfo("America/New_York"), "UTC"):
            with self.subTest(zone=repr(zone)):
                members = self.members.copy()
                members.index = members.index.tz_convert(zone)
                times = self.times.tz_convert(zone)
                self.assertEqual(self.identity(members, times), expected)
                result = self.window(members, times)
                self.assertEqual(result.matrices["close"].index[0].utcoffset().total_seconds(), -5 * 3600)
                self.assertEqual(result.matrices["close"].index[1].utcoffset().total_seconds(), -4 * 3600)

    def test_direct_pit_window_normalizes_all_features_and_members(self):
        close = pd.DataFrame(1., index=self.times, columns=["A", "B"])
        volume = close.copy()
        volume.index = volume.index.tz_convert("UTC")
        members = self.members.copy()
        members.index = members.index.tz_convert(ZoneInfo("America/New_York"))
        result = PITWindow(self.times[-1], {"close": close, "volume": volume}, ("A", "B"), members)
        self.assertTrue(result.matrices["close"].index.equals(result.matrices["volume"].index))
        self.assertTrue(result.universe_membership.index.equals(result.matrices["close"].index))
        self.assertIs(result.matrices["volume"].index.tz, NY)

    def test_fall_dst_two_distinct_instants_with_same_wall_clock_stay_distinct(self):
        times = pd.DatetimeIndex([pd.Timestamp("2018-11-04 05:30", tz="UTC"),
                                  pd.Timestamp("2018-11-04 06:30", tz="UTC")])
        event = pd.Timestamp("2018-11-03 16:00", tz="America/New_York")
        records = pd.DataFrame([["A", "close", event, event, 7., "v1"]], columns=RECORD_COLUMNS)
        members = pd.DataFrame(True, index=times.tz_convert("America/New_York"), columns=["A"])
        result = causal_window(records, times, ["A"], {"close": "exact_session"},
                               dict.fromkeys(times, event), membership=members)
        self.assertTrue(result.universe_membership.index.is_unique)
        self.assertEqual(result.universe_membership.index.hour.tolist(), [1, 1])
        self.assertNotEqual(result.universe_membership.index[0].utcoffset(),
                            result.universe_membership.index[1].utcoffset())

    def test_true_misalignment_duplicates_order_and_naive_members_still_fail(self):
        variants = []
        shifted = self.members.copy()
        shifted.index = shifted.index + pd.Timedelta(minutes=1)
        variants.append(shifted)
        duplicated = self.members.copy()
        duplicated.index = pd.DatetimeIndex([self.times[0], self.times[0]])
        variants.extend((duplicated, self.members.iloc[::-1], self.members.iloc[:-1]))
        naive = self.members.copy()
        naive.index = naive.index.tz_localize(None)
        variants.append(naive)
        for members in variants:
            for entry in (self.window, self.identity):
                with self.subTest(index=str(members.index), entry=entry.__name__), self.assertRaises(ValueError):
                    entry(members)

    def test_future_members_and_duplicate_sids_remain_invalid(self):
        frame = pd.DataFrame(1., index=self.times, columns=["A", "B"])
        future = self.members.copy()
        future.index = future.index + pd.Timedelta(days=7)
        with self.assertRaises(ValueError):
            PITWindow(self.times[-1], {"close": frame}, ("A", "B"), future)
        duplicated = pd.concat([self.members, self.members[["A"]]], axis=1)
        for entry in (self.window, self.identity):
            with self.subTest(entry=entry.__name__), self.assertRaises(ValueError):
                entry(duplicated)

    def test_cache_identity_and_result_are_reused_for_equivalent_timezone_input(self):
        rows = self.records
        class Provider:
            calls = 0
            def fetch(self, request):
                self.calls += 1
                return rows.copy()
        provider = Provider()
        cache = SharedDataCache(MemoryArtifactStore(), provider)
        engine = ResearchEngine(cache, synthetic=True)
        engine.prepare([self.request])
        spec = complete_study().factor_specs[0]
        arguments = ([spec], self.request, self.times, ("A", "B"),
                     {"close": "exact_session"}, self.events)
        first = engine.evaluate(*arguments, membership=self.members)
        members = self.members.copy()
        members.index = members.index.tz_convert("UTC")
        second = engine.evaluate(*arguments, membership=members)
        self.assertEqual(first, second)
        self.assertEqual(provider.calls, 1)

    def test_unadapted_pandas_members_run_cache_factor_label_sixfold_chain(self):
        study = complete_study()
        document = study.to_dict()
        document["factor_specs"][0]["formula"] = {"op": "field", "name": "close"}
        document.pop("component_hashes")  # Rebuild this new synthetic fixture's identities.
        study = StudySpec.from_dict(document, field_catalog=["close"])
        features, trades = roundtrip_rows()
        # Exercise the original failure route: pandas string-zone members.
        features["formation_at"] = features.formation_at.dt.tz_convert("America/New_York")
        rows, events = [], {}
        for row in features.itertuples():
            event = row.formation_at - pd.Timedelta(days=3)
            events[row.formation_at] = event
            rows.append([row.sid, "close", event, event, row.fixture_factor, "v1"])
        class Provider:
            calls = 0
            def fetch(self, request):
                self.calls += 1
                data = pd.DataFrame(rows, columns=RECORD_COLUMNS)
                return data[(data.event_time >= request.start) & (data.event_time < request.end)].copy()
        provider = Provider()
        cache = SharedDataCache(MemoryArtifactStore(), provider)
        engine = ResearchEngine(cache, synthetic=True)
        request = DataRequest("synthetic", ("close",), ("SID-A", "SID-B", "SID-C"),
            pd.Timestamp("2010-01-01", tz=NY), pd.Timestamp("2024-01-01", tz=NY),
            "synthetic-v1", "synthetic-members")
        engine.prepare([request])
        prefetch_calls = provider.calls
        generated = []
        for time in features.formation_at.unique():
            members = pd.DataFrame(True, index=pd.DatetimeIndex([time]), columns=request.sids)
            payload = engine.evaluate(study.factor_specs, request, [time], request.sids,
                {"close": "exact_session"}, {time: events[time]}, membership=members)
            for sid, values in zip(payload["values"]["index"], payload["values"]["data"]):
                generated.append({"sid": sid, "formation_at": time, "fixture_factor": values[0]})
        result = evaluate_registered_study(study, pd.DataFrame(generated), trades)
        self.assertEqual(len(result.folds), 6)
        self.assertEqual(result.folds.train_n.tolist(), [24] * 6)
        np.testing.assert_allclose(result.daily_ic.ic, [-1.] * 6)
        self.assertEqual(provider.calls, prefetch_calls)


if __name__ == "__main__":
    unittest.main()
