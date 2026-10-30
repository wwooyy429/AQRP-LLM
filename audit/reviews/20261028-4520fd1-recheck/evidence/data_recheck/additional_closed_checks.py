"""Independent synthetic adversarial cases, not developer test imports."""
import argparse, copy, hashlib, io, json, random, sys, time, unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True;sys.path.insert(0,str(args.source.resolve()/'cloud'))
import numpy as np
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.collection import HistoricalCollectionPlan,HistoricalSnapshotCollector,CollectionError,CollectionIntegrityError,CollectionInterrupted,CollectionMiss
from qresearch.historical_source import QuantConnectSnapshotSource,HistoricalSourceError,observed_liquidity_record
from qresearch.ingestion import HistoricalBatchIngestor,MissingPITEvidence

SCENARIOS=[]
CAT={
 'dollar_volume':dict(kind='number',role='synthetic_liquidity',unit='USD',period_accessor=None),
 'flag':dict(kind='boolean',role='synthetic_flag',unit='flag',period_accessor=None),
 'release':dict(kind='date',role='synthetic_date',unit='date',period_accessor=None),
 'text':dict(kind='text',role='synthetic_text',unit='text',period_accessor=None)}
def plan(batch=3,limit=100,days=1,version=2,fields=None):
 raw=dict(schema_version=version,plan_id='independent-recheck',scope='engineering',source='quantconnect_fundamental_universe',data_version='synthetic-v2',start='2018-11-04T00:00:00-04:00',end_exclusive=f'2018-11-{4+days:02d}T00:00:00-05:00',timezone='America/New_York',fields=list(fields or CAT),calendar_days_per_request=1,max_batch_records=batch,max_records_per_window=limit,source_manifest_hash='7'*64)
 if version==2:raw['observation_policy']='retain_source_occurrences'
 return HistoricalCollectionPlan.from_dict(raw,field_catalog=CAT)
def row(sid,index,values=None,stamp='2018-11-04T01:30:00-04:00'):
 return dict(sid=sid,snapshot_at=stamp,source_record_index=index,values=copy.deepcopy(values or dict(dollar_volume=None,flag=None,release=None,text=None)))
class Source:
 def __init__(self,rows):self.rows=rows;self.calls=0
 def fetch(self,*a):self.calls+=1;return iter(copy.deepcopy(self.rows))
def writer(rows,p=None):
 store=MemoryArtifactStore();source=Source(rows);p=p or plan();collector=HistoricalSnapshotCollector(store,source,p,synthetic=True)
 return store,source,collector
def oracle(rows):
 # Direct tuple comparisons form independent known answers, not product count/hash helpers.
 seen={};dup=conf=0;missing={k:0 for k in CAT}
 for r in rows:
  key=(r['sid'],r['snapshot_at']);v=tuple(r['values'][k]for k in sorted(CAT))
  if key in seen:dup+=1;conf+=seen[key]!=v
  else:seen[key]=v
  for k in missing:missing[k]+=r['values'][k]is None
 return len(rows),dup,conf,missing
def rewrite_manifest(store,ref,mutator):
 m=json.loads(store.read_bytes(ref['key']));mutator(m)
 store._data[ref['key']]=canonical_json(m)
 return {'key':ref['key'],'sha256':content_hash(m)}
def mutate_payload(store,ref,mutator):
 def apply(m):
  b=m['batches'][0];v=json.loads(store.read_bytes(b['key']));mutator(v)
  digest=content_hash(v);key='historical-snapshots/v2/objects/'+digest+'.json'
  store._data[key]=canonical_json(v);m['batches'][0]={'key':key,'sha256':digest}
 return rewrite_manifest(store,ref,apply)
class QB:
 def __init__(self,response):self.response=response;self.time=datetime(2018,11,7);self.calls=[];self.universe_settings=NS()
 def set_time_zone(self,z):assert z=='America/New_York'
 def add_universe(self,selector):self.selector=selector;return NS(symbol='U')
 def universe_history(self,u,start,end,flatten):self.calls.append((start,end,flatten));return self.response
def native_response(pairs):
 return pd.Series([value for stamp,value in pairs],index=pd.MultiIndex.from_tuples([('U',pd.Timestamp(stamp))for stamp,value in pairs],names=['symbol','time']),dtype=object)
def native_obj(sid,value=1):return NS(symbol=NS(id=sid),dollar_volume=value,flag=np.bool_(True),release=datetime(1,1,1),text='kept')
API=NS(Resolution=NS(DAILY='DAILY'))

class AdditionalTests(unittest.TestCase):
 def case(self,name):SCENARIOS.append(name);return self.subTest(name=name)
 def test_total_window_limit_across_two_snapshots(self):
  for total in [5,6]:
   with self.case('cross-snapshot-total-'+str(total)):
    rows=[row(str(i),i,stamp='2018-11-04T09:00:00-05:00')for i in range(3)]
    rows += [row(str(i),i,stamp='2018-11-04T10:00:00-05:00')for i in range(total-3)]
    store,source,w=writer(rows,plan(batch=2,limit=5))
    if total==5:self.assertEqual(w.collect()['record_count'],5)
    else:
     with self.assertRaises(CollectionError):w.collect()
     with self.assertRaises(CollectionInterrupted):w.collect()
    self.assertEqual(source.calls,1)
 def test_equivalent_UTC_instants_group_in_NY_and_cache_must_be_canonical(self):
  with self.case('UTC-normalize-and-rehash-reject'):
   rows=[row('A',0,stamp='2018-11-04T05:30:00+00:00'),row('A',1,dict(dollar_volume=4,flag=None,release=None,text=None),stamp='2018-11-04T01:30:00-04:00'),row('A',0,stamp='2018-11-04T06:30:00+00:00')]
   store,source,w=writer(rows,plan(batch=1));r=w.collect();out=w.read_window(r['window_refs'][0])
   self.assertEqual([x['snapshot_at']for x in out],['2018-11-04T01:30:00-04:00','2018-11-04T01:30:00-04:00','2018-11-04T01:30:00-05:00'])
   self.assertEqual((r['duplicate_projection_records'],r['conflicting_projection_records']),(1,1))
   ref=mutate_payload(store,r['window_refs'][0],lambda p:p['records'][0].update(snapshot_at='2018-11-04T05:30:00+00:00'))
   with self.assertRaises(CollectionIntegrityError):w.read_window(ref)
 def test_projection_does_not_read_unselected_supplier_properties(self):
  class OnlyValue:
   symbol=NS(id='SID-A');dollar_volume=7
   @property
   def has_fundamental_data(self):raise RuntimeError('SECRET-unselected')
  with self.case('selected-only-no-financial-filter'):
   catalog={'dollar_volume':CAT['dollar_volume']};qb=QB(native_response([('2018-11-04T09:00:00-05:00',[OnlyValue(),OnlyValue()])]))
   src=QuantConnectSnapshotSource(qb,catalog,api=API,observation_policy='retain_source_occurrences');p=plan(fields=['dollar_volume']);store=MemoryArtifactStore();w=HistoricalSnapshotCollector(store,src,p,synthetic=True);r=w.collect()
   self.assertEqual((r['record_count'],r['duplicate_projection_records'],r['conflicting_projection_records']),(2,1,0))
   self.assertEqual([x['values']for x in w.read_window(r['window_refs'][0])],[{'dollar_volume':7},{'dollar_volume':7}])

suite=unittest.defaultTestLoader.loadTestsFromTestCase(AdditionalTests)
stream=io.StringIO();start=time.monotonic();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(args.output/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
report=dict(methods=result.testsRun,passed_methods=result.testsRun-len({str(t).split(' (')[0]for t,_ in result.failures+result.errors}),failure_records=len(result.failures),error_records=len(result.errors),skipped=len(result.skipped),named_scenario_checks=len(SCENARIOS),unittest_subcases=None,scenario_names=SCENARIOS,seconds=time.monotonic()-start,actually_executed=True,success=result.wasSuccessful(),developer_fixture_imports=False,synthetic=True,market_calls=0,failures=[dict(test=str(t),trace=tr)for t,tr in result.failures],errors=[dict(test=str(t),trace=tr)for t,tr in result.errors])
(args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items()if k not in ['scenario_names','failures','errors']}));print(stream.getvalue());raise SystemExit(not result.wasSuccessful())
