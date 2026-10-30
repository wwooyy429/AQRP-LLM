from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
FIXED=WORK/'fixed81-final'
sys.path[:0]=[str(FIXED/'cloud'),str(FIXED/'tools')]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash, decode_events
from qresearch.registry import Registry
import qresearch.registry as registry_module
import qresearch.engineering_tasks as bridge_module
import stage2

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
runtime=ROOT/'audit/runtime'
actual={p.relative_to(runtime).as_posix():p.read_bytes() for p in sorted(runtime.rglob('*'))
        if p.is_file() and '.lock' not in p.name and '.locks' not in p.parts}
initial=read(WORK/'isolation_manifest_final.json')['actual_runtime_raw_sha256']
actual_hashes={p:sha(raw) for p,raw in actual.items()}
events=decode_events(actual['registry/events.jsonl'])
assert len(events)==13
prefix=b''.join(actual['registry/events.jsonl'].splitlines(keepends=True)[:12])
assert sha(prefix)==initial['registry/events.jsonl']

# Replay only a byte-for-byte in-memory copy; no Registry is opened on real disk.
memory=MemoryArtifactStore()
for path,raw in actual.items():memory.write_once(path,raw)
registry=Registry(memory,json.loads(actual['registry/baseline.json']))
snapshot=registry.snapshot()
attempt='bfd00f2611fd4496b9498d4597618a8e'
record=next(x for x in snapshot['attempts'] if x['attempt_id']==attempt)
assert record['status']=='failed' and record['external_id']=='39cafa1e9b11f91b27e396b66d033a6d'
usage={k:v['total'] for k,v in snapshot['usage'].items()}
assert usage=={'configurations':6,'research':9,'lean':1}
last=events[-1]['event']
assert last['kind']=='failed' and last['attempt_id']==attempt
assert last['error']['platform_status']=='runtime_error'
reference=last['error']['evidence_ref']
saved=json.loads(actual[reference['key']])
assert actual[reference['key']]==canonical_json(saved)
assert reference['sha256']==content_hash(saved)==last['reconciliation']=='ff5002cdf15423e9a7f45a0b5b5744d89c675506ef7331df49bdec9b4f5c3233'
assert saved==read(WORK/'parsed_observation.json')
native_path=ROOT/'audit/tool_observations'/f'{attempt}-terminal-runtime-error.json'
native_raw=native_path.read_bytes();native=json.loads(native_raw)
assert sha(native_raw)=='867148e882d39a024d12d68a01803ba80c282f05b872f16616dfded53c7eea27'
platform=saved['platform'];raw=platform['raw_receipt']
assert raw['response_sha256']==content_hash(native['result'])
assert raw['tool_name']==native['tool_name']=='mcp__quantconnect__read_backtest'
assert raw['arguments']==native['arguments']=={'projectId':38436695,'backtestId':record['external_id']}
admitted=json.loads(actual['engineering/admitted-inputs/'+attempt+'.json'])
submission=json.loads(actual['engineering/submissions/'+attempt+'.json'])
assert platform['identity']==dict(admitted['payload']['identity'],external_id=record['external_id'])
assert platform['deployment']==admitted['deployment']==submission['deployment']
assert sha((ROOT/admitted['input_path']).read_bytes())==admitted['deployment']['input_hash']=='95092b4de264c961895655f0853de639981143ad8cdb41e2c0d22b0adc7136b0'
original_reference=submission['receipt_ref']
original=json.loads(actual[original_reference['key']])
assert content_hash(original)==original_reference['sha256']
assert original['accepted'] is True and original['external_id']==record['external_id']
assert original['identity']==admitted['payload']['identity'] and original['deployment']==platform['deployment']
assert not memory.exists(record['result_key'])
bridge=stage2.bridge_for_attempt(attempt,registry=registry)
payload=bridge.payload(attempt)
accepted=bridge._recorded_submission(payload)
assert bridge._completion_contract(payload,accepted,saved)==('runtime_error',False)
new=sorted(set(actual)-set(initial))
changed=sorted(path for path in set(actual)&set(initial) if sha(actual[path])!=initial[path])
assert new==[reference['key']]
assert changed==['registry/events.jsonl']
assert not set(initial)-set(actual)
protected=['audit/engineering_current.json','config/budget.json','audit/data_exposure.json']
git_matches={}
for path in protected:
    expected=subprocess.check_output(['git','rev-parse','HEAD:'+path],cwd=ROOT).decode().strip()
    current=subprocess.check_output(['git','hash-object','--path='+path,'--',path],cwd=ROOT).decode().strip()
    assert current==expected,path
    git_matches[path]=current
assert actual_hashes=={p.relative_to(runtime).as_posix():sha(p.read_bytes()) for p in sorted(runtime.rglob('*'))
        if p.is_file() and '.lock' not in p.name and '.locks' not in p.parts}
report={'kind':'independent_readonly_postcheck_after_root_actual_settlement',
    'state_reader_source_commit':'81fbe5294055423e88ee5aeae48ca6223e7971da',
    'modules':{'Registry':registry_module.__file__,'Bridge':bridge_module.__file__,'stage2':stage2.__file__},
    'event_chain_records':13,'all_event_hashes_verified':True,'first12_raw_bytes_preserved':True,
    'last_event_hash':events[-1]['hash'],'last_event_kind':last['kind'],'actual_usage':usage,
    'attempt_id':attempt,'external_id':record['external_id'],'status':record['status'],
    'native_original_raw_sha256':sha(native_raw),'saved_observation_sha256':content_hash(saved),
    'new_runtime_paths':new,'changed_existing_runtime_paths':changed,'removed_runtime_paths':[],
    'original_input_and_submission_pointer_raw_preserved':True,
    'config_budget_pointer_exposure_match_prior_Git_blobs':git_matches,
    'success_result_absent':True,'order_count_progress_completed_not_inferred':True,
    'native_packet_identity_and_response_hash_binding_valid':True,
    'fixed81_completion_contract_verified_without_transition':True,
    'registry_replayed_from_memory_only':True,'real_registry_writes_by_postcheck':0,
    'real_QC_calls':0,'stage2_acceptance_granted':False,'financial_evidence':False,
    'new_parser_independent_review_still_pending':True}
(WORK/'post_settlement_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
