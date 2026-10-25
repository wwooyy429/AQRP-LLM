"""Three manual factor answers; no market factor is registered or selected."""
from fractions import Fraction
import unittest
import numpy as np
import pandas as pd
from qresearch.contracts import PITWindow, NY
from qresearch.factors import FactorSpec


class KnownAnswerTests(unittest.TestCase):
    def test_three_fixed_arithmetic_fixtures(self):
        times = pd.DatetimeIndex([pd.Timestamp("2018-01-03 09:00", tz=NY),
                                  pd.Timestamp("2018-01-04 09:00", tz=NY),
                                  pd.Timestamp("2018-01-05 09:00", tz=NY)])
        close = pd.DataFrame([[100., 100.], [110., 100.], [121., 90.]], index=times, columns=["A", "B"])
        volume = pd.DataFrame([[10., 2.], [20., 4.], [30., 6.]], index=times, columns=["A", "B"])
        window = PITWindow(times[-1], {"close": close, "volume": volume}, ("A", "B"))
        price = {"op": "field", "name": "close"}
        previous = {"op": "positive_session_lag", "periods": 1, "arg": price}
        fixtures = [({"op": "safe_divide", "args": [{"op": "subtract", "args": [price, previous]}, previous]},
                     [float(Fraction(1, 10)), float(Fraction(-1, 10))]),
                    ({"op": "trailing_mean", "window": 3, "arg": {"op": "field", "name": "volume"}}, [20., 4.]),
                    ({"op": "cross_section_rank", "arg": price}, [1., .5])]
        for index, (formula, answer) in enumerate(fixtures):
            raw = {"schema_version": 1, "factor_id": "synthetic-manual-" + str(index),
                   "economic_hypothesis": {"mechanism": "Known-answer engineering fixture, not an economic study",
                   "expected_direction": 1, "prediction_horizon_sessions": 1,
                   "applicable_regimes": ["synthetic"], "failure_conditions": ["arithmetic mismatch"]},
                   "allowed_fields": ["close", "volume"],
                   "allowed_operators": ["safe_divide", "subtract", "positive_session_lag", "trailing_mean", "cross_section_rank"],
                   "parameters": {}, "formula": formula}
            result = FactorSpec.from_dict(raw).evaluate(window)
            np.testing.assert_allclose(result.to_numpy(), answer, rtol=0, atol=1e-14)


if __name__ == "__main__":
    unittest.main()
