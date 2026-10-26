"""Synthetic snapshot collection boundaries; no SDK or market-data access."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.collection import (CollectionError, CollectionIntegrityError,
    CollectionInterrupted, CollectionMiss, HistoricalCollectionPlan,
    HistoricalSnapshotCollector)


CATALOG = {
    "dollar_volume": {"kind": "number", "role": "liquidity", "unit": "USD", "period_accessor": None},
    "has_fundamental_data": {"kind": "boolean", "role": "coverage", "unit": "boolean", "period_accessor": None},
    "financial_statements.file_date.value": {"kind": "date", "role": "source_metadata", "unit": "date", "period_accessor": "value"},
    "security_reference.exchange_id": {"kind": "text", "role": "classification", "unit": "code", "period_accessor": None},
}


def plan_dict(**changes):
    return dict(schema_version=1, plan_id="synthetic-plan", scope="engineering",
        source="quantconnect_fundamental_universe", data_version="synthetic-v1",
        start="2018-01-01T00:00:00-05:00", end_exclusive="2018-01-03T00:00:00-05:00",
        timezone="America/New_York", fields=list(CATALOG), calendar_days_per_request=1,
        max_batch_records=2, max_records_per_window=10, source_manifest_hash="a" * 64) | changes


def plan(**changes):
    return HistoricalCollectionPlan.from_dict(plan_dict(**changes), field_catalog=CATALOG)


def row(sid="synthetic-SID-A", stamp="2018-01-01T09:00:00-05:00", **values):
    projected = {"dollar_volume": 0, "has_fundamental_data": False,
        "financial_statements.file_date.value": None, "security_reference.exchange_id": "SYN"}
    return {"sid": sid, "snapshot_at": stamp, "values": projected | values}


class Source:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def fetch(self, start, end, catalog):
        self.calls.append((start, end, deepcopy(catalog)))
        for item in self.rows:
            if start <= pd.Timestamp(item["snapshot_at"]) < end:
                yield deepcopy(item)


class RawSource:
    """Deliberately ignore bounds, for collector validation tests."""
    def __init__(self, rows):
        self.rows, self.calls = rows, 0

    def fetch(self, start, end, catalog):
        self.calls += 1
        yield from self.rows


class CollectionPlanTests(unittest.TestCase):
    def test_plan_immutable_and_identity_pins_selected_catalog(self):
        raw, catalog = plan_dict(), deepcopy(CATALOG)
        frozen = HistoricalCollectionPlan.from_dict(raw, field_catalog=catalog)
        before = frozen.hash
        raw["fields"].clear()
        catalog["dollar_volume"]["unit"] = "changed"
        copied = frozen.to_dict()
        copied["fields"].clear()
        frozen.field_catalog["dollar_volume"]["unit"] = "changed"
        self.assertEqual(frozen.hash, before)
        self.assertEqual(frozen.field_catalog["dollar_volume"]["unit"], "USD")
        with self.assertRaises((AttributeError, TypeError)):
            frozen._encoded = b"changed"
        updated = deepcopy(CATALOG)
        updated["dollar_volume"]["unit"] = "other"
        self.assertNotEqual(before, HistoricalCollectionPlan.from_dict(plan_dict(), field_catalog=updated).hash)

    def test_catalog_field_order_and_unselected_fields_do_not_change_identity(self):
        a = plan(fields=["dollar_volume", "has_fundamental_data"])
        b = plan(fields=["has_fundamental_data", "dollar_volume"])
        extra = deepcopy(CATALOG)
        extra["unused"] = {"kind": "text", "role": "unused", "unit": "code", "period_accessor": None}
        c = HistoricalCollectionPlan.from_dict(plan_dict(fields=a.to_dict()["fields"]), field_catalog=extra)
        self.assertEqual(a.hash, b.hash)
        self.assertEqual(a.hash, c.hash)

    def test_unknown_overrides_and_unrestricted_fields_rejected(self):
        for changes in ({"extra": 1}, {"scope": "research"}, {"source": "current_constituents"},
                        {"timezone": "UTC"}, {"schema_version": True}, {"fields": []},
                        {"fields": ["dollar_volume", "dollar_volume"]}, {"fields": ["future_return"]},
                        {"fields": "dollar_volume"}, {"source_manifest_hash": "A" * 64},
                        {"data_version": " "}, {"plan_id": None}, {"plan_id": float("nan")}):
            with self.subTest(changes=changes), self.assertRaises(CollectionError):
                plan(**changes)
        missing = plan_dict()
        del missing["source_manifest_hash"]
        with self.assertRaises(CollectionError):
            HistoricalCollectionPlan.from_dict(missing, field_catalog=CATALOG)

    def test_strict_integer_bounds_and_batch_window_consistency(self):
        for key, value in (("calendar_days_per_request", True), ("calendar_days_per_request", 0),
                           ("calendar_days_per_request", 8), ("max_batch_records", 10001),
                           ("max_records_per_window", 200001), ("max_batch_records", 2.0),
                           ("max_batch_records", 11)):
            with self.subTest(key=key, value=value), self.assertRaises(CollectionError):
                plan(**{key: value})

    def test_naive_nonmidnight_final_and_empty_dates_rejected(self):
        for changes in ({"start": "2018-01-01"}, {"end_exclusive": None},
                        {"start": "2018-01-01T01:00:00-05:00"},
                        {"start": "2018-01-03T00:00:00-05:00"},
                        {"end_exclusive": "2024-01-02T00:00:00-05:00"},
                        {"start": "2024-01-01T00:00:00-05:00", "end_exclusive": "2025-01-01T00:00:00-05:00"}):
            with self.subTest(changes=changes), self.assertRaises(CollectionError):
                plan(**changes)
        self.assertEqual(len(plan(end_exclusive="2024-01-01T00:00:00-05:00", calendar_days_per_request=7).windows()), 313)

    def test_calendar_windows_preserve_NY_midnight_across_both_DST_edges(self):
        for start, end, expected_hours in (("2018-03-10T00:00:00-05:00", "2018-03-13T00:00:00-04:00", [24, 23, 24]),
                                          ("2018-11-03T00:00:00-04:00", "2018-11-06T00:00:00-05:00", [24, 25, 24])):
            windows = plan(start=start, end_exclusive=end).windows()
            self.assertEqual([(b-a).total_seconds()/3600 for a,b in windows], expected_hours)
            self.assertTrue(all(a.hour == b.hour == 0 for a,b in windows))
            self.assertTrue(all(windows[i][1] == windows[i+1][0] for i in range(len(windows)-1)))

    def test_trusted_catalog_requires_safe_complete_typed_attribute_definitions(self):
        cases = ({}, {"_private": CATALOG["dollar_volume"]},
                 {"a.__class__": CATALOG["dollar_volume"]}, {"f()": CATALOG["dollar_volume"]},
                 {"dollar_volume": {"kind": "number"}},
                 {"dollar_volume": CATALOG["dollar_volume"] | {"extra": 1}},
                 {"dollar_volume": CATALOG["dollar_volume"] | {"kind": "arbitrary"}},
                 {"dollar_volume": CATALOG["dollar_volume"] | {"role": None}},
                 {"dollar_volume": CATALOG["dollar_volume"] | {"period_accessor": 1}})
        for catalog in cases:
            with self.subTest(catalog=catalog), self.assertRaises(CollectionError):
                HistoricalCollectionPlan.from_dict(plan_dict(), field_catalog=catalog)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.store, self.plan = MemoryArtifactStore(), plan()

    def collect(self, source, frozen=None):
        collector = HistoricalSnapshotCollector(self.store, source, frozen or self.plan, synthetic=True)
        return collector, collector.collect()

    def one_day(self, **changes):
        return plan(end_exclusive="2018-01-02T00:00:00-05:00", **changes)

    def rewrite(self, reference, document):
        raw = canonical_json(document)
        self.store._data[reference["key"]] = raw
        return {"key": reference["key"], "sha256": sha256(raw).hexdigest()}

    def test_real_rows_require_cloud_and_synthetic_flag_is_boolean(self):
        with self.assertRaises(CollectionError):
            HistoricalSnapshotCollector(self.store, Source([]), self.plan)
        with self.assertRaises(CollectionError):
            HistoricalSnapshotCollector(self.store, Source([]), self.plan, synthetic="true")
        self.store.residency = "quantconnect_cloud"
        collector = HistoricalSnapshotCollector(self.store, Source([]), self.plan)
        self.assertFalse(collector.synthetic)
        with self.assertRaises(CollectionError):
            HistoricalSnapshotCollector(self.store, object(), self.plan)
        with self.assertRaises(CollectionError):
            HistoricalSnapshotCollector(self.store, Source([]), plan_dict(), synthetic=True)

    def test_batches_reused_without_source_calls_or_additional_objects(self):
        source = Source([row("A"), row("B"), row("C"), row("A", "2018-01-02T09:00:00-05:00")])
        collector, first = self.collect(source)
        keys = dict(self.store._data)
        second = collector.collect()
        self.assertEqual(first["window_refs"], second["window_refs"])
        self.assertEqual((first["provider_calls"], second["provider_calls"]), (2, 0))
        self.assertEqual(second["reused_windows"], 2)
        self.assertEqual(len(source.calls), 2)
        self.assertEqual(self.store._data, keys)
        window = json.loads(self.store.read_bytes(first["window_refs"][0]["key"]))
        self.assertEqual([len(json.loads(self.store.read_bytes(ref["key"]))["records"]) for ref in window["batches"]], [2, 1])
        self.assertEqual(len(collector.read_window(first["window_refs"][0])), 3)

    def test_receipt_exports_counts_and_hashes_without_row_values_or_sids(self):
        collector, receipt = self.collect(Source([row()]))
        exported = json.dumps(receipt)
        self.assertNotIn("synthetic-SID-A", exported)
        self.assertNotIn('"snapshot_at"', exported)
        self.assertNotIn('"values"', exported)
        self.assertEqual(receipt["missing_values"]["financial_statements.file_date.value"], 1)
        for name in ("full_historical_US200_certified", "actual_availability_certified", "research_certified", "row_values_exported"):
            self.assertIs(receipt[name], False)
        restored = collector.read_window(receipt["window_refs"][0])[0]["values"]
        self.assertEqual(restored["dollar_volume"], 0)
        self.assertIs(restored["has_fundamental_data"], False)
        self.assertIsNone(restored["financial_statements.file_date.value"])

    def test_cache_only_reads_completed_windows_and_never_fetches_missing_windows(self):
        with self.assertRaises(CollectionMiss):
            HistoricalSnapshotCollector(self.store, None, self.plan, synthetic=True).collect()
        self.assertEqual(self.store._data, {})
        _, receipt = self.collect(Source([row()]))
        reader = HistoricalSnapshotCollector(self.store, None, self.plan, synthetic=True)
        self.assertEqual(reader.collect()["provider_calls"], 0)
        self.assertEqual(len(reader.read_window(receipt["window_refs"][0])), 1)

    def test_empty_windows_are_explicit_and_never_coverage_certification(self):
        collector, receipt = self.collect(Source([]))
        self.assertEqual((receipt["empty_windows"], receipt["record_count"]), (2, 0))
        self.assertEqual(collector.read_window(receipt["window_refs"][0]), [])
        self.assertFalse(receipt["full_historical_US200_certified"])

    def test_strict_row_schema_and_bounds_leave_intent_and_prevent_retry(self):
        bad_rows = [row() | {"extra": 1}, row() | {"sid": ""}, row() | {"sid": "x" * 257},
                    row() | {"snapshot_at": "2018-01-01"},
                    row() | {"snapshot_at": "2018-01-02T00:00:00-05:00"},
                    row() | {"snapshot_at": "2024-01-01T00:00:00-05:00"},
                    row() | {"values": {}}, row() | {"values": row()["values"] | {"extra": 3}}]
        for bad in bad_rows:
            with self.subTest(bad=bad):
                store, source = MemoryArtifactStore(), RawSource([bad])
                collector = HistoricalSnapshotCollector(store, source, self.one_day(), synthetic=True)
                with self.assertRaises(CollectionError):
                    collector.collect()
                with self.assertRaises(CollectionInterrupted):
                    collector.collect()
                self.assertEqual(source.calls, 1)
                self.assertTrue(any("/intents/" in key for key in store._data))
                self.assertFalse(any("/windows/" in key for key in store._data))

    def test_invalid_scalar_types_and_nonfinite_values_rejected(self):
        bad_values = [("dollar_volume", True), ("dollar_volume", "100"),
                      ("dollar_volume", float("nan")), ("dollar_volume", float("inf")),
                      ("dollar_volume", 10 ** 1000), ("has_fundamental_data", 0),
                      ("security_reference.exchange_id", 1), ("security_reference.exchange_id", "x" * 4097),
                      ("financial_statements.file_date.value", "2018-01-01T00:00:00"),
                      ("financial_statements.file_date.value", "2018-02-30"),
                      ("financial_statements.file_date.value", "20180101")]
        for field, value in bad_values:
            with self.subTest(field=field, value=str(value)[:30]), self.assertRaises(CollectionError):
                HistoricalSnapshotCollector(MemoryArtifactStore(), RawSource([row(**{field: value})]),
                    self.one_day(), synthetic=True).collect()

    def test_each_declared_scalar_kind_accepts_only_its_canonical_value(self):
        collector, receipt = self.collect(Source([row(**{"dollar_volume": 2.5,
            "has_fundamental_data": True, "financial_statements.file_date.value": "2017-12-31"})]))
        values = collector.read_window(receipt["window_refs"][0])[0]["values"]
        self.assertEqual(values["dollar_volume"], 2.5)
        self.assertIs(values["has_fundamental_data"], True)
        self.assertEqual(values["financial_statements.file_date.value"], "2017-12-31")

    def test_duplicate_sid_snapshot_rejected_even_across_batches(self):
        with self.assertRaises(CollectionError):
            self.collect(RawSource([row("A"), row("B"), row("A")]), self.one_day())
        self.assertEqual(len([key for key in self.store._data if "/objects/" in key]), 1)
        self.assertFalse(any("/windows/" in key for key in self.store._data))

    def test_window_record_bound_fails_before_completed_publication(self):
        with self.assertRaises(CollectionError):
            self.collect(RawSource([row("A"), row("B"), row("C")]), self.one_day(max_records_per_window=2))
        self.assertFalse(any("/windows/" in key for key in self.store._data))

    def test_source_failure_is_redacted_and_cannot_automatically_retry(self):
        class FailingSource:
            calls = 0
            def fetch(inner, start, end, fields):
                inner.calls += 1
                yield row()
                raise CollectionError("LICENSED synthetic-SID-A value=123.45")
        source = FailingSource()
        collector = HistoricalSnapshotCollector(self.store, source, self.one_day(), synthetic=True)
        with self.assertRaises(CollectionError) as caught:
            collector.collect()
        self.assertNotIn("LICENSED", str(caught.exception))
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(source.calls, 1)
        self.assertFalse(any("/windows/" in key for key in self.store._data))

    def test_fetch_call_failure_or_noniterator_result_is_redacted(self):
        class BadSource:
            def fetch(inner, start, end, fields):
                raise RuntimeError("PRIVATE_DATA")
        class NonIteratorSource:
            def fetch(inner, start, end, fields):
                return None
        for source in (BadSource(), NonIteratorSource()):
            with self.subTest(source=type(source).__name__), self.assertRaises(CollectionError) as caught:
                HistoricalSnapshotCollector(MemoryArtifactStore(), source, self.one_day(), synthetic=True).collect()
            self.assertNotIn("PRIVATE_DATA", str(caught.exception))

    def test_partial_plan_reuses_completed_prefix_but_blocks_failed_window(self):
        class SecondWindowFails(Source):
            def fetch(inner, start, end, catalog):
                if start.day == 2:
                    inner.calls.append((start, end, catalog))
                    raise RuntimeError("failure")
                yield from super(SecondWindowFails, inner).fetch(start, end, catalog)
        source = SecondWindowFails([row()])
        collector = HistoricalSnapshotCollector(self.store, source, self.plan, synthetic=True)
        with self.assertRaises(CollectionError):
            collector.collect()
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(len(source.calls), 2)
        self.assertEqual(len([key for key in self.store._data if "/windows/" in key]), 1)

    def test_cross_plan_source_catalog_and_synthetic_reference_rejected(self):
        _, receipt = self.collect(Source([row()]))
        reference = receipt["window_refs"][0]
        for other in (plan(data_version="other"), plan(source_manifest_hash="b" * 64), plan(fields=["dollar_volume"])):
            with self.subTest(other=other.hash), self.assertRaises(CollectionIntegrityError):
                HistoricalSnapshotCollector(self.store, None, other, synthetic=True).read_window(reference)
        self.store.residency = "quantconnect_cloud"
        with self.assertRaises(CollectionIntegrityError):
            HistoricalSnapshotCollector(self.store, None, self.plan).read_window(reference)

    def test_reference_payload_hash_corruption_missing_and_noncanonical_bytes_rejected(self):
        collector, receipt = self.collect(Source([row()]))
        reference = receipt["window_refs"][0]
        original = self.store.read_bytes(reference["key"])
        for raw in (original + b"\n", b"{}", b"not JSON"):
            self.store._data[reference["key"]] = raw
            with self.assertRaises(CollectionIntegrityError):
                collector.read_window(reference)
        del self.store._data[reference["key"]]
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window(reference)
        self.store._data[reference["key"]] = original
        for bad in (reference | {"extra": 1}, reference | {"key": "../bad"},
                    reference | {"sha256": "0" * 64}, reference | {"sha256": True}):
            with self.assertRaises(CollectionIntegrityError):
                collector.read_window(bad)

    def test_rehashed_manifest_cannot_change_counts_flags_or_source_identity(self):
        collector, receipt = self.collect(Source([row()]))
        reference = receipt["window_refs"][0]
        original = json.loads(self.store.read_bytes(reference["key"]))
        bad_changes = ({"record_count": True}, {"record_count": 2}, {"provider_calls": True},
                       {"provider_calls": 2}, {"missing_values": {}},
                       {"full_historical_US200_certified": True}, {"research_certified": 0},
                       {"status": "partial"}, {"plan_hash": "0" * 64}, {"synthetic": 1})
        for change in bad_changes:
            changed = self.rewrite(reference, original | change)
            with self.subTest(change=change), self.assertRaises(CollectionIntegrityError):
                collector.read_window(changed)

    def test_rehashed_manifest_cannot_point_to_cross_window_or_forged_batch(self):
        collector, receipt = self.collect(Source([row(), row("B", "2018-01-02T09:00:00-05:00")]))
        first, second = receipt["window_refs"]
        original = json.loads(self.store.read_bytes(first["key"]))
        other = json.loads(self.store.read_bytes(second["key"]))
        replaced = self.rewrite(first, original | {"batches": other["batches"]})
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window(replaced)
        original_ref = original["batches"][0]
        payload = json.loads(self.store.read_bytes(original_ref["key"]))
        payload["records"] *= 2
        digest = content_hash(payload)
        key = "historical-snapshots/v1/objects/" + digest + ".json"
        self.store.write_once(key, canonical_json(payload))
        replaced = self.rewrite(first, original | {"batches": [{"key": key, "sha256": digest}]})
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window(replaced)

    def test_rehashed_payload_with_invalid_row_is_integrity_failure(self):
        collector, receipt = self.collect(Source([row()]))
        reference = receipt["window_refs"][0]
        manifest = json.loads(self.store.read_bytes(reference["key"]))
        payload = json.loads(self.store.read_bytes(manifest["batches"][0]["key"]))
        payload["records"][0]["values"]["has_fundamental_data"] = 0
        digest = content_hash(payload)
        key = "historical-snapshots/v1/objects/" + digest + ".json"
        self.store.write_once(key, canonical_json(payload))
        changed = self.rewrite(reference, manifest | {"batches": [{"key": key, "sha256": digest}]})
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window(changed)


if __name__ == "__main__":
    unittest.main()
