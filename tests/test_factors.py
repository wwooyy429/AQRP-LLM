"""Synthetic engineering checks; none of these tests constitute market evidence."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.contracts import PITWindow, RECORD_COLUMNS, validate_records
from qresearch.factors import (FactorSpec, FactorValidationError, evaluate_factors,
                               structure_similarity)
from qresearch.evaluation import (EvaluationError, build_fold_splits, daily_rank_ic,
                                  paired_factor_correlation, pairwise_factor_correlations,
                                  six_rolling_folds, summarize_ic, walk_forward_evaluate)


def stamp(text):
    return pd.Timestamp(text, tz="America/New_York")


def specification(formula=None, factor_id="synthetic"):
    return {
        "schema_version": 1, "factor_id": factor_id,
        "economic_hypothesis": {
            "mechanism": "Synthetic mechanism for engineering validation only",
            "expected_direction": 1, "prediction_horizon_sessions": 5,
            "applicable_regimes": ["Synthetic environment"],
            "failure_conditions": ["Synthetic failure condition"],
        },
        "allowed_fields": ["close", "volume"],
        "allowed_operators": ["add", "subtract", "multiply", "safe_divide", "positive_log",
                              "positive_session_lag", "trailing_mean", "trailing_std",
                              "trailing_correlation", "cross_section_rank", "cross_section_zscore"],
        "parameters": {},
        "formula": formula if formula is not None else {"op": "field", "name": "close"},
    }


def window(close=None, volume=None):
    times = pd.date_range("2018-01-02 16:00", periods=4, tz="America/New_York")
    columns = ["A", "B", "C"]
    close = [[1, 2, 4], [2, 4, 8], [3, 6, 12], [4, 8, 16]] if close is None else close
    volume = [[4, 3, 2], [3, 2, 1], [2, 1, 4], [1, 4, 3]] if volume is None else volume
    return PITWindow(times[-1], {"close": pd.DataFrame(close, index=times, columns=columns),
                                 "volume": pd.DataFrame(volume, index=times, columns=columns)}, tuple(columns))


class FactorEngineTests(unittest.TestCase):
    def test_economic_and_field_operator_contracts(self):
        for key, value in (("mechanism", ""), ("expected_direction", True),
                           ("prediction_horizon_sessions", 0), ("applicable_regimes", []),
                           ("failure_conditions", [])):
            raw = specification()
            raw["economic_hypothesis"][key] = value
            with self.subTest(key=key), self.assertRaises(FactorValidationError):
                FactorSpec.from_dict(raw)
        for field in ("label", "target_return", "future.price", "forward_return"):
            raw = specification({"op": "field", "name": field})
            raw["allowed_fields"] = [field]
            with self.subTest(field=field), self.assertRaises(FactorValidationError):
                FactorSpec.from_dict(raw)
        with self.assertRaises(FactorValidationError):
            FactorSpec.from_dict(specification(), field_catalog=["volume"])
        raw = specification({"op": "positive_log", "arg": {"op": "field", "name": "close"}})
        raw["allowed_operators"] = []
        with self.assertRaises(FactorValidationError):
            FactorSpec.from_dict(raw)
        with self.assertRaises(FactorValidationError):
            FactorSpec.from_dict(specification({"op": "__import__", "args": ["os"]}))

    def test_lag_window_and_json_bounds(self):
        field = {"op": "field", "name": "close"}
        bad = [{"op": "lag", "arg": field, "periods": -1},
               {"op": "lag", "arg": field, "periods": 0},
               {"op": "lag", "arg": field, "periods": True},
               {"op": "rolling_mean", "arg": field, "window": 100000},
               {"op": "rolling_mean", "arg": field, "window": 3, "min_periods": 1},
               {"op": "rolling_std", "arg": field, "window": 1},
               {"op": "safe_divide", "args": [field, 1e20]},
               "__import__('os').system('echo unapproved')"]
        for formula in bad:
            with self.subTest(formula=formula), self.assertRaises(FactorValidationError):
                FactorSpec.from_dict(specification(formula))
        raw = specification(float("inf"))
        with self.assertRaises(FactorValidationError):
            FactorSpec.from_dict(raw)

    def test_commutative_alias_hash_and_configuration_change(self):
        first = specification({"op": "add", "args": [
            {"op": "field", "field": "close"}, {"op": "field", "name": "volume"}]})
        second = deepcopy(first)
        second["formula"]["args"].reverse()
        a, b = FactorSpec.from_dict(first), FactorSpec.from_dict(second)
        self.assertEqual(a.configuration_hash, b.configuration_hash)
        self.assertEqual(a.structure_hash, b.structure_hash)
        second["economic_hypothesis"]["expected_direction"] = -1
        c = FactorSpec.from_dict(second)
        self.assertNotEqual(a.configuration_hash, c.configuration_hash)
        self.assertEqual(a.structure_hash, c.structure_hash)
        report = structure_similarity(a, c)
        self.assertEqual(report["subtree_dice"], 1)
        self.assertFalse(report["economic_equivalence_proven"])
        lag = specification({"op": "positive_session_lag", "arg": {"op": "field", "name": "close"}, "periods": 2})
        canonical_lag = deepcopy(lag)
        canonical_lag["formula"]["op"] = "lag"
        self.assertEqual(FactorSpec.from_dict(lag).configuration_hash,
                         FactorSpec.from_dict(canonical_lag).configuration_hash)

    def test_full_rolling_and_positive_lag_are_causal(self):
        spec = FactorSpec.from_dict(specification({"op": "rolling_mean", "window": 3,
            "arg": {"op": "lag", "periods": 1, "arg": {"op": "field", "name": "close"}}}))
        self.assertEqual(spec.lookback_sessions, 3)
        np.testing.assert_allclose(spec.evaluate(window()).to_numpy(), [2, 4, 8])
        short = window()
        short = PITWindow(short.as_of, {name: frame.iloc[-2:] for name, frame in short.matrices.items()}, short.sids)
        self.assertTrue(spec.evaluate(short).isna().all())
        missing = window(close=[[1, 2, 4], [2, None, 8], [3, 6, 12], [4, 8, 16]])
        self.assertTrue(np.isnan(spec.evaluate(missing)["B"]))

    def test_safe_divide_logs_rank_and_all_missing(self):
        field = {"op": "field", "name": "close"}
        ratio = FactorSpec.from_dict(specification({"op": "safe_divide", "args": [field, 0]}))
        self.assertTrue(ratio.evaluate(window()).isna().all())
        log = FactorSpec.from_dict(specification({"op": "positive_log", "arg": field}))
        out = log.evaluate(window(close=[[1, 2, 3]] * 3 + [[-1, 0, np.e]]))
        self.assertTrue(out.iloc[:2].isna().all())
        self.assertAlmostEqual(out.iloc[2], 1)
        rank = FactorSpec.from_dict(specification({"op": "rank", "arg": field}))
        np.testing.assert_allclose(rank.evaluate(window()).to_numpy(), [1 / 3, 2 / 3, 1])
        missing = window(close=[[np.nan] * 3] * 4)
        self.assertTrue(rank.evaluate(missing).isna().all())

    def test_shared_window_batch_no_mutation_and_empty(self):
        source = window()
        before = source.matrices["close"].copy()
        a = FactorSpec.from_dict(specification())
        b = FactorSpec.from_dict(specification({"op": "multiply", "args": [
            {"op": "field", "name": "close"}, 2]}, "doubled"))
        actual = evaluate_factors([a, b], source)
        np.testing.assert_allclose(actual["doubled"], 2 * actual["synthetic"])
        pd.testing.assert_frame_equal(before, source.matrices["close"])
        empty = PITWindow(source.as_of, {name: frame.iloc[:0] for name, frame in source.matrices.items()}, source.sids)
        self.assertTrue(a.evaluate(empty).isna().all())
        with self.assertRaises(FactorValidationError):
            evaluate_factors([a, a], source)

    def test_future_and_malformed_window_are_rejected(self):
        source = window()
        unsafe = SimpleNamespace(as_of=source.matrices["close"].index[0], matrices=source.matrices, sids=source.sids)
        with self.assertRaises(FactorValidationError):
            FactorSpec.from_dict(specification()).evaluate(unsafe)
        unsafe = SimpleNamespace(as_of=stamp("2024-01-01"), matrices=source.matrices, sids=source.sids)
        with self.assertRaises(FactorValidationError):
            FactorSpec.from_dict(specification()).evaluate(unsafe)
        with self.assertRaises(ValueError):
            PITWindow(source.matrices["close"].index[0], source.matrices, source.sids)

    def test_historical_cross_sections_use_their_own_membership(self):
        source = window()
        members = pd.DataFrame([[True, True, False]] * 3 + [[False, True, True]],
                               index=source.matrices["close"].index, columns=source.sids)
        scoped = PITWindow(source.as_of, source.matrices, source.sids, members)
        for cross_section in ("rank", "zscore"):
            raw = specification({"op": "lag", "periods": 1,
                                  "arg": {"op": cross_section, "arg": {"op": "field", "name": "close"}}})
            spec = FactorSpec.from_dict(raw)
            self.assertTrue(spec.requires_historical_membership)
            with self.assertRaises(FactorValidationError):
                spec.evaluate(source)
            actual = spec.evaluate(scoped)
            self.assertEqual(list(actual.index), ["B", "C"])
            self.assertAlmostEqual(actual["B"], 1.)
            self.assertTrue(np.isnan(actual["C"]))
        members.loc[:, "B"] = False
        self.assertTrue(scoped.universe_membership.B.all())  # Defensive copy.

    def test_entrant_keeps_raw_history_and_final_output_is_current_pool(self):
        source = window()
        members = pd.DataFrame([[True, True, False]] * 3 + [[False, True, True]],
                               index=source.matrices["close"].index, columns=source.sids)
        scoped = PITWindow(source.as_of, source.matrices, source.sids, members)
        spec = FactorSpec.from_dict(specification({"op": "rolling_mean", "window": 3,
                                                  "arg": {"op": "field", "name": "close"}}))
        actual = evaluate_factors([spec], scoped)
        self.assertEqual(list(actual.index), ["B", "C"])
        self.assertEqual(actual.loc["C", "synthetic"], 12.)
        pd.testing.assert_frame_equal(scoped.matrices["close"], source.matrices["close"])

    def test_membership_shape_values_and_simultaneous_vintages_fail_closed(self):
        source = window()
        members = pd.DataFrame(True, index=source.matrices["close"].index, columns=source.sids)
        for malformed in (members.iloc[:-1], members.astype(int), members.iloc[:, :-1]):
            with self.subTest(shape=malformed.shape), self.assertRaises(ValueError):
                PITWindow(source.as_of, source.matrices, source.sids, malformed)
        event = stamp("2018-01-02 16:00")
        records = pd.DataFrame([["A", "close", event, event, 10., "v10"],
                                ["A", "close", event, event, 2., "v2"]], columns=RECORD_COLUMNS)
        with self.assertRaisesRegex(ValueError, "Ambiguous simultaneous vintages"):
            validate_records(records)
        empty = validate_records(pd.DataFrame(columns=RECORD_COLUMNS))
        self.assertIsNotNone(empty.event_time.dt.tz)
        self.assertIsNotNone(empty.available_time.dt.tz)

    def test_rolling_statistics_have_fixed_complete_window_conventions(self):
        field = {"op": "field", "name": "close"}
        std = FactorSpec.from_dict(specification({"op": "rolling_std", "arg": field, "window": 3}))
        np.testing.assert_allclose(std.evaluate(window()), [1, 2, 4])
        corr = FactorSpec.from_dict(specification({"op": "rolling_corr", "window": 3,
            "args": [field, {"op": "field", "name": "volume"}]}))
        self.assertAlmostEqual(corr.evaluate(window())["A"], -1)
        zscore = FactorSpec.from_dict(specification({"op": "zscore", "arg": field}))
        raw = np.array([4., 8., 16.])
        np.testing.assert_allclose(zscore.evaluate(window()), (raw - raw.mean()) / raw.std(ddof=0))


def record(year, sid="A", x=1., label=None, date=None, entry=None, exit=None, available=None):
    date = date or f"{year}-01-02 16:00"
    entry = entry or f"{year}-01-03 09:31"
    exit = exit or f"{year}-01-08 16:00"
    available = available or f"{year}-01-08 17:00"
    return {"sid": sid, "formation_at": stamp(date), "entry_at": stamp(entry),
            "exit_at": stamp(exit), "label_available_at": stamp(available),
            "x": x, "realized": year + x / 100 if label is None else label}


def all_records():
    return pd.DataFrame([record(year, sid, x) for year in range(2010, 2024)
                         for sid, x in zip(("A", "B", "C"), (1., 2., 3.))])


class EvaluationTests(unittest.TestCase):
    def test_exact_registered_rolling_windows_drop_oldest_year(self):
        folds = six_rolling_folds()
        self.assertEqual(len(folds), 6)
        self.assertEqual((folds[0].train_start.year, folds[0].validation_start.year), (2010, 2018))
        self.assertEqual((folds[-1].train_start.year, folds[-1].validation_start.year), (2015, 2023))
        data = pd.concat([all_records(), pd.DataFrame([record(2009)])], ignore_index=True)
        for fold in folds:
            split = build_fold_splits(data, fold)
            self.assertEqual(len(split.train), 24)
            self.assertEqual(len(split.validation), 3)
            self.assertEqual(split.train.formation_at.dt.year.min(), fold.train_start.year)
            self.assertEqual(split.train.formation_at.dt.year.max(), fold.train_end.year - 1)
            self.assertEqual(set(split.validation.formation_at.dt.year), {fold.validation_start.year})

    def test_label_maturity_and_actual_entry_exit_purging(self):
        extra = [record(2017, "immature", date="2017-12-20 16:00", entry="2017-12-21 09:31",
                        exit="2017-12-28 16:00", available="2018-01-02 17:00"),
                 record(2017, "entry_crossing", date="2017-12-30 16:00", entry="2018-01-02 09:31",
                        exit="2018-01-05 16:00", available="2018-01-05 17:00"),
                 record(2018, "validation_crossing", date="2018-12-20 16:00", entry="2018-12-21 09:31",
                        exit="2019-01-03 16:00", available="2019-01-03 17:00"),
                 record(2023, "test_crossing", date="2023-12-20 16:00", entry="2023-12-21 09:31",
                        exit="2024-01-03 16:00", available="2024-01-03 17:00")]
        data = pd.concat([all_records(), pd.DataFrame(extra)], ignore_index=True)
        first = build_fold_splits(data, six_rolling_folds()[0])
        self.assertEqual(first.excluded_train, 2)
        self.assertEqual(first.excluded_validation, 1)
        self.assertNotIn("immature", set(first.train.sid))
        second = build_fold_splits(data, six_rolling_folds()[1])
        self.assertIn("immature", set(second.train.sid))
        final = build_fold_splits(data, six_rolling_folds()[-1])
        self.assertNotIn("test_crossing", set(final.validation.sid))

    def test_final_test_and_naive_times_fail_closed(self):
        with self.assertRaises(EvaluationError):
            build_fold_splits(pd.DataFrame([record(2024)]), six_rolling_folds()[0])
        data = all_records()
        data["entry_at"] = data.entry_at.dt.tz_localize(None)
        with self.assertRaises(EvaluationError):
            build_fold_splits(data, six_rolling_folds()[0])

    def test_each_fold_gets_fresh_fit_and_exact_predictions(self):
        instances = []
        class InjectedModel:
            def __init__(self):
                instances.append(self)
                self.fit_calls = 0
            def fit(self, features, labels):
                self.fit_calls += 1
                self.labels = labels.copy()
                self.feature_columns = list(features.columns)
            def predict(self, features):
                return features.x.to_numpy()
        result = walk_forward_evaluate(all_records(), ["x"], "realized", InjectedModel)
        self.assertEqual(len(instances), 6)
        self.assertEqual([m.fit_calls for m in instances], [1] * 6)
        self.assertEqual([int(m.labels.min()) for m in instances], list(range(2010, 2016)))
        self.assertEqual([m.feature_columns for m in instances], [["x"]] * 6)
        self.assertEqual(list(result.folds.train_n), [24] * 6)
        self.assertEqual(list(result.daily_ic.n), [3] * 6)
        np.testing.assert_allclose(result.daily_ic.ic, np.ones(6))
        self.assertEqual(result.ic_statistics["valid_days"], 6)
        self.assertAlmostEqual(result.ic_statistics["mean_ic"], 1)
        self.assertTrue(np.isnan(result.ic_statistics["icir"]))
        reused = InjectedModel()
        with self.assertRaises(EvaluationError):
            walk_forward_evaluate(all_records(), ["x"], "realized", lambda: reused)

    def test_ic_and_correlations_use_common_samples_and_sample_icir(self):
        data = pd.DataFrame({"formation_at": [stamp("2018-01-02 16:00")] * 4
                             + [stamp("2018-01-03 16:00")] * 3,
                             "sid": ["A", "B", "C", "D", "A", "B", "C"],
                             "prediction": [1, 2, 3, 4, 1, 2, 3],
                             "label": [1, 2, 3, np.nan, 3, 2, 1]})
        data.index = [0] * len(data)  # Row labels must not accidentally multiply samples.
        daily = daily_rank_ic(data)
        self.assertEqual(list(daily.n), [3, 3])
        np.testing.assert_allclose(daily.ic, [1., -1.])
        stats = summarize_ic(daily)
        self.assertAlmostEqual(stats["sample_std_ic"], np.sqrt(2))
        self.assertEqual(stats["icir"], 0)
        self.assertFalse(stats["icir_annualized"])
        left = pd.Series([1, 2, np.nan, 4], index=list("ABCD"))
        right = pd.Series([8, 6, 0, np.inf], index=list("ABCE"))
        for method in ("pearson", "spearman"):
            result = paired_factor_correlation(left, right, method)
            self.assertEqual(result["n"], 2)
            self.assertAlmostEqual(result["absolute_correlation"], 1)
        matrix = pairwise_factor_correlations(pd.DataFrame({"left": left, "right": right}))
        self.assertEqual(matrix["n"].loc["left", "right"], 2)
        self.assertAlmostEqual(matrix["absolute_spearman"].loc["left", "right"], 1)


if __name__ == "__main__":
    unittest.main()
