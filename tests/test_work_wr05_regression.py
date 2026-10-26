"""WR-05 synthetic regressions: rank correlation depends on order, not scale."""
import math
import unittest

import numpy as np
import pandas as pd

from qresearch.evaluation import EvaluationError, daily_rank_ic, paired_factor_correlation


SCALES = (1e-200, 1.0, 1e200)


def ic_records(prediction, label):
    return pd.DataFrame({
        "formation_at": [pd.Timestamp("2018-06-04 09:00", tz="America/New_York")] * len(prediction),
        "sid": [f"S{i}" for i in range(len(prediction))],
        "prediction": prediction,
        "label": label,
    })


class WR05RankCorrelationTests(unittest.TestCase):
    def test_daily_positive_correlation_at_small_normal_and_large_scales(self):
        for score_scale in SCALES:
            for label_scale in SCALES:
                with self.subTest(score_scale=score_scale, label_scale=label_scale):
                    result = daily_rank_ic(ic_records(
                        np.array([1., 2., 3.]) * score_scale,
                        np.array([1., 2., 3.]) * label_scale)).iloc[0]
                    self.assertEqual(result["n"], 3)
                    self.assertAlmostEqual(result["ic"], 1.0)

    def test_daily_negative_correlation_is_scale_invariant(self):
        for scale in SCALES:
            with self.subTest(scale=scale):
                result = daily_rank_ic(ic_records(
                    np.array([1., 2., 3.]) * scale, [.3, .2, .1])).iloc[0]
                self.assertAlmostEqual(result["ic"], -1.0)

    def test_daily_average_ties_match_hand_rank_covariance(self):
        # Average ranks [1.5, 1.5, 3, 4] versus [1, 2, 3, 4]:
        # centered dot product 4.5, squared lengths 4.5 and 5.
        expected = 4.5 / math.sqrt(4.5 * 5.0)
        for scale in SCALES:
            with self.subTest(scale=scale):
                result = daily_rank_ic(ic_records(
                    np.array([1., 1., 2., 3.]) * scale, [1., 2., 3., 4.])).iloc[0]
                self.assertAlmostEqual(result["ic"], expected)

    def test_daily_constant_scores_or_labels_are_undefined(self):
        for scale in SCALES:
            for prediction, label in (([scale] * 3, [1., 2., 3.]),
                                      ([1., 2., 3.], [scale] * 3)):
                with self.subTest(scale=scale, prediction=prediction):
                    result = daily_rank_ic(ic_records(prediction, label)).iloc[0]
                    self.assertEqual(result["n"], 3)
                    self.assertTrue(math.isnan(result["ic"]))

    def test_daily_missing_rows_and_minimum_sample_count(self):
        data = ic_records([1e-200, 2e-200, np.nan, np.inf, 5.],
                          [.1, .2, .3, .4, np.nan])
        insufficient = daily_rank_ic(data).iloc[0]
        self.assertEqual(insufficient["n"], 2)
        self.assertTrue(math.isnan(insufficient["ic"]))
        enough = daily_rank_ic(data, min_names=2).iloc[0]
        self.assertEqual(enough["n"], 2)
        self.assertAlmostEqual(enough["ic"], 1.0)
        for invalid in (True, 1, 2.0):
            with self.subTest(invalid=invalid), self.assertRaises(EvaluationError):
                daily_rank_ic(data, min_names=invalid)

    def test_paired_spearman_sign_and_absolute_value_are_scale_invariant(self):
        for left_scale in SCALES:
            for right_scale in SCALES:
                for direction in (-1, 1):
                    with self.subTest(left_scale=left_scale, right_scale=right_scale,
                                      direction=direction):
                        result = paired_factor_correlation(
                            pd.Series(np.array([1., 2., 3.]) * left_scale),
                            pd.Series(np.array([1., 2., 3.]) * right_scale * direction),
                            method="spearman")
                        self.assertEqual(result["n"], 3)
                        self.assertEqual(result["method"], "spearman")
                        self.assertAlmostEqual(result["correlation"], direction)
                        self.assertAlmostEqual(result["absolute_correlation"], 1.0)

    def test_paired_spearman_ties_match_hand_rank_covariance(self):
        expected = 4.5 / math.sqrt(4.5 * 5.0)
        for scale in SCALES:
            with self.subTest(scale=scale):
                result = paired_factor_correlation(
                    pd.Series(np.array([1., 1., 2., 3.]) * scale),
                    pd.Series([1., 2., 3., 4.]), method="spearman")
                self.assertAlmostEqual(result["correlation"], expected)

    def test_paired_spearman_constants_remain_undefined(self):
        for scale in SCALES:
            for left, right in (([scale] * 3, [1., 2., 3.]),
                                ([1., 2., 3.], [scale] * 3)):
                with self.subTest(scale=scale, left=left):
                    result = paired_factor_correlation(pd.Series(left), pd.Series(right),
                                                       method="spearman")
                    self.assertEqual(result["n"], 3)
                    self.assertTrue(math.isnan(result["correlation"]))
                    self.assertTrue(math.isnan(result["absolute_correlation"]))

    def test_paired_common_finite_alignment_and_minimum_count(self):
        left = pd.Series([1e-200, np.nan, np.inf, 2e-200, 9.], index=list("ABCDE"))
        right = pd.Series([.2, .1, .5, .3, 7.], index=list("DACBF"))
        # Inner finite pairs are A=(1e-200,.1), D=(2e-200,.2).
        result = paired_factor_correlation(left, right, method="spearman")
        self.assertEqual(result["n"], 2)
        self.assertAlmostEqual(result["correlation"], 1.0)
        for left, right, expected_n in ((pd.Series([1.], index=["A"]),
                                         pd.Series([2.], index=["B"]), 0),
                                        (pd.Series([1.]), pd.Series([2.]), 1)):
            with self.subTest(expected_n=expected_n):
                result = paired_factor_correlation(left, right, method="spearman")
                self.assertEqual(result["n"], expected_n)
                self.assertTrue(math.isnan(result["correlation"]))

    def test_pearson_remains_a_distinct_supported_contract(self):
        pearson = paired_factor_correlation(pd.Series([1., 2., 3.]),
                                            pd.Series([1., 2., 4.]))
        # Centered dot=3, squared lengths=2 and 14/3.
        self.assertEqual(pearson["method"], "pearson")
        self.assertAlmostEqual(pearson["correlation"], 3 / math.sqrt(2 * (14 / 3)))
        spearman = paired_factor_correlation(pd.Series([1., 2., 3.]),
                                             pd.Series([1., 2., 4.]), method="spearman")
        self.assertAlmostEqual(spearman["correlation"], 1.)
        with self.assertRaises(EvaluationError):
            paired_factor_correlation(pd.Series([1., 2.]), pd.Series([1., 2.]),
                                      method="unsupported")


if __name__ == "__main__":
    unittest.main()
