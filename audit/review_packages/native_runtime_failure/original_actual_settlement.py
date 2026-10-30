from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'.git/repair-work/old-terminal-independent'
FIXED=WORK/'fixed81-final'
sys.path[:0]=[str(FIXED/'cloud'),str(FIXED/'tools')]
import stage2
import research
import qresearch.registry as registry_module
import qresearch.engineering_tasks as bridge_module
from qresearch.artifacts import content_hash

modules={name:module.__file__ for name,module in [('stage2',stage2),('research',research),
    ('Registry',registry_module),('Bridge',bridge_module)]}
assert all(Path(file).resolve().is_relative_to(FIXED.resolve()) for file in modules.values())
stage2.ROOT=ROOT
research.ROOT=ROOT
attempt='bfd00f2611fd4496b9498d4597618a8e'
native_path=ROOT/'audit/tool_observations'/f'{attempt}-terminal-runtime-error.json'
native_raw=native_path.read_bytes()
assert hashlib.sha256(native_raw).hexdigest()=='867148e882d39a024d12d68a01803ba80c282f05b872f16616dfded53c7eea27'
parser_path=ROOT/'cloud/qresearch/engineering_receipts.py'
assert hashlib.sha256(parser_path.read_bytes()).hexdigest()=='11863a4d6995ada9cd32afdb02bb66057ec1c82e9de70c0fd2111b1a844e04b1'
packet=json.loads(native_raw)
observed=json.loads((WORK/'parsed_observation.json').read_bytes())
assert content_hash(observed)=='ff5002cdf15423e9a7f45a0b5b5744d89c675506ef7331df49bdec9b4f5c3233'
assert observed['platform']['raw_receipt']['response_sha256']==content_hash(packet['result'])
assert observed['platform']['raw_receipt']['arguments']==packet['arguments']
assert packet['result']['isError'] is True
assert packet['result']['structuredContent']['errors'][0]=='The backtest ended with a runtime error.'
mirror=json.loads((WORK/'settlement_report_final.json').read_text(encoding='utf-8'))
assert mirror['event_counts']=={'before':12,'after':13,'same_receipt_replay':13}
assert mirror['parser_source_evidence']==hashlib.sha256(parser_path.read_bytes()).hexdigest()
bridge=stage2.bridge_for_attempt(attempt)
admitted=stage2.admitted_input(bridge,attempt)
record=bridge._record(attempt)
assert record['status']=='pending' and record['external_id']==packet['arguments']['backtestId']
assert admitted['deployment']==observed['platform']['deployment']
events=ROOT/'audit/runtime/registry/events.jsonl'
before_bytes=events.read_bytes()
assert len(before_bytes.splitlines())==12
before=bridge.registry.snapshot()
protected=['audit/task_inputs/'+attempt+'.py','audit/runtime/engineering/submissions/'+attempt+'.json',
    'audit/engineering_current.json','config/budget.json','audit/data_exposure.json']
protected_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in protected}
result=bridge.consume_completion(attempt,completion_source=lambda _:observed)
assert result.status=='failed'
after=bridge.registry.snapshot()
after_bytes=events.read_bytes()
assert after_bytes.startswith(before_bytes) and len(after_bytes.splitlines())==13
assert before['usage']==after['usage']==mirror['usage_before']==mirror['usage_after']
record=next(x for x in after['attempts'] if x['attempt_id']==attempt)
assert record['error']['platform_status']=='runtime_error'
assert record['external_id']==packet['arguments']['backtestId']
assert not bridge.store.exists(record['result_key'])
reference=record['error']['evidence_ref']
assert content_hash(json.loads(bridge.store.read_bytes(reference['key'])))==content_hash(observed)
assert protected_hashes=={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in protected}
report={'schema_version':1,'kind':'actual_original_attempt_terminal_reconciliation_no_new_execution',
    'attempt_id':attempt,'backtest_id':record['external_id'],'platform_status':'Runtime Error',
    'registry_status':'failed','failure_stage':'algorithm_initialization',
    'failure_reason':'Cloud implementation differs from the frozen deployment',
    'specific_differing_file_not_proven':True,
    'native_tool_receipt':str(native_path.relative_to(ROOT)).replace('\\','/'),
    'native_tool_receipt_raw_sha256':hashlib.sha256(native_raw).hexdigest(),
    'parsed_observation_sha256':content_hash(observed),'parser_source_raw_sha256':hashlib.sha256(parser_path.read_bytes()).hexdigest(),
    'state_transition_source_commit':'81fbe5294055423e88ee5aeae48ca6223e7971da','state_transition_modules':modules,
    'new_parser_independent_GPT_Work_acceptance':False,
    'event_counts':{'before':12,'after':13,'mirror_same_receipt_replay':13},
    'usage_before':before['usage'],'usage_after':after['usage'],'usage_refunded':False,
    'budget_usage':{'configurations':6,'research':9,'lean':1},
    'new_actual_charges':{'configurations':0,'research':0,'lean':0,'model_API':0},
    'original_input_submission_pointer_budget_and_exposure_unchanged':True,
    'success_result_created':False,'orders_count':None,'progress':None,'completed_flag':None,
    'missing_native_statistics_not_inferred':True,'specific_failure_diagnostic_strings':2,
    'diagnostic_strings_are_not_distinct_failures':True,
    'UI_terminal_observed_before_native_read':True,'completed_result_read_count':1,'backtest_poll_count':0,
    'new_cloud_source_or_input_writes':0,'new_backtest_submissions':0,
    'UI_auto_build_observed_on_project_open':{'build_id':'5a7946-6f121c','lean_version':'2.5.0.0.18207',
        'backtest_submission_or_runtime_success':False},
    'new_candidate_deployed':False,'stage2_accepted':False,'data_certification':False,
    'final_test_enabled':False,'financial_evidence':False}
(ROOT/'audit/stage2_terminal_reconciliation.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'attempt_id':attempt,'platform_status':'Runtime Error','registry_status':'failed',
    'events_before':12,'events_after':13,'usage_unchanged':True,'new_executions':0,
    'state_transition_code':'81fbe52','new_parser_pending_independent_review':True}))
