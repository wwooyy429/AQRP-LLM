"""Synthetic lossless engineering observations; no SDK or provider execution."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.collection import (CollectionError, CollectionIntegrityError, CollectionInterrupted,
    CollectionMiss, HistoricalCollectionPlan, HistoricalSnapshotCollector)
from test_collection import CATALOG, RawSource, Source, plan_dict, row


POLICY = "retain_source_occurrences"
FLAGS = ("full_historical_US200_certified", "actual_availability_certified", "research_certified", "row_values_exported")


def occurrence(index=0, sid="A", stamp="2018-01-01T09:00:00-05:00", **values):
    return row(sid, stamp, **values) | {"source_record_index": index}


def plan(**changes):
    raw = plan_dict(schema_version=2, observation_policy=POLICY,
                    end_exclusive="2018-01-02T00:00:00-05:00") | changes
    return HistoricalCollectionPlan.from_dict(raw, field_catalog=CATALOG)


class CollectionOccurrenceTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()

    def collect(self, records, frozen=None):
        source = Source(records)
        collector = HistoricalSnapshotCollector(self.store, source, frozen or plan(), synthetic=True)
        return collector, collector.collect(), source

    def manifest(self, receipt):
        reference = receipt["window_refs"][0]
        return reference, json.loads(self.store.read_bytes(reference["key"]))

    def rewrite_manifest(self, reference, document):
        encoded = canonical_json(document)
        self.store._data[reference["key"]] = encoded
        return {"key": reference["key"], "sha256": sha256(encoded).hexdigest()}

    def mutate_batch(self, collector, receipt, index, mutate):
        reference, manifest = self.manifest(receipt)
        batch = json.loads(self.store.read_bytes(manifest["batches"][index]["key"]))
        mutate(batch)
        digest = content_hash(batch)
        batch_ref = {"key": "historical-snapshots/v2/objects/" + digest + ".json", "sha256": digest}
        self.store.write_once(batch_ref["key"], canonical_json(batch))
        manifest["batches"][index] = batch_ref
        changed = self.rewrite_manifest(reference, manifest)
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window(changed)

    def test_version_two_exact_plan_and_identity_cannot_mix_with_version_one(self):
        frozen = plan()
        expected = plan_dict(schema_version=2, observation_policy=POLICY,
                             end_exclusive="2018-01-02T00:00:00-05:00")
        expected["fields"] = sorted(expected["fields"])
        self.assertEqual(frozen.to_dict(), expected)
        legacy = HistoricalCollectionPlan.from_dict(plan_dict(), field_catalog=CATALOG)
        self.assertNotIn("observation_policy", legacy.to_dict())
        self.assertNotEqual(frozen.hash, legacy.hash)
        invalid = [plan_dict(schema_version=2), plan_dict(observation_policy=POLICY),
                   expected | {"observation_policy": "unique_sid"}, expected | {"extra": 1},
                   expected | {"schema_version": 3}, expected | {"scope": "research"},
                   expected | {"observation_policy": True}, expected | {"schema_version": True}]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(CollectionError):
                HistoricalCollectionPlan.from_dict(raw, field_catalog=CATALOG)

    def test_identical_and_conflicting_occurrences_retained_in_source_order_across_batches(self):
        records = [occurrence(0), occurrence(1, "B"), occurrence(2),
                   occurrence(3, dollar_volume=7), occurrence(4)]
        collector, receipt, _ = self.collect(records)
        reference, manifest = self.manifest(receipt)
        self.assertEqual(collector.read_window(reference), records)
        for document in (receipt, manifest):
            self.assertEqual(document["schema_version"], 2)
            self.assertEqual(document["observation_policy"], POLICY)
            self.assertEqual(document["record_count"], 5)
            self.assertEqual(document["duplicate_projection_records"], 3)
            self.assertEqual(document["conflicting_projection_records"], 1)
            self.assertTrue(all(document[name] is False for name in FLAGS))
        self.assertEqual((manifest["unique_sid_count"], manifest["snapshot_count"]), (2, 1))
        self.assertEqual(manifest["missing_values"]["financial_statements.file_date.value"], 5)
        batches = [json.loads(self.store.read_bytes(ref["key"])) for ref in manifest["batches"]]
        self.assertEqual([len(batch["records"]) for batch in batches], [2, 2, 1])
        self.assertTrue(all(batch["schema_version"] == 2 for batch in batches))
        self.assertTrue(all(key.startswith("historical-snapshots/v2/") for key in self.store._data))
        self.assertNotIn('"values"', json.dumps(receipt))
        self.assertNotIn('"snapshot_at"', json.dumps(receipt))

    def test_indices_reset_per_snapshot_and_counts_aggregate_windows(self):
        records = [occurrence(0), occurrence(1, dollar_volume=1),
                   occurrence(0, stamp="2018-01-01T10:00:00-05:00", dollar_volume=2),
                   occurrence(1, stamp="2018-01-01T10:00:00-05:00", dollar_volume=2),
                   occurrence(0, stamp="2018-01-02T09:00:00-05:00", dollar_volume=3)]
        collector, receipt, _ = self.collect(records, plan(end_exclusive="2018-01-03T00:00:00-05:00"))
        self.assertEqual((receipt["record_count"], receipt["duplicate_projection_records"],
                          receipt["conflicting_projection_records"]), (5, 2, 1))
        first = json.loads(self.store.read_bytes(receipt["window_refs"][0]["key"]))
        self.assertEqual(first["snapshot_count"], 2)
        self.assertEqual(first["unique_sid_count"], 1)
        self.assertEqual(collector.read_window(receipt["window_refs"][1]), records[-1:])

    def test_conflicts_compare_every_later_projection_with_first_not_previous(self):
        collector, receipt, _ = self.collect([occurrence(0), occurrence(1, dollar_volume=1),
                                             occurrence(2, dollar_volume=1), occurrence(3)])
        self.assertEqual(receipt["duplicate_projection_records"], 3)
        self.assertEqual(receipt["conflicting_projection_records"], 2)
        self.assertEqual(len(collector.read_window(receipt["window_refs"][0])), 4)

    def test_empty_window_has_explicit_zero_counts_and_no_certification(self):
        collector, receipt, _ = self.collect([])
        reference, manifest = self.manifest(receipt)
        self.assertEqual(collector.read_window(reference), [])
        for document in (receipt, manifest):
            self.assertEqual(document["record_count"], 0)
            self.assertEqual(document["duplicate_projection_records"], 0)
            self.assertEqual(document["conflicting_projection_records"], 0)
            self.assertTrue(all(document[name] is False for name in FLAGS))
        self.assertEqual(manifest["batches"], [])
        self.assertEqual((manifest["snapshot_count"], manifest["unique_sid_count"]), (0, 0))

    def test_cache_only_revalidates_all_rows_without_source_calls_or_writes(self):
        with self.assertRaises(CollectionMiss):
            HistoricalSnapshotCollector(self.store, None, plan(), synthetic=True).collect()
        self.assertEqual(self.store._data, {})
        collector, receipt, source = self.collect([occurrence(0), occurrence(1)])
        saved = dict(self.store._data)
        reader = HistoricalSnapshotCollector(self.store, None, plan(), synthetic=True)
        replayed = reader.collect()
        self.assertEqual((replayed["provider_calls"], replayed["reused_windows"]), (0, 1))
        self.assertEqual(replayed["duplicate_projection_records"], 1)
        self.assertEqual(reader.read_window(receipt["window_refs"][0]), collector.read_window(receipt["window_refs"][0]))
        self.assertEqual(len(source.calls), 1)
        self.assertEqual(self.store._data, saved)

    def test_strict_occurrence_row_schema_and_native_index_leave_unfinished_intent(self):
        records = [row(), occurrence() | {"extra": 1}]
        records += [occurrence() | {"source_record_index": value}
                    for value in (True, False, -1, 1.0, "0", None, np.int64(0), 10)]
        for record in records:
            with self.subTest(record=record):
                store, source = MemoryArtifactStore(), RawSource([record])
                collector = HistoricalSnapshotCollector(store, source, plan(), synthetic=True)
                with self.assertRaises(CollectionError):
                    collector.collect()
                with self.assertRaises(CollectionInterrupted):
                    collector.collect()
                self.assertEqual(source.calls, 1)
                self.assertFalse(any("/windows/" in key for key in store._data))

    def test_index_start_skip_repeat_and_cross_batch_reset_are_rejected(self):
        invalid = [[occurrence(1)], [occurrence(0), occurrence(2)],
                   [occurrence(0), occurrence(0)], [occurrence(0), occurrence(1), occurrence(0)],
                   [occurrence(0), occurrence(1, stamp="2018-01-01T10:00:00-05:00")]]
        for records in invalid:
            with self.subTest(records=records), self.assertRaises(CollectionError):
                HistoricalSnapshotCollector(MemoryArtifactStore(), RawSource(records), plan(), synthetic=True).collect()

    def test_record_bound_counts_all_occurrences_and_all_snapshot_rows(self):
        for records in ([occurrence(0), occurrence(1), occurrence(2)],
                        [occurrence(0, stamp="2018-01-01T0%d:00:00-05:00" % hour)
                         for hour in (1, 2, 3)]):
            with self.subTest(records=records):
                store = MemoryArtifactStore()
                collector = HistoricalSnapshotCollector(store, RawSource(records),
                    plan(max_batch_records=1, max_records_per_window=2), synthetic=True)
                with self.assertRaises(CollectionError):
                    collector.collect()
                self.assertFalse(any("/windows/" in key for key in store._data))
                with self.assertRaises(CollectionInterrupted):
                    collector.collect()

    def test_rehashed_manifest_counts_policy_flags_schema_and_unknown_fields_rejected(self):
        collector, receipt, _ = self.collect([occurrence(0), occurrence(1, dollar_volume=2)])
        reference, original = self.manifest(receipt)
        changes = [{"duplicate_projection_records": 0}, {"conflicting_projection_records": 0},
                   {"duplicate_projection_records": True}, {"conflicting_projection_records": True},
                   {"record_count": 1}, {"observation_policy": "unique_sid"}, {"schema_version": 1},
                   {"unexpected": 0}] + [{flag: True} for flag in FLAGS]
        for change in changes:
            changed = self.rewrite_manifest(reference, original | change)
            with self.subTest(change=change), self.assertRaises(CollectionIntegrityError):
                collector.read_window(changed)
        self.rewrite_manifest(reference, original)
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window(self.rewrite_manifest(reference,
                {key: value for key, value in original.items() if key != "observation_policy"}))

    def test_rehashed_batches_cannot_hide_skips_resets_counts_or_row_schema(self):
        mutations = [lambda b: b["records"][0].update(source_record_index=0),
                     lambda b: b["records"][0].update(source_record_index=3),
                     lambda b: b["records"][0].update(source_record_index=True),
                     lambda b: b["records"][0].update(extra=0),
                     lambda b: b.update(schema_version=1), lambda b: b.update(extra=0),
                     lambda b: b["records"][0]["values"].update(dollar_volume=7)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.store = MemoryArtifactStore()
                collector, receipt, _ = self.collect([occurrence(0), occurrence(1), occurrence(2)])
                self.mutate_batch(collector, receipt, 1, mutate)

    def test_legacy_rows_bytes_and_strict_duplicate_semantics_are_unchanged(self):
        frozen = HistoricalCollectionPlan.from_dict(plan_dict(end_exclusive="2018-01-02T00:00:00-05:00"), field_catalog=CATALOG)
        collector = HistoricalSnapshotCollector(self.store, Source([row("A"), row("B")]), frozen, synthetic=True)
        receipt = collector.collect()
        reference, manifest = self.manifest(receipt)
        for document in (receipt, manifest):
            self.assertEqual(document["schema_version"], 1)
            self.assertTrue({"observation_policy", "duplicate_projection_records", "conflicting_projection_records"}.isdisjoint(document))
        self.assertTrue(all(key.startswith("historical-snapshots/v1/") for key in self.store._data))
        self.assertEqual(collector.read_window(reference), [row("A"), row("B")])
        with self.assertRaises(CollectionError):
            HistoricalSnapshotCollector(MemoryArtifactStore(), RawSource([row(), row()]), frozen, synthetic=True).collect()
        with self.assertRaises(CollectionError):
            HistoricalSnapshotCollector(MemoryArtifactStore(), RawSource([occurrence()]), frozen, synthetic=True).collect()
        reader = HistoricalSnapshotCollector(self.store, None, plan(), synthetic=True)
        with self.assertRaises(CollectionIntegrityError):
            reader.read_window(reference)

    def test_source_error_cannot_publish_partial_window_or_retry(self):
        class FailingSource:
            calls = 0
            def fetch(inner, start, end, catalog):
                inner.calls += 1
                yield occurrence(0)
                yield occurrence(1)
                raise RuntimeError("LICENSED_ROW_VALUE")
        source = FailingSource()
        collector = HistoricalSnapshotCollector(self.store, source, plan(), synthetic=True)
        with self.assertRaises(CollectionError) as caught:
            collector.collect()
        self.assertNotIn("LICENSED", str(caught.exception))
        self.assertEqual(len([key for key in self.store._data if "/objects/" in key]), 1)
        self.assertFalse(any("/windows/" in key for key in self.store._data))
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(source.calls, 1)


if __name__ == "__main__":
    unittest.main()
