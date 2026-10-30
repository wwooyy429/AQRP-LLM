from pathlib import Path
import ast
import hashlib
import html
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
ATTEMPT='37dc855045e14ca49c88fd9d75f40cf7'
BACKTEST='3e68866a46ca88ff16481c31b3c2c822'
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
from qresearch.artifacts import MemoryArtifactStore,content_hash
from qresearch.registry import Registry
from qresearch.engineering_receipts import backtest_observation,backtest_submission,_native
from stage2 import bridge_for_attempt,admitted_input

def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(name,value):(OUT/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
tracked=[p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p]
protected={p:sha((ROOT/p).read_bytes()) for p in tracked if p.startswith(('cloud/','config/','tools/','tests/','audit/runtime/'))}
original=OUT/'fixed-fixture'
store=MemoryArtifactStore()
for path in (original/'audit/runtime').rglob('*'):
    if path.is_file():store._data[path.relative_to(original/'audit/runtime').as_posix()]=path.read_bytes()
registry=Registry(store,json.loads((original/'audit/runtime/registry/baseline.json').read_bytes()))
bridge=bridge_for_attempt(ATTEMPT,registry=registry)
record=bridge._record(ATTEMPT)
assert record['status']=='pending' and record['external_id']==BACKTEST
admission=admitted_input(bridge,ATTEMPT)
payload,deployment=admission['payload'],admission['deployment']
assert payload['research_resolution']==bridge._research_result()['cloud_report']['resolution']
native_path=ROOT/f'audit/tool_observations/{ATTEMPT}-backtest-result.json'
logs_path=ROOT/f'audit/tool_observations/{ATTEMPT}-backtest-logs.json'
native=json.loads(native_path.read_bytes());logs=json.loads(logs_path.read_bytes())
assert native['arguments']==dict(projectId=38436695,backtestId=BACKTEST)
submission=json.loads((ROOT/f'audit/tool_observations/{ATTEMPT}-submission.json').read_bytes())
original_submission=backtest_submission(payload,deployment,submission)
assert original_submission['external_id']==BACKTEST
assert bridge._recorded_submission(payload)['receipt_ref']['sha256']==content_hash(original_submission)
observed=backtest_observation(payload,deployment,BACKTEST,native,logs)
assert observed['platform']['status']=='runtime_error' and set(observed)=={'platform'}
before=registry.snapshot()
settled=bridge.consume_completion(ATTEMPT,completion_source=lambda _:observed)
after=registry.snapshot()
assert settled.status=='failed' and before['usage']==after['usage']
assert len(store.read_bytes(registry.JOURNAL).splitlines())==47
saved=dict(store._data)
assert bridge.consume_completion(ATTEMPT,completion_source=lambda _:observed).status=='failed'
assert store._data==saved
decoded=_native(native['result'],allow_tool_error=True)
assert decoded['errors'][0]=='The backtest ended with a runtime error.'
text=html.unescape(decoded['errors'][1])
position=text.index('diagnostics=')+len('diagnostics=')
diagnostic,_=json.JSONDecoder().raw_decode(text[position:])
assert diagnostic['schema_version']==2 and diagnostic['failure_kind']=='source_hash_mismatch'
assert diagnostic['path']=='engineering_smoke.py'
worker=diagnostic['worker_observation'];worker_format=worker['source_format']
assert worker['coverage_scope']=='first_rejected_declared_source'
assert worker['old_worker_root_cause_proven'] is False and worker['strict_identity_relaxed'] is False
frozen=(original/'cloud/engineering_smoke.py').read_bytes()
assert sha(frozen)==diagnostic['expected_sha256']==payload['deployment_manifest']['engineering_smoke.py']
assert (ROOT/'cloud/engineering_smoke.py').read_bytes()==frozen
fixed_import=b'from AlgorithmImports import *\n'
assert frozen.count(fixed_import)==1
without_import=frozen.replace(fixed_import,b'',1)
candidates=[('identity',frozen),('append_one_LF_only',frozen+b'\n'),('append_two_LF_only',frozen+b'\n\n'),
    ('prepend_fixed_import_without_removing_existing',fixed_import+frozen),
    ('move_existing_fixed_import_to_front',fixed_import+without_import),
    ('move_existing_fixed_import_to_front_and_append_one_LF',fixed_import+without_import+b'\n')]
profiles=[]
for label,raw in candidates:
    tree=ast.parse(raw.decode('utf-8-sig'))
    star_count=sum(isinstance(n,ast.ImportFrom) and n.module=='AlgorithmImports' and any(a.name=='*' for a in n.names) for n in ast.walk(tree))
    profile=dict(label=label,sha256=sha(raw),byte_count=len(raw),lf_count=raw.count(b'\n'),crlf_count=raw.count(b'\r\n'),
        normalized_trailing_lf_count=len(raw)-len(raw.rstrip(b'\n')),algorithm_star_import_count=star_count)
    profile['matches_observed_sha256']=profile['sha256']==diagnostic['observed_sha256']
    profile['matches_reported_format']=all(profile[name]==worker_format[name] for name in (
        'byte_count','lf_count','crlf_count','normalized_trailing_lf_count','algorithm_star_import_count'))
    profiles.append(profile)
matches=[p for p in profiles if p['matches_observed_sha256']]
assert len(matches)==1 and matches[0]['label']=='append_one_LF_only' and matches[0]['matches_reported_format']
for name,digest in protected.items():assert sha((ROOT/name).read_bytes())==digest,name
summary=dict(schema_version=1,kind='developer_readonly_native_terminal_failure_and_finite_byte_check',
    runtime_source_commit='662ccd876b67ca0949f921a53c4c33df37cfbbf1',archive_source_commit='d23c0ab93ceba71529eb813e349c8dfdcbb5ea88',
    attempt_id=ATTEMPT,backtest_id=BACKTEST,native_packet_sha256=sha(native_path.read_bytes()),native_logs_packet_sha256=sha(logs_path.read_bytes()),
    original_admission_and_submission_bound=True,original_completed_Research_resolution_bound=True,
    parsed_platform_status=observed['platform']['status'],parsed_completion=observed,
    memory_settlement_status=settled.status,memory_events_before=46,memory_events_after=47,
    usage_before=before['usage'],usage_after=after['usage'],memory_replay_byte_identical=True,
    native_success_logs_empty=True,actual_seven_success_checks=None,actual_orders=None,LEAN_gate_passed=False,
    worker_diagnostic=diagnostic,finite_byte_candidates=profiles,exact_matching_candidate='append_one_LF_only',
    conclusion='For this first rejected source only, the observed raw SHA256 and reported size/line/import profile exactly match the frozen bytes plus one terminal LF, with the existing single AlgorithmImports star import unchanged.',
    attribution_limitations=['The responsible platform/transport/packaging step was not observed or proved.',
        'No claim about other31 worker files; diagnostic scope is first rejected declared source.',
        'No claim that old39cafa failure had this cause.',
        'Original platform I/O context supplies task identity; native error text has no complete attempt/source authentication and hashes are not a remote signature.'],
    source_modified=False,strict_identity_relaxed=False,true_ledger_writes=0,QC_calls=0,Research_calls=0,LEAN_submissions=0,
    protected_files_unchanged=len(protected),independent_review_approval=False,financial_evidence=False,final_test_enabled=False)
write('delivered_failure_result.json',summary)
print(json.dumps(dict(parsed_platform_status=observed['platform']['status'],memory_settlement=settled.status,
    real_ledger_writes=0,usage_unchanged=True,exact_candidate='append_one_LF_only',expected_sha256=diagnostic['expected_sha256'],
    observed_sha256=diagnostic['observed_sha256'],actual_success_checks=None,actual_orders=None)),flush=True)
