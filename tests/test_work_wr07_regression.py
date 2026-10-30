"""WR-07 synthetic Pearson regressions, with an exact-input independent oracle.

The rational/Decimal oracle is intentionally separate from NumPy's covariance
implementation. These are developer tests, not independent financial evidence.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import unittest

import numpy as np
import pandas as pd

from qresearch.evaluation import (
    EvaluationError, paired_factor_correlation, pairwise_factor_correlations,
)


SCALES = (1e-200, 1.0, 1e200)


def exact_float_pearson(left, right):
    """Exact binary64 input moments followed by a high precision square root."""
    x = [Fraction.from_float(float(value)) for value in left]
    y = [Fraction.from_float(float(value)) for value in right]
    if len(x) < 2:
        return math.nan
    mean_x, mean_y = sum(x) / len(x), sum(y) / len(y)
    dx, dy = [value - mean_x for value in x], [value - mean_y for value in y]
    xx, yy = sum(value * value for value in dx), sum(value * value for value in dy)
    if not xx or not yy:
        return math.nan
    xy = sum(a * b for a, b in zip(dx, dy))
    squared = xy * xy / (xx * yy)
    with localcontext() as context:
        context.prec = 90
        magnitude = (Decimal(squared.numerator) / Decimal(squared.denominator)).sqrt()
    return math.copysign(float(magnitude), -1 if xy < 0 else 1)


class WR07PearsonTests(unittest.TestCase):
    def assert_pearson(self, left, right, expected=None):
        if expected is None:
            expected = exact_float_pearson(left, right)
        # Accepted finite inputs should not emit overflow/invalid/divide errors.
        # Underflow of numerically negligible, discarded digits is not itself
        # an invalid correlation, so this does not demand an unused precision.
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = paired_factor_correlation(pd.Series(left), pd.Series(right))
        self.assertEqual(result["method"], "pearson")
        self.assertEqual(result["n"], len(left))
        if math.isnan(expected):
            self.assertTrue(math.isnan(result["correlation"]))
            self.assertTrue(math.isnan(result["absolute_correlation"]))
        else:
            self.assertAlmostEqual(result["correlation"], expected, delta=5e-14)
            self.assertAlmostEqual(result["absolute_correlation"], abs(expected), delta=5e-14)
            self.assertLessEqual(abs(result["correlation"]), 1.0)
        return result

    def test_default_pearson_perfect_signs_with_independently_scaled_inputs(self):
        for left_scale in SCALES:
            for right_scale in SCALES:
                for sign in (-1, 1):
                    with self.subTest(left_scale=left_scale, right_scale=right_scale, sign=sign):
                        self.assert_pearson(np.array([1., 2., 3.]) * left_scale,
                            np.array([1., 2., 3.]) * right_scale * sign, float(sign))

    def test_nonperfect_hand_calculation_at_small_normal_large_scales(self):
        # x=[1,2,3], y=[1,2,4]: dot=3, xx=2, yy=14/3.
        expected = 3 / math.sqrt(2 * (14 / 3))
        for left_scale in SCALES:
            for right_scale in SCALES:
                with self.subTest(left_scale=left_scale, right_scale=right_scale):
                    self.assert_pearson(np.array([1., 2., 3.]) * left_scale,
                        np.array([1., 2., 4.]) * right_scale, expected)

    def test_nonperfect_negative_correlation_uses_exact_binary_input_oracle(self):
        for left_scale in SCALES:
            for right_scale in SCALES:
                with self.subTest(left_scale=left_scale, right_scale=right_scale):
                    self.assert_pearson(np.array([0., 1., 4., 9.]) * left_scale,
                                       np.array([7., 2., 1., 3.]) * right_scale)

    def test_symmetric_float64_maximum_inputs_do_not_overflow(self):
        maximum = np.finfo(float).max
        self.assert_pearson([-maximum, -maximum / 2, 0., maximum / 2, maximum],
                            [-2., -1., 0., 1., 2.], 1.0)
        self.assert_pearson([-maximum, 0., maximum], [maximum, 0., -maximum], -1.0)

    def test_smallest_subnormal_inputs_keep_nonconstant_variation(self):
        smallest = np.nextafter(0., 1.)
        self.assert_pearson([smallest, 2 * smallest, 3 * smallest], [1., 2., 3.], 1.0)
        self.assert_pearson([smallest, 2 * smallest, 3 * smallest], [3., 2., 1.], -1.0)

    def test_ulp_variation_with_large_common_offset_matches_exact_oracle(self):
        for base in (1e-200, 1., 1e200):
            spacing = np.spacing(base)
            left = base + spacing * np.array([0., 1., 2., 4.])
            right = np.array([4., 1., 2., 8.])
            with self.subTest(base=base):
                self.assertEqual(len(np.unique(left)), 4)
                self.assert_pearson(left, right)

    def test_near_maximum_positive_offset_preserves_small_spread(self):
        base = np.finfo(float).max / 2
        left = [base]
        for _ in range(3):
            left.append(np.nextafter(left[-1], np.inf))
        self.assert_pearson(left, [2., 4., 1., 8.])

    def test_common_row_permutation_preserves_offset_correlation(self):
        base = 1e200
        left = base + np.spacing(base) * np.array([0., 1., 3., 9.])
        right = np.array([8., 1., 4., 2.])
        expected = exact_float_pearson(left, right)
        for order in ([0, 1, 2, 3], [3, 0, 2, 1], [1, 2, 3, 0]):
            with self.subTest(order=order):
                self.assert_pearson(left[order], right[order], expected)

    def test_constant_inputs_at_extreme_scales_remain_undefined(self):
        for value in (0., np.nextafter(0., 1.), 1e-200, 1., 1e200, np.finfo(float).max):
            with self.subTest(value=value):
                self.assert_pearson([value] * 3, [1., 2., 3.], math.nan)
                self.assert_pearson([1., 2., 3.], [value] * 3, math.nan)

    def test_common_finite_samples_follow_index_alignment(self):
        left = pd.Series([1e-200, np.nan, np.inf, 2e-200, 9.], index=list("ABCDE"))
        right = pd.Series([.2, .1, .5, .3, 7.], index=list("DACBF"))
        result = paired_factor_correlation(left, right)
        # Common finite rows: A=(1e-200,.1), D=(2e-200,.2).
        self.assertEqual(result["method"], "pearson")
        self.assertEqual(result["n"], 2)
        self.assertAlmostEqual(result["correlation"], 1.)

    def test_zero_one_and_two_observation_boundaries(self):
        for n in (0, 1):
            with self.subTest(n=n):
                self.assert_pearson(list(range(n)), list(range(n)), math.nan)
        result = paired_factor_correlation(pd.Series([1.], index=["A"]),
                                           pd.Series([2.], index=["B"]))
        self.assertEqual(result["n"], 0)
        self.assertTrue(math.isnan(result["correlation"]))
        self.assert_pearson([1e-200, 2e-200], [2e200, 1e200], -1.)

    def test_absolute_pearson_matrix_uses_pairwise_common_sample_counts(self):
        features = pd.DataFrame({"tiny": [1e-200, 2e-200, np.nan, 4e-200, 5e-200],
                                 "large": [1e200, .8e200, .6e200, np.nan, .2e200],
                                 "constant": [2.] * 5})
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = pairwise_factor_correlations(features)
        expected_n = pd.DataFrame([[4., 3., 4.], [3., 4., 4.], [4., 4., 5.]],
                                  index=features.columns, columns=features.columns)
        pd.testing.assert_frame_equal(result["n"], expected_n)
        self.assertAlmostEqual(result["absolute_pearson"].loc["tiny", "large"], 1.)
        self.assertAlmostEqual(result["absolute_pearson"].loc["large", "tiny"], 1.)
        self.assertAlmostEqual(result["absolute_pearson"].loc["tiny", "tiny"], 1.)
        self.assertTrue(result["absolute_pearson"].loc["constant"].isna().all())
        self.assertTrue(result["absolute_pearson"]["constant"].isna().all())

    def test_pearson_stays_distinct_from_spearman_at_extreme_scales(self):
        left = pd.Series([1e-200, 2e-200, 3e-200])
        right = pd.Series([1e200, 2e200, 4e200])
        pearson = paired_factor_correlation(left, right)
        spearman = paired_factor_correlation(left, right, method="spearman")
        self.assertEqual(pearson["method"], "pearson")
        self.assertAlmostEqual(pearson["correlation"], 3 / math.sqrt(2 * (14 / 3)))
        self.assertAlmostEqual(spearman["correlation"], 1.)
        self.assertGreater(spearman["correlation"], pearson["correlation"])

    def test_spearman_average_ties_and_sign_still_match_hand_ranks(self):
        expected = 4.5 / math.sqrt(4.5 * 5)
        for scale in SCALES:
            with self.subTest(scale=scale):
                left = pd.Series(np.array([1., 1., 2., 3.]) * scale)
                result = paired_factor_correlation(left, pd.Series([4., 3., 2., 1.]), method="spearman")
                self.assertAlmostEqual(result["correlation"], -expected)
                self.assertAlmostEqual(result["absolute_correlation"], expected)

    def test_duplicate_observation_indices_and_unknown_methods_still_fail(self):
        left = pd.Series([1., 2.], index=["A", "A"])
        with self.assertRaises(EvaluationError):
            paired_factor_correlation(left, pd.Series([1., 2.]))
        with self.assertRaises(EvaluationError):
            paired_factor_correlation(pd.Series([1., 2.]), pd.Series([1., 2.]), method="invalid")
        with self.assertRaises(EvaluationError):
            pairwise_factor_correlations(pd.DataFrame([[1., 2.]], columns=["A", "A"]))


if __name__ == "__main__":
    unittest.main()
