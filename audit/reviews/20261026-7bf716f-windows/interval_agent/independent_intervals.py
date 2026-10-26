"""Independent WR-10 contract tests. Synthetic data only, no SDK/market fixtures."""
import argparse
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import platform
import socket
import sys
from types import SimpleNamespace as NS
import unittest
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True)
parser.add_argument('--label', required=True)
parser.add_argument('--out', required=True)
parser.add_argument('--methods', nargs='*')
args = parser.parse_args()
ROOT = Path(args.source).resolve()
OUT = Path(args.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'cloud'))
import numpy as np
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.collection import (HistoricalCollectionPlan, HistoricalSnapshotCollector,
    CollectionError, CollectionInterrupted)
from qresearch.historical_source import QuantConnectSnapshotSource, HistoricalSourceError

def forbidden(*args, **kwargs):
    raise AssertionError('network prohibited in independent synthetic review')
socket.socket = forbidden
NY = ZoneInfo('America/New_York')
US = timedelta(microseconds=1)
UTC = timezone.utc
CATALOG = {
    'dollar_volume': {'kind': 'number', 'role': 'independent_synthetic', 'unit': 'USD', 'period_accessor': None},
    'time': {'kind': 'text', 'role': 'observed_clock', 'unit': 'native_clock', 'period_accessor': None},
    'end_time': {'kind': 'text', 'role': 'observed_clock', 'unit': 'native_clock', 'period_accessor': None},
}
API = NS(Resolution=NS(DAILY='independent_daily'))
INPUTS = []

def ny(value):
    stamp = pd.Timestamp(value)
    return stamp.tz_localize(NY) if stamp.tzinfo is None else stamp.tz_convert(NY)

def native(value):
    return ny(value).tz_localize(None).to_pydatetime()

def instant(value):
    # Independent oracle: standard-library UTC arithmetic and zoneinfo.
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if value.tzinfo is None:
        value = value.replace(tzinfo=NY)
    return value.astimezone(UTC)

def wanted_endpoint(value):
    return (instant(value) - US).astimezone(NY).replace(tzinfo=None)

def items_for(stamp):
    end = native(stamp)
    # Native daily Fundamental EndTime is Time + one calendar day. The
    # clock metadata are observations and never availability evidence.
    return [NS(symbol=NS(id='INDEPENDENT-SID-0'), dollar_volume=0,
        time=end - timedelta(days=1), end_time=end),
        NS(symbol=NS(id='INDEPENDENT-SID-1'), dollar_volume=None,
        time=end - timedelta(days=1), end_time=end)]

class FakeQB:
    """Replays fixed LEAN (start,end] EndTime filtering in absolute time.

    No desired [start,end) filtering appears here. Native arguments are
    interpreted using the configured algorithm zone, as HistoryRequestFactory.
    """
    def __init__(self, stamps=(), frontier='2024-01-01', *, index_mode='naive', inject=None):
        self.stamps = list(stamps)
        self.time = native(frontier)
        self.universe_settings = NS()
        self.calls = []
        self.zones = []
        self.selectors = []
        self.index_mode = index_mode
        self.inject = inject
    def set_time_zone(self, value):
        if value != 'America/New_York':
            raise AssertionError('wrong notebook zone')
        self.zones.append(value)
    def add_universe(self, selector):
        self.selectors.append(selector)
        return NS(symbol='INDEPENDENT-UNIVERSE')
    def universe_history(self, universe, start, end, *, flatten):
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise AssertionError('expected Python datetime arguments')
        if start.tzinfo is not None or end.tzinfo is not None or flatten is not False:
            raise AssertionError('expected NY-naive unflattened request')
        self.calls.append((start, end))
        accepted = [x for x in self.stamps if instant(start) < instant(x) <= instant(end)]
        pairs = [('INDEPENDENT-UNIVERSE', x) for x in accepted]
        if self.inject is not None:
            pairs = self.inject(pairs)
        clocks = [(u, native(x) if self.index_mode == 'naive' else instant(x)) for u, x in pairs]
        index = pd.MultiIndex.from_tuples(clocks, names=['symbol', 'time'])
        return pd.Series([items_for(x) for _, x in pairs], index=index, dtype=object)

class RecordingSource(QuantConnectSnapshotSource):
    def __init__(self, qb):
        super().__init__(qb, CATALOG, api=API)
        self.frozen_calls = []
    def fetch(self, start, end, catalog):
        self.frozen_calls.append((start.isoformat(), end.isoformat(), catalog))
        yield from super().fetch(start, end, catalog)

def plan(start, end, days):
    return HistoricalCollectionPlan.from_dict({
        'schema_version': 1, 'plan_id': 'INDEPENDENT-WR10', 'scope': 'engineering',
        'source': 'quantconnect_fundamental_universe', 'data_version': 'independent-v1',
        'start': ny(start).isoformat(), 'end_exclusive': ny(end).isoformat(),
        'timezone': 'America/New_York', 'fields': list(CATALOG),
        'calendar_days_per_request': days, 'max_batch_records': 3,
        'max_records_per_window': 1000,
        'source_manifest_hash': hashlib.sha256((ROOT / 'cloud/qresearch/historical_source.py').read_bytes()).hexdigest()
    }, field_catalog=CATALOG)

def all_clocks(rows):
    return sorted({instant(pd.Timestamp(row['snapshot_at'])) for row in rows})

class IndependentIntervals(unittest.TestCase):
    def case(self, **params):
        INPUTS.append({'method': self._testMethodName, **params})
        return self.subTest(**params)
    def source(self, qb):
        return QuantConnectSnapshotSource(qb, CATALOG, api=API)
    def test_reference_contract_dense_microsecond_edges(self):
        for initial in ('2016-02-28', '2018-03-10', '2018-11-03', '2023-12-25'):
            for days in (1, 2, 7):
                with self.case(initial=initial, days=days):
                    left = ny(initial); right = left + pd.DateOffset(days=days)
                    points = [instant(left)-US, instant(left), instant(left)+US,
                              instant(right)-2*US, instant(right)-US, instant(right), instant(right)+US]
                    qb = FakeQB(points, right, index_mode='aware')
                    rows = list(self.source(qb).fetch(left, right, CATALOG))
                    expected = sorted(set(x for x in points if instant(left) <= x < instant(right)))
                    self.assertEqual(all_clocks(rows), expected)
                    self.assertEqual(len(rows), 2*len(expected))
                    self.assertEqual(qb.calls, [(wanted_endpoint(left), wanted_endpoint(right))])
                    self.assertEqual(len(qb.selectors), 1)
    def test_daily_one_two_seven_day_across_dst_years(self):
        for initial in ('2012-03-10', '2012-11-03', '2018-03-10', '2018-11-03',
                        '2020-03-07', '2020-10-31', '2023-03-11', '2023-11-04'):
            for days in (1, 2, 7):
                with self.case(initial=initial, days=days):
                    left = ny(initial); right = left + pd.DateOffset(days=days)
                    points = list(pd.date_range(left-pd.DateOffset(days=1), right+pd.DateOffset(days=1), freq='D'))
                    qb = FakeQB(points, right)
                    rows = list(self.source(qb).fetch(left, right, CATALOG))
                    expected = [instant(x) for x in points if instant(left) <= instant(x) < instant(right)]
                    self.assertEqual(all_clocks(rows), expected)
                    self.assertEqual(qb.calls[0], (wanted_endpoint(left), wanted_endpoint(right)))
                    self.assertEqual(len(rows), days*2)
    def test_utc_inputs_preserve_frozen_ny_midnight(self):
        for initial in ('2018-03-11', '2018-11-04', '2023-12-31'):
            for days in (1,):
                with self.case(initial=initial, days=days):
                    left = ny(initial); right = left + pd.DateOffset(days=days)
                    qb = FakeQB([left, right], right)
                    rows = list(self.source(qb).fetch(instant(left), instant(right), CATALOG))
                    self.assertEqual(all_clocks(rows), [instant(left)])
                    self.assertEqual(qb.calls, [(wanted_endpoint(left), wanted_endpoint(right))])
    def test_aware_repeated_fall_hour_is_two_distinct_instants(self):
        for initial in ('2018-11-04', '2023-11-05'):
            with self.case(initial=initial):
                left = ny(initial); right = left+pd.DateOffset(days=1)
                local = left.to_pydatetime().replace(hour=1, minute=30)
                points = [local.replace(fold=0), local.replace(fold=1)]
                qb = FakeQB(points, right, index_mode='aware')
                rows = list(self.source(qb).fetch(left, right, CATALOG))
                self.assertEqual(all_clocks(rows), sorted(instant(x) for x in points))
                self.assertEqual(len(rows), 4)
    def test_public_chain_source_to_collector(self):
        for initial in ('2018-03-07', '2018-10-31', '2023-12-12'):
            for days in (1, 2, 7):
                with self.case(initial=initial, days=days):
                    left = ny(initial); right = left+pd.DateOffset(days=20)
                    points = list(pd.date_range(left-pd.DateOffset(days=1), right, freq='D'))
                    qb = FakeQB(points, right)
                    source = RecordingSource(qb); frozen = plan(left, right, days)
                    store = MemoryArtifactStore()
                    collector = HistoricalSnapshotCollector(store, source, frozen, synthetic=True)
                    receipt = collector.collect()
                    rows = [r for ref in receipt['window_refs'] for r in collector.read_window(ref)]
                    expected = [instant(x) for x in points if instant(left) <= instant(x) < instant(right)]
                    self.assertEqual(all_clocks(rows), expected)
                    self.assertEqual(len(rows), len(expected)*2)
                    self.assertEqual(len({(r['sid'],r['snapshot_at']) for r in rows}), len(rows))
                    windows = frozen.windows()
                    self.assertEqual(source.frozen_calls, [(a.isoformat(),b.isoformat(),frozen.field_catalog) for a,b in windows])
                    self.assertEqual(qb.calls, [(wanted_endpoint(a),wanted_endpoint(b)) for a,b in windows])
                    for ref,(a,b) in zip(receipt['window_refs'],windows):
                        stored = json.loads(store.read_bytes(ref['key']))
                        self.assertEqual(stored['window'], {'start':a.isoformat(),'end_exclusive':b.isoformat()})
                        self.assertEqual(stored['missing_values']['dollar_volume'], stored['snapshot_count'])
                        self.assertFalse(stored['full_historical_US200_certified'])
                        self.assertFalse(stored['actual_availability_certified'])
                        self.assertFalse(stored['research_certified'])
                    self.assertEqual(receipt['provider_calls'], len(windows))
                    before = dict(store._data)
                    replay = HistoricalSnapshotCollector(store, None, frozen, synthetic=True).collect()
                    self.assertEqual(replay['provider_calls'], 0)
                    self.assertEqual(replay['window_refs'], receipt['window_refs'])
                    self.assertEqual(store._data, before)
    def test_sparse_daily_chain_retains_metadata_and_zero(self):
        with self.case(initial='2018-01-02', days=7, shape='three daily snapshots two SIDs'):
            left = ny('2018-01-02'); right = ny('2018-01-09')
            points = [ny('2018-01-02'),ny('2018-01-04'),ny('2018-01-08')]
            qb = FakeQB(points,right)
            collector = HistoricalSnapshotCollector(MemoryArtifactStore(),self.source(qb),plan(left,right,2),synthetic=True)
            receipt = collector.collect()
            rows = [r for ref in receipt['window_refs'] for r in collector.read_window(ref)]
            self.assertEqual(all_clocks(rows), [instant(x) for x in points])
            self.assertEqual(receipt['record_count'],6)
            self.assertEqual(receipt['missing_values']['dollar_volume'],3)
            for row in rows:
                clock = native(row['snapshot_at'])
                self.assertEqual(row['values']['end_time'],clock.isoformat())
                self.assertEqual(row['values']['time'],(clock-timedelta(days=1)).isoformat())
                self.assertEqual(row['values']['dollar_volume'],0 if row['sid'].endswith('0') else None)
    def test_empty_windows_complete_without_coverage_claim(self):
        for initial in ('2018-03-11','2018-11-04','2023-12-31'):
            with self.case(initial=initial):
                left=ny(initial); right=left+pd.DateOffset(days=1)
                qb=FakeQB([],right)
                collector=HistoricalSnapshotCollector(MemoryArtifactStore(),self.source(qb),plan(left,right,1),synthetic=True)
                receipt=collector.collect()
                self.assertEqual(receipt['record_count'],0)
                self.assertEqual(receipt['empty_windows'],1)
                self.assertEqual(collector.read_window(receipt['window_refs'][0]),[])
                self.assertFalse(receipt['full_historical_US200_certified'])
    def test_final_boundary_keeps_last_microsecond(self):
        for days in (1,2,7):
            with self.case(days=days,end='2024-01-01T00:00:00-05:00'):
                right=ny('2024-01-01'); left=right-pd.DateOffset(days=days)
                points=[instant(left),instant(right)-US,instant(right),instant(right)+US]
                qb=FakeQB(points,right,index_mode='aware')
                collector=HistoricalSnapshotCollector(MemoryArtifactStore(),self.source(qb),plan(left,right,days),synthetic=True)
                receipt=collector.collect()
                rows=[r for ref in receipt['window_refs'] for r in collector.read_window(ref)]
                self.assertEqual(all_clocks(rows),points[:2])
                self.assertTrue(all(instant(b)<instant(right) for _,b in qb.calls))
    def test_invalid_request_ranges_never_dispatch(self):
        cases=[('2024-01-01T00:00:00-05:00','2024-01-02T00:00:00-05:00'),
               ('2023-12-31T00:00:00-05:00','2024-01-01T00:00:00.000001-05:00'),
               ('2018-01-01T00:00:00-05:00','2018-01-09T00:00:00-05:00'),
               ('2018-01-01T00:00:00-05:00','2018-01-01T00:00:00-05:00'),
               ('2018-01-02T00:00:00-05:00','2018-01-01T00:00:00-05:00'),
               ('2018-01-01T00:00:00.000001-05:00','2018-01-02T00:00:00-05:00'),
               ('2018-01-01','2018-01-02T00:00:00-05:00'),
               (None,'2018-01-02T00:00:00-05:00'),('bad','2018-01-02T00:00:00-05:00')]
        for left,right in cases:
            with self.case(start=left,end=right):
                qb=FakeQB()
                with self.assertRaises(HistoricalSourceError):
                    list(self.source(qb).fetch(left,right,CATALOG))
                self.assertEqual(qb.calls,[])
                self.assertEqual(qb.selectors,[])
    def test_frontier_contract_blocks_future_and_pre_request(self):
        for frontier in ('2018-01-01','2024-01-02'):
            with self.case(frontier=frontier):
                qb=FakeQB([],frontier)
                with self.assertRaises(HistoricalSourceError):
                    list(self.source(qb).fetch(ny('2018-01-01'),ny('2018-01-02'),CATALOG))
                self.assertEqual(qb.calls,[])
    def test_outside_response_and_duplicate_rejected(self):
        left=ny('2018-03-11'); right=ny('2018-03-12')
        mutations={
            'before_start':lambda pairs:[('INDEPENDENT-UNIVERSE',instant(left)-US)],
            'at_end':lambda pairs:[('INDEPENDENT-UNIVERSE',right)],
            'after_end':lambda pairs:[('INDEPENDENT-UNIVERSE',instant(right)+US)],
            'duplicate':lambda pairs:pairs+pairs,
            'mixed_universe':lambda pairs:pairs+[('OTHER-UNIVERSE',left)],
        }
        for label,mutation in mutations.items():
            with self.case(mutation=label):
                qb=FakeQB([left],right,inject=mutation)
                with self.assertRaises(HistoricalSourceError):
                    list(self.source(qb).fetch(left,right,CATALOG))
                self.assertEqual(len(qb.calls),1)
    def test_failed_end_response_keeps_intent_and_blocks_retry(self):
        for end in ('2018-01-02','2024-01-01'):
            with self.case(end=end):
                right=ny(end); left=right-pd.DateOffset(days=1)
                qb=FakeQB([left],right,inject=lambda pairs:[('INDEPENDENT-UNIVERSE',right)])
                source=self.source(qb); store=MemoryArtifactStore()
                collector=HistoricalSnapshotCollector(store,source,plan(left,right,1),synthetic=True)
                with self.assertRaises(CollectionError): collector.collect()
                self.assertTrue(any('/intents/' in key for key in store._data))
                self.assertFalse(any('/windows/' in key for key in store._data))
                before=dict(store._data)
                with self.assertRaises(CollectionInterrupted): collector.collect()
                self.assertEqual(store._data,before)
                self.assertEqual(len(qb.calls),1)

class AuditResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw); self.subcases=0; self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err is not None and self.first_failure is None:
            self.first_failure={'test':str(test),'subtest':str(subtest),'error':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None: self.first_failure={'test':str(test),'error':self._exc_info_to_string(err,test)}
        super().addError(test,err)
    def addFailure(self,test,err):
        if self.first_failure is None: self.first_failure={'test':str(test),'error':self._exc_info_to_string(err,test)}
        super().addFailure(test,err)

suite=unittest.TestSuite(IndependentIntervals(name) for name in args.methods) if args.methods else unittest.defaultTestLoader.loadTestsFromTestCase(IndependentIntervals)
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(suite)
raw=stream.getvalue()
path=OUT/(args.label+'_unittest.txt'); path.write_text(raw,encoding='utf-8')
files=['cloud/qresearch/historical_source.py','cloud/qresearch/collection.py','cloud/qresearch/contracts.py','cloud/qresearch/artifacts.py']
hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
summary={'label':args.label,'source_root':str(ROOT),'fixed_commit':('7bf716f45fd6183951a492f0201012af717070f0' if args.label=='candidate' else 'fbe2454e6ea10aa59211c01f236c54bb251527be'),
    'command_argv':sys.argv,'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__,
    'hashes_raw_sha256':hashes,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'methods':result.testsRun,'subcases':result.subcases,'failure_records':len(result.failures),
    'error_records':len(result.errors),'skipped':len(result.skipped),'success':result.wasSuccessful(),
    'first_failure':result.first_failure,'inputs':INPUTS,'raw_log':str(path),
    'prohibited_actions':{'real_SDK':0,'market':0,'Research':0,'LEAN':0,'models':0,'deploy':0,'budget_changes':0},
    'claim_scope':'fixed official static contract replay with synthetic objects, not actual SDK execution or financial evidence'}
(OUT/(args.label+'_summary.json')).write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
print(raw)
print(json.dumps({k:v for k,v in summary.items() if k not in {'inputs','first_failure'}},ensure_ascii=False,default=str))
sys.exit(0 if result.wasSuccessful() else 1)
