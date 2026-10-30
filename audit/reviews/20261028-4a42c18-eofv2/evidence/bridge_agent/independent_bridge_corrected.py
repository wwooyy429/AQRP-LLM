"""Independent metadata-only deployment-policy integration and boundary cases."""
import argparse,base64,hashlib,json,os,sys,time,unittest
from pathlib import Path
from copy import deepcopy
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args();S=args.source.resolve();O=args.out.resolve();O.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(S/'cloud'),str(S/'tools')]
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,EngineeringTaskError,submission_protocol
from qresearch.collection_tasks import CollectionTaskPlan,CollectionTaskBridge
from qresearch.collection_execution import run_collection_task,stdout_marker,collection_research_observation
from qresearch.engineering_data import verify_deployment_observation,DeploymentVerificationError,_context
from qresearch.deployment_observation import validate_observation_binding
import qresearch.engineering_receipts as receipts
import stage2,collection_task_cli as cc,deployment_preflight as project

P='utf8_sig_universal_newlines_terminal_lf_v1';SOURCEHASH='a'*64
SOURCES={'receiver.py':b'VALUE = 17\n','q/helper.py':b'HELPER = 23'}
CAT={'dollar_volume':{'kind':'number','role':'synthetic_liquidity','unit':'USD','period_accessor':None}}
CAP={n:{'normal':8,'reserve':2,'total':10}for n in ['configurations','research','lean']}
FLAGS=['market_values_exported','economic_factor_tested','final_data_accessed','full_US200_coverage_certified','actual_availability_verified']
scenarios=[];stats={'worker_checks':0,'research_parser':0,'collection_parser':0,'bridge_completion':0,'project_reads':0,'native_rejections':0}
def scene(name):scenarios.append(name)
def h(b):return hashlib.sha256(b).hexdigest()
def wrapper(sources=SOURCES,version=2):
 if version==1:return {n:h(b)for n,b in sources.items()}
 return {'schema_version':2,'source_identity_policy':P,'files':{n:{'source_sha256':h(b),'canonical_sha256':h(b.rstrip(b'\n')+b'\n'),'terminal_lf_count':len(b)-len(b.rstrip(b'\n'))}for n,b in sources.items()}}
def native(v):return {'structuredContent':deepcopy(v),'content':[{'type':'text','text':json.dumps(v)}],'isError':False}
def env(name,args,v):return {'tool_name':'mcp__quantconnect__'+name,'arguments':args,'result':native(v)}
def mark(w):return 'AQRP_ENGINEERING_JSON '+base64.b64encode(canonical_json(w)).decode()
def exec_envelope(w):return env('jupyter_execute_cell',{'projectId':17,'index':4},{'success':True,'outputs':[{'output_type':'stream','name':'stdout','text':mark(w)+'\n'}]})
def eng_plan(m,*,resolved=False):
 raw=dict(schema_version=1,plan_id='independent-v2-bridge',scope='engineering',project_id=17,source_manifest_hash=SOURCEHASH,deployment_hash=content_hash(m),request_mode='resolved'if resolved else'symbol_resolution',observation_window={'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-06T00:00:00-05:00'},required_checks={'research':['source_snapshot_matches'],'lean':['source_snapshot_matches','no_orders','corporate_action_received']},max_retries={'research':1,'lean':1},report_namespace='synthetic/engineering',orders_enabled=False,financial_metrics_enabled=False,economic_factor=None,economic_model=None)
 req=dict(dataset='US Equities',fields=['close'],start='2018-01-01T00:00:00-05:00',end='2019-01-01T00:00:00-05:00',data_version='synthetic-v1',universe_hash='d'*64,normalization='raw',timezone='America/New_York')
 if resolved:raw['data_request']=dict(req,sids=['permanent-A','permanent-B'])
 else:raw.update(request_template=req,symbol_resolution={'tickers':['AAPL','MSFT'],'as_of':req['end'],'method':'QuantBook.add_equity/as-of fixed fixture'})
 return EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[17])
def collection_plan(m):
 child=dict(schema_version=1,plan_id='independent-projection',scope='engineering',source='quantconnect_fundamental_universe',data_version='synthetic-v1',start='2018-01-03T00:00:00-05:00',end_exclusive='2018-01-05T00:00:00-05:00',timezone='America/New_York',fields=['dollar_volume'],calendar_days_per_request=1,max_batch_records=2,max_records_per_window=10,source_manifest_hash=SOURCEHASH)
 raw=dict(schema_version=1,task_kind='historical_collection',scope='engineering',plan_id='independent-collection-task',project_id=17,source_manifest_hash=SOURCEHASH,deployment_hash=content_hash(m),collection_plan=child,field_catalog=CAT,report_namespace='synthetic/collection',max_retries=1)
 return CollectionTaskPlan.from_dict(raw,discovered_project_ids=[17],field_catalog=CAT)
def resolution():
 refs={'resolved_registry_ref':{'key':'synthetic/resolved-registry.json','sha256':'b'*64},'resolved_request_ref':{'key':'synthetic/resolved-request.json','sha256':'c'*64}}
 return dict(refs,resolved_registry_hash='b'*64,resolved_request_hash='c'*64,resolution_artifact_hash=content_hash(refs),tickers=['AAPL','MSFT'],ticker_count=2,permanent_sid_count=2,method='QuantBook.add_equity/as-of fixed fixture')
def report(payload,obs=None):
 stage=payload['identity']['stage'];counts={'record_count':2,'history_calls_second':0}if stage=='research'else{'data_event_count':2,'orders_submitted':0,'runtime_error_count':0,'dividend_event_count':1}
 d=dict(schema_version=1,identity=payload['identity'],status='completed',terminal=True,checks={k:True for k in payload['plan']['required_checks'][stage]},statistics=counts,evidence={})
 d.update({k:False for k in FLAGS})
 if payload['plan']['request_mode']=='symbol_resolution':d['resolution']=resolution()
 if obs is not None:d['evidence']['deployment_verification']=deepcopy(obs)
 return {'cloud_report':d,'report_ref':{'key':payload['report_key'],'sha256':content_hash(d)}}

class Fixture:
 def __init__(self,*,version=2,collection=False,resolved=False):
  self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name);self.stack=ExitStack();self.collection=collection;self.m=wrapper(version=version)
  for n,b in SOURCES.items():
   p=self.root/'cloud'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  (self.root/'audit').mkdir(exist_ok=True);(self.root/'config').mkdir(exist_ok=True)
  self.dump('audit/deployment.json',dict(source_files=wrapper(version=1),**({'deployment_manifest':self.m}if version==2 else{})))
  self.dump('config/quantconnect.json',{'active_project_id':17})
  self.store=MemoryArtifactStore();self.registry=Registry(self.store,deepcopy(CAP));self.plan=collection_plan(self.m)if collection else eng_plan(self.m,resolved=resolved)
  self.bridge=(CollectionTaskBridge if collection else EngineeringTaskBridge)(self.registry,self.plan)
  self.stack.enter_context(patch.object(stage2,'ROOT',self.root));self.stack.enter_context(patch.object(cc,'ROOT',self.root))
  self.stack.enter_context(patch.object(stage2,'open_registry',return_value=self.registry));self.stack.enter_context(patch.object(cc,'open_registry',return_value=self.registry))
  self.stack.enter_context(patch.object(stage2,'source_manifest',return_value={'source_hash':SOURCEHASH}))
  self.stack.enter_context(patch.object(cc,'execution_source_manifest',return_value={'source_hash':SOURCEHASH}))
 def __enter__(self):return self
 def __exit__(self,*e):self.stack.close();self.tmp.cleanup()
 def dump(self,n,d):p=self.root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(canonical_json(d))
 def start(self,stage='research'):
  self.bridge.register();self.attempt=self.bridge.claim(stage);self.admission=(cc.prepare_task if self.collection else stage2.prepare)(self.bridge,self.attempt.attempt_id);return self.admission
 def summary(self,changed=True):
  if changed:(self.root/'cloud/receiver.py').write_bytes(SOURCES['receiver.py']+b'\n')
  stats['worker_checks']+=1
  return verify_deployment_observation(self.m,content_hash(self.m),source_root=self.root/'cloud')
 def research_binding(self,ad=None):
  ad=self.admission if ad is None else ad;source=receipts.research_cell_source(ad['payload'],ad['deployment'])
  return env('jupyter_read_cell',{'projectId':17,'index':4},{'cellType':'code','source':source.splitlines(keepends=True)})
 def finish_engineering_research(self):
  stage2.research_dispatch(self.bridge,self.attempt.attempt_id,self.research_binding())
  observation=self.summary();w=report(self.admission['payload'],observation)
  stats['research_parser']+=1
  result=stage2.settle_research_result(self.bridge,self.attempt.attempt_id,exec_envelope(w));stats['bridge_completion']+=1
  return result,w

class BridgeTests(unittest.TestCase):
 def reject_without_write(self,f,call):
  before=dict(f.store._data)
  with self.assertRaises((ValueError,EngineeringTaskError)):call()
  self.assertEqual(f.store._data,before)
 def test_local_and_first_prepare_stay_strict_while_worker_accepts(self):
  for collection in [False,True]:
   for kind in ['extra_lf','body','missing','extra']:
    scene('local-strict-%s-%s'%(collection,kind))
    with Fixture(collection=collection)as f:
     f.bridge.register();a=f.bridge.claim('research')
     if kind=='extra_lf':(f.root/'cloud/receiver.py').write_bytes(SOURCES['receiver.py']+b'\n')
     elif kind=='body':(f.root/'cloud/receiver.py').write_bytes(b'VALUE = 18\n')
     elif kind=='missing':(f.root/'cloud/receiver.py').unlink()
     else:(f.root/'cloud/extra.py').write_bytes(b'EXTRA = 1\n')
     self.reject_without_write(f,lambda:(cc.prepare_task if collection else stage2.prepare)(f.bridge,a.attempt_id))
     if kind=='extra_lf':self.assertEqual(f.summary(False)['eof_normalized_file_count'],1)
 def test_freeze_preview_is_strict_and_never_registers(self):
  for changed in [False,True]:
   scene('freeze-preview-%s'%changed)
   with Fixture()as f:
    f.dump('plan.json',f.plan.to_dict());before=dict(f.store._data)
    if changed:(f.root/'cloud/q/helper.py').write_bytes(SOURCES['q/helper.py']+b'\n')
    if changed:
     with self.assertRaises(ValueError):stage2.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=f.root/'plan.json',preview=True)
    else:
     x=stage2.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=f.root/'plan.json',preview=True)
     self.assertEqual(x['deployment_hash'],content_hash(f.m));self.assertFalse(x['budget_admission_performed']);self.assertFalse(x['configuration_registered'])
    self.assertEqual(f.store._data,before)
 def test_project_is_exact_and_collection_input_opaque(self):
  for changed in ['none','lf','body','missing','extra','input_mismatch','collection_opaque']:
   scene('project-'+changed)
   files=[{'filePath':n,'content':b.decode()}for n,b in SOURCES.items()]
   if changed=='lf':files[0]['content']+='\n'
   if changed=='body':files[0]['content']+='VALUE = 18\n'
   if changed=='missing':files.pop()
   if changed=='extra':files.append({'filePath':'extra.py','content':'EXTRA=1\n'})
   if changed=='input_mismatch':files.append({'filePath':'_engineering_task_input.py','content':'TASK_INPUT_JSON = "wrong"\n'})
   if changed=='collection_opaque':files.append({'filePath':'_collection_task_input.py','content':'\x00SYNTHETIC-OPAQUE\ud7ff'})
   m=wrapper();native_project=dict(success=True,project=dict(projectId=17,name='synthetic',language='Py',files=files))
   out=project.read_project_preflight(env('read_project',{'projectId':17},native_project),native({'success':True,'projects':[{'projectId':17}]}),m,content_hash(m),project_id=17,input_sha256='d'*64 if changed=='input_mismatch'else None);stats['project_reads']+=1
   self.assertEqual(out['preflight_passed'],changed in ['none','collection_opaque'])
   self.assertFalse(out['ready_to_dispatch']);self.assertFalse(out['worker_source_verified'])
   if changed=='collection_opaque':self.assertEqual(out['ignored_generated_input_file_count'],1);self.assertNotIn('SYNTHETIC-OPAQUE',json.dumps(out))
 def test_engineering_research_to_lean_completion_exact_policy_summary(self):
  scene('engineering-research-lean-endtoend')
  with Fixture()as f:
   f.start();before=f.registry.snapshot()['usage'];done,w=f.finish_engineering_research();self.assertEqual(done.status,'completed');self.assertEqual(f.registry.snapshot()['usage'],before)
   obs=w['cloud_report']['evidence']['deployment_verification'];self.assertEqual((obs['declared_file_count'],obs['eof_normalized_file_count'],obs['original_source_identity_match']),(2,1,False))
   # Restore author bytes before a new LEAN input can be admitted.
   (f.root/'cloud/receiver.py').write_bytes(SOURCES['receiver.py']);lean=f.bridge.claim('lean');ad=stage2.prepare(f.bridge,lean.attempt_id)
   native_submit=env('create_backtest',{'projectId':17},{'success':True,'backtestId':'synthetic-lean'})
   submission=receipts.backtest_submission(ad['payload'],ad['deployment'],native_submit);f.bridge.record_submission(lean,submission)
   summary=f.summary();wrap=report(ad['payload'],summary)
   complete={'platform':{'identity':dict(ad['payload']['identity'],external_id='synthetic-lean'),'status':'completed','terminal':True,'deployment':ad['deployment'],'raw_receipt':{'success':True,'fixture':True}},**wrap}
   use=f.registry.snapshot()['usage'];r=f.bridge.consume_completion(lean,completion_source=lambda _:complete);stats['bridge_completion']+=1
   self.assertEqual(r.status,'completed');self.assertEqual(f.registry.snapshot()['usage'],use)
   before=dict(f.store._data);f.bridge.consume_completion(lean,completion_source=lambda _:self.fail('repeat must not read'));self.assertEqual(f.store._data,before)
 def test_new_dispatch_rechecks_original_source_before_any_dispatch_record(self):
  scene('dispatch-eof-drift-refused')
  with Fixture()as f:
   f.start();cell=f.research_binding();f.summary();self.reject_without_write(f,lambda:stage2.research_dispatch(f.bridge,f.attempt.attempt_id,cell))
 def test_engineering_summary_mutants_and_missing_admission_rejected(self):
  mutations=[('missing',lambda x:x.pop('deployment_verification')),('schema_bool',lambda x:x['deployment_verification'].update(schema_version=True)),('mode_project',lambda x:x['deployment_verification'].update(verification_mode='project_original_source')),('count_wrong',lambda x:x['deployment_verification'].update(declared_file_count=1,verified_file_count=1)),('count_bool',lambda x:x['deployment_verification'].update(eof_normalized_file_count=True)),('zero_inconsistent',lambda x:x['deployment_verification'].update(eof_normalized_file_count=0)),('hash',lambda x:x['deployment_verification'].update(deployment_hash='f'*64)),('canonical_false',lambda x:x['deployment_verification'].update(canonical_sources_verified=False)),('extra',lambda x:x['deployment_verification'].update(path='SYNTHETIC-LEAK')),('original_true',lambda x:x['deployment_verification'].update(original_source_identity_match=True))]
  for label,mut in mutations:
   scene('engineering-summary-'+label)
   with Fixture()as f:
    f.start();stage2.research_dispatch(f.bridge,f.attempt.attempt_id,f.research_binding());w=report(f.admission['payload'],f.summary());mut(w['cloud_report']['evidence']);w['report_ref']['sha256']=content_hash(w['cloud_report'])
    self.reject_without_write(f,lambda:stage2.settle_research_result(f.bridge,f.attempt.attempt_id,exec_envelope(w)))
  scene('engineering-namespace-substitution')
  with Fixture()as f:
   f.start();w=report(f.admission['payload'],f.summary());b=receipts.research_observation(f.admission['payload'],f.admission['deployment'],exec_envelope(w));stats['research_parser']+=1;f.bridge.record_submission(f.attempt,b['submission'])
   original=f.store._data.pop('engineering/admitted-inputs/'+f.attempt.attempt_id+'.json');f.store.write_once('collection/admitted-inputs/'+f.attempt.attempt_id+'.json',original)
   self.reject_without_write(f,lambda:f.bridge.consume_completion(f.attempt,completion_source=lambda _:b['completion']))
 def test_collection_real_worker_parser_bridge_and_namespace(self):
  class Source:
   calls=0
   def fetch(self,start,end,catalog):
    self.calls+=1;return iter([{'sid':'synthetic-permanent','snapshot_at':(start+__import__('pandas').Timedelta(hours=9)).isoformat(),'values':{'dollar_volume':7}}])
  scene('collection-worker-parser-bridge')
  with Fixture(collection=True)as f:
   f.start();f.summary();src=Source();cloud=MemoryArtifactStore()
   w=run_collection_task(f.admission['payload'],field_catalog=CAT,store=cloud,source=src,synthetic=True,source_root=f.root/'cloud');self.assertEqual(src.calls,2);self.assertEqual(w['cloud_report']['statistics']['record_count'],2)
   marker=stdout_marker(w,payload=f.admission['payload'],field_catalog=CAT);self.assertEqual(marker,mark(w))
   result=collection_research_observation(f.admission['payload'],f.admission['deployment'],exec_envelope(w),field_catalog=CAT);stats['collection_parser']+=1
   # Wrong namespace is not repaired by an engineering admission with same bytes.
   admission=f.store._data.pop('collection/admitted-inputs/'+f.attempt.attempt_id+'.json');f.store.write_once('engineering/admitted-inputs/'+f.attempt.attempt_id+'.json',admission);f.bridge.record_submission(f.attempt,result['submission'])
   self.reject_without_write(f,lambda:f.bridge.consume_completion(f.attempt,completion_source=lambda _:result['completion']))
   f.store.write_once('collection/admitted-inputs/'+f.attempt.attempt_id+'.json',admission);use=f.registry.snapshot()['usage'];done=f.bridge.consume_completion(f.attempt,completion_source=lambda _:result['completion']);stats['bridge_completion']+=1
   self.assertEqual(done.status,'completed');self.assertEqual(f.registry.snapshot()['usage'],use)
   repeat=run_collection_task(f.admission['payload'],field_catalog=CAT,store=cloud,source=None,synthetic=True,source_root=f.root/'cloud');self.assertEqual(repeat,w);self.assertEqual(src.calls,2)
 def test_collection_summary_mutants_stop_marker_parser_and_bridge(self):
  mutations=[('missing',lambda x:x.pop('deployment_verification')),('namespace_hash',lambda x:x['deployment_verification'].update(deployment_hash='e'*64)),('count_wrong',lambda x:x['deployment_verification'].update(declared_file_count=1,verified_file_count=1)),('mode',lambda x:x['deployment_verification'].update(verification_mode='project_original_source')),('unknown',lambda x:x['deployment_verification'].update(raw='forbidden'))]
  for label,mut in mutations:
   scene('collection-summary-'+label)
   with Fixture(collection=True)as f:
    f.start();summary=f.summary();cp=f.plan.collection_plan;report_key=f.admission['payload']['report_key'];ident=f.admission['payload']['identity']
    d={'schema_version':1,'identity':ident,'status':'completed','terminal':True,'checks':{x:True for x in ['all_windows_completed','cache_only_replay_zero_fetch','same_completed_refs','source_identity_matches','cloud_rows_not_exported','development_only']},'statistics':{'window_count':2,'record_count':2,'source_fetch_calls':2,'reused_windows':0,'empty_windows':0,'cache_only_source_fetch_calls':0},'evidence':{'collection_plan_hash':cp.hash,'collection_receipt_ref':{'key':'synthetic/collection/receipts/'+f.attempt.attempt_id+'.json','sha256':'b'*64},'missing_values':{'dollar_volume':0},'deployment_verification':summary},**{k:False for k in FLAGS}}
    mut(d['evidence']);w={'cloud_report':d,'report_ref':{'key':report_key,'sha256':content_hash(d)}}
    self.reject_without_write(f,lambda:collection_research_observation(f.admission['payload'],f.admission['deployment'],exec_envelope(w),field_catalog=CAT))
 def test_v1_admission_restore_and_strict_worker_preserved(self):
  for collection in [False,True]:
   scene('legacy-original-recovery-%s'%collection)
   with Fixture(collection=collection,version=1)as f:
    f.start();self.assertIsNone(f.summary(False));original=deepcopy(f.admission);before=dict(f.store._data);use=f.registry.snapshot()['usage']
    f.dump('audit/deployment.json',{'source_files':wrapper(version=1),'deployment_manifest':wrapper()});(f.root/'cloud/receiver.py').write_bytes(SOURCES['receiver.py']+b'\n')
    recovered=(cc.prepare_task if collection else stage2.prepare)(f.bridge,f.attempt.attempt_id);self.assertEqual(recovered,original);self.assertEqual(f.store._data,before);self.assertEqual(f.registry.snapshot()['usage'],use)
    with self.assertRaises(DeploymentVerificationError):verify_deployment_observation(f.m,content_hash(f.m),source_root=f.root/'cloud')
    validate_observation_binding({},f.m,content_hash(f.m))
    with self.assertRaises(ValueError):validate_observation_binding({'deployment_verification':{}},f.m,content_hash(f.m))
 def test_v2_native_rejection_uses_records_not_manifest_wrapper_keys(self):
  scene('native-rejection-v2-records')
  with Fixture(resolved=True)as f:
   f.start();w=report(f.admission['payload'],f.summary());parsed=receipts.research_observation(f.admission['payload'],f.admission['deployment'],exec_envelope(w));f.bridge.record_submission(f.attempt,parsed['submission']);f.bridge.consume_completion(f.attempt,completion_source=lambda _:parsed['completion'])
   (f.root/'cloud/receiver.py').write_bytes(SOURCES['receiver.py']);a=f.bridge.claim('lean');ad=stage2.prepare(f.bridge,a.attempt_id)
   for name,expected in [('receiver.py',True),('q/helper.py',True),('_engineering_task_input.py',True),('files',False),('source_identity_policy',False),('other.py',False)]:
    scene('native-file-'+name);out=receipts.backtest_rejection(ad['payload'],ad['deployment'],env('create_backtest',{'projectId':17},{'success':False,'errors':{name:['2:3 synthetic compile failure']},'warnings':{}}));stats['native_rejections']+=1
    self.assertEqual(out['raw_receipt']['settlement_eligible'],expected)
   accepted=receipts.backtest_rejection(ad['payload'],ad['deployment'],env('create_backtest',{'projectId':17},{'success':False,'errors':{'q/helper.py':['2:3 synthetic compile failure']},'warnings':{}}));use=f.registry.snapshot()['usage'];r=f.bridge.record_rejection(a,accepted);self.assertEqual(r.status,'failed');self.assertEqual(f.registry.snapshot()['usage'],use)
   before=dict(f.store._data);self.assertEqual(f.bridge.record_rejection(a,accepted).status,'failed');self.assertEqual(f.store._data,before)

def source_guard():return {p.relative_to(S).as_posix():h(p.read_bytes())for p in S.rglob('*')if p.is_file()}
before=source_guard();stream=(O/'unittest.txt').open('w',encoding='utf-8');t=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(BridgeTests);r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);stream.close();after=source_guard()
result={'methods':r.testsRun,'passed_methods':r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),'failure_records':len(r.failures),'error_records':len(r.errors),'skipped':len(r.skipped),'named_scenarios':len(scenarios),'scenario_names':scenarios,'counts':stats,'seconds':time.monotonic()-t,'failures':[{'test':str(x),'traceback':e}for x,e in r.failures],'errors':[{'test':str(x),'traceback':e}for x,e in r.errors],'source_raw_unchanged':before==after,'source_files':len(after),'actually_executed':True,'QC_calls':0,'financial_evidence':False}
(O/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));raise SystemExit(0 if r.wasSuccessful()and before==after else 1)
