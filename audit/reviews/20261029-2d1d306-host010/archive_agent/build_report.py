from pathlib import Path
from hashlib import sha256
import json, sys, platform
sys.dont_write_bytecode=True
A=Path(__file__).resolve().parent;R=A.parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
static=read(A/'static_results.json');extra=read(A/'extra_results.json');replays=read(A/'replay_execution.json')
maps=read(R/'source_git_manifest.json');guard={}
for folder,item in maps.items():
    changed=[name for name,old in item['files'].items() if sha256((R/folder/name).read_bytes()).hexdigest()!=old['sha256']]
    guard[folder]={'files':len(item['files']),'changed':changed}
original=maps['source']['files'];replay_source=A/'replay_context/source'
guard['private_replay_source']={'files':len(original),'changed':[name for name,old in original.items() if sha256((replay_source/name).read_bytes()).hexdigest()!=old['sha256']]}
assert all(not v['changed'] for v in guard.values())
(A/'source_guard.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
tests=[]
for run in replays:
    item=run['output_result'];tests.append({'name':run['name'],'methods':item['methods'],'named_scenarios':item['named_scenarios'],'failures':item['failures'],'errors':item['errors'],'skipped':item.get('skipped',item.get('skips')),'exit_code':run['exit_code'],'first_execution_passed':run['exit_code']==0,'actually_executed':True,'original_script_changed':False,'original_script_sha256':run['script_original_sha256'],'actual_executed_source_commit':maps['source']['commit'],'embedded_historical_SHA_not_current_source_identity':True})
assert all(x['exit_code']==0 and x['failures']==0 and x['errors']==0 and x['skipped']==0 for x in tests)
report={
 'review_kind':'independent_host010_archive_budget_version_and_prior_finite_regressions',
 'source_commit':maps['source']['commit'],'materials_commit':maps['materials']['commit'],
 'environment':{'platform':platform.platform(),'python':sys.version,'executable':sys.executable},
 'findings':[],
 'tests':tests,'counting':'Original prior reviewer suites rerun on current fixed source, not new independent methods; method/scenario/process/static counts overlap and no unique grand total. Embedded old SHA in unchanged historical output is historical label, not current source identity.',
 'static_logical_checks':static['static_logical_checks']+extra['logical_checks'],'static_main':static['static_logical_checks'],'static_additional':extra['logical_checks'],'static_checks_are_not_unit_methods':True,
 'old_complete_ZIP':static['old_ZIP'],'selected_archive':static['selected_archive'],
 'developer_record_original_recoveries':extra['developer_records'],'current_packet_raw_files':extra['packet_files'],
 'preserved_first_failures_and_corrections':{'original_notification_first_fixture_error':True,'original_carrier_44_then14_then0_fixture_compatibility':True,'original_formal_QA_wording_and_all_QA':True,'WR01_WR28_matrix_raw_preserved':True,'new_developer_UTF8_direct_API_status_initial_failures':True,'provisional14_generated_store_import_failure':True},
 'current_identity':static['identity'],'developer_guard':static['development_guard'],'source_guard':guard,
 'budget':static['budget'],'provisional_import':static['provisional_import'],
 'scope':{'prior975_acceptance':'retained_only_in_original_exact_SHA_and_tested_scope','prior_43_replayed_methods_on_new_source':'passed','new_host_local_software':'not_determined_by_this_archive_subtask','new_live_host_or_cloud':'unverified','stage2_overall':'not_accepted','stages3_to7':'not_accepted','data_certification':'insufficient_evidence','financial_evidence':False},
 'platform_evidence_level':'No QC access. Prior native engineering statements are archived historical b1a metadata, not new candidate execution. Current cloud/config raw bytes equal975 and old43-worker EOF scope is separate from current44 deployment files.',
 'reviewer_corrections':[{'scope':'audit helper only','initial_script':'audit_archive_first.py','initial_exit':1,'initial_stdout':'static_first.stdout','initial_stderr':'static_first.stderr','reason':'Reviewer omitted UTF8 when reading readable Chinese JSON under Windows defaultGBK, causing UnicodeDecodeError after ZIP/205 raw checks; fixed only audit helper encoding.','corrected_script':'audit_archive.py','corrected_exit':0,'corrected_stdout':'static_second.stdout','corrected_stderr':'static_second.stderr','product_or_expected_hash_changed':False}],
 'unverified':static['limitations']+['No new live provider/platform results or financial test; current host adapter behavior is reviewed separately by parent sibling agents.','Original human authorization dialogue for existing budget changes not independently obtained; consistent ledger replay does not grant execution.','No complete old WR01-28 independent suite rerun or new whole-system acceptance; only named suites above plus root full repository run.'],
 'external_calls':{'QC':0,'Research':0,'LEAN':0,'compile':0,'market':0,'model':0},'authoritative_budget_or_production_writes':0,
 'artifacts':{'static_main':'static_results.json','static_extra':'extra_results.json','git_commands':'git_execution.json','replay_commands_and_outputs':'replay_execution.json; *_result.json; *.stdout; *.stderr','guard':'source_guard.json'},
 'financial_evidence':False}
(A/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
commands=[{'label':'static_first','command':[sys.executable,'-B',str(A/'audit_archive_first.py')],'exit_code':1,'evidence':'static_first.stderr','kind':'preserved_reviewer_encoding_error'},
 {'label':'static_second','command':[sys.executable,'-B',str(A/'audit_archive.py')],'exit_code':0,'evidence':'static_second.stdout;static_second.stderr'},
 {'label':'static_extra','command':[sys.executable,'-B',str(A/'audit_extra.py')],'exit_code':0,'evidence':'extra_first.stdout;extra_first.stderr'}]
(A/'execution_records.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report_sha256':sha256((A/'report.json').read_bytes()).hexdigest(),'static_checks':report['static_logical_checks'],'tests':[{k:x[k] for k in ['name','methods','named_scenarios','exit_code']} for x in tests],'guard':guard},ensure_ascii=False),flush=True)
