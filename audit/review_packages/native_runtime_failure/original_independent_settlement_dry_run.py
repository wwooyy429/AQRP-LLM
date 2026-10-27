from copy import deepcopy
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
LABEL=sys.argv[1] if len(sys.argv)>1 else 'fixed81'
assert LABEL in {'fixed81','fixed81-final'}
FIXED=WORK/LABEL
sys.path[:0]=[str(FIXED/'cloud'),str(FIXED/'tools')]
import stage2
import qresearch.registry as registry_module
import qresearch.engineering_tasks as bridge_module
from qresearch.artifacts import content_hash
from qresearch.engineering_tasks import EngineeringTaskError

attempt='bfd00f2611fd4496b9498d4597618a8e'
observed=json.loads((WORK/'parsed_observation.json').read_text(encoding='utf-8'))
bridge=stage2.bridge_for_attempt(attempt)
admitted=stage2.admitted_input(bridge,attempt)
original_record=bridge._record(attempt)
assert original_record['status']=='pending'
assert original_record['external_id']=='39cafa1e9b11f91b27e396b66d033a6d'
event_file=FIXED/'audit/runtime/registry/events.jsonl'
before_bytes=event_file.read_bytes()
before=bridge.registry.snapshot()
assert len(before_bytes.splitlines())==12
pointer_path=FIXED/'audit/runtime/engineering/submissions'/f'{attempt}.json'
input_path=FIXED/admitted['input_path']
pointer_before=pointer_path.read_bytes()
input_before=input_path.read_bytes()
def inventory(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file() and '.lock' not in p.name and '.locks' not in p.parts}
mirror_before=inventory(FIXED/'audit/runtime')
negative_checks=[]
for field in ('input_hash','external_id'):
    bad=deepcopy(observed)
    if field=='input_hash':bad['platform']['deployment']['input_hash']='0'*64
    else:bad['platform']['identity']['external_id']='independent-negative-id'
    try:
        bridge.consume_completion(attempt,completion_source=lambda _,value=bad:value)
    except EngineeringTaskError as error:
        negative_checks.append({'name':field,'rejected':True,'reason':str(error)})
    else:
        raise AssertionError('Unbound failure observation settled: '+field)
    assert event_file.read_bytes()==before_bytes
    assert inventory(FIXED/'audit/runtime')==mirror_before

settled=bridge.consume_completion(attempt,completion_source=lambda _:deepcopy(observed))
after=bridge.registry.snapshot()
after_bytes=event_file.read_bytes()
assert settled.status=='failed'
assert len(after_bytes.splitlines())==13
assert after['usage']==before['usage']
record=next(x for x in after['attempts'] if x['attempt_id']==attempt)
assert record['external_id']==original_record['external_id']
assert record['error']['platform_status']=='runtime_error'
assert pointer_path.read_bytes()==pointer_before and input_path.read_bytes()==input_before
assert not bridge.store.exists(record['result_key'])
reference=record['error']['evidence_ref']
saved=json.loads(bridge.store.read_bytes(reference['key']))
assert saved==observed and content_hash(saved)==reference['sha256']
mirror_after=inventory(FIXED/'audit/runtime')
replayed=bridge.consume_completion(attempt,completion_source=lambda _:deepcopy(observed))
assert replayed.status=='failed'
assert event_file.read_bytes()==after_bytes
assert inventory(FIXED/'audit/runtime')==mirror_after
manifest=json.loads((WORK/('isolation_manifest_final.json' if LABEL.endswith('-final') else 'isolation_manifest.json')).read_text(encoding='utf-8'))
assert inventory(ROOT/'audit/runtime')==manifest['actual_runtime_raw_sha256']
modules={name:mod.__file__ for name,mod in [('stage2',stage2),('Registry',registry_module),('Bridge',bridge_module)]}
for file in modules.values():assert Path(file).is_relative_to(FIXED)
report={'kind':'new_fixed_parser_output_consumed_by_independently_accepted81f_mirror_only',
    'parser_source_evidence':json.loads((WORK/'actual_parser_report.json').read_text(encoding='utf-8'))['parser_raw_sha256'],
    'actual_receipt_raw_sha256':manifest['native_original_raw_sha256'],
    'old_source_commit':'81fbe5294055423e88ee5aeae48ca6223e7971da','modules':modules,
    'event_counts':{'before':12,'after':13,'same_receipt_replay':13},
    'usage_before':before['usage'],'usage_after':after['usage'],
    'original_attempt':attempt,'original_external_id':record['external_id'],
    'settled_status':record['status'],'platform_status':'runtime_error','negative_checks':negative_checks,
    'input_and_submission_pointer_raw_unchanged':True,'success_result_not_created':True,
    'order_count_not_inferred':True,'observation_sha256':content_hash(observed),
    'new_mirror_paths':sorted(set(mirror_after)-set(mirror_before)),
    'changed_mirror_paths':sorted(p for p in set(mirror_before)&set(mirror_after) if mirror_before[p]!=mirror_after[p]),
    'real_registry_writes':0,'real_registry_raw_unchanged':True,'real_QC_calls':0,
    'new_parser_requires_GPT_Work_review':True,'stage2_acceptance_granted':False,'financial_evidence':False}
(WORK/('settlement_report_final.json' if LABEL.endswith('-final') else 'settlement_report.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
