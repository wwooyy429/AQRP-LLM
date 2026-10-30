"""Independent synthetic schema3 LEAN and adversarial decode probe."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys
import tempfile
from unittest.mock import patch
import zlib
from datetime import datetime
from types import SimpleNamespace as NS

ROOT=Path.cwd()
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tests')]
from qresearch.artifacts import canonical_json
from qresearch.engineering_storage import encode_compressed_json, decode_compressed_json
from qresearch.engineering_tasks import validate_joint_report
from test_engineering_storage import StorageRepairWorkerTests
from test_engineering_data import EngineeringDataTests, FakeAlgorithm
from test_wr13_annotations import ToySymbol, ToyHours
import qresearch.engineering_data as worker

def metadata(raw,stored):
 return {'schema_version':1,'encoding':'zlib_json_v1','uncompressed_bytes':len(raw),'stored_bytes':len(stored),
  'raw_sha256':hashlib.sha256(raw).hexdigest(),'stored_sha256':hashlib.sha256(stored).hexdigest()}

results=[]
raw=canonical_json({'synthetic':[1,2,3]});stored=zlib.compress(raw)
for name,buffer,claimed_raw in (
 ('second_stream',stored+zlib.compress(b'{}'),raw),
 ('truncated',stored[:-1],raw),
 ('duplicate_json_key',zlib.compress(b'{"x":1,"x":2}'),b'{"x":1,"x":2}'),
 ('noncanonical_whitespace',zlib.compress(b'{ "x":1}'),b'{ "x":1}'),
 ('decompression_bomb',zlib.compress(b'x'*(2**21+1)),b'x'*(2**21)),
):
 try:decode_compressed_json(buffer,metadata(claimed_raw,buffer))
 except ValueError:results.append({'case':name,'rejected':True})
 else:raise AssertionError(name+' accepted')

guard_paths=['audit/runtime/registry/events.jsonl','config/budget.json']
before={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in guard_paths}
case=StorageRepairWorkerTests()
class Algorithm(FakeAlgorithm):
 def add_equity(self,ticker,resolution,**kwargs):
  security=super().add_equity(ticker,resolution,**kwargs)
  security.symbol=ToySymbol(ticker)
  security.exchange.hours=ToyHours()
  return security

with tempfile.TemporaryDirectory() as directory:
 root,qb,api,payload,capacity,old=case.fixture(directory)
 research=case.execute(root,qb,api,payload,capacity)
 lean=deepcopy(payload)
 lean['identity'].update(stage='lean',attempt_id='b'*32)
 lean['report_key']=payload['plan']['report_namespace']+'/reports/'+payload['identity']['plan_hash']+'/lean/'+'b'*32+'.json'
 lean['external_identity_kind']='quantconnect_backtest_id'
 lean['research_resolution']=research['cloud_report']['resolution']
 algorithm=Algorithm();algorithm.object_store=qb.object_store
 original=worker._context
 with patch.object(worker,'_context',side_effect=lambda v,s,**kw:original(v,s,source_root=root,**kw)), \
      patch.object(worker.ObjectStoreArtifactStore,'preflight_capacity',return_value=capacity):
  worker.initialize_receiver(algorithm,lean,api=api)
  for day in (3,4,5,8,9):
   moment=datetime(2018,1,day,16);algorithm.time=moment
   bars={s.symbol:NS(symbol=s.symbol,end_time=moment,open=430.,high=432.,low=429.,close=431.25,volume=123456)
    for s in algorithm.created.values()}
   symbol=algorithm.created['AAPL'].symbol
   dividends={symbol:NS(symbol=symbol,distribution=.63)} if day==9 else {}
   worker.receive_slice(algorithm,NS(bars=bars,dividends=dividends,splits={},delistings={},symbol_changed_events={}))
  result=worker.finish_receiver(algorithm)
 report=result['cloud_report']
 if report['status']!='completed':
  print(json.dumps({'synthetic_initial_receiver_status':report['status'],'checks':report['checks'],'statistics':report['statistics'],
   'observation_window':lean['plan']['observation_window']}))
 assert report['status']=='completed'
 validate_joint_report(report,lean['plan'])
 assert '431.25' not in json.dumps(result)
 evidence=report['evidence'];encoded=evidence['receiver_storage'];reference=evidence['received_bar_ref']
 assert reference['sha256']==encoded['stored_sha256']
 decoded=decode_compressed_json(worker._cloud_store(qb.object_store).read_bytes(reference['key']),encoded)
 assert decoded['rows']==algorithm._engineering_state['records']
 results.append({'case':'schema3_fake_receiver_complete','completed':True,'orders':report['statistics']['orders_submitted'],
  'raw_bytes':encoded['uncompressed_bytes'],'stored_bytes':encoded['stored_bytes'],'rows_not_exported':True})

after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in guard_paths}
assert before==after
out={'kind':'independent_synthetic_schema3_receiver_and_compression_probe','results':results,
 'real_budget_and_journal_unchanged':True,'cloud_calls':0,'actual_Research_executions':0,'actual_LEAN_submissions':0,
 'preflight_mock_note':'SDK preflight returns a synthetic capacity fixture; separate storage_capacity tests cover actual metadata-only adapter.',
 'reviewer_fixture_correction':'First two probe attempts used February helper slices for a January3-10 frozen observation window. complete_expected_bars correctly failed. Probe was corrected to matching explicit January synthetic sessions; no production edit.'}
Path(__file__).with_name('compression_receiver_probe_result.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out))
