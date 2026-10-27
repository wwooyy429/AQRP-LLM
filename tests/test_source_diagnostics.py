"""Closed source diagnostics and immutable failure intents; synthetic only."""
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
    HistoricalSnapshotCollector, SourceDiagnosticError, _safe_source_diagnostic)
from qresearch.historical_source import HistoricalSourceError, QuantConnectSnapshotSource
from test_historical_source import CATALOG, FakeQB, native, response, ts


class SourceDiagnosticsTests(unittest.TestCase):
    def source(self, qb):
        return QuantConnectSnapshotSource(qb, CATALOG, api=NS(Resolution=NS(DAILY="synthetic_daily")))

    def plan(self):
        return HistoricalCollectionPlan.from_dict(dict(schema_version=1, plan_id="SYNTHETIC-DIAGNOSTIC",
            scope="engineering", source="quantconnect_fundamental_universe", data_version="synthetic-v1",
            start=ts("2018-01-03").isoformat(), end_exclusive=ts("2018-01-04").isoformat(),
            timezone="America/New_York", fields=list(CATALOG), calendar_days_per_request=1,
            max_batch_records=1, max_records_per_window=20, source_manifest_hash="a" * 64), field_catalog=CATALOG)

    def fail(self, qb):
        store, source = MemoryArtifactStore(), self.source(qb)
        collector = HistoricalSnapshotCollector(store, source, self.plan(), synthetic=True)
        with self.assertRaises(CollectionError) as caught:
            collector.collect()
        message = str(caught.exception)
        self.assertNotIn("LICENSED", message)
        self.assertNotIn("SYNTHETIC-SID", message)
        rendered = "".join(traceback.format_exception(type(caught.exception), caught.exception, caught.exception.__traceback__))
        self.assertNotIn("LICENSED", rendered)
        self.assertNotIn("SYNTHETIC-SID", rendered)
        self.assertFalse(any("/windows/" in key for key in store._data))
        self.assertTrue(any("/intents/" in key for key in store._data))
        return json.loads(message.split("; diagnostic=", 1)[1]), collector, source

    def test_native_failure_stage_kind_and_intent_no_retry(self):
        qb = FakeQB(RuntimeError("LICENSED-SECRET price=123.45"))
        diagnostic, collector, source = self.fail(qb)
        self.assertEqual(diagnostic["stage"], "history_request")
        self.assertEqual(diagnostic["exception_kind"], "runtime_error")
        self.assertEqual(diagnostic["native_calls"], 1)
        self.assertEqual(diagnostic["response_kind"], "not_observed")
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(source.history_call_count, 1)
        self.assertEqual(len(qb.calls), 1)

    def test_timezone_failure_occurs_before_provider_request(self):
        qb = FakeQB()
        def bad_zone(zone):
            raise AttributeError("LICENSED-SECRET")
        qb.set_time_zone = bad_zone
        diagnostic, _, _ = self.fail(qb)
        self.assertEqual(diagnostic["stage"], "notebook_timezone")
        self.assertEqual(diagnostic["exception_kind"], "attribute_error")
        self.assertEqual(diagnostic["native_calls"], 0)
        self.assertEqual(qb.calls, [])

    def test_universe_setup_failure_occurs_before_provider_request(self):
        qb = FakeQB()
        def bad_universe(selector):
            raise TypeError("LICENSED-SECRET")
        qb.add_universe = bad_universe
        diagnostic, _, _ = self.fail(qb)
        self.assertEqual(diagnostic["stage"], "universe_setup")
        self.assertEqual(diagnostic["native_calls"], 0)
        self.assertEqual(qb.calls, [])

    def test_dataframe_shape_uses_only_closed_structure_tokens(self):
        qb = FakeQB(pd.DataFrame({"LICENSED-COLUMN": ["LICENSED-ROW"]}, index=["LICENSED-INDEX"]))
        diagnostic, _, _ = self.fail(qb)
        self.assertEqual(diagnostic["stage"], "response_contract")
        self.assertEqual(diagnostic["response_kind"], "dataframe")
        self.assertEqual(diagnostic["response_rows"], 1)
        self.assertEqual(diagnostic["index_kind"], "other")
        self.assertEqual(diagnostic["index_levels"], 1)
        self.assertEqual(diagnostic["index_names"], "other")

    def test_index_names_are_never_exported(self):
        data = response([native()])
        data.index.names = ["LICENSED-INDEX-NAME", "time"]
        diagnostic, _, _ = self.fail(FakeQB(data))
        self.assertEqual(diagnostic["index_kind"], "multiindex")
        self.assertEqual(diagnostic["index_names"], "other")
        self.assertEqual(diagnostic["index_levels"], 2)

    def test_snapshot_container_rejected_without_representation(self):
        data = response("LICENSED-SNAPSHOT")
        diagnostic, _, _ = self.fail(FakeQB(data))
        self.assertEqual(diagnostic["stage"], "snapshot_container")
        self.assertEqual(diagnostic["snapshot_kind"], "other")
        self.assertEqual(diagnostic["snapshots_seen"], 1)
        self.assertEqual(diagnostic["rows_emitted"], 0)

    def test_retired_property_has_fixed_failure_code_and_projection_ordinal(self):
        class Retired:
            symbol = NS(id="LICENSED-SECRET-SID")
            @property
            def dollar_volume(self):
                raise RuntimeError("LICENSED-SECRET value=123.45")
        diagnostic, _, _ = self.fail(FakeQB(response([Retired()])))
        self.assertEqual(diagnostic["stage"], "field_projection")
        self.assertEqual(diagnostic["failure_code"], "native_property_failed")
        self.assertEqual(diagnostic["exception_kind"], "source_contract")
        self.assertEqual(diagnostic["projection_kind"], "number")
        self.assertEqual(diagnostic["projection_position"], list(self.plan().field_catalog).index("dollar_volume") + 1)

    def test_invalid_scalar_never_formats_object(self):
        class SecretObject:
            def __str__(self):
                raise AssertionError("object must not be formatted")
            __repr__ = __str__
        item = native()
        item.dollar_volume = SecretObject()
        diagnostic, _, _ = self.fail(FakeQB(response([item])))
        self.assertEqual(diagnostic["failure_code"], "source_contract")
        self.assertEqual(diagnostic["stage"], "field_projection")

    def test_partial_rows_are_counted_but_no_success_is_published(self):
        class Retired:
            symbol = NS(id="LICENSED-SECOND-SID")
            @property
            def dollar_volume(self):
                raise RuntimeError("LICENSED-SECRET")
        diagnostic, collector, source = self.fail(FakeQB(response([native(), Retired()])))
        self.assertEqual(diagnostic["rows_emitted"], 1)
        self.assertEqual(diagnostic["snapshots_seen"], 1)
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(source.history_call_count, 1)

    def test_response_iterator_failure_reports_progress_without_secret(self):
        class InterruptedSeries(pd.Series):
            def items(self):
                yield from super().items()
                raise RuntimeError("LICENSED-ITERATOR-SECRET")
        diagnostic, _, _ = self.fail(FakeQB(InterruptedSeries(response([native()]))))
        self.assertEqual(diagnostic["stage"], "response_iteration")
        self.assertEqual(diagnostic["rows_emitted"], 1)
        self.assertEqual(diagnostic["exception_kind"], "runtime_error")

    def test_snapshot_iterator_failure_is_distinct_from_response_iteration(self):
        class InterruptedList(list):
            def __iter__(self):
                yield from super().__iter__()
                raise RuntimeError("LICENSED-SNAPSHOT-ITERATOR")
        diagnostic, _, _ = self.fail(FakeQB(response(InterruptedList([native()]))))
        self.assertEqual(diagnostic["stage"], "snapshot_iteration")
        self.assertEqual(diagnostic["rows_emitted"], 1)
        self.assertEqual(diagnostic["snapshot_kind"], "list")

    def test_unknown_native_exception_type_name_is_not_exported(self):
        SecretType = type("LICENSED_SECRET_TYPE_NAME", (Exception,), {})
        diagnostic, _, _ = self.fail(FakeQB(SecretType("LICENSED-EXCEPTION-VALUE")))
        self.assertEqual(diagnostic["exception_kind"], "other")

    def test_direct_source_preserves_error_type_and_only_safe_diagnostic(self):
        source = self.source(FakeQB(ValueError("LICENSED-SECRET")))
        with self.assertRaises(HistoricalSourceError) as caught:
            list(source.fetch(ts("2018-01-03"), ts("2018-01-04"), CATALOG))
        self.assertNotIn("LICENSED", str(caught.exception))
        self.assertEqual(caught.exception.diagnostic["exception_kind"], "value_error")
        self.assertEqual(caught.exception.diagnostic, _safe_source_diagnostic(caught.exception.diagnostic))

    def test_diagnostic_validation_is_closed_and_rechecked_after_mutation(self):
        diagnostic, _, _ = self.fail(FakeQB(RuntimeError("LICENSED")))
        mutations = [dict(extra="LICENSED"), dict(stage="LICENSED"), dict(exception_kind="LICENSED"),
            dict(response_rows="LICENSED"), dict(response_rows=True), dict(response_rows=-1),
            dict(response_rows=1000000001), dict(schema_version=True)]
        for change in mutations:
            with self.subTest(change=change):
                error = SourceDiagnosticError("LICENSED-EXCEPTION", diagnostic=diagnostic)
                error.diagnostic.update(change)
                class BadSource:
                    def fetch(self, *args):
                        raise error
                collector = HistoricalSnapshotCollector(MemoryArtifactStore(), BadSource(), self.plan(), synthetic=True)
                with self.assertRaises(CollectionError) as caught:
                    collector.collect()
                self.assertNotIn("LICENSED", str(caught.exception))
                self.assertNotIn("diagnostic=", str(caught.exception))

    def test_arbitrary_exception_cannot_opt_in_to_diagnostic_export(self):
        diagnostic, _, _ = self.fail(FakeQB(RuntimeError("LICENSED")))
        error = RuntimeError("LICENSED-EXCEPTION")
        error.diagnostic = diagnostic
        class BadSource:
            def fetch(self, *args):
                raise error
        with self.assertRaises(CollectionError) as caught:
            HistoricalSnapshotCollector(MemoryArtifactStore(), BadSource(), self.plan(), synthetic=True).collect()
        self.assertNotIn("LICENSED", str(caught.exception))
        self.assertNotIn("diagnostic=", str(caught.exception))

    def test_owned_exception_diagnostic_property_failure_is_redacted(self):
        class HostileError(SourceDiagnosticError):
            @property
            def diagnostic(self):
                raise RuntimeError("LICENSED-DIAGNOSTIC")
        error = HostileError.__new__(HostileError)
        class BadSource:
            def fetch(self, *args):
                raise error
        with self.assertRaises(CollectionError) as caught:
            HistoricalSnapshotCollector(MemoryArtifactStore(), BadSource(), self.plan(), synthetic=True).collect()
        self.assertNotIn("LICENSED", str(caught.exception))
        self.assertNotIn("diagnostic=", str(caught.exception))

    def test_success_and_completed_cache_have_unchanged_receipt_and_no_refetch(self):
        source = self.source(FakeQB())
        collector = HistoricalSnapshotCollector(MemoryArtifactStore(), source, self.plan(), synthetic=True)
        first = collector.collect()
        second = collector.collect()
        self.assertEqual(first["window_refs"], second["window_refs"])
        self.assertEqual(source.history_call_count, 1)
        self.assertNotIn("diagnostic", first)
        self.assertFalse(first["full_historical_US200_certified"])
        self.assertFalse(first["actual_availability_certified"])


if __name__ == "__main__":
    unittest.main()
