"""Native-shaped known answers only; no SDK, provider or real financial rows."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.financial_fields import (FINANCIAL_FIELD_PATH, FinancialFieldError,
    extract_financial_field, financial_field_definition)
from qresearch.historical_source import HistoricalSourceError, QuantConnectSnapshotSource
from test_historical_source import FakeQB, native, response, ts


class NativePeriod:
    def __init__(self, value, present=True):
        self.twelve_months = value
        self.present = present
        self.presence_calls = []

    def has_period_value(self, period):
        self.presence_calls.append(period)
        return self.present

    @property
    def has_value(self):
        raise AssertionError("Default-period flag must not be read")

    @property
    def value(self):
        raise AssertionError("Default-period value must not be read")

    def get_period_value(self, period):
        raise AssertionError("The selected property must be used after presence")


def item(period):
    return NS(financial_statements=NS(income_statement=NS(total_revenue_as_reported=period)))


class FinancialFieldTests(unittest.TestCase):
    def extract(self, value, definition=None, path=FINANCIAL_FIELD_PATH):
        return extract_financial_field(value, path,
            financial_field_definition() if definition is None else definition)

    def source(self, period):
        row = native()
        row.financial_statements = item(period).financial_statements
        definition = {FINANCIAL_FIELD_PATH: financial_field_definition()}
        source = QuantConnectSnapshotSource(FakeQB(response([row])), definition,
            api=NS(Resolution=NS(DAILY="synthetic_daily")))
        return source, definition

    def test_known_answers_zero_positive_negative_and_exact_period(self):
        for raw, expected in ((0, 0), (42, 42), (3.25, 3.25), (-17, -17),
                              (np.int64(9), 9), (np.float64(0), 0.0)):
            with self.subTest(raw=raw):
                period = NativePeriod(raw)
                actual = self.extract(item(period))
                self.assertEqual(actual, expected)
                self.assertEqual(period.presence_calls, ["12M"])
                self.assertNotIsInstance(actual, bool)

    def test_missing_period_returns_none_without_reading_zero_or_property(self):
        class Absent:
            def has_period_value(self, period):
                self.period = period
                return False

            @property
            def twelve_months(self):
                raise AssertionError("A missing SDK period must not read its zero sentinel")

        absent = Absent()
        self.assertIsNone(self.extract(item(absent)))
        self.assertEqual(absent.period, "12M")
        self.assertIsNone(self.extract(item(NativePeriod(0, False))))

    def test_missing_each_parent_and_missing_scalar_remain_none(self):
        for value in (None, NS(), {"financial_statements": None},
                      NS(financial_statements=NS()),
                      NS(financial_statements=NS(income_statement=None)),
                      NS(financial_statements=NS(income_statement=NS())),
                      item(None), item(NativePeriod(None)), item(NativePeriod(float("nan")))):
            with self.subTest(shape=type(value).__name__):
                self.assertIsNone(self.extract(value))

    def test_parent_mappings_allowed_but_period_mapping_cannot_install_method(self):
        value = {"financial_statements": {"income_statement": {
            "total_revenue_as_reported": NativePeriod(11)}}}
        self.assertEqual(self.extract(value), 11)
        calls = []
        value["financial_statements"]["income_statement"]["total_revenue_as_reported"] = {
            "has_period_value": lambda period: calls.append(period) or True,
            "twelve_months": 1}
        with self.assertRaises(FinancialFieldError):
            self.extract(value)
        self.assertEqual(calls, [])

    def test_default_value_or_flag_cannot_substitute_for_fixed_period_presence(self):
        for period in (NS(twelve_months=0, has_value=False, value=0),
                       NS(twelve_months=7, has_value=True, value=7),
                       NS(twelve_months=9, has_period_value=True),
                       NS(twelve_months=9, get_period_value=lambda name: 9)):
            with self.subTest(fields=tuple(vars(period))):
                with self.assertRaises(FinancialFieldError) as seen:
                    self.extract(item(period))
                self.assertEqual(seen.exception.reason, "period_presence_unavailable")

    def test_invalid_native_presence_is_not_coerced(self):
        for present in (0, 1, None, "true", np.bool_(True)):
            with self.subTest(present=present):
                with self.assertRaises(FinancialFieldError) as seen:
                    self.extract(item(NativePeriod(5, present)))
                self.assertEqual(seen.exception.reason, "invalid_period_presence")

    def test_non_numeric_boolean_infinite_values_reject_without_coercion(self):
        for value in (True, False, np.bool_(False), "0", float("inf"), float("-inf"), object()):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(FinancialFieldError):
                    self.extract(item(NativePeriod(value)))

    def test_unknown_path_and_definition_reject_before_touching_native(self):
        class Tripwire:
            @property
            def financial_statements(self):
                raise AssertionError("Must reject declaration before native access")

        cases = []
        for key, replacement in (("unit", "USD"), ("period_accessor", "value"),
                                 ("role", "standardized_financial_value"), ("kind", "text")):
            definition = financial_field_definition()
            definition[key] = replacement
            cases.append((FINANCIAL_FIELD_PATH, definition))
        cases.extend((path, financial_field_definition()) for path in (
            FINANCIAL_FIELD_PATH.replace("total_revenue_as_reported", "total_revenue"),
            FINANCIAL_FIELD_PATH.replace("twelve_months", "value"),
            FINANCIAL_FIELD_PATH.replace("twelve_months", "has_period_value"),
            "financial_statements.__dict__", "", True))
        extra = financial_field_definition() | {"fallback": "value"}
        cases.append((FINANCIAL_FIELD_PATH, extra))
        for path, definition in cases:
            with self.subTest(path=path, definition=definition):
                with self.assertRaises(FinancialFieldError) as seen:
                    self.extract(Tripwire(), path=path, definition=definition)
                self.assertEqual(seen.exception.reason, "unsupported_field")

    def test_callable_parents_periods_and_values_never_invoked(self):
        calls = []
        def forbidden():
            calls.append(True)
            return 1
        for value in (NS(financial_statements=forbidden),
                      NS(financial_statements=NS(income_statement=forbidden)),
                      item(forbidden), item(NativePeriod(forbidden))):
            with self.assertRaises(FinancialFieldError):
                self.extract(value)
        self.assertEqual(calls, [])

    def test_throwing_properties_and_presence_have_static_redacted_diagnostics(self):
        class BadRoot:
            @property
            def financial_statements(self):
                raise RuntimeError("SYNTHETIC-PRIVATE-FINANCIAL-VALUE")
        class BadPresence:
            def has_period_value(self, period):
                raise RuntimeError("SYNTHETIC-PRIVATE-FINANCIAL-VALUE")
        class BadValue:
            def has_period_value(self, period):
                return True
            @property
            def twelve_months(self):
                raise RuntimeError("SYNTHETIC-PRIVATE-FINANCIAL-VALUE")
        for value in (BadRoot(), item(BadPresence()), item(BadValue())):
            with self.assertRaises(FinancialFieldError) as seen:
                self.extract(value)
            self.assertEqual(seen.exception.reason, "native_property_failed")
            self.assertNotIn("PRIVATE", str(seen.exception))

    def test_numeric_error_subclass_never_stringified_or_exported(self):
        rendered = []
        class LeakingError(FinancialFieldError):
            def __init__(self):
                super().__init__("invalid_numeric_value")
            def __str__(self):
                rendered.append(True)
                return "SYNTHETIC-PRIVATE-FINANCIAL-VALUE"
        class BadFloat(float):
            def __float__(self):
                raise LeakingError()
        value = BadFloat(1)
        with self.assertRaises(FinancialFieldError) as seen:
            self.extract(item(NativePeriod(value)))
        self.assertIs(type(seen.exception), FinancialFieldError)
        self.assertNotIn("PRIVATE", str(seen.exception))
        source, catalog = self.source(NativePeriod(value))
        with self.assertRaises(HistoricalSourceError) as seen:
            list(source.fetch(ts("2018-01-03"), ts("2018-01-04"), catalog))
        self.assertNotIn("PRIVATE", str(seen.exception))
        self.assertEqual(rendered, [])

    def test_native_class_predicates_fail_with_owned_static_errors(self):
        class PrivateClass:
            @property
            def __class__(self):
                raise RuntimeError("SYNTHETIC_PRIVATE_NATIVE_CLASS_ERROR")
        cases = [item(NativePeriod(PrivateClass())), item(PrivateClass()),
                 NS(financial_statements=PrivateClass()), PrivateClass()]
        for value in cases:
            with self.subTest(shape=type(value).__name__):
                with self.assertRaises(FinancialFieldError) as seen:
                    self.extract(value)
                self.assertIs(type(seen.exception), FinancialFieldError)
                self.assertNotIn("PRIVATE", str(seen.exception))

    def test_mutable_or_subclass_native_errors_cannot_export_foreign_reason(self):
        class BadPresence:
            def has_period_value(self, period):
                error = FinancialFieldError("native_property_failed")
                error.args = ("SYNTHETIC_PRIVATE_NATIVE_MESSAGE",)
                error.reason = "SYNTHETIC_PRIVATE_NATIVE_REASON"
                raise error
        with self.assertRaises(FinancialFieldError) as seen:
            self.extract(item(BadPresence()))
        self.assertIs(type(seen.exception), FinancialFieldError)
        self.assertNotIn("PRIVATE", str(seen.exception))

    def test_misdeclared_financial_catalog_rejected_before_native_history(self):
        qb = FakeQB()
        for path, definition in (
                (FINANCIAL_FIELD_PATH, financial_field_definition() | {"unit": "USD"}),
                (FINANCIAL_FIELD_PATH.replace("twelve_months", "value"), financial_field_definition()),
                (FINANCIAL_FIELD_PATH, financial_field_definition() | {"role": "synthetic_observation"})):
            with self.subTest(path=path, definition=definition):
                with self.assertRaises(HistoricalSourceError):
                    QuantConnectSnapshotSource(qb, {path: definition},
                        api=NS(Resolution=NS(DAILY="synthetic_daily")))
                self.assertEqual(qb.calls, [])

    def test_snapshot_hook_preserves_zero_and_missing_without_coverage_approval(self):
        for raw, present, expected in ((0, True, 0), (0, False, None), (float("nan"), True, None)):
            with self.subTest(raw=raw, present=present):
                source, catalog = self.source(NativePeriod(raw, present))
                rows = list(source.fetch(ts("2018-01-03"), ts("2018-01-04"), catalog))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["values"][FINANCIAL_FIELD_PATH], expected)
                self.assertEqual(rows[0]["sid"], "SYNTHETIC-SID")
                self.assertFalse(source.provenance()["financial_field_coverage_certified"])
                self.assertFalse(source.provenance()["vendor_revision_certified"])
                self.assertFalse(source.provenance()["actual_availability_certified"])

    def test_snapshot_hook_native_error_keeps_value_free_diagnostics(self):
        class BadPeriod:
            def has_period_value(self, period):
                raise RuntimeError("SYNTHETIC-PRIVATE-VALUE")
        source, catalog = self.source(BadPeriod())
        with self.assertRaises(HistoricalSourceError) as seen:
            list(source.fetch(ts("2018-01-03"), ts("2018-01-04"), catalog))
        self.assertEqual(seen.exception.diagnostic["failure_code"], "native_property_failed")
        self.assertEqual(seen.exception.diagnostic["stage"], "field_projection")
        self.assertNotIn("PRIVATE", str(seen.exception))

    def test_catalog_is_explicit_reported_currency_and_still_not_factor_enabled(self):
        catalog = json.loads((ROOT / "config/source_catalog.json").read_bytes())
        self.assertEqual(catalog["fields"][FINANCIAL_FIELD_PATH], financial_field_definition())
        financial = [value for value in catalog["fields"].values()
                     if value["role"] == "as_reported_financial_value"]
        self.assertEqual(len(financial), 1)
        self.assertEqual(financial[0]["unit"], "reported_currency")
        self.assertIs(catalog["factor_fields_enabled"], False)
        self.assertIs(catalog["vendor_revision_certified"], False)
        self.assertIs(catalog["actual_availability_certified"], False)
        definition = financial_field_definition()
        definition["unit"] = "USD"
        self.assertEqual(financial_field_definition()["unit"], "reported_currency")


if __name__ == "__main__":
    unittest.main()
