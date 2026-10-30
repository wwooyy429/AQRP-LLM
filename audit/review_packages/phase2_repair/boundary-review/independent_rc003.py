"""Independent RC003 boundaries: synthetic objects only, no SDK/provider I/O."""
from datetime import datetime, timedelta, date, time
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'cloud'))
import pandas as pd
from qresearch.historical_source import QuantConnectSnapshotSource, HistoricalSourceError, _history_start
from qresearch.collection import HistoricalCollectionPlan, HistoricalSnapshotCollector, CollectionError, CollectionInterrupted
from qresearch.artifacts import MemoryArtifactStore

FIELD = {'dollar_volume': {'kind': 'number', 'role': 'synthetic_only', 'unit': 'synthetic', 'period_accessor': None}}

def ny(value):
    return pd.Timestamp(value, tz='America/New_York')

class Symbol:
    id = 'SYNTHETIC-UNIVERSE-SID'
    def __str__(self):
        return 'SYNTHETIC-UNIVERSE-TICKER'

class Book:
    def __init__(self, entries=(), frontier=datetime(2018, 1, 20)):
        self.time = frontier
        self.universe_settings = SimpleNamespace(resolution=None)
        self.entries = list(entries)
        self.calls = []
        self.symbol = Symbol()
    def set_time_zone(self, value):
        assert value == 'America/New_York'
    def add_universe(self, selector):
        return SimpleNamespace(symbol=self.symbol)
    def universe_history(self, universe, start, end, *, flatten):
        self.calls.append((start, end, flatten))
        if not self.entries:
            return pd.DataFrame()
        index = pd.MultiIndex.from_tuples([(identity, stamp) for identity, stamp, _ in self.entries], names=['symbol', 'time'])
        return pd.Series([values for _, _, values in self.entries], index=index, dtype=object)

def row(sid='SYNTHETIC-STOCK-SID', value=17):
    return {'symbol': {'id': sid}, 'dollar_volume': value}

def source(book):
    return QuantConnectSnapshotSource(book, FIELD, api=SimpleNamespace(Resolution=SimpleNamespace(DAILY='SYNTHETIC')))

def entries(*values):
    return [('SYNTHETIC-UNIVERSE-TICKER', pd.Timestamp(stamp), payload) for stamp, payload in values]

class BoundaryReview(unittest.TestCase):
    def test_manual_prior_file_endtime_is_recovered(self):
        class FileBook(Book):
            # Independent finite inventory: no weekday loop and no production endpoint helper.
            files = [(date(2018, 1, 8), datetime(2018, 1, 9), 17),
                     (date(2018, 1, 9), datetime(2018, 1, 10), 29)]
            def universe_history(self, universe, start, end, *, flatten):
                self.calls.append((start, end, flatten))
                answer = []
                for file_date, endpoint, value in self.files:
                    opening = datetime.combine(file_date, time(9, 30))
                    closing = datetime.combine(file_date, time(16))
                    if start < closing and end >= opening and start < endpoint <= end:
                        answer.append(('SYNTHETIC-UNIVERSE-TICKER', pd.Timestamp(endpoint), [row(value=value)]))
                self.entries = answer
                if not answer:
                    return pd.DataFrame()
                return pd.Series([e[2] for e in answer], index=pd.MultiIndex.from_tuples([(e[0], e[1]) for e in answer], names=['symbol','time']), dtype=object)
        qb = FileBook()
        answer = list(source(qb).fetch(ny('2018-01-09'), ny('2018-01-10'), FIELD))
        self.assertEqual([(x['snapshot_at'], x['values']['dollar_volume']) for x in answer], [('2018-01-09T00:00:00-05:00', 17)])
        self.assertEqual(qb.calls, [(datetime(2018,1,8), datetime(2018,1,9,23,59,59,999999), False)])

    def test_lower_envelope_item_is_cropped_without_touching_fields(self):
        class CannotRead:
            def __getattribute__(self, name):
                raise RuntimeError('SYNTHETIC SECRET OUTSIDE LOGICAL WINDOW')
        qb = Book(entries(('2018-01-08 12:00', CannotRead()), ('2018-01-09', [row()])))
        answer = list(source(qb).fetch(ny('2018-01-09'), ny('2018-01-10'), FIELD))
        self.assertEqual(len(answer), 1)
        self.assertEqual(answer[0]['values'], {'dollar_volume':17})

    def test_cropped_duplicate_remains_error(self):
        qb = Book(entries(('2018-01-08 12:00', []), ('2018-01-08 12:00', []), ('2018-01-09', [row()])))
        with self.assertRaises(HistoricalSourceError):
            list(source(qb).fetch(ny('2018-01-09'), ny('2018-01-10'), FIELD))

    def test_wrong_universe_outside_logical_still_rejected(self):
        qb = Book([('FOREIGN-SYNTHETIC', pd.Timestamp('2018-01-08 12:00'), []),
            ('SYNTHETIC-UNIVERSE-TICKER', pd.Timestamp('2018-01-09'), [row()])])
        with self.assertRaises(HistoricalSourceError):
            list(source(qb).fetch(ny('2018-01-09'), ny('2018-01-10'), FIELD))

    def test_end_and_submicrosecond_overflow_remain_errors(self):
        for clock in ('2018-01-10', '2018-01-09 23:59:59.999999500'):
            qb = Book(entries((clock, [])))
            with self.subTest(clock=clock), self.assertRaises(HistoricalSourceError):
                list(source(qb).fetch(ny('2018-01-09'), ny('2018-01-10'), FIELD))

    def test_utc_spelling_normalizes_to_same_NY_window(self):
        qb = Book(entries(('2018-01-09', [row()])))
        got = list(source(qb).fetch(pd.Timestamp('2018-01-09T05:00Z'), pd.Timestamp('2018-01-10T05:00Z'), FIELD))
        self.assertEqual(got[0]['snapshot_at'], '2018-01-09T00:00:00-05:00')
        self.assertEqual(qb.calls[0][0], datetime(2018,1,8))

    def test_DST_lower_day_remains_midnight_for_UTC_input(self):
        self.assertEqual(_history_start(pd.Timestamp('2018-03-12T04:00Z')), datetime(2018,3,11))
        self.assertEqual(_history_start(pd.Timestamp('2018-11-05T05:00Z')), datetime(2018,11,4))

    def test_last_development_interval_excludes_reserved_start(self):
        qb = Book(entries(('2023-12-30', [row()])), frontier=datetime(2024,1,1))
        got = list(source(qb).fetch(ny('2023-12-29'), ny('2024-01-01'), FIELD))
        self.assertEqual([x['snapshot_at'] for x in got], ['2023-12-30T00:00:00-05:00'])
        self.assertEqual(qb.calls[0][1], datetime(2023,12,31,23,59,59,999999))
        bad = Book(entries(('2024-01-01', [row()])), frontier=datetime(2024,1,1))
        with self.assertRaises(HistoricalSourceError):
            list(source(bad).fetch(ny('2023-12-29'), ny('2024-01-01'), FIELD))

    def test_missing_native_sentinel_is_not_a_synthetic_fill(self):
        qb = Book()
        adapter = source(qb)
        self.assertEqual(list(adapter.fetch(ny('2018-01-09'), ny('2018-01-10'), FIELD)), [])
        self.assertEqual(len(qb.calls), 1)
        self.assertFalse(adapter.provenance()['actual_availability_certified'])

    def test_partial_failure_keeps_intent_and_prohibits_fetch(self):
        qb = Book(entries(('2018-01-09', [row()]), ('2024-01-01', [])))
        adapter = source(qb)
        plan = HistoricalCollectionPlan.from_dict({'schema_version':1, 'plan_id':'SYNTHETIC-INDEPENDENT-BOUNDARY',
            'scope':'engineering', 'source':'quantconnect_fundamental_universe', 'data_version':'SYNTHETIC-v1',
            'start':ny('2018-01-09').isoformat(), 'end_exclusive':ny('2018-01-10').isoformat(),
            'timezone':'America/New_York', 'fields':['dollar_volume'], 'calendar_days_per_request':1,
            'max_batch_records':1, 'max_records_per_window':2, 'source_manifest_hash':'e'*64}, field_catalog=FIELD)
        store = MemoryArtifactStore()
        collector = HistoricalSnapshotCollector(store, adapter, plan, synthetic=True)
        with self.assertRaises(CollectionError):
            collector.collect()
        prior = dict(store._data)
        with self.assertRaises(CollectionInterrupted):
            collector.collect()
        self.assertEqual(store._data, prior)
        self.assertEqual(len(qb.calls), 1)
        self.assertFalse(any('/windows/' in key for key in prior))
        self.assertTrue(any('/intents/' in key for key in prior))

if __name__ == '__main__':
    unittest.main(verbosity=2)
