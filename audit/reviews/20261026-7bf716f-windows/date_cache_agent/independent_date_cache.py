"""WR09 independent public source/date/cache tests, entirely synthetic.

The same script's --legacy-source mode uses the unmodified fbe archive to
produce genuine old-format cache artifacts from independently created inputs.
It does not import any developer or archived independent test fixtures.
"""
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
from types import SimpleNamespace as NS
from hashlib import sha256
from copy import deepcopy
from uuid import uuid4
import ast, difflib, io, json, math, subprocess, sys, unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'source'
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-fbe2454-20261026\source')
LEGACY=len(sys.argv)>1 and sys.argv[1]=='--legacy-source'
sys.path.insert(0,str((OLD if LEGACY else SOURCE)/'cloud'))
import numpy as np
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore,FilesystemArtifactStore,canonical_json,content_hash
from qresearch.collection import (HistoricalCollectionPlan,HistoricalSnapshotCollector,CollectionError,
                                 CollectionIntegrityError,CollectionInterrupted)
from qresearch.historical_source import QuantConnectSnapshotSource,HistoricalSourceError

RUN=ROOT/'stores'/uuid4().hex
P1='financial_statements.file_date.value'
P2='financial_statements.period_ending_date.value'
CAT={P1:{'kind':'date','role':'independent_filing_day','unit':'ISO_date','period_accessor':'value'},
     P2:{'kind':'date','role':'independent_period_end','unit':'ISO_date','period_accessor':'value'},
     'dollar_volume':{'kind':'number','role':'independent_observed_liquidity','unit':'USD','period_accessor':None},
     'has_fundamental_data':{'kind':'boolean','role':'coverage','unit':'boolean','period_accessor':None},
     'time':{'kind':'text','role':'native_clock_observation','unit':'ISO_clock','period_accessor':None}}
API=NS(Resolution=NS(DAILY='synthetic-daily'))
OBS={}
def ts(s):return pd.Timestamp(s,tz='America/New_York')
def plan():
    return HistoricalCollectionPlan.from_dict({'schema_version':1,'plan_id':'independent-wr09-new-data',
      'scope':'engineering','source':'quantconnect_fundamental_universe','data_version':'independent-date-cache-v1',
      'start':ts('2021-11-08').isoformat(),'end_exclusive':ts('2021-11-10').isoformat(),
      'timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':1,
      'max_batch_records':2,'max_records_per_window':12,'source_manifest_hash':'e'*64},field_catalog=CAT)

class ResolvedDate:
    def __init__(self,resolved):self.resolved=resolved;self.value_reads=0
    @property
    def value(self):self.value_reads+=1;return self.resolved
    @property
    def has_value(self):raise AssertionError('Default-period has_value must not discard resolved fallback')

def item(sid,a,b,volume=0,covered=False):
    return NS(symbol=NS(id=sid),financial_statements=NS(file_date=ResolvedDate(a),period_ending_date=ResolvedDate(b)),
              dollar_volume=volume,has_fundamental_data=covered,time=datetime(2021,11,8,12,17))

class NativeBook:
    """Independent SDK-shaped book with explicit right-closed native filter."""
    def __init__(self,snapshots):
        self.snapshots=snapshots;self.time=datetime(2021,11,11);self.universe_settings=NS();self.calls=[]
    def set_time_zone(self,zone):
        if zone!='America/New_York':raise AssertionError(zone)
    def add_universe(self,selector):return NS(symbol='independent-date-universe')
    def universe_history(self,universe,start,end,*,flatten):
        self.calls.append((start.isoformat(),end.isoformat(),flatten))
        if flatten is not False:raise AssertionError('flatten changes projected shape')
        selected=[(stamp,objects) for stamp,objects in self.snapshots if start<stamp<=end]
        index=pd.MultiIndex.from_tuples([('independent-date-universe',stamp) for stamp,_ in selected],names=['symbol','time'])
        return pd.Series([objects for _,objects in selected],index=index,dtype=object)

def source(book):return QuantConnectSnapshotSource(book,CAT,api=API)
def fetch_one(a,b=None):
    book=NativeBook([(datetime(2021,11,8,12,17),[item('independent-date-A',a,a if b is None else b)])])
    rows=list(source(book).fetch(ts('2021-11-08'),ts('2021-11-09'),CAT))
    return book,rows[0]
def scan(path):
    return {p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
def all_rows(collector,receipt):
    return [row for reference in receipt['window_refs'] for row in collector.read_window(reference)]

def legacy_build(mode,path):
    bad=mode=='bad'
    people=[item('legacy-valid-A',date(2021,10,27),date(2021,9,30)),
            item('legacy-valid-B',None,None),
            item('legacy-sentinel-C',datetime.min if bad else date(1,1,2),date.min if bad else date(2000,2,29))]
    book=NativeBook([(datetime(2021,11,8,12,17),people)])
    store=FilesystemArtifactStore(path,data_classification='synthetic')
    c=HistoricalSnapshotCollector(store,source(book),plan(),synthetic=True)
    receipt=c.collect();rows=all_rows(c,receipt)
    result={'baseline':'fbe2454e6ea10aa59211c01f236c54bb251527be','mode':mode,'source_calls':len(book.calls),
            'receipt':receipt,'rows':rows,'source_files_sha256':{
                rel:sha256((OLD/rel).read_bytes()).hexdigest() for rel in ['cloud/qresearch/historical_source.py','cloud/qresearch/collection.py']}}
    target=Path(path).parent/(mode+'-baseline-generation.json')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False));return 0

class CountingNeverFetch:
    def __init__(self):self.calls=0
    def fetch(self,*a,**k):self.calls+=1;raise AssertionError('Old cache must not trigger a repair fetch')

class DateCacheTests(unittest.TestCase):
    def test_public_source_recognizes_only_date_min_as_missing(self):
        values=[date.min,datetime.min,pd.Timestamp(datetime.min),'0001-01-01']
        for value in values:
            with self.subTest(type=type(value).__name__):
                book,record=fetch_one(value)
                self.assertIsNone(record['values'][P1]);self.assertIsNone(record['values'][P2])
                self.assertEqual(len(book.calls),1);self.assertEqual(record['sid'],'independent-date-A')

    def test_real_dates_adjacent_to_sentinel_and_leap_day_are_preserved(self):
        values=[(date(1,1,2),'0001-01-02'),('0001-01-02','0001-01-02'),
                (datetime(1,1,2,23,59,59),'0001-01-02'),(date(1899,12,31),'1899-12-31'),
                (date(2000,2,29),'2000-02-29'),(pd.Timestamp('2020-02-29T23:00:00Z'),'2020-02-29')]
        for value,expected in values:
            with self.subTest(value=str(value)):
                _,record=fetch_one(value)
                self.assertEqual(record['values'][P1],expected);self.assertEqual(record['values'][P2],expected)

    def test_valid_resolved_fallback_is_preserved_without_reading_default_has_value(self):
        a=item('fallback-A',datetime(2021,10,27),date(2021,9,30))
        # Properties deliberately raise if the source tries to inspect the
        # default period instead of the already resolved public Value.
        book=NativeBook([(datetime(2021,11,8,12,17),[a])]);store=MemoryArtifactStore()
        c=HistoricalSnapshotCollector(store,source(book),plan(),synthetic=True)
        receipt=c.collect();record=all_rows(c,receipt)[0]
        self.assertEqual(record['values'][P1],'2021-10-27');self.assertEqual(record['values'][P2],'2021-09-30')
        self.assertEqual(receipt['missing_values'][P1],0);self.assertEqual(receipt['missing_values'][P2],0)
        self.assertEqual(a.financial_statements.file_date.value_reads,1)
        self.assertEqual(a.financial_statements.period_ending_date.value_reads,1)

    def test_existing_null_variants_and_zero_fields_keep_their_types(self):
        for value in [None,pd.NaT,pd.NA,float('nan'),np.float64('nan')]:
            with self.subTest(type=type(value).__name__):
                _,record=fetch_one(value)
                self.assertIsNone(record['values'][P1]);self.assertIsNone(record['values'][P2])
                self.assertEqual(record['values']['dollar_volume'],0)
                self.assertIs(type(record['values']['dollar_volume']),int)
                self.assertIs(record['values']['has_fundamental_data'],False)
        book=NativeBook([(datetime(2021,11,8,12,17),[item('signed-zero',date.min,date(1,1,2),volume=-0.0)])])
        record=list(source(book).fetch(ts('2021-11-08'),ts('2021-11-09'),CAT))[0]
        self.assertEqual(math.copysign(1,record['values']['dollar_volume']),-1)

    def test_complete_source_collector_read_chain_counts_independent_date_gaps(self):
        people=[item('chain-A',datetime.min,date.min),
                item('chain-B',date(2021,10,27),date(2021,9,30),volume=5),
                item('chain-C',date(2021,10,26),datetime.min),
                item('chain-D',date(1,1,2),None)]
        last=[item('chain-E',date(1899,12,31),'0001-01-01')]
        book=NativeBook([(datetime(2021,11,8,12,17),people),(datetime(2021,11,9,12,17),last)])
        store=MemoryArtifactStore();c=HistoricalSnapshotCollector(store,source(book),plan(),synthetic=True)
        receipt=c.collect();records=all_rows(c,receipt);before=dict(store._data);second=c.collect()
        self.assertEqual(receipt['record_count'],5);self.assertEqual(receipt['window_count'],2)
        self.assertEqual(receipt['missing_values'][P1],1);self.assertEqual(receipt['missing_values'][P2],4)
        self.assertEqual([r['values'][P1] for r in records],[None,'2021-10-27','2021-10-26','0001-01-02','1899-12-31'])
        self.assertEqual([r['values'][P2] for r in records],[None,'2021-09-30',None,None,None])
        self.assertEqual(len(book.calls),2);self.assertEqual(second['provider_calls'],0)
        self.assertEqual(second['window_refs'],receipt['window_refs']);self.assertEqual(store._data,before)
        for flag in ['full_historical_US200_certified','actual_availability_certified','research_certified','row_values_exported']:
            with self.subTest(flag=flag):self.assertIs(receipt[flag],False)
        OBS['new_chain']={'record_count':5,'window_count':2,'missing_values':receipt['missing_values'],
                          'source_calls':len(book.calls),'second_new_calls':second['provider_calls'],
                          'stored_dates':[{P1:r['values'][P1],P2:r['values'][P2]} for r in records]}

    def generate_old(self,mode):
        path=RUN/(mode+'-legacy')
        cmd=[sys.executable,'-B',str(Path(__file__).resolve()),'--legacy-source',mode,str(path)]
        completed=subprocess.run(cmd,text=True,capture_output=True,timeout=30)
        (ROOT/(mode+'-baseline-command.json')).write_text(json.dumps({'command':cmd,'returncode':completed.returncode,
            'stdout':completed.stdout,'stderr':completed.stderr},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        payload=json.loads(completed.stdout);return path,payload

    def test_actual_fbe_written_wrong_cache_is_rejected_whole_without_repair_or_mutation(self):
        path,old=self.generate_old('bad');before=scan(path);source_spy=CountingNeverFetch()
        self.assertEqual(old['rows'][2]['values'][P1],'0001-01-01')
        self.assertEqual(old['rows'][2]['values'][P2],'0001-01-01')
        self.assertEqual(old['receipt']['missing_values'][P1],1)
        # There are two complete batches in the first window; the first is
        # legitimate, so rejecting the second must not expose a partial list.
        ref=old['receipt']['window_refs'][0]
        for supplied_source in [None,source_spy]:
            with self.subTest(source=type(supplied_source).__name__):
                store=FilesystemArtifactStore(path,data_classification='synthetic')
                c=HistoricalSnapshotCollector(store,supplied_source,plan(),synthetic=True)
                with self.assertRaises(CollectionIntegrityError):c.read_window(ref)
                with self.assertRaises(CollectionIntegrityError):c.collect()
                self.assertEqual(scan(path),before)
        self.assertEqual(source_spy.calls,0)
        OBS['legacy_rejection']={'written_by_commit':old['baseline'],'old_sentinel_values':old['rows'][2]['values'],
            'first_window_batches':2,'current_attempts':4,'current_source_calls':0,'all_store_bytes_unchanged':True,
            'old_missing_values':old['receipt']['missing_values'],'baseline_source_calls':old['source_calls']}

    def test_actual_fbe_written_legal_cache_is_still_reused_and_read_without_changes(self):
        path,old=self.generate_old('good');before=scan(path);spy=CountingNeverFetch()
        store=FilesystemArtifactStore(path,data_classification='synthetic')
        c=HistoricalSnapshotCollector(store,spy,plan(),synthetic=True)
        receipt=c.collect();records=all_rows(c,receipt)
        self.assertEqual(records,old['rows']);self.assertEqual(receipt['window_refs'],old['receipt']['window_refs'])
        self.assertEqual(receipt['missing_values'],old['receipt']['missing_values'])
        self.assertEqual(receipt['provider_calls'],0);self.assertEqual(spy.calls,0);self.assertEqual(scan(path),before)
        self.assertEqual(records[2]['values'][P1],'0001-01-02');self.assertEqual(records[2]['values'][P2],'2000-02-29')

    def test_invalid_date_strings_still_fail_and_do_not_become_repaired_cache(self):
        values=['0000-01-01','0001-1-1','0001-01-01T00:00:00','2021-02-29','20211108',0]
        for value in values:
            with self.subTest(value=value):
                book=NativeBook([(datetime(2021,11,8,12,17),[item('invalid-date',value,date(2021,9,30))])])
                store=MemoryArtifactStore();c=HistoricalSnapshotCollector(store,source(book),plan(),synthetic=True)
                with self.assertRaises(CollectionError):c.collect()
                self.assertFalse(any('/windows/' in k for k in store._data))
                with self.assertRaises(CollectionInterrupted):c.collect()
                self.assertEqual(len(book.calls),1)

    def test_direct_projected_sentinel_is_rejected_without_silent_conversion(self):
        class Projected:
            calls=0
            def fetch(self,start,end,catalog):
                self.calls+=1
                yield {'sid':'already-projected','snapshot_at':ts('2021-11-08 12:17').isoformat(),
                       'values':{P1:'0001-01-01',P2:'2021-09-30','dollar_volume':0,'has_fundamental_data':False,
                                 'time':'2021-11-08T12:17:00'}}
        store=MemoryArtifactStore();s=Projected();c=HistoricalSnapshotCollector(store,s,plan(),synthetic=True)
        with self.assertRaises(CollectionError):c.collect()
        self.assertFalse(any('/windows/' in k for k in store._data))
        with self.assertRaises(CollectionInterrupted):c.collect()
        self.assertEqual(s.calls,1)

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)

def static_review():
    def node(root,rel,name):
        text=(root/rel).read_text(encoding='utf-8-sig')
        n=next(n for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==name)
        return ast.get_source_segment(text,n)
    unchanged={}
    for name in ['HistoricalCollectionPlan','_load_window','read_window','_collect_window','collect']:
        rel='cloud/qresearch/collection.py';unchanged[name]=node(OLD,rel,name)==node(SOURCE,rel,name)
    lines={}
    for rel in ['cloud/qresearch/collection.py','cloud/qresearch/historical_source.py']:
        old=(OLD/rel).read_text(encoding='utf-8-sig');new=(SOURCE/rel).read_text(encoding='utf-8-sig')
        for n in ast.walk(ast.parse(new)):
            if isinstance(n,(ast.ClassDef,ast.FunctionDef)):lines[rel+':'+n.name]={'start':n.lineno,'end':n.end_lineno}
        (ROOT/(Path(rel).stem+'-baseline.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='fbe/'+rel,tofile='7bf/'+rel)),encoding='utf-8')
    return {'baseline':'fbe2454e6ea10aa59211c01f236c54bb251527be','unchanged_protected_collection_functions':unchanged,'source_locations':lines}

def main():
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DateCacheTests))
    output=stream.getvalue();(ROOT/'first_output.txt').write_text(output,encoding='utf-8')
    def method(t):return getattr(t,'test_case',t).id()
    failed={method(t) for t,_ in r.failures};errored={method(t) for t,_ in r.errors}
    result={'commit':'7bf716f45fd6183951a492f0201012af717070f0','actually_executed':True,
      'methods':r.testsRun,'passed_methods':r.testsRun-len(failed|errored),'failed_methods':len(failed),
      'error_methods':len(errored),'subcases':r.subcases,'skipped':len(r.skipped),'failure_records':len(r.failures),'error_records':len(r.errors),
      'failures':[{'method':method(t),'traceback':tb} for t,tb in r.failures],
      'errors':[{'method':method(t),'traceback':tb} for t,tb in r.errors],
      'observations':OBS,'static_review':static_review(),'developer_test_helpers_imported':False,
      'actual_external_calls':0,'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,
      'command':[sys.executable,'-B',str(Path(__file__).resolve())],
      'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'first_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(output);print(json.dumps({k:result[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}))
    return result['exit_code']

if __name__=='__main__':
    if LEGACY:raise SystemExit(legacy_build(sys.argv[2],sys.argv[3]))
    raise SystemExit(main())
