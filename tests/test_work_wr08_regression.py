"""WR-08 developer regressions for synthetic IC summaries and integration.

Fraction moments describe the actual binary64 inputs; Decimal supplies an
independent square-root oracle. The registered-chain fixture reuses the
repository author's Study/transaction templates, not independent audit inputs.
These tests do not access market data or establish financial effectiveness.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import unittest

import numpy as np
import pandas as pd

from qresearch.artifacts import MemoryArtifactStore
from qresearch.contracts import NY
from qresearch.evaluation import daily_rank_ic, summarize_ic, walk_forward_evaluate
from qresearch.pipeline import evaluate_registered_study
from test_pipeline import complete_study, roundtrip_rows


def exact_summary(values):
    numbers = [Fraction.from_float(float(value)) for value in values]
    if not numbers:
        return math.nan, math.nan, math.nan
    mean = sum(numbers) / len(numbers)
    if len(numbers) == 1:
        return float(mean), math.nan, math.nan
    variance = sum((value - mean) ** 2 for value in numbers) / (len(numbers) - 1)
    if variance == 0:
        return float(mean), 0.0, math.nan
    with localcontext() as context:
        context.prec = 160
        std = (Decimal(variance.numerator) / Decimal(variance.denominator)).sqrt()
        ratio = (Decimal(mean.numerator) / Decimal(mean.denominator)) / std
    return float(mean), float(std), float(ratio)


def daily_frame(values, counts=None):
    return pd.DataFrame({"ic": list(values), "n": [5] * len(values) if counts is None else counts})


def five_name_records():
    rows = []
    for year in range(2010, 2024):
        formation = pd.Timestamp(f"{year}-06-01 09:00", tz=NY)
        for number, label in enumerate((1., 2., 4., 5., 3.), start=1):
            rows.append({"sid": f"SID-{number}", "formation_at": formation,
                "entry_at": formation + pd.Timedelta(hours=1),
                "exit_at": formation + pd.Timedelta(days=1, hours=1),
                "label_available_at": formation + pd.Timedelta(days=1, hours=2),
                "score": float(number), "realized": label})
    return pd.DataFrame(rows)


class WR08ICSummaryTests(unittest.TestCase):
    def assert_numerical_summary(self, values):
        expected_mean, expected_std, expected_icir = exact_summary(values)
        result = summarize_ic(daily_frame(values))
        self.assertEqual(result["mean_ic"], expected_mean)
        if math.isnan(expected_std):
            self.assertTrue(math.isnan(result["sample_std_ic"]))
        elif expected_std == 0:
            self.assertEqual(result["sample_std_ic"], 0.)
        else:
            self.assertGreater(result["sample_std_ic"], 0.)
            self.assertTrue(math.isclose(result["sample_std_ic"], expected_std,
                rel_tol=5e-15, abs_tol=0.), (result, expected_std))
        if math.isnan(expected_icir):
            self.assertTrue(math.isnan(result["icir"]))
        else:
            self.assertTrue(math.isclose(result["icir"], expected_icir,
                rel_tol=5e-15, abs_tol=0.), (result, expected_icir))
        self.assertFalse(result["icir_annualized"])
        self.assertEqual(result["valid_days"], len(values))
        self.assertEqual(result["total_days"], len(values))
        self.assertEqual(result["common_observations"], 5 * len(values))
        return result

    def test_positive_constant_nonperfect_ic_is_exactly_zero_variance(self):
        for count in (2, 3, 6, 7, 30, 252):
            with self.subTest(days=count):
                self.assert_numerical_summary([.7] * count)

    def test_negative_constant_nonperfect_ic_is_exactly_zero_variance(self):
        for count in (2, 3, 6, 7, 30, 252):
            with self.subTest(days=count):
                self.assert_numerical_summary([-.7] * count)

    def test_zero_constant_ic_has_undefined_ratio(self):
        for count in (2, 6, 13):
            with self.subTest(days=count):
                self.assert_numerical_summary([0.] * count)

    def test_other_identical_binary_float_values_remain_constant(self):
        for value in (.1, .3, -.2, 1., -1.):
            for count in (6, 13):
                with self.subTest(value=value, days=count):
                    self.assert_numerical_summary([value] * count)

    def test_zero_valid_days_and_empty_input_have_undefined_statistics(self):
        for values in ([], [math.nan, math.inf, -math.inf]):
            with self.subTest(values=values):
                result = summarize_ic(daily_frame(values))
                self.assertEqual(result["valid_days"], 0)
                self.assertEqual(result["total_days"], len(values))
                self.assertEqual(result["common_observations"], 5 * len(values))
                for field in ("mean_ic", "sample_std_ic", "icir"):
                    self.assertTrue(math.isnan(result[field]))
                self.assertFalse(result["icir_annualized"])

    def test_one_valid_day_keeps_mean_but_has_undefined_sample_std(self):
        result = summarize_ic(daily_frame([math.nan, .7, math.inf], [3, 7, 11]))
        self.assertEqual(result["valid_days"], 1)
        self.assertEqual(result["total_days"], 3)
        self.assertEqual(result["mean_ic"], .7)
        self.assertTrue(math.isnan(result["sample_std_ic"]))
        self.assertTrue(math.isnan(result["icir"]))
        self.assertEqual(result["common_observations"], 21)

    def test_missing_and_infinite_days_preserve_existing_count_rules(self):
        result = summarize_ic(daily_frame([.7, math.nan, math.inf, .7, -math.inf, .7],
                                         [5, 7, 9, 11, 13, 17]))
        self.assertEqual(result["valid_days"], 3)
        self.assertEqual(result["total_days"], 6)
        self.assertEqual(result["common_observations"], 62)
        self.assertEqual(result["mean_ic"], .7)
        self.assertEqual(result["sample_std_ic"], 0.)
        self.assertTrue(math.isnan(result["icir"]))

    def test_nonconstant_hand_answer_uses_sample_ddof_one(self):
        # For [0, 1/2, 1], mean=1/2, sample variance=1/4, ICIR=1.
        result = self.assert_numerical_summary([0., .5, 1.])
        self.assertEqual(result["sample_std_ic"], .5)
        self.assertEqual(result["icir"], 1.)

    def test_adjacent_floats_have_real_nonzero_variance_without_threshold(self):
        for value, direction in ((.7, math.inf), (-.7, -math.inf)):
            adjacent = np.nextafter(value, direction)
            for values in ([value, adjacent], [value, adjacent] * 3):
                with self.subTest(value=value, days=len(values)):
                    self.assert_numerical_summary(values)

    def test_small_but_nonzero_ic_scale_is_not_rounded_to_constant(self):
        self.assert_numerical_summary([1e-200, 2e-200, 3e-200])

    def test_subnormal_real_variation_is_not_discarded_by_variance_squaring(self):
        smallest = float(np.nextafter(0., 1.))
        self.assert_numerical_summary([0., smallest])

    def test_permutation_preserves_micro_variance_and_mean(self):
        low = .7
        high = float(np.nextafter(low, math.inf))
        highest = float(np.nextafter(high, math.inf))
        values = [low, high, low, high, highest, low]
        first = self.assert_numerical_summary(values)
        for order in (list(reversed(values)), [values[i] for i in (2, 5, 4, 0, 3, 1)]):
            result = self.assert_numerical_summary(order)
            self.assertEqual(result["mean_ic"], first["mean_ic"])
            self.assertTrue(math.isclose(result["sample_std_ic"], first["sample_std_ic"],
                                        rel_tol=5e-15, abs_tol=0.))

    def test_daily_rank_ic_to_summary_reproduces_seven_tenths_constant(self):
        rows = []
        for day in range(1, 7):
            for sid, label in enumerate((1., 2., 4., 5., 3.), start=1):
                rows.append({"formation_at": pd.Timestamp(f"2018-06-{day:02d} 09:00", tz=NY),
                    "sid": str(sid), "prediction": float(sid), "label": label})
        daily = daily_rank_ic(pd.DataFrame(rows))
        np.testing.assert_array_equal(daily.ic.to_numpy(), [.7] * 6)
        result = summarize_ic(daily)
        self.assertEqual(result["mean_ic"], .7)
        self.assertEqual(result["sample_std_ic"], 0.)
        self.assertTrue(math.isnan(result["icir"]))
        self.assertEqual(result["common_observations"], 30)

    def test_walk_forward_statistics_do_not_publish_spurious_icir(self):
        class Identity:
            def fit(self, features, labels):
                pass
            def predict(self, features):
                return features.score.to_numpy()
        result = walk_forward_evaluate(five_name_records(), ["score"], "realized", Identity)
        np.testing.assert_array_equal(result.daily_ic.ic.to_numpy(), [.7] * 6)
        self.assertEqual(result.folds.train_n.tolist(), [40] * 6)
        self.assertEqual(len(result.predictions), 30)
        self.assertEqual(result.ic_statistics["sample_std_ic"], 0.)
        self.assertEqual(result.ic_statistics["mean_ic"], .7)
        self.assertTrue(math.isnan(result.ic_statistics["icir"]))

    def test_registered_study_statistics_preserve_constant_nonperfect_ic(self):
        # Reuse the author's valid synthetic execution schema, but supply a new
        # explicit five-name outcome pattern for every development year.
        _, templates = roundtrip_rows()
        features, trades = [], []
        for year in range(2010, 2024):
            base = templates.loc[templates.formation_at.dt.year == year].iloc[0].to_dict()
            for score, outcome in enumerate((1., 2., 4., 5., 3.), start=1):
                sid, trade_id = f"SID-{score}", f"wr08-{year}-{score}"
                features.append({"sid": sid, "formation_at": base["formation_at"],
                                 "fixture_factor": float(score)})
                trade = dict(base, sid=sid, trade_id=trade_id,
                    entry_execution_id=trade_id + "-buy", exit_execution_id=trade_id + "-sell",
                    entry_price=100., exit_price=100. + outcome,
                    entry_fee=0., exit_fee=0., other_costs=0., cash_distributions=0.)
                trades.append(trade)
        result = evaluate_registered_study(complete_study(), pd.DataFrame(features),
            pd.DataFrame(trades), audit_store=MemoryArtifactStore())
        np.testing.assert_array_equal(result.daily_ic.ic.to_numpy(), [.7] * 6)
        self.assertEqual(result.folds.train_n.tolist(), [40] * 6)
        self.assertEqual(len(result.model_artifacts), 6)
        self.assertEqual(len(result.predictions), 30)
        self.assertEqual(result.ic_statistics["mean_ic"], .7)
        self.assertEqual(result.ic_statistics["sample_std_ic"], 0.)
        self.assertTrue(math.isnan(result.ic_statistics["icir"]))


if __name__ == "__main__":
    unittest.main()
