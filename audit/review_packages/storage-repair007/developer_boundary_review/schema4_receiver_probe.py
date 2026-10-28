"""Independent synthetic end-to-end schema4 + retired-schema3 boundary check."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import patch
import hashlib
import json
import sys
import tempfile

import pandas as pd

ROOT=Path.cwd()
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tests')]
from qresearch.artifacts import canonical_json,content_hash
from qresearch.engineering_tasks import EngineeringTaskPlan,validate_joint_report
from test_engineering_storage import StorageRepairWorkerTests
import test_engineering_storage as storage_tests
from test_phase2_joint_plan import JointQuantBook
from test_engineering_data import FakeAlgorithm
from test_wr13_annotations import ToySymbol,ToyHours
import qresearch.engineering_data as worker

guard_paths=['audit/runtime/registry/events.jsonl','config/budget.json']
before={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in guard_paths}
FIELDS=['open','high','low','close','volume']
VALUES={'open':430.,'high':432.,'low':429.,'close':431.25,'volume':123456.}
original_raw=storage_tests.joint_raw
def five_field_raw():
 raw=original_raw();raw['request_template']['fields']=FIELDS
 return raw
def five_field_history(self,symbols,start,end,resolution,**kwargs):
 self.calls+=1
 index=pd.MultiIndex.from_tuples([(symbol,day.to_pydatetime().replace(hour=16))
  for symbol in symbols for day in pd.bdate_range(start,end,inclusive='left')],names=['symbol','time'])
 return pd.DataFrame(VALUES,index=index)

class Algorithm(FakeAlgorithm):
 def add_equity(self,ticker,resolution,**kwargs):
  security=super().add_equity(ticker,resolution,**kwargs)
  security.symbol=ToySymbol(ticker);security.exchange.hours=ToyHours()
  return security

def slices(algorithm):
 for day in (3,4,5,8,9):
  moment=datetime(2018,1,day,16);algorithm.time=moment
  bars={s.symbol:NS(symbol=s.symbol,end_time=moment,**VALUES) for s in algorithm.created.values()}
  symbol=algorithm.created['AAPL'].symbol
  dividends={symbol:NS(symbol=symbol,distribution=.63)} if day==9 else {}
  worker.receive_slice(algorithm,NS(bars=bars,dividends=dividends,splits={},delistings={},symbol_changed_events={}))

def reject(results,name,callback):
 try:callback()
 except (ValueError,RuntimeError):results.append({'case':name,'rejected':True})
 else:raise AssertionError(name+' unexpectedly accepted')

results=[];case=StorageRepairWorkerTests()
with tempfile.TemporaryDirectory() as directory, \
     patch.object(storage_tests,'joint_raw',side_effect=five_field_raw), \
     patch.object(JointQuantBook,'history',five_field_history):
 root,qb,api,payload,capacity,old=case.fixture(directory)
 calls=qb.calls;universe_calls=qb.universe_calls
 research=case.execute(root,qb,api,payload,capacity)
 assert qb.calls==calls and qb.universe_calls==universe_calls
 lean=deepcopy(payload);lean['identity'].update(stage='lean',attempt_id='b'*32)
 lean['report_key']=payload['plan']['report_namespace']+'/reports/'+payload['identity']['plan_hash']+'/lean/'+'b'*32+'.json'
 lean['external_identity_kind']='quantconnect_backtest_id';lean['research_resolution']=research['cloud_report']['resolution']
 original_context=worker._context
 def initialized():
  algorithm=Algorithm();algorithm.object_store=qb.object_store
  worker.initialize_receiver(algorithm,lean,api=api);slices(algorithm)
  return algorithm
 with patch.object(worker,'_context',side_effect=lambda v,s,**kw:original_context(v,s,source_root=root,**kw)), \
      patch.object(worker.ObjectStoreArtifactStore,'preflight_capacity',return_value=capacity):
  algorithm=initialized();old_keys=set(qb.object_store.data)
  result=worker.finish_receiver(algorithm)
  report=result['cloud_report'];assert report['status']=='completed'
  validate_joint_report(report,lean['plan'])
  evidence=report['evidence'];metadata=evidence['receiver_storage'];ref=evidence['received_bar_ref']
  manifest=worker._load(worker._cloud_store(qb.object_store),ref)
  assert 'rows' not in manifest and manifest['row_values_stored'] is False
  assert metadata['record_count']==50 and metadata['cache_reference_count']==5
  assert manifest['actual_rowset_sha256']==manifest['cached_rowset_sha256']==metadata['rowset_sha256']
  assert '431.25' not in json.dumps(result) and '431.25' not in json.dumps(manifest)
  assert metadata['new_row_objects'] is False and report['statistics']['orders_submitted']==0
  results.append({'case':'schema4_full_Research_and_LEAN_synthetic_chain','completed':True,'rows_verified':50,
   'new_history_calls':qb.calls-calls,'new_universe_calls':qb.universe_calls-universe_calls,'manifest_stores_rows':False})
  for name,edit in (
   ('wrong_manifest_ref',lambda r:r['evidence']['received_bar_ref'].update(sha256='f'*64)),
   ('wrong_received_count',lambda r:r['evidence']['receiver_storage'].update(record_count=49)),
   ('wrong_reference_count',lambda r:r['evidence']['receiver_storage'].update(cache_reference_count=4)),
   ('claims_new_row_objects',lambda r:r['evidence']['receiver_storage'].update(new_row_objects=True)),
   ('unsupported_metadata_encoding',lambda r:r['evidence']['receiver_storage'].update(encoding='zlib_json_v1')),
  ):
   altered=deepcopy(report);edit(altered)
   reject(results,name,lambda:validate_joint_report(altered,lean['plan']))
  changed=initialized();changed._engineering_state['records'][0][4]+=1
  before_bad=set(qb.object_store.data)
  reject(results,'changed_bar_value_does_not_write_manifest',lambda:worker.finish_receiver(changed))
  assert set(qb.object_store.data)==before_bad

 raw3=deepcopy(payload['plan']);raw3['schema_version']=3
 raw3['storage_policy']['lean_record_encoding']='zlib_json_v1'
 plan3=EngineeringTaskPlan.from_dict(raw3,discovered_project_ids=[17])
 historical=deepcopy(report)
 historical['identity'].update(plan_hash=plan3.hash,data_request_hash=plan3.request_hash)
 digest='a'*64
 historical['evidence']['receiver_storage']={'schema_version':1,'encoding':'zlib_json_v1','uncompressed_bytes':100,
  'stored_bytes':80,'raw_sha256':'c'*64,'stored_sha256':digest}
 historical['evidence']['received_bar_ref']={'key':raw3['report_namespace']+'/received/'+'b'*32+'/'+digest+'.zlib','sha256':digest}
 validate_joint_report(historical,raw3)
 results.append({'case':'schema3_historical_metadata_parser','accepted':True})
 payload3=deepcopy(payload);payload3['plan']=raw3
 with patch.object(worker,'verify_deployment_observation',side_effect=AssertionError('Retired task reached deployment')):
  reject(results,'schema3_runtime_rejects_before_deployment_or_QuantBook',lambda:worker.run_research_task(payload3,api=api,
   quantbook_factory=lambda:(_ for _ in ()).throw(AssertionError('SDK reached'))))

after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in guard_paths};assert before==after
output={'kind':'independent_synthetic_schema4_whole_receiver_and_schema3_metadata_probe','results':results,
 'real_registry_budget_unchanged':True,'actual_cloud_calls':0,'actual_Research_executions':0,'actual_LEAN_submissions':0,
 'fixture_scope':'Five-field synthetic yearly cache plus actual module calls; native preflight is patched to a known synthetic capacity observation.'}
Path(__file__).with_name('schema4_receiver_probe_result.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
print(json.dumps(output))
