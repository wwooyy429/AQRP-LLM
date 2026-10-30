"""Apply parsed real receipt only to an independent fixed81 Git mirror."""
from pathlib import Path
from copy import deepcopy
import hashlib,io,json,socket,subprocess,sys,tarfile
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;S=R/'source';FIXED=O/'isolated_fixed81'
G=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo';SHA='81fbe5294055423e88ee5aeae48ca6223e7971da'
assert not FIXED.exists(),'Do not overwrite a previous replay mirror'
archive=subprocess.check_output(['git','-C',G,'archive',SHA]);FIXED.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive)) as t:
 for m in t.getmembers():
  if m.isfile():
   p=FIXED/m.name;assert p.resolve().is_relative_to(FIXED.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
def inventory(p):return {x.relative_to(p).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in p.rglob('*') if x.is_file() and '.locks' not in x.parts and not x.name.endswith('.lock')}
source_before=inventory(S);socket_attempts=[]
def denied(*a,**k):socket_attempts.append(True);raise AssertionError('No network in mirror replay')
socket.socket.connect=denied;socket.create_connection=denied;sys.dont_write_bytecode=True;sys.path[:0]=[str(FIXED/'tools'),str(FIXED/'cloud')]
import stage2
import qresearch.registry as registry_module
import qresearch.engineering_tasks as bridge_module
from qresearch.artifacts import content_hash
from qresearch.engineering_tasks import EngineeringTaskError
attempt='bfd00f2611fd4496b9498d4597618a8e';observed=json.loads((O/'parsed_observation.json').read_bytes())
bridge=stage2.bridge_for_attempt(attempt);admitted=stage2.admitted_input(bridge,attempt);record=bridge._record(attempt)
assert record['status']=='pending' and record['external_id']=='39cafa1e9b11f91b27e396b66d033a6d'
eventpath=FIXED/'audit/runtime/registry/events.jsonl';before_events=eventpath.read_bytes();assert len(before_events.splitlines())==12
before=bridge.registry.snapshot();before_runtime=inventory(FIXED/'audit/runtime');negative=[]
for field in ('input_hash','external_id'):
 bad=deepcopy(observed)
 if field=='input_hash':bad['platform']['deployment']['input_hash']='0'*64
 else:bad['platform']['identity']['external_id']='wrong-independent-identity'
 try:bridge.consume_completion(attempt,completion_source=lambda _,v=bad:v)
 except EngineeringTaskError as exc:negative.append({'mutation':field,'rejected':True,'reason':str(exc)})
 else:raise AssertionError('Unbound observation admitted: '+field)
 assert before_runtime==inventory(FIXED/'audit/runtime') and eventpath.read_bytes()==before_events
protected=['audit/task_inputs/'+attempt+'.py','audit/runtime/engineering/submissions/'+attempt+'.json','audit/runtime/engineering/admitted-inputs/'+attempt+'.json','audit/engineering_current.json','config/budget.json','audit/data_exposure.json']
protected_before={p:(FIXED/p).read_bytes() for p in protected}
settled=bridge.consume_completion(attempt,completion_source=lambda _:deepcopy(observed));assert settled.status=='failed'
after=bridge.registry.snapshot();after_events=eventpath.read_bytes();assert after_events.startswith(before_events) and len(after_events.splitlines())==13 and before['usage']==after['usage']
record=next(v for v in after['attempts'] if v['attempt_id']==attempt);reference=record['error']['evidence_ref']
assert record['error']['platform_status']=='runtime_error' and not bridge.store.exists(record['result_key'])
assert json.loads(bridge.store.read_bytes(reference['key']))==observed and reference['sha256']==content_hash(observed)
after_runtime=inventory(FIXED/'audit/runtime');again=bridge.consume_completion(attempt,completion_source=lambda _:deepcopy(observed))
assert again.status=='failed' and eventpath.read_bytes()==after_events and inventory(FIXED/'audit/runtime')==after_runtime
assert all((FIXED/p).read_bytes()==v for p,v in protected_before.items()) and source_before==inventory(S)
modules={n:m.__file__ for n,m in [('stage2',stage2),('Registry',registry_module),('Bridge',bridge_module)]};assert all(Path(p).is_relative_to(FIXED) for p in modules.values())
actual_events=(S/'audit/runtime/registry/events.jsonl').read_bytes();actual_last=json.loads(actual_events.splitlines()[-1])['event'];mirror_last=json.loads(after_events.splitlines()[-1])['event']
assert {k:v for k,v in actual_last.items() if k!='recorded_at'}=={k:v for k,v in mirror_last.items() if k!='recorded_at'}
report={'kind':'independent_saved_native_parser_to_old81_Bridge_Registry_mirror_only','fixed_settlement_code_commit':SHA,'modules':modules,'mirror':str(FIXED),'event_counts':{'before':12,'after':13,'same_receipt_replay':13},'usage_before':before['usage'],'usage_after':after['usage'],'settled_status':record['status'],'platform_status':'runtime_error','attempt_id':attempt,'external_id':record['external_id'],'negative_bindings':negative,'original_input_submission_admission_pointer_budget_exposure_unchanged':True,'success_result_created':False,'evidence_ref':reference,'actual13_event_semantics_match_mirror_ignoring_recorded_at':True,
 'production_consume_completion_calls':4,'negative_calls':2,'one_failure_settlement_call':1,'same_receipt_idempotent_call':1,'software_unit_methods':0,'actual_registry_writes':0,'actual_source_unchanged':True,'provider_socket_attempts':len(socket_attempts),'new_platform_or_market_or_model_calls':0,
 'boundary':'Only a fresh independent Git81 mirror was mutated. Current authoritative13-event source was read, never reset or settled again. No real execution or data/financial success inferred.'}
assert not socket_attempts
(O/'old_bridge_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
