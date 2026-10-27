"""Explicit occurrence-preserving native collection; synthetic sources only."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import traceback
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.historical_source import (HistoricalSourceError, QuantConnectSnapshotSource,
    observed_liquidity_record)
from test_historical_source import FakeQB, response, ts
from test_native_sid_diagnostics import CATALOG, KEYS, item


RETAIN = "retain_source_occurrences"


class NativeOccurrenceSourceTests(unittest.TestCase):
    def source(self, data, **kwargs):
        return QuantConnectSnapshotSource(FakeQB(data), CATALOG,
            api=NS(Resolution=NS(DAILY="synthetic_daily")), **kwargs)

    def fetch(self, source, end="2018-01-04"):
        return list(source.fetch(ts("2018-01-03"), ts(end), CATALOG))

    def failure(self, data, **kwargs):
        source = self.source(data, observation_policy=RETAIN, **kwargs)
        with self.assertRaises(HistoricalSourceError) as caught:
            self.fetch(source)
        diagnostic = caught.exception.diagnostic
        self.assertEqual(set(diagnostic), KEYS)
        rendered = "".join(traceback.format_exception(type(caught.exception),
            caught.exception, caught.exception.__traceback__))
        self.assertNotIn("LICENSED", rendered)
        return diagnostic

    def test_default_and_explicit_unique_policy_keep_original_strict_contract(self):
        default = self.source(response([item("SYNTHETIC-ONE")]))
        explicit = self.source(response([item("SYNTHETIC-ONE")]), observation_policy="unique_sid")
        default_rows, explicit_rows = self.fetch(default), self.fetch(explicit)
        self.assertEqual(default_rows, explicit_rows)
        self.assertEqual(set(explicit_rows[0]), {"sid", "snapshot_at", "values"})
        self.assertEqual(default.provenance(), explicit.provenance())
        self.assertNotIn("observation_policy", default.provenance())
        for options in ({}, {"observation_policy": "unique_sid"}):
            with self.subTest(options=options):
                with self.assertRaises(HistoricalSourceError) as caught:
                    self.fetch(self.source(response([item("SYNTHETIC-ONE"), item("SYNTHETIC-ONE")]), **options))
                self.assertEqual(caught.exception.diagnostic["failure_code"], "native_sid_duplicate")

    def test_retain_preserves_all_duplicate_values_aliases_and_native_order(self):
        source = self.source(response([item("SYNTHETIC-A", ticker="LICENSED-OLD", value=3),
            item("SYNTHETIC-B", value=2), item("SYNTHETIC-A", ticker="LICENSED-NEW", value=1)]),
            observation_policy=RETAIN)
        rows = self.fetch(source)
        self.assertEqual([row["sid"] for row in rows], ["SYNTHETIC-A", "SYNTHETIC-B", "SYNTHETIC-A"])
        self.assertEqual([row["values"]["dollar_volume"] for row in rows], [3, 2, 1])
        self.assertEqual([row["source_record_index"] for row in rows], [0, 1, 2])
        for row in rows:
            self.assertEqual(set(row), {"sid", "snapshot_at", "source_record_index", "values"})
            self.assertIs(type(row["source_record_index"]), int)
        self.assertEqual(len(source.qb.calls), 1)

    def test_indices_restart_per_snapshot_and_tuple_order_is_retained(self):
        data = pd.concat([response((item("SYNTHETIC-A"), item("SYNTHETIC-A"))),
            response([item("SYNTHETIC-A")], "2018-01-04")])
        source = self.source(data, observation_policy=RETAIN)
        source.qb.time = datetime(2018, 1, 5)
        rows = self.fetch(source, "2018-01-05")
        self.assertEqual([row["source_record_index"] for row in rows], [0, 1, 0])
        self.assertNotEqual(rows[1]["snapshot_at"], rows[2]["snapshot_at"])

    def test_observation_policy_is_an_exact_string_closed_set(self):
        class StringSubclass(str):
            pass

        for policy in (None, True, 0, [], {}, "", "retain", "unique_sid ", StringSubclass(RETAIN)):
            with self.subTest(kind=type(policy).__name__):
                qb = FakeQB()
                with self.assertRaises(HistoricalSourceError):
                    QuantConnectSnapshotSource(qb, CATALOG, observation_policy=policy)
                self.assertEqual(qb.calls, [])
                self.assertEqual(qb.zones, [])

    def test_retain_keeps_missing_empty_and_noncanonical_sid_failures(self):
        for row, code in ((NS(), "native_sid_missing"), (item(None), "native_sid_missing"),
                          (item(" 0"), "native_sid_empty"), (item(""), "native_sid_noncanonical"),
                          (item(" LICENSED-SID"), "native_sid_noncanonical")):
            with self.subTest(code=code):
                diagnostic = self.failure(response([row]))
                self.assertEqual(diagnostic["failure_code"], code)
                self.assertEqual(diagnostic["stage"], "row_identity")
                self.assertEqual(diagnostic["rows_emitted"], 0)

    def test_retain_does_not_relax_snapshot_identity_time_or_container(self):
        different_universe = response([item("SYNTHETIC-A")])
        different_universe.index = pd.MultiIndex.from_tuples(
            [("LICENSED-WRONG-UNIVERSE", pd.Timestamp("2018-01-03"))], names=["symbol", "time"])
        cases = ((different_universe, "snapshot_identity"),
            (response([item("SYNTHETIC-A")], "2018-01-04"), "snapshot_clock"),
            (pd.concat([response([item("SYNTHETIC-A")]), response([item("SYNTHETIC-A")])]), "snapshot_clock"),
            (response("LICENSED-NOT-A-LIST"), "snapshot_container"))
        for data, stage in cases:
            with self.subTest(stage=stage):
                # Establish the expected identity for the mismatched-universe case.
                source = self.source(data, observation_policy=RETAIN)
                if data is different_universe:
                    source.qb.add_universe = lambda selector: NS(symbol="SYNTHETIC-UNIVERSE")
                with self.assertRaises(HistoricalSourceError) as caught:
                    self.fetch(source)
                self.assertEqual(caught.exception.diagnostic["stage"], stage)

    def test_no_unselected_or_alias_field_is_accessed_and_each_occurrence_is_projected(self):
        class Symbol:
            id = "SYNTHETIC-A"

            @property
            def value(self):
                raise AssertionError("LICENSED-ALIAS-MUST-NOT-BE-READ")

        class Row:
            symbol = Symbol()
            reads = 0

            @property
            def dollar_volume(self):
                self.reads += 1
                return self.reads

            @property
            def financial_statements(self):
                raise AssertionError("LICENSED-UNSELECTED-FIELD-MUST-NOT-BE-READ")

        row = Row()
        rows = self.fetch(self.source(response([row, row]), observation_policy=RETAIN))
        self.assertEqual([record["values"]["dollar_volume"] for record in rows], [1, 2])
        self.assertEqual(row.reads, 2)

    def test_occurrence_mode_cannot_bypass_snapshot_row_bound(self):
        diagnostic = self.failure(response([item("SYNTHETIC-A"), item("SYNTHETIC-A")]),
            max_records_per_snapshot=1)
        self.assertEqual(diagnostic["stage"], "snapshot_container")
        self.assertEqual(diagnostic["rows_emitted"], 0)

    def test_retain_provenance_identifies_policy_without_certifying_data(self):
        source = self.source(response([item("SYNTHETIC-A")]), observation_policy=RETAIN)
        provenance = source.provenance()
        self.assertEqual(provenance["observation_policy"], RETAIN)
        self.assertFalse(provenance["actual_availability_certified"])
        self.assertFalse(provenance["full_historical_US200_certified"])
        self.assertFalse(provenance["financial_field_coverage_certified"])

    def test_retained_records_cannot_enter_legacy_liquidity_bridge(self):
        row = self.fetch(self.source(response([item("SYNTHETIC-A")]), observation_policy=RETAIN))[0]
        with self.assertRaises(HistoricalSourceError):
            observed_liquidity_record(row, session_close=ts("2018-01-02 16:00"))


if __name__ == "__main__":
    unittest.main()
