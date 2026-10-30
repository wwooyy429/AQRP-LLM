"""New SID diagnostic codes: independent synthetic/privacy tests only."""
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import json
import sys
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'cloud'))
import pandas as pd
from qresearch.collection import CollectionError, CollectionInterrupted, HistoricalCollectionPlan, HistoricalSnapshotCollector, _safe_source_diagnostic
from qresearch.historical_source import QuantConnectSnapshotSource, HistoricalSourceError
from qresearch.artifacts import MemoryArtifactStore
from independent_rc003 import Book, FIELD, row, entries, ny

SECRET = 'SENSITIVE-UNEXPORTED-IDENTIFIER'
OLD_KEYS = {'schema_version','stage','failure_code','exception_kind','response_kind','index_kind','index_names',
    'snapshot_kind','projection_kind','native_calls','response_rows','index_levels','snapshots_seen','rows_emitted','projection_position'}

class SIDReview(unittest.TestCase):
    def fail(self, data=None, error=None):
        class ErrorBook(Book):
            def universe_history(self, universe, start, end, *, flatten):
                if error is not None:
                    self.calls.append((start,end,flatten))
                    raise error
                return super().universe_history(universe,start,end,flatten=flatten)
        qb = ErrorBook(entries(('2018-01-09', data)))
        source = QuantConnectSnapshotSource(qb, FIELD, api=NS(Resolution=NS(DAILY='SYNTHETIC')))
        plan = HistoricalCollectionPlan.from_dict({'schema_version':1, 'plan_id':'SYNTHETIC-SID-INDEPENDENT',
            'scope':'engineering','source':'quantconnect_fundamental_universe','data_version':'SYNTHETIC-v1',
            'start':ny('2018-01-09').isoformat(),'end_exclusive':ny('2018-01-10').isoformat(),
            'timezone':'America/New_York','fields':['dollar_volume'],'calendar_days_per_request':1,
            'max_batch_records':1,'max_records_per_window':5,'source_manifest_hash':'b'*64}, field_catalog=FIELD)
        store = MemoryArtifactStore()
        collector = HistoricalSnapshotCollector(store, source, plan, synthetic=True)
        with self.assertRaises(CollectionError) as caught:
            collector.collect()
        message = str(caught.exception)
        formatted = ''.join(traceback.format_exception(type(caught.exception),caught.exception,caught.exception.__traceback__))
        self.assertNotIn(SECRET, message)
        self.assertNotIn(SECRET, formatted)
        diagnostic = json.loads(message.split('; diagnostic=',1)[1])
        self.assertEqual(set(diagnostic), OLD_KEYS)
        self.assertEqual(diagnostic, _safe_source_diagnostic(diagnostic))
        self.assertEqual(diagnostic['schema_version'],1)
        before = dict(store._data)
        self.assertTrue(any('/intents/' in k for k in before))
        self.assertFalse(any('/windows/' in k for k in before))
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(before,store._data)
        self.assertEqual(len(qb.calls),1)
        return diagnostic

    def test_actual_missing_is_distinct(self):
        for data in ({}, {'symbol':{}}, {'symbol':{'id':None}}):
            with self.subTest(data_kind=list(data)):
                d = self.fail([data])
                self.assertEqual(d['failure_code'],'native_sid_missing')
                self.assertEqual(d['rows_emitted'],0)

    def test_empty_trimmed_and_overlength_are_noncanonical(self):
        for value in ('', ' '+SECRET, SECRET+'\t', SECRET*20):
            with self.subTest(length=len(value)):
                d = self.fail([row(value)])
                self.assertEqual(d['failure_code'],'native_sid_noncanonical')
                self.assertEqual(d['rows_emitted'],0)

    def test_duplicate_uses_sid_equality_not_object_or_ticker(self):
        class SyntheticSID:
            def __str__(self):
                return SECRET
        d = self.fail([row(SyntheticSID(),1),row(SyntheticSID(),2)])
        self.assertEqual(d['failure_code'],'native_sid_duplicate')
        self.assertEqual(d['rows_emitted'],1)

    def test_native_RuntimeError_literals_cannot_choose_code(self):
        for text in ('Missing native permanent SID','Noncanonical native permanent SID','Duplicate native permanent SID'):
            with self.subTest(message=text):
                d = self.fail(error=RuntimeError(text))
                self.assertEqual(d['failure_code'],'unexpected_exception')
                self.assertEqual(d['stage'],'history_request')

    def test_hostile_sid_conversion_cannot_choose_code_or_leak(self):
        class SID:
            def __str__(self):
                raise ValueError('Duplicate native permanent SID '+SECRET)
        d = self.fail([row(SID())])
        self.assertEqual(d['failure_code'],'unexpected_exception')
        self.assertEqual(d['stage'],'row_identity')

    def test_property_exception_preserves_old_code(self):
        class S:
            @property
            def id(self):
                raise AttributeError(SECRET)
        d = self.fail([NS(symbol=S(),dollar_volume=1)])
        self.assertEqual(d['failure_code'],'native_property_failed')

    def test_old_error_contract_still_valid(self):
        d = self.fail(error=HistoricalSourceError('Unique native permanent SIDs are required'))
        self.assertEqual(d['failure_code'],'source_contract')

    def test_diagnostic_closed_enum_and_shape(self):
        d = self.fail([{'symbol':{}}])
        for bad in (SECRET, 'native_sid_duplicate '+SECRET, None, 1, True):
            self.assertIsNone(_safe_source_diagnostic(dict(d,failure_code=bad)))
        self.assertIsNone(_safe_source_diagnostic(dict(d,sid=SECRET)))
        self.assertIsNone(_safe_source_diagnostic(dict(d,rows_emitted=True)))

    def test_same_sid_on_distinct_snapshot_not_dropped(self):
        qb = Book(entries(('2018-01-09',[row(SECRET,1)]),('2018-01-10',[row(SECRET,2)])))
        adapter = QuantConnectSnapshotSource(qb,FIELD,api=NS(Resolution=NS(DAILY='SYNTHETIC')))
        got = list(adapter.fetch(ny('2018-01-09'),ny('2018-01-11'),FIELD))
        self.assertEqual([x['values']['dollar_volume'] for x in got],[1,2])
        self.assertEqual([x['sid'] for x in got],[SECRET,SECRET])

if __name__=='__main__':
    unittest.main(verbosity=2)
