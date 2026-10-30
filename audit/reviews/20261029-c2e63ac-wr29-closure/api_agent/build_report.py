from pathlib import Path
from hashlib import sha256
import json,sys,subprocess,os,platform,time
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent;R=OUT.parent
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8-sig'))
main=read('corrected_results.json');supp=read('supplement_results.json');fault=read('append_recovery_results.json')
assert main['methods']==12 and main['named_scenarios']==63 and not main['failures'] and not main['errors']
assert supp['methods']==6 and supp['named_scenarios']==26 and not supp['failures'] and not supp['errors']
assert fault['methods']==3 and fault['named_scenarios']==28 and not fault['failures'] and not fault['errors']
cmd=[sys.executable,'-B',str(OUT/'audit_auxiliary.py')]
start=time.time()
with (OUT/'auxiliary.stdout').open('wb') as out,(OUT/'auxiliary.stderr').open('wb') as err:
    c=subprocess.run(cmd,cwd=OUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=out,stderr=err)
assert c.returncode==0
(OUT/'auxiliary_execution.json').write_text(json.dumps({'command':cmd,'cwd':str(OUT),'exit_code':c.returncode,'seconds':round(time.time()-start,3),'kind':'repeat_of_35_static_checks_to_capture_portable_stdout_not_new_unit_tests'},indent=2),encoding='utf-8')
aux=read('auxiliary_metadata_verification.json')
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
guard={}
for label,item in maps.items():
    changed=[name for name,v in item['files'].items() if sha256((R/label/name).read_bytes()).hexdigest()!=v['sha256']]
    guard[label]={'files':len(item['files']),'changed':changed}
    assert changed==[]
private=OUT/'replay_context/source'
changed=[name for name,v in maps['source']['files'].items() if sha256((private/name).read_bytes()).hexdigest()!=v['sha256']]
assert changed==[]
guard['private_replay_source']={'files':len(maps['source']['files']),'changed':changed}
(OUT/'source_guard.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
hostdiff={}
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029\source\tools\followup_host.py').read_text(encoding='utf-8')
new=(R/'source/tools/followup_host.py').read_text(encoding='utf-8')
old_start=old.index('@dataclass(frozen=True)');new_start=new.index('@dataclass(frozen=True)')
old_end=old.index('\nif __name__ == "__main__":',old.index('def main('))
new_end=len(new)
# The selected core begins at ReadGrant and ends before the original bottom
# __main__ stub; the new thin entrypoint is earlier than all definitions.
core_old=old[old_start:old_end].rstrip();core_new=new[new_start:].rstrip()
hostdiff={'core_from_ReadGrant_through_main_unchanged':core_old==core_new,'old_core_sha256':sha256(core_old.encode()).hexdigest(),'new_core_sha256':sha256(core_new.encode()).hexdigest()}
assert hostdiff['core_from_ReadGrant_through_main_unchanged']
report={
 'reviewed_source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','materials_commit':'f698a38a99c3ed8388c9403f2eda723b579c5eaf',
 'review_kind':'independent_Python_API_regression_append_fault_recovery_and_auxiliary_failure_audit',
 'environment':{'platform':platform.platform(),'python':sys.version,'executable':sys.executable},
 'actually_executed':True,
 'tests':[
  {'name':'original_independent_API_main','methods':12,'named_scenarios':63,'passed':12,'failures':0,'errors':0,'skips':0,'first_execution_passed':True,'original_script_bytes_unchanged':True},
  {'name':'original_independent_API_supplement','methods':6,'named_scenarios':26,'passed':6,'failures':0,'errors':0,'skips':0,'first_execution_passed':True,'original_script_bytes_unchanged':True},
  {'name':'new_independent_append_faults_and_native_CLI_recovery','methods':3,'named_scenarios':28,'passed':3,'failures':0,'errors':0,'skips':0,'first_execution_passed':False,'corrected_reviewer_OS_error_field_expectation_only':True}
 ],
 'counting':'The18/89 replay methods and3/28 new methods overlap semantically with repository/CLI/native-process checks. No unique grand total;6-process18-request and4CLI subprocesses are contained scenarios, not additional methods.',
 'API_coverage':'Exact controller/authority/enabled gates, original pending1800second boundary, discovery/history/read grants,3pages, response identity, restart/unknown no redispatch, two durable-reservation gap, threads and native6processes. Full independent native-shaped read+AQRP500byte zero-based logs+TotalOrders0 -> original parser/Bridge/Registry/watch chain.',
 'canonical_fix_core_scope':hostdiff,
 'append_recovery':{
  'injected_preappend_refusal':'No response bytes;unknown remains;exact original response recovers/idempotent;one next history;budget unchanged.',
  'injected_post_full_append_ack_loss':'Complete valid response event remains durable;exact original response idempotent;no reexecution.',
  'controller_observed_before_host_ack_refusal':'Controller original observation durable;host pending unknown;original response later repairs host acknowledgement without duplicate controller observation or budget mutation.',
  'actual_native_Windows':fault['observations'],
  'actual_CLI_subprocesses':4,
  'cross_entry_recovery':'Actual documented script refused under held Win32 share;after explicit release same exact original response across canonical/script/-m accepted idempotently. First wake permits one history;remaining wakes stop unknown. One discovery+one history reservation,unchanged synthetic Registry journal.',
  'partial_append_or_power_loss_certified':False
 },
 'developer_auxiliary_metadata':{
  'static_logical_checks':aux['logical_checks'],'not_unit_methods':True,
  'original_recovered_files':20,
  'first_round':aux['first_and_corrected_counts']['initial'],
  'corrected_round':aux['first_and_corrected_counts']['corrected'],
  'first_two_untraced_causes_retroactively_proven':False,
  'captured_developer_trace_proves':'PermissionError errno13 at private host-stream artifacts.append_event path.open(ab), not its native underlying cause.',
  'developer_original_store_recovery_8_program_executed':False,
  'developer_original_response_clone_10_program_executed':False,
  'reason':'The historical generated private stores are explicitly excluded from the selected evidence. Metadata,exact original raw hashes and failure counts were checked;unavailable initial store states are not recreated as claimed originals.',
  'new_equivalent_tests_are_not_the_original_historical_runs':True
 },
 'reviewer_corrections':[{
  'first_script':'append_recovery_first_script.py','first_results':'append_recovery_first_results.json','first_stderr':'append_recovery_first.stderr','first_methods':3,'first_failures':1,'first_errors':0,'first_skips':0,
  'cause':'Reviewer incorrectly expected Path.open(ab) PermissionError.winerror==32. Actual CPython CRT reports errno13/winerrorNone. Direct CreateFileW write-open independently confirms underlying native ERROR_SHARING_VIOLATION32.',
  'correction':'Only independent OS observation expectation was corrected;retained exact filename/errno checks and all product recovery outcomes. No product or original replay assertion edited.',
  'corrected_result':'3methods/28scenarios passed;real child CLI trace and same-response recovery preserved.'
 }],
 'findings':[],
 'software_acceptance':{'Python_API_and_actually_tested_fault_scope':'passed','WR29_canonical_CLI_identity':'not_decided_by_this_API_specialist;entry_agent_actual_ordinary_factory_subprocess_evidence_controls','real_host_transport_or_cloud':'not_verified','phase2_overall':'not_accepted'},
 'unverified':[
  'Two historical untraced first-round exact exceptions and their causes.',
  'Native underlying source of developer traced EACCES (sharing/sync/ACL/other). Our native injected sharing violation is a new controlled equivalent case only.',
  'Exact developer original stores, original8/8 recovery and10/10 clone programs not independently executed because store initial states excluded.',
  'Partial/torn stream writes,power loss,OS kill or all filesystem races. Safe stop on corrupt state is not universal durability certification.',
  'Real production factory/MCP transport/scheduling/native notifications/cloud runs,data certification or financial effectiveness.'
 ],
 'source_guard':guard,'external_calls':{'QC':0,'Research':0,'LEAN':0,'compile':0,'market':0,'model':0},'authoritative_budget_or_production_writes':0,'financial_evidence':False,
 'artifacts':{'replay_commands':'execution_records.json','fault_commands':'fault_execution.json','static_commands':'auxiliary_execution.json','original_replays':'replay_context/host_api_agent','new_fault_program':'independent_append_recovery.py','native_API_trace':'native_api_trace.txt','native_CLI_trace':'native_cli_denied.trace','metadata_checks':'auxiliary_metadata_verification.json','source_guard':'source_guard.json'}
}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'sha256':sha256((OUT/'report.json').read_bytes()).hexdigest(),'methods':'original18/89 + new3/28','findings':0}))
