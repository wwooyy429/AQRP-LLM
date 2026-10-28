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

class IndependentTests(unittest.TestCase):
 def case(self,name):SCENARIOS.append(name);return self.subTest(name=name)
 def test_seeded_multi_snapshot_batch_invariance(self):
  for seed in range(16):
   rng=random.Random(seed);rows=[]
   stamps=['2018-11-04T01:30:00-04:00','2018-11-04T01:30:00-05:00','2018-11-04T08:00:00-05:00']
   for stamp in stamps:
    for i in range(9):
     rows.append(row(rng.choice(['A','A','B']),i,dict(dollar_volume=rng.choice([None,0,1,2]),flag=rng.choice([None,False,True]),release=rng.choice([None,'2018-09-30']),text=rng.choice([None,'x','y'])),stamp))
   n,d,c,miss=oracle(rows)
   for batch in [1,2,5,11]:
    with self.case(f'seed{seed}-batch{batch}'):
     store,source,w=writer(rows,plan(batch=batch));r=w.collect()
     self.assertEqual((r['record_count'],r['duplicate_projection_records'],r['conflicting_projection_records'],r['missing_values']),(n,d,c,miss))
     self.assertEqual(w.read_window(r['window_refs'][0]),rows)
     self.assertEqual(len(json.loads(store.read_bytes(r['window_refs'][0]['key']))['batches']),(n+batch-1)//batch)
     before=dict(store._data);reader=HistoricalSnapshotCollector(store,None,w.plan,synthetic=True);again=reader.collect()
     self.assertEqual(reader.read_window(again['window_refs'][0]),rows);self.assertEqual(again['provider_calls'],0);self.assertEqual(source.calls,1);self.assertEqual(store._data,before)
     for flag in ['research_certified','actual_availability_certified','full_historical_US200_certified','row_values_exported']:self.assertIs(r[flag],False)

 def test_ordinals_reject_reset_gap_float_bool_and_duplicate(self):
  for name,bad in [('reset',[0,0]),('gap',[0,2]),('negative',[-1]),('bool',[False]),('float',[0.0]),('numpy',[np.int64(0)]),('start1',[1]),('huge',[100])]:
   with self.case(name):
    rows=[row('A',i)for i in bad];store,source,w=writer(rows)
    with self.assertRaises(CollectionError):w.collect()
    before=dict(store._data)
    with self.assertRaises(CollectionInterrupted):w.collect()
    self.assertEqual(source.calls,1);self.assertEqual(store._data,before)

 def test_manifest_rehash_never_promotes_counts_or_certification(self):
  rows=[row('A',0),row('A',1),row('B',2)]
  mutations={
   'duplicate_count':lambda m:m.update(duplicate_projection_records=0),
   'conflict_count':lambda m:m.update(conflicting_projection_records=1),
   'missing_count':lambda m:m['missing_values'].update(dollar_volume=0),
   'bool_count':lambda m:m.update(unique_sid_count=True),
   'certify':lambda m:m.update(research_certified=True),
   'provider_calls':lambda m:m.update(provider_calls=0),
   'extra_hidden':lambda m:m.update(hidden_values=['SECRET']),
   'policy':lambda m:m.update(observation_policy='deduplicate')}
  for name,mut in mutations.items():
   with self.case(name):
    store,source,w=writer(rows);r=w.collect();ref=rewrite_manifest(store,r['window_refs'][0],mut)
    with self.assertRaises(CollectionIntegrityError):w.read_window(ref)
    with self.assertRaises(CollectionIntegrityError):HistoricalSnapshotCollector(store,None,w.plan,synthetic=True).collect()
    self.assertEqual(source.calls,1)

 def test_batch_rehash_still_requires_closed_canonical_sequence(self):
  mutations={
   'ordinal_gap':lambda p:p['records'][0].update(source_record_index=2),
   'sid_space':lambda p:p['records'][0].update(sid=' A'),
   'field_extra':lambda p:p['records'][0]['values'].update(secret='SECRET'),
   'field_missing':lambda p:p['records'][0]['values'].pop('text'),
   'num_bool':lambda p:p['records'][0]['values'].update(dollar_volume=True),
   'text_number':lambda p:p['records'][0]['values'].update(text=2),
   'date_min':lambda p:p['records'][0]['values'].update(release='0001-01-01'),
   'batch_index':lambda p:p.update(batch_index=1),
   'snapshot_end':lambda p:p['records'][0].update(snapshot_at='2018-11-05T00:00:00-05:00'),
   'schema_bool':lambda p:p.update(schema_version=True)}
  for name,mut in mutations.items():
   with self.case(name):
    store,source,w=writer([row('A',0),row('B',1)],plan(batch=1));r=w.collect();ref=mutate_payload(store,r['window_refs'][0],mut)
    with self.assertRaises(CollectionIntegrityError):w.read_window(ref)
    self.assertEqual(source.calls,1)

 def test_partial_second_window_failure_keeps_prior_and_never_refetches(self):
  class Partial:
   calls=0
   def fetch(self,start,end,fields):
    self.calls+=1
    yield row('A',0,stamp=start.isoformat())
    yield row('B',1,stamp=start.isoformat())
    if self.calls==2:raise RuntimeError('licensed_SECRET_123')
  source=Partial();store=MemoryArtifactStore();p=plan(batch=1,days=2);w=HistoricalSnapshotCollector(store,source,p,synthetic=True)
  with self.case('partial-two-window'):
   with self.assertRaises(CollectionError)as caught:w.collect()
   self.assertNotIn('SECRET',str(caught.exception));self.assertEqual(source.calls,2)
   before=dict(store._data);windows=[k for k in before if '/windows/'in k];self.assertEqual(len(windows),1)
   for refetch in [source,None]:
    with self.assertRaises(CollectionInterrupted):HistoricalSnapshotCollector(store,refetch,p,synthetic=True).collect()
   self.assertEqual(source.calls,2);self.assertEqual(store._data,before)

 def test_window_limit_exact_and_overflow(self):
  for count,ok in [(5,True),(6,False)]:
   with self.case(f'limit-{count}'):
    store,source,w=writer([row(str(i),i)for i in range(count)],plan(batch=2,limit=5))
    if ok:self.assertEqual(w.collect()['record_count'],5)
    else:
     with self.assertRaises(CollectionError):w.collect()
     with self.assertRaises(CollectionInterrupted):w.collect()
    self.assertEqual(source.calls,1)

 def test_native_source_real_interface_synthetic_data_and_DST(self):
  class Poison:
   @property
   def symbol(self):raise RuntimeError('not permitted to inspect cropped values')
  pairs=[('2018-11-03T12:00:00-04:00',[Poison()]),('2018-11-04T01:30:00-04:00',[native_obj('A',2),native_obj('A',2),native_obj('B',None)]),('2018-11-04T01:30:00-05:00',[native_obj('A',4),native_obj('A',7)])]
  qb=QB(native_response(pairs));source=QuantConnectSnapshotSource(qb,CAT,api=API,observation_policy='retain_source_occurrences');p=plan(batch=2)
  store=MemoryArtifactStore();w=HistoricalSnapshotCollector(store,source,p,synthetic=True)
  with self.case('native-DST-crop-and-occurrences'):
   result=w.collect();rows=w.read_window(result['window_refs'][0]);self.assertEqual([r['source_record_index']for r in rows],[0,1,2,0,1]);self.assertEqual([r['sid']for r in rows],['A','A','B','A','A'])
   self.assertEqual((result['record_count'],result['duplicate_projection_records'],result['conflicting_projection_records']),(5,2,1))
   self.assertEqual(result['missing_values'],dict(dollar_volume=1,flag=0,release=5,text=0));self.assertEqual(len(qb.calls),1)
   begin,end,flat=qb.calls[0];self.assertEqual(begin,datetime(2018,11,3));self.assertEqual(end,datetime(2018,11,4,23,59,59,999999));self.assertIs(flat,False)
   self.assertFalse(source.provenance()['actual_availability_certified'])

 def test_native_uniqueness_limit_and_empty_contracts(self):
  examples=[('v1dup',native_response([('2018-11-04T09:00:00-05:00',[native_obj('A'),native_obj('A')])]),'unique_sid',3,False),('v2limit',native_response([('2018-11-04T09:00:00-05:00',[native_obj('A')for i in range(4)])]),'retain_source_occurrences',3,False),('empty00',pd.DataFrame(),'retain_source_occurrences',3,True),('empty_named',pd.DataFrame().rename_axis('secret'),'retain_source_occurrences',3,False)]
  p=plan()
  for name,response,policy,limit,ok in examples:
   with self.case(name):
    qb=QB(response);s=QuantConnectSnapshotSource(qb,CAT,api=API,observation_policy=policy,max_records_per_snapshot=limit)
    if ok:self.assertEqual(list(s.fetch(*p.windows()[0],CAT)),[])
    else:
     with self.assertRaises(HistoricalSourceError):list(s.fetch(*p.windows()[0],CAT))

 def test_ambiguous_projection_cannot_enter_unique_liquidity_adapter(self):
  with self.case('v2-reject-and-v1-unknown-receipt'):
   v2=row('A',0,dict(dollar_volume=10,flag=True,release=None,text='kept'),stamp='2018-11-04T09:00:00-05:00')
   with self.assertRaises(HistoricalSourceError):observed_liquidity_record(v2,session_close='2018-11-02T16:00:00-04:00')
   v1={k:v for k,v in v2.items()if k!='source_record_index'}
   observed=observed_liquidity_record(v1,session_close='2018-11-02T16:00:00-04:00')
   self.assertIsNone(observed['vendor_available_at']);self.assertIsNone(observed['historical_ingested_at']);self.assertEqual(observed['availability_basis'],'unknown')
   ing=HistoricalBatchIngestor(MemoryArtifactStore(),source='independent',data_version='v1',origin='historical_declared_fixture',synthetic=True)
   receipt=ing.ingest('liquidity',[observed],partition='2018/A')
   with self.assertRaises(MissingPITEvidence):ing.liquidity_rows_asof(receipt['batch_ref'],'2018-11-04T10:00:00-05:00',['2018-11-02T16:00:00-04:00'])

 def test_plan_identity_separates_schema_catalog_fields_bounds_and_source(self):
  base=plan();raw=base.to_dict();changes=[('source_manifest_hash','8'*64),('max_batch_records',4),('max_records_per_window',101),('data_version','synthetic-new')]
  for name,value in changes:
   with self.case('identity-'+name):
    changed=copy.deepcopy(raw);changed[name]=value;p=HistoricalCollectionPlan.from_dict(changed,field_catalog=CAT);self.assertNotEqual(p.hash,base.hash)
  with self.case('identity-catalog'):
   cat=copy.deepcopy(CAT);cat['text']['role']='new-role';p=HistoricalCollectionPlan.from_dict(raw,field_catalog=cat);self.assertNotEqual(p.hash,base.hash)
  store,source,w=writer([row('A',0)],base);w.collect();before=dict(store._data)
  with self.case('read-only-other-plan-miss'):
   raw['data_version']='other';other=HistoricalCollectionPlan.from_dict(raw,field_catalog=CAT)
   with self.assertRaises(CollectionMiss):HistoricalSnapshotCollector(store,None,other,synthetic=True).collect()
   self.assertEqual(store._data,before)

suite=unittest.defaultTestLoader.loadTestsFromTestCase(IndependentTests)
stream=io.StringIO();start=time.monotonic();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(args.output/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
report=dict(methods=result.testsRun,passed_methods=result.testsRun-len({str(t).split(' (')[0]for t,_ in result.failures+result.errors}),failure_records=len(result.failures),error_records=len(result.errors),skipped=len(result.skipped),named_scenario_checks=len(SCENARIOS),unittest_subcases=None,scenario_names=SCENARIOS,seconds=time.monotonic()-start,actually_executed=True,success=result.wasSuccessful(),developer_fixture_imports=False,synthetic=True,market_calls=0,failures=[dict(test=str(t),trace=tr)for t,tr in result.failures],errors=[dict(test=str(t),trace=tr)for t,tr in result.errors])
(args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items()if k not in ['scenario_names','failures','errors']}));print(stream.getvalue());raise SystemExit(not result.wasSuccessful())
