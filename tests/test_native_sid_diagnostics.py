"""Value-free native permanent-SID failure classes; synthetic source only."""
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import traceback
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.collection import (CollectionError, CollectionInterrupted, HistoricalCollectionPlan,
    HistoricalSnapshotCollector, _safe_source_diagnostic)
from qresearch.historical_source import HistoricalSourceError, QuantConnectSnapshotSource
from test_historical_source import FakeQB, response, ts


CATALOG = {"dollar_volume": {"kind": "number", "role": "synthetic_liquidity", "unit": "synthetic", "period_accessor": None}}
KEYS = {"schema_version", "stage", "failure_code", "exception_kind", "response_kind", "index_kind", "index_names",
    "snapshot_kind", "projection_kind", "native_calls", "response_rows", "index_levels", "snapshots_seen",
    "rows_emitted", "projection_position"}


def item(sid, *, ticker="LICENSED-TICKER", value=1):
    return NS(symbol=NS(id=sid, value=ticker), dollar_volume=value)


class NativeSIDDiagnosticsTests(unittest.TestCase):
    def source(self, qb):
        return QuantConnectSnapshotSource(qb, CATALOG, api=NS(Resolution=NS(DAILY="synthetic_daily")))

    def plan(self):
        return HistoricalCollectionPlan.from_dict(dict(schema_version=1, plan_id="SYNTHETIC-SID-DIAGNOSTIC",
            scope="engineering", source="quantconnect_fundamental_universe", data_version="SYNTHETIC-SID-v1",
            start=ts("2018-01-03").isoformat(), end_exclusive=ts("2018-01-04").isoformat(),
            timezone="America/New_York", fields=list(CATALOG), calendar_days_per_request=1,
            max_batch_records=1, max_records_per_window=20, source_manifest_hash="a" * 64), field_catalog=CATALOG)

    def fail(self, items_or_error):
        qb = FakeQB(items_or_error if isinstance(items_or_error, Exception) else response(items_or_error))
        source, store = self.source(qb), MemoryArtifactStore()
        collector = HistoricalSnapshotCollector(store, source, self.plan(), synthetic=True)
        with self.assertRaises(CollectionError) as caught:
            collector.collect()
        message = str(caught.exception)
        rendered = "".join(traceback.format_exception(type(caught.exception), caught.exception, caught.exception.__traceback__))
        self.assertNotIn("LICENSED", message)
        self.assertNotIn("LICENSED", rendered)
        diagnostic = json.loads(message.split("; diagnostic=", 1)[1])
        self.assertEqual(set(diagnostic), KEYS)
        self.assertEqual(diagnostic, _safe_source_diagnostic(diagnostic))
        self.assertEqual(diagnostic["native_calls"], 1)
        self.assertFalse(any("/windows/" in key for key in store._data))
        before = dict(store._data)
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(store._data, before)
        self.assertEqual(source.history_call_count, 1)
        self.assertEqual(len(qb.calls), 1)
        return diagnostic

    def test_missing_symbol_or_identifier_is_one_fixed_missing_code(self):
        for row in (NS(), NS(symbol=None), NS(symbol=NS()), item(None), {}):
            with self.subTest(row_kind=type(row).__name__):
                diagnostic = self.fail([row])
                self.assertEqual(diagnostic["stage"], "row_identity")
                self.assertEqual(diagnostic["failure_code"], "native_sid_missing")
                self.assertEqual(diagnostic["rows_emitted"], 0)

    def test_noncanonical_identifiers_are_one_fixed_code_without_identifier_text(self):
        for sid in ("", " ", " LICENSED-SID", "LICENSED-SID ", "LICENSED-SID\n", "LICENSED" * 37):
            with self.subTest(length=len(sid)):
                diagnostic = self.fail([item(sid)])
                self.assertEqual(diagnostic["failure_code"], "native_sid_noncanonical")
                self.assertEqual(diagnostic["stage"], "row_identity")
                self.assertEqual(diagnostic["rows_emitted"], 0)

    def test_duplicate_sid_rejects_different_ticker_and_values_without_deduplication(self):
        diagnostic = self.fail([item("LICENSED-SAME-SID", ticker="LICENSED-OLD", value=1),
                                item("LICENSED-SAME-SID", ticker="LICENSED-NEW", value=2)])
        self.assertEqual(diagnostic["failure_code"], "native_sid_duplicate")
        self.assertEqual(diagnostic["stage"], "row_identity")
        self.assertEqual(diagnostic["rows_emitted"], 1)  # First artificial row observed; no completed window.
        self.assertEqual(diagnostic["snapshots_seen"], 1)

    def test_same_display_ticker_with_distinct_sids_is_not_deduplicated(self):
        qb = FakeQB(response([item("SYNTHETIC-ONE"), item("SYNTHETIC-TWO")]))
        rows = list(self.source(qb).fetch(ts("2018-01-03"), ts("2018-01-04"), CATALOG))
        self.assertEqual([row["sid"] for row in rows], ["SYNTHETIC-ONE", "SYNTHETIC-TWO"])
        self.assertEqual(len(qb.calls), 1)

    def test_duplicate_check_is_per_snapshot_not_across_time(self):
        data = pd.concat([response([item("SYNTHETIC-SID")], "2018-01-03"),
                          response([item("SYNTHETIC-SID")], "2018-01-04")])
        qb = FakeQB(data)
        qb.time = datetime(2018, 1, 5)
        rows = list(self.source(qb).fetch(ts("2018-01-03"), ts("2018-01-05"), CATALOG))
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["sid"] for row in rows], ["SYNTHETIC-SID", "SYNTHETIC-SID"])

    def test_legacy_generic_contract_code_and_message_remain_accepted(self):
        diagnostic = self.fail(HistoricalSourceError("Unique native permanent SIDs are required"))
        self.assertEqual(diagnostic["failure_code"], "source_contract")
        self.assertEqual(diagnostic["stage"], "history_request")

    def test_native_exception_message_cannot_select_an_owned_identity_code(self):
        for text in ("Missing native permanent SID", "Noncanonical native permanent SID", "Duplicate native permanent SID"):
            with self.subTest(message=text):
                diagnostic = self.fail(RuntimeError(text))
                self.assertEqual(diagnostic["failure_code"], "unexpected_exception")
                self.assertEqual(diagnostic["exception_kind"], "runtime_error")

    def test_identifier_conversion_error_stays_redacted_without_inventing_a_missing_sid(self):
        class HostileSID:
            def __str__(self):
                raise RuntimeError("LICENSED-SID-CONVERSION-SECRET")
        diagnostic = self.fail([item(HostileSID())])
        self.assertEqual(diagnostic["stage"], "row_identity")
        self.assertEqual(diagnostic["failure_code"], "unexpected_exception")
        self.assertEqual(diagnostic["exception_kind"], "runtime_error")

    def test_owned_native_property_failure_keeps_previous_specific_code(self):
        class BadSymbol:
            @property
            def id(self):
                raise RuntimeError("LICENSED-PROPERTY-SECRET")
        diagnostic = self.fail([NS(symbol=BadSymbol(), dollar_volume=1)])
        self.assertEqual(diagnostic["failure_code"], "native_property_failed")
        self.assertEqual(diagnostic["stage"], "row_identity")

    def test_failure_code_whitelist_keeps_old_shape_and_rejects_arbitrary_values(self):
        diagnostic = self.fail([item(None)])
        for code in ("unexpected_exception", "source_contract", "native_property_failed",
                     "native_sid_missing", "native_sid_noncanonical", "native_sid_duplicate"):
            self.assertIsNotNone(_safe_source_diagnostic(dict(diagnostic, failure_code=code)))
        for bad in ("LICENSED-SID", "native_sid_duplicate:LICENSED", True, 1, None):
            self.assertIsNone(_safe_source_diagnostic(dict(diagnostic, failure_code=bad)))
        self.assertIsNone(_safe_source_diagnostic(dict(diagnostic, sid="LICENSED-SID")))


if __name__ == "__main__":
    unittest.main()
