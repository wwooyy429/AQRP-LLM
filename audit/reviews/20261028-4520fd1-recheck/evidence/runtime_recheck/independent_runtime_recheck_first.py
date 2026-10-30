"""Independent synthetic parser/bridge checks; never calls QC or writes source."""
import argparse,base64,copy,hashlib,json,platform,sys,time,unittest
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--source',required=True);P.add_argument('--out',required=True)
A=P.parse_args();S=Path(A.source).resolve();O=Path(A.out).resolve();O.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True;sys.path[:0]=[str(S/'cloud'),str(S/'tools')]
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash,ArtifactConflict
from qresearch.registry import Registry
from qresearch.engineering_receipts import research_observation,research_cell_source,research_dispatch_binding,backtest_submission,backtest_observation,ReceiptParseError
from qresearch.engineering_tasks import EngineeringTaskError
import stage2
IDS={'diagnostic':'b9f952c1de3a44f9b06e5c552f7d1af3','research':'2d1095df62dc4222bffd8000c0737d38','lean':'37dc855045e14ca49c88fd9d75f40cf7'}
EXTERNAL='3e68866a46ca88ff16481c31b3c2c822'
RECORDS=[];COUNTS={'research_parser_calls':0,'lean_parser_calls':0,'synthetic_completion_calls':0,'original_research_replays':0}
SOURCE_HASHES={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in S.rglob('*')if p.is_file()}
def J(p):return json.loads(p.read_bytes())
def copy_store():
 m=MemoryArtifactStore()
 for p in (S/'audit/runtime').rglob('*'):
  if p.is_file()and p.suffix in {'.json','.jsonl','.py'}:m.write_once(p.relative_to(S/'audit/runtime').as_posix(),p.read_bytes())
 return m
def native(packet):
 r=packet['result'];vals=[]
 if r.get('structuredContent')is not None:vals.append(r['structuredContent'])
 for b in r.get('content',[]):
  assert b['type']=='text';vals.append(json.loads(b['text']))
 assert vals and all(canonical_json(v)==canonical_json(vals[0])for v in vals)
 return vals[0]
def packet(tool,args,value):return {'tool_name':tool,'arguments':args,'result':{'isError':False,'structuredContent':value,'content':[{'type':'text','text':json.dumps(value,indent=1)}]}}
def read_ctx(reg,label):
 a=IDS[label];b=stage2.bridge_for_attempt(a,registry=reg);ad=stage2.admitted_input(b,a)
 ret={'id':a,'bridge':b,'payload':ad['payload'],'deployment':ad['deployment'],'admission':ad}
 if label!='lean':
  ret['binding']=stage2._read_research_dispatch(b,ad['payload'],ad['deployment'],require_dispatch=True)
  ret['packet']=J(S/'audit/tool_observations'/(a+'-research.json'))
 else:ret['packet']=J(S/'audit/tool_observations'/(a+'-submission.json'))
 return ret
def parse_research(c,p=None,binding=None):
 COUNTS['research_parser_calls']+=1
 return research_observation(c['payload'],c['deployment'],c['packet']if p is None else p,dispatch_binding=c['binding']if binding is None else binding,dispatch_required=True)
def marker_packet(c,wrapper):
 wrapper=copy.deepcopy(wrapper);wrapper['report_ref']['sha256']=content_hash(wrapper['cloud_report'])
 stream={'output_type':'stream','name':'stdout','text':'AQRP_ENGINEERING_JSON '+base64.b64encode(canonical_json(wrapper)).decode()+'\n'}
 return packet('mcp__quantconnect__jupyter_execute_cell',copy.deepcopy(c['packet']['arguments']),stream)
def research_wrapper(c):
 text=native(c['packet'])['text'].strip();assert text.startswith('AQRP_ENGINEERING_JSON ')
 return json.loads(base64.b64decode(text.split(' ',1)[1],validate=True))
def lean_fixture(c):
 p=c['payload'];report={'schema_version':1,'identity':p['identity'],'terminal':True,'status':'completed',
  'checks':dict.fromkeys(p['plan']['required_checks']['lean'],True),
  'statistics':{'data_event_count':1,'orders_submitted':0,'runtime_error_count':0,'dividend_event_count':1},
  'resolution':p['research_resolution'],'evidence':{},
  **dict.fromkeys(['market_values_exported','economic_factor_tested','final_data_accessed','full_US200_coverage_certified','actual_availability_verified'],False)}
 wrapper={'cloud_report':report,'report_ref':{'key':p['report_key'],'sha256':content_hash(report)}}
 value={'success':True,'backtest':{'backtestId':EXTERNAL,'projectId':p['identity']['project_id'],'completed':True,'hasInitializeError':False,'progress':1,'status':'Completed.','statistics':{'Total Orders':'0'}}}
 return wrapper,packet('mcp__quantconnect__read_backtest',{'projectId':p['identity']['project_id'],'backtestId':EXTERNAL},value)
def log_packets(c,w,pages=1):
 w=copy.deepcopy(w);w['report_ref']['sha256']=content_hash(w['cloud_report']);encoded=base64.b64encode(canonical_json(w)).decode()
 chunks=[encoded[i:i+500]for i in range(0,len(encoded),500)]
 lines=['AQRP_ENGINEERING '+c['id']+' '+str(i)+'/'+str(len(chunks))+' '+v for i,v in enumerate(chunks)]
 groups=[lines]if pages==1 else [lines[:len(lines)//2],lines[len(lines)//2:]]
 return [packet('mcp__quantconnect__search_backtest_logs',{'projectId':c['payload']['identity']['project_id'],'backtestId':EXTERNAL,'query':'AQRP_ENGINEERING '+c['id'],'page':i+1},{'success':True,'logs':g,'totalPages':len(groups)})for i,g in enumerate(groups)]
def parse_lean(c,n,w=None,logs=None):
 COUNTS['lean_parser_calls']+=1
 return backtest_observation(c['payload'],c['deployment'],EXTERNAL,n,log_packets(c,w)if logs is None else logs)
class Tests(unittest.TestCase):
 def setUp(self):
  self.store=copy_store();self.reg=Registry(self.store,J(S/'audit/runtime/registry/baseline.json'));self.ctx={k:read_ctx(self.reg,k)for k in IDS};self.before=dict(self.store._data)
 def case(self,name,fn):
  with self.subTest(name=name):fn();RECORDS.append({'method':self._testMethodName,'name':name,'passed':True})
 def reject(self,fn):
  before=dict(self.store._data)
  with self.assertRaises((ValueError,ArtifactConflict)):fn()
  self.assertEqual(self.store._data,before)
 def test_01_archived_versions_inputs_and_required_checks(self):
  self.assertEqual(len(self.store.read_bytes('registry/events.jsonl').splitlines()),46)
  for label,c in self.ctx.items():
   def verify(c=c,label=label):
    p=c['payload'];encoded=('TASK_INPUT_JSON = '+repr(canonical_json(p).decode())+'\n').encode()
    self.assertEqual((S/c['admission']['input_path']).read_bytes(),encoded)
    self.assertEqual(hashlib.sha256(encoded).hexdigest(),c['deployment']['input_hash'])
    self.assertEqual(content_hash(p['deployment_manifest']),c['deployment']['deployment_hash'])
    self.assertEqual(len(p['deployment_manifest']),32)
    if label!='lean':
     cp=J(S/'audit/tool_observations'/(c['id']+'-read-cell.json'));self.assertEqual(research_dispatch_binding(p,c['deployment'],cp),c['binding'])
    else:
     self.assertEqual(len(p['plan']['required_checks']['research']),13);self.assertEqual(len(p['plan']['required_checks']['lean']),7)
     self.assertEqual(sorted(x.name for x in (S/'audit/tool_observations').glob(c['id']+'*')),[c['id']+'-submission.json'])
   self.case('frozen_identity_'+label,verify)
 def test_02_original_research_recovers_without_current_pointer(self):
  oldroot=stage2.ROOT;unrelated=O/'unrelated_current';(unrelated/'audit').mkdir(parents=True,exist_ok=True);(unrelated/'audit/engineering_current.json').write_text('{"corrupt":"unrelated"}',encoding='utf-8')
  try:
   stage2.ROOT=unrelated
   for label,status in [('research','completed'),('diagnostic','failed'),('research','completed'),('diagnostic','failed')]:
    c=self.ctx[label]
    def replay(c=c,status=status):
     global COUNTS
     b=stage2.bridge_for_attempt(c['id'],registry=self.reg);r=stage2.settle_research_result(b,c['id'],c['packet']);COUNTS['original_research_replays']+=1
     self.assertEqual(r.status,status);self.assertEqual(self.store._data,self.before)
    self.case('frozen_recovery_'+label+'_'+str(COUNTS['original_research_replays']),replay)
  finally:stage2.ROOT=oldroot
 def test_03_semantic_carriers_and_duplicate_error_annotations(self):
  c=self.ctx['research'];v=native(c['packet']);p=packet(c['packet']['tool_name'],c['packet']['arguments'],v)
  self.case('success_semantic_mirror_key_order',lambda:self.assertEqual(parse_research(c,p)['completion']['platform']['status'],'completed'))
  c=self.ctx['diagnostic'];v=native(c['packet']);a={'audience':['assistant'],'priority':0.7,'lastModified':'2026-10-28T00:00:00.123456+00:00'}
  p={'tool_name':c['packet']['tool_name'],'arguments':c['packet']['arguments'],'result':{'isError':True,'structuredContent':v,'content':[{'type':'text','text':json.dumps(v),'annotations':a},{'type':'text','text':json.dumps(v,sort_keys=True),'annotations':copy.deepcopy(a)}]}}
  self.case('two_error_texts_and_structured_fractional_annotation',lambda:self.assertEqual(parse_research(c,p)['completion']['platform']['raw_receipt']['native_error_representation_count'],3))
  p['result']['content'][1]['annotations']['priority']=0.8
  self.case('unequal_supported_annotations_rejected',lambda:self.reject(lambda:parse_research(c,p)))
 def test_04_rehashed_probe_arithmetic_and_positive_cache_mix(self):
  c=self.ctx['research'];original=research_wrapper(c)
  mutants=[('window39',{'window_count':39}),('fetch_plus_reuse41',{'source_fetch_calls':40,'reused_windows':1}),('fetch_plus_reuse39',{'source_fetch_calls':39,'reused_windows':0}),('empty41',{'empty_windows':41}),('zero_records_nonempty_windows',{'record_count':0}),('one_short_record_for_nonempty_windows',{'record_count':26,'duplicate_projection_records':0})]
  for name,delta in mutants:
   w=copy.deepcopy(original);w['cloud_report']['evidence']['collection_probe'].update(delta)
   self.case(name,lambda w=w:self.reject(lambda:parse_research(c,marker_packet(c,w))))
  w=copy.deepcopy(original);probe=w['cloud_report']['evidence']['collection_probe'];probe['source_fetch_calls']=13;probe['reused_windows']=27
  self.case('valid_mixed_cache_window_partition',lambda:self.assertEqual(parse_research(c,marker_packet(c,w))['completion']['cloud_report']['evidence']['collection_probe']['reused_windows'],27))
 def test_05_cross_attempt_binding_and_failure_replacement(self):
  good,bad=self.ctx['research'],self.ctx['diagnostic']
  self.case('failure_packet_on_success_attempt',lambda:self.reject(lambda:parse_research(good,bad['packet'])))
  self.case('success_packet_on_failed_attempt',lambda:self.reject(lambda:parse_research(bad,good['packet'])))
  self.case('foreign_original_dispatch',lambda:self.reject(lambda:parse_research(good,binding=bad['binding'])))
  changed=copy.deepcopy(bad['packet']);v=native(changed);v['evalue']+=' INDEPENDENT_SYNTHETIC_DIAGNOSTIC'
  changed['result']={'isError':False,'content':[{'type':'text','text':json.dumps(v)}]}
  self.case('different_but_valid_failure_cannot_replace_original',lambda:self.reject(lambda:stage2.settle_research_result(bad['bridge'],bad['id'],changed)))
 def test_06_synthetic_lean_seven_checks_zero_orders_complete(self):
  c=self.ctx['lean'];w,n=lean_fixture(c);self.assertEqual(len(w['cloud_report']['checks']),7)
  for zero in ['0','0.00','0E-24','-0']:
   v=copy.deepcopy(n);nv=native(v);nv['backtest']['statistics']['Total Orders']=zero;v=packet(v['tool_name'],v['arguments'],nv)
   def verify(v=v):
    observed=parse_lean(c,v,w);submission=c['bridge']._recorded_submission(c['payload']);self.assertEqual(c['bridge']._completion_contract(c['payload'],submission,observed),('completed',True))
   self.case('synthetic_lean_native_zero_'+zero,verify)
  observed=parse_lean(c,n,w);before_usage=copy.deepcopy(self.reg.snapshot()['usage'])
  r=c['bridge'].consume_completion(c['id'],completion_source=lambda _:copy.deepcopy(observed));COUNTS['synthetic_completion_calls']+=1
  self.assertEqual(r.status,'completed');self.assertEqual(self.reg.snapshot()['usage'],before_usage)
  self.assertEqual(len(self.store.read_bytes('registry/events.jsonl').splitlines()),47)
  self.case('synthetic_only_pending_to_completed_no_charge',lambda:self.assertEqual(c['bridge'].read_result(c['id'])['financial_evidence'],False))
 def test_07_synthetic_lean_failed_checks_and_counters(self):
  c=self.ctx['lean'];w,n=lean_fixture(c);submission=c['bridge']._recorded_submission(c['payload'])
  for name in sorted(w['cloud_report']['checks']):
   changed=copy.deepcopy(w);changed['cloud_report']['checks'][name]=False;changed['cloud_report']['status']='failed'
   def verify(changed=changed):self.assertEqual(c['bridge']._completion_contract(c['payload'],submission,parse_lean(c,n,changed)),('completed',False))
   self.case('synthetic_false_'+name,verify)
  for key,value in [('data_event_count',0),('orders_submitted',1),('runtime_error_count',1),('dividend_event_count',0)]:
   changed=copy.deepcopy(w);changed['cloud_report']['statistics'][key]=value
   self.case('synthetic_counter_'+key,lambda changed=changed:self.assertEqual(c['bridge']._completion_contract(c['payload'],submission,parse_lean(c,n,changed)),('completed',False)))
 def test_08_synthetic_lean_pagination_and_chunk_integrity(self):
  c=self.ctx['lean'];w,n=lean_fixture(c);logs=log_packets(c,w,pages=2)
  self.case('reversed_complete_native_pages_accepted',lambda:self.assertEqual(parse_lean(c,n,logs=logs[::-1])['cloud_report']['checks'],w['cloud_report']['checks']))
  cases={}
  cases['missing_page']=logs[:1]
  cases['duplicate_page']=logs+[copy.deepcopy(logs[0])]
  mismatch=copy.deepcopy(logs);v=native(mismatch[1]);v['totalPages']=3;mismatch[1]=packet(mismatch[1]['tool_name'],mismatch[1]['arguments'],v);cases['inconsistent_total_pages']=mismatch
  foreign=copy.deepcopy(logs);v=native(foreign[0]);v['logs'][0]=v['logs'][0].replace(c['id'],'0'*32);foreign[0]=packet(foreign[0]['tool_name'],foreign[0]['arguments'],v);cases['foreign_chunk_attempt']=foreign
  duplicated=copy.deepcopy(logs);v=native(duplicated[0]);v['logs'].append(v['logs'][0]);duplicated[0]=packet(duplicated[0]['tool_name'],duplicated[0]['arguments'],v);cases['duplicate_chunk']=duplicated
  for name,ls in cases.items():self.case(name,lambda ls=ls:self.reject(lambda:parse_lean(c,n,logs=ls)))
 def test_09_synthetic_lean_terminal_state_and_actual_order_rejections(self):
  c=self.ctx['lean'];w,n=lean_fixture(c)
  cases=[('wrong_external',{'backtestId':'foreign'}),('wrong_project',{'projectId':c['payload']['identity']['project_id']+1}),('running',{'completed':False,'status':'Running','progress':0.5}),('unknown_terminal_status',{'status':'Unknown'}),('incomplete_progress',{'progress':0.999}),('bool_progress',{'progress':True})]
  for name,delta in cases:
   nv=native(n);nv['backtest'].update(delta);v=packet(n['tool_name'],n['arguments'],nv)
   self.case(name,lambda v=v:self.reject(lambda:parse_lean(c,v,w)))
  for bad in [1,'0.01','NaN',True]:
   nv=native(n);nv['backtest']['statistics']['Total Orders']=bad;v=packet(n['tool_name'],n['arguments'],nv)
   self.case('nonzero_or_invalid_native_orders_'+repr(bad),lambda v=v:self.reject(lambda:parse_lean(c,v,w)))
 def test_10_synthetic_failure_receipts_and_original_pending_unchanged(self):
  c=self.ctx['lean'];native_failure={'success':False,'errors':['The backtest ended with a runtime error.','SYNTHETIC bounded diagnostic']}
  n=packet('mcp__quantconnect__read_backtest',{'projectId':c['payload']['identity']['project_id'],'backtestId':EXTERNAL},native_failure);n['result']['isError']=True
  observed=parse_lean(c,n,logs=[]);self.case('synthetic_runtime_failure_accepted_without_logs',lambda:self.assertEqual(observed['platform']['status'],'runtime_error'))
  n['result']['structuredContent']['errors'][0]='Connection timed out';n['result']['content'][0]['text']=json.dumps(n['result']['structuredContent'])
  self.case('transport_timeout_not_terminal',lambda:self.reject(lambda:parse_lean(c,n,logs=[])))
  self.case('real_frozen_ledger_still_pending',lambda:self.assertEqual(c['bridge']._record(c['id'])['status'],'pending'))
  self.assertEqual(self.store._data,self.before)
class Result(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.passed_methods=[]
 def addSuccess(self,t):super().addSuccess(t);self.passed_methods.append(t.id())
start=time.monotonic()
with (O/'first_unittest.txt').open('w',encoding='utf-8')as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
out={'source_commit':'4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8','methods':r.testsRun,'passed_methods':len(r.passed_methods),'failure_records':len(r.failures),'error_records':len(r.errors),'skipped':len(r.skipped),'named_scenario_records':len(RECORDS),'scenario_records':RECORDS,'counts':COUNTS,'seconds':time.monotonic()-start,'success':r.wasSuccessful(),'environment':{'python':sys.version,'platform':platform.platform()},'current_platform_calls':0,'LEAN_terminal_or_log_reads':0,'actual_QC_workers':0,'financial_evidence':False,'source_raw_unchanged':SOURCE_HASHES=={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in S.rglob('*')if p.is_file()},'failure_details':r.failures,'error_details':r.errors,'counting':'Named scenarios/parser calls/methods/Memory replay counts overlap; no actual QC worker. All newLEAN terminal data are explicit synthetic fixtures; actual archive remains pending.'}
out['failure_details']=[{'test':str(t),'traceback':tb}for t,tb in r.failures];out['error_details']=[{'test':str(t),'traceback':tb}for t,tb in r.errors]
(O/'first_results.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items()if k not in ['scenario_records','failure_details','error_details']},indent=2));sys.exit(0 if r.wasSuccessful()and out['source_raw_unchanged']else 1)
