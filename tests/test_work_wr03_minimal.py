"""WR-03 standalone minimal reproduction: synthetic data, no external APIs.

Save as test_wr03_minimal.py.
Run against a fixed checkout:
    PYTHONPATH=/path/to/checkout/cloud python -B test_wr03_minimal.py

Expected on dd7710854bca31135d2fc86f4f5625b8ded05d65:
    1 test method, 2 failing subtests, exit code 1.
The assertions express required rejection, not expectedFailure.
"""

from decimal import Decimal
import unittest

import pandas as pd

from qresearch.labels import (
    LabelProtocol,
    LabelValidationError,
    build_execution_labels,
)


class WR03Minimal(unittest.TestCase):
    def test_originally_unequal_quantities_must_be_rejected(self):
        protocol = LabelProtocol.from_dict({
            "schema_version": 1,
            "protocol_id": "wr03-independent-synthetic",
            "target_kind": "net_return",
            "price_basis": "actual_fill",
            "currency": "USD",
            "normalization": "raw",
            "corporate_action_policy": "reject_non_cash_actions",
            "denominator": "entry_notional",
            "purpose": "engineering_fixture",
        })
        t = pd.Timestamp(
            "2020-02-03 09:00", tz="America/New_York"
        )

        for kind in (Decimal, str):
            with self.subTest(quantity_type=kind.__name__):
                entry = kind("1")
                exit_ = kind("1.00000000000000001")

                # Original precision distinguishes the quantities.
                self.assertNotEqual(entry, exit_)
                # Narrowing destroys their difference.
                self.assertEqual(float(entry), float(exit_))

                frame = pd.DataFrame([{
                    "trade_id": "wr03-one",
                    "sid": "A",
                    "side": "long",
                    "currency": "USD",
                    "normalization": "raw",
                    "execution_source": "independent-synthetic",
                    "entry_execution_id": "wr03-buy",
                    "exit_execution_id": "wr03-sell",
                    "non_cash_corporate_action": False,
                    "formation_at": t,
                    "entry_at": t + pd.Timedelta(hours=1),
                    "exit_at": t + pd.Timedelta(days=1),
                    "entry_available_at":
                        t + pd.Timedelta(hours=2),
                    "exit_available_at":
                        t + pd.Timedelta(days=1, minutes=1),
                    "costs_available_at":
                        t + pd.Timedelta(days=1, minutes=2),
                    "corporate_actions_available_at":
                        t + pd.Timedelta(days=1, minutes=3),
                    "entry_quantity": entry,
                    "exit_quantity": exit_,
                    "entry_price": 100,
                    "exit_price": 90,
                    "entry_fee": 1,
                    "exit_fee": 1,
                    "other_costs": 0,
                    "cash_distributions": 0,
                }]).astype(object)

                # dd771 incorrectly accepts both variants and returns
                # gross_return=-0.1, net_return=-0.12.
                with self.assertRaises(LabelValidationError):
                    build_execution_labels(frame, protocol)


if __name__ == "__main__":
    unittest.main(verbosity=2)
