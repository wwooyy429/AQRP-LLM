"""Synthetic quarantine protocol boundaries; no SDK, QC, or real registry."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tests')]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.collection import (HistoricalCollectionPlan, HistoricalSnapshotCollector,
    CollectionError, CollectionIntegrityError, CollectionInterrupted)
from qresearch.historical_source import QuantConnectSnapshotSource, HistoricalSourceError, observed_liquidity_record
from test_collection import CATALOG, plan_dict, row, RawSource
from test_historical_source import CATALOG as NATIVE_CATALOG, FakeQB, native, response, ts


def frozen(version=2, **changes):
    raw = plan_dict(schema_version=version, end_exclusive='2018-01-02T00:00:00-05:00', **changes)
    if version == 2:
        raw['observation_policy'] = 'retain_source_occurrences'
    return HistoricalCollectionPlan.from_dict(raw, field_catalog=CATALOG)


def occurrence(sid='SYN-A', index=0, stamp='2018-01-01T09:00:00-05:00', **values):
    return dict(row(sid, stamp, **values), source_record_index=index)


class IndependentOccurrenceTests(unittest.TestCase):
    def collect(self, rows, plan=None):
        store = MemoryArtifactStore(); source = RawSource(rows)
        collector = HistoricalSnapshotCollector(store, source, plan or frozen(), synthetic=True)
        return store, source, collector, collector.collect()

    def rejected_without_completed_window(self, rows):
        store = MemoryArtifactStore(); source = RawSource(rows)
        collector = HistoricalSnapshotCollector(store, source, frozen(max_batch_records=1), synthetic=True)
        with self.assertRaises(CollectionError):
            collector.collect()
        self.assertFalse(any('/windows/' in key for key in store._data))
        self.assertTrue(any('/intents/' in key for key in store._data))
        before = source.calls
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(source.calls, before)

    def test_v2_preserves_all_occurrences_missingness_and_first_relative_conflicts(self):
        rows = [occurrence(index=0, dollar_volume=10), occurrence(index=1, dollar_volume=20),
                occurrence(index=2, dollar_volume=10)]
        store, source, collector, receipt = self.collect(rows)
        self.assertEqual(receipt['record_count'], 3)
        self.assertEqual(receipt['duplicate_projection_records'], 2)
        self.assertEqual(receipt['conflicting_projection_records'], 1)
        self.assertEqual(receipt['missing_values']['financial_statements.file_date.value'], 3)
        ref = receipt['window_refs'][0]
        manifest = json.loads(store.read_bytes(ref['key']))
        self.assertEqual((manifest['unique_sid_count'], manifest['snapshot_count']), (1, 1))
        self.assertEqual(collector.read_window(ref), rows)
        self.assertEqual([len(json.loads(store.read_bytes(r['key']))['records']) for r in manifest['batches']], [2, 1])
        again = HistoricalSnapshotCollector(store, None, frozen(), synthetic=True).collect()
        self.assertEqual(again['window_refs'], receipt['window_refs'])
        self.assertEqual(again['provider_calls'], 0)
        self.assertEqual(source.calls, 1)
        for flag in ('full_historical_US200_certified', 'actual_availability_certified', 'research_certified', 'row_values_exported'):
            self.assertIs(receipt[flag], False)

    def test_indices_are_for_entire_snapshot_not_each_sid_and_reset_at_new_snapshot(self):
        self.rejected_without_completed_window([occurrence('A', 0), occurrence('B', 0)])
        rows = [occurrence('A', 0), occurrence('B', 1),
                occurrence('A', 0, stamp='2018-01-01T10:00:00-05:00')]
        _, _, _, report = self.collect(rows)
        self.assertEqual(report['duplicate_projection_records'], 0)
        self.assertEqual(report['conflicting_projection_records'], 0)

    def test_ordinal_gaps_repetition_reordering_and_noninteger_types_fail_closed(self):
        for indexes in ((1,), (0, 2), (0, 0), (0, 2, 1), (False,), (0.0,), (-1,), (None,)):
            with self.subTest(indexes=indexes):
                self.rejected_without_completed_window([occurrence(str(n), index) for n, index in enumerate(indexes)])

    def test_occurrences_not_unique_sids_consume_record_cap(self):
        rows = [occurrence(index=0), occurrence(index=1), occurrence(index=2)]
        store = MemoryArtifactStore(); source = RawSource(rows)
        collector = HistoricalSnapshotCollector(store, source,
            frozen(max_records_per_window=2, max_batch_records=1), synthetic=True)
        with self.assertRaises(CollectionError):
            collector.collect()
        self.assertFalse(any('/windows/' in key for key in store._data))
        self.assertEqual(len([key for key in store._data if '/objects/' in key]), 2)

    def test_v1_rejects_occurrence_rows_and_v2_rejects_legacy_rows(self):
        for plan, rows in ((frozen(1), [occurrence()]), (frozen(), [row()])):
            with self.subTest(version=plan.to_dict()['schema_version']), self.assertRaises(CollectionError):
                self.collect(rows, plan)
        with self.assertRaises(CollectionError):
            self.collect([row('A'), row('A')], frozen(1))
        store, _, _, report = self.collect([row('A')], frozen(1))
        self.assertEqual(report['schema_version'], 1)
        self.assertNotIn('observation_policy', report)
        self.assertNotIn('duplicate_projection_records', report)
        self.assertTrue(all(key.startswith('historical-snapshots/v1/') for key in store._data))

    def test_v1_and_v2_plans_remain_closed_distinct_contracts(self):
        for raw in (plan_dict(schema_version=2),
                    plan_dict(observation_policy='retain_source_occurrences'),
                    dict(plan_dict(schema_version=2), observation_policy='unique_sid'),
                    dict(plan_dict(schema_version=2), observation_policy=True)):
            with self.subTest(raw=raw), self.assertRaises(CollectionError):
                HistoricalCollectionPlan.from_dict(raw, field_catalog=CATALOG)
        self.assertNotEqual(frozen().hash, frozen(1).hash)

    def test_rehashed_manifest_cannot_change_occurrence_counters_or_certification(self):
        store, _, collector, receipt = self.collect([occurrence(index=0), occurrence(index=1, dollar_volume=1)])
        ref = receipt['window_refs'][0]; original = store.read_bytes(ref['key']); manifest = json.loads(original)
        for changes in ({'duplicate_projection_records': 0}, {'conflicting_projection_records': 0},
                        {'duplicate_projection_records': True}, {'record_count': 1},
                        {'research_certified': True}, {'observation_policy': 'unique_sid'}):
            with self.subTest(changes=changes):
                altered = manifest | changes
                store._data[ref['key']] = canonical_json(altered)
                forged = {'key': ref['key'], 'sha256': content_hash(altered)}
                with self.assertRaises(CollectionIntegrityError):
                    collector.read_window(forged)
                store._data[ref['key']] = original

    def test_rehashed_batch_ordinal_reset_cannot_be_hidden_by_plausible_counts(self):
        store, _, collector, receipt = self.collect([occurrence('A', 0), occurrence('B', 1), occurrence('A', 2)])
        ref = receipt['window_refs'][0]; manifest = json.loads(store.read_bytes(ref['key']))
        payload = json.loads(store.read_bytes(manifest['batches'][1]['key']))
        payload['records'][0]['source_record_index'] = 0
        digest = content_hash(payload); key = 'historical-snapshots/v2/objects/'+digest+'.json'
        store.write_once(key, canonical_json(payload))
        manifest['batches'][1] = {'key': key, 'sha256': digest}
        store._data[ref['key']] = canonical_json(manifest)
        with self.assertRaises(CollectionIntegrityError):
            collector.read_window({'key': ref['key'], 'sha256': content_hash(manifest)})

    def test_native_default_rejects_duplicates_explicit_retain_keeps_order(self):
        a, b, c = native('A'), native('A'), native('A')
        b.dollar_volume = 200
        for policy in (None, 'retain_source_occurrences'):
            qb = FakeQB(response([a, b, c]))
            options = {} if policy is None else {'observation_policy': policy}
            source = QuantConnectSnapshotSource(qb, NATIVE_CATALOG,
                api=NS(Resolution=NS(DAILY='synthetic')), **options)
            if policy is None:
                with self.assertRaises(HistoricalSourceError):
                    list(source.fetch(ts('2018-01-03'), ts('2018-01-04'), NATIVE_CATALOG))
            else:
                rows = list(source.fetch(ts('2018-01-03'), ts('2018-01-04'), NATIVE_CATALOG))
                self.assertEqual([r['source_record_index'] for r in rows], [0, 1, 2])
                self.assertEqual([r['values']['dollar_volume'] for r in rows], [100, 200, 100])
                self.assertEqual(len(qb.calls), 1)
                for r in rows:
                    with self.assertRaises(HistoricalSourceError):
                        observed_liquidity_record(r, session_close=ts('2018-01-02')+__import__('pandas').Timedelta(hours=16))

    def test_retain_policy_does_not_skip_invalid_sid_or_projection(self):
        for bad in (native(None), native(' bad '), native(' 0')):
            qb = FakeQB(response([native('A'), bad, native('A')]))
            source = QuantConnectSnapshotSource(qb, NATIVE_CATALOG,
                api=NS(Resolution=NS(DAILY='synthetic')), observation_policy='retain_source_occurrences')
            with self.assertRaises(HistoricalSourceError):
                list(source.fetch(ts('2018-01-03'), ts('2018-01-04'), NATIVE_CATALOG))


if __name__ == '__main__':
    unittest.main(verbosity=2)
