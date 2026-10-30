"""Exact SDK Empty-SID subtype; synthetic fixtures without provider access."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import traceback
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.collection import (CollectionError, HistoricalCollectionPlan,
    HistoricalSnapshotCollector, _safe_source_diagnostic)
from qresearch.historical_source import HistoricalSourceError, QuantConnectSnapshotSource
from test_historical_source import FakeQB, response, ts
from test_native_sid_diagnostics import CATALOG, KEYS, item


class NativeSIDSubtypeTests(unittest.TestCase):
    def source(self, result):
        return QuantConnectSnapshotSource(FakeQB(result), CATALOG,
            api=NS(Resolution=NS(DAILY="synthetic_daily")))

    def failure(self, result):
        source = self.source(result)
        with self.assertRaises(HistoricalSourceError) as caught:
            list(source.fetch(ts("2018-01-03"), ts("2018-01-04"), CATALOG))
        diagnostic = caught.exception.diagnostic
        self.assertEqual(set(diagnostic), KEYS)
        self.assertEqual(diagnostic, _safe_source_diagnostic(diagnostic))
        self.assertEqual(diagnostic["native_calls"], 1)
        rendered = "".join(traceback.format_exception(type(caught.exception),
            caught.exception, caught.exception.__traceback__))
        self.assertNotIn("LICENSED", rendered)
        return diagnostic

    def test_exact_sdk_empty_rejects_before_field_access_with_closed_code(self):
        class EmptySID:
            def __str__(self):
                return " 0"

        class EmptyRow:
            symbol = NS(id=EmptySID())

            @property
            def dollar_volume(self):
                raise AssertionError("LICENSED-FIELD-MUST-NOT-BE-READ")

        diagnostic = self.failure(response([EmptyRow()]))
        self.assertEqual(diagnostic["failure_code"], "native_sid_empty")
        self.assertEqual(diagnostic["exception_kind"], "source_contract")
        self.assertEqual(diagnostic["stage"], "row_identity")
        self.assertEqual(diagnostic["rows_emitted"], 0)
        self.assertIsNone(diagnostic["projection_position"])

    def test_zero_text_is_not_empty_and_nearby_whitespace_keeps_old_code(self):
        rows = list(self.source(response([item("0")])).fetch(
            ts("2018-01-03"), ts("2018-01-04"), CATALOG))
        self.assertEqual([row["sid"] for row in rows], ["0"])
        for sid in ("", " ", " 0 ", "0 ", "\t0", " 00"):
            with self.subTest(length=len(sid)):
                diagnostic = self.failure(response([item(sid)]))
                self.assertEqual(diagnostic["failure_code"], "native_sid_noncanonical")

    def test_runtime_message_cannot_forge_empty_subtype(self):
        diagnostic = self.failure(RuntimeError("Empty native permanent SID"))
        self.assertEqual(diagnostic["failure_code"], "unexpected_exception")
        self.assertEqual(diagnostic["exception_kind"], "runtime_error")

    def test_empty_after_valid_row_never_completes_collection_window(self):
        plan = HistoricalCollectionPlan.from_dict(dict(schema_version=1,
            plan_id="SYNTHETIC-EMPTY-SID", scope="engineering",
            source="quantconnect_fundamental_universe", data_version="SYNTHETIC-EMPTY-v1",
            start=ts("2018-01-03").isoformat(), end_exclusive=ts("2018-01-04").isoformat(),
            timezone="America/New_York", fields=list(CATALOG), calendar_days_per_request=1,
            max_batch_records=1, max_records_per_window=20, source_manifest_hash="a" * 64),
            field_catalog=CATALOG)
        store = MemoryArtifactStore()
        collector = HistoricalSnapshotCollector(store,
            self.source(response([item("SYNTHETIC-VALID"), item(" 0")])), plan, synthetic=True)
        with self.assertRaises(CollectionError) as caught:
            collector.collect()
        diagnostic = json.loads(str(caught.exception).split("; diagnostic=", 1)[1])
        self.assertEqual(diagnostic["failure_code"], "native_sid_empty")
        self.assertEqual(diagnostic["rows_emitted"], 1)
        self.assertFalse(any("/windows/" in key for key in store._data))

    def test_schema_one_accepts_legacy_codes_and_only_fixed_empty_token(self):
        diagnostic = self.failure(response([item(" 0")]))
        self.assertEqual(diagnostic["schema_version"], 1)
        for code in ("unexpected_exception", "source_contract", "native_property_failed",
                     "native_sid_missing", "native_sid_noncanonical", "native_sid_duplicate",
                     "native_sid_empty"):
            self.assertIsNotNone(_safe_source_diagnostic(dict(diagnostic, failure_code=code)))
        for code in ("native_sid_empty:LICENSED", " 0", True, None):
            self.assertIsNone(_safe_source_diagnostic(dict(diagnostic, failure_code=code)))
        self.assertIsNone(_safe_source_diagnostic(dict(diagnostic, sid="LICENSED-SID")))


if __name__ == "__main__":
    unittest.main()
