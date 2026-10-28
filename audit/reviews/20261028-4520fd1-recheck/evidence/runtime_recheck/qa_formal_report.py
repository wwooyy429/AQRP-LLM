"""Read-only final-report QA; not a new product test."""
from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent;ROOT=R.parent
D=json.loads((ROOT/'formal_report.json').read_bytes());OWN=json.loads((R/'report.json').read_bytes())
H=hashlib.sha256((ROOT/'formal_report.json').read_bytes()).hexdigest()
assert H=='a17ced54d0f5c64289a5d9bcdd2dd65556e445b52b570f3f0a8eaeac108809e3'
CHECKS=[]
def ck(name,value):CHECKS.append({'name':name,'passed':bool(value)});assert value,name
ck('fixed_review_source',D['reviewed_source_commit']==OWN['reviewed_source_commit'])
ck('diagnostic_runtime_version',D['evidence_commits']['diagnostic_runtime']==OWN['archived_evidence']['diagnostic']['runtime_source_commit'])
ck('repaired_runtime_version',D['evidence_commits']['repaired_runtime']==OWN['archived_evidence']['repaired_Research']['runtime_source_commit'])
P=D['platform_evidence_level'];L=P['LEAN'];Q=OWN['archived_evidence']['LEAN']
ck('diagnostic_is_failed_partial_fetch',P['diagnostic']['status']=='failed/runtime_error'and P['diagnostic']['partial_fetch_emitted_rows']==5124 and P['diagnostic']['whole_Research_completed']is False)
ck('Research13_actual_archived_checks',P['Research']['checks_required']==P['Research']['checks_true']==13)
ck('LEAN7_frozen_check_list',L['required_checks']==Q['required_checks']['lean']and len(L['required_checks'])==7)
ck('LEAN_identity',L['attempt_id']==Q['attempt_id']and L['backtest_id']==Q['external_id'])
ck('LEAN_pending_without_runtime_claim',L['frozen_ledger_status']=='pending'and L['terminal_status']is None and L['runtime_success']is None and L['orders']is None and L['actual_runtime_check_results']is None)
ck('zero_current_QC_and_terminal_reads',D['tool_capabilities']['QC_calls_this_round']==D['tool_capabilities']['LEAN_terminal_or_log_reads']==0)
ck('zero_current_dispatch_and_compile',D['tool_capabilities']['Research_executions']==D['tool_capabilities']['LEAN_submissions']==D['tool_capabilities']['compile_calls']==0)
ck('archive_vs_live_evidence',P['archived_native'].startswith('Developer-archived')and 'not reviewer live platform results'in P['archived_native']and 'no new cloud read'in P['source_readback'])
T=next(x for x in D['tests']if x['name']=='native_parser_bridge')
ck('runtime_current_count10_57',T['methods']==10 and T['named_scenarios']==57 and (ROOT/T['evidence']).is_file())
ck('runtime_result_disclosed_corrections','after_disclosed_reviewer_helper_and_scope_corrections'in T['result'])
F=D['first_results_and_corrections']['runtime_first']
ck('first_two_failures_preserved',F['methods']==10 and F['passed_methods']==8 and F['failure_records']==2 and F['error_records']==0 and (ROOT/F['evidence']).is_file())
ck('old_rejection_oracle_not_claimed_passed','NOT claimed to pass'in D['first_results_and_corrections']['runtime_scope'])
ck('native_provenance_limit_explicit','no originating attempt/source identity'in P['authenticity_boundary']and 'not remote provenance'in P['authenticity_boundary'])
A=D['additional_executions'];C=OWN['current_executions']['corrected_independent_suite']['counts']
ck('Research_parser_and_bridge_counts',A['direct_Research_parser_calls']==C['direct_research_parser_calls']==13 and A['Research_bridge_calls']==C['original_research_replays']+C['different_terminal_replacement_attempts']==6)
ck('original_replays_and_replacement_rejections',A['original_Research_replays']==4 and A['original_terminal_replacement_rejections']==2)
ck('LEAN_synthetic_parser_completion_counts',A['synthetic_LEAN_parser_calls']==C['lean_parser_calls']==34 and A['synthetic_LEAN_private_Memory_completion']==C['synthetic_completion_calls']==1 and A['synthetic_LEAN_usage_changed']is False)
ck('archive_static_counts_not_methods',A['native_archive_static_checks']==OWN['current_executions']['static_archived_checks']['checks']==35)
ck('prior13_for_LEAN_correction','Research13, LEAN7'in D['first_results_and_corrections']['prior_report_metadata'])
ck('phase2_not_accepted',D['software_acceptance']['phase2_overall']=='not_accepted'and not D['budget_replay']['real_terminal_settlement_this_round'])
ck('financial_not_claimed',D['financial_evidence']is False and all(v is None for v in D['financial_metrics'].values()))
ck('no_new_product_WR',D['findings']==[]and D['historical_findings']['new_WRs']==[])
ck('all_seven_test_evidence_paths_exist',len(D['tests'])==7 and all((ROOT/x['evidence']).is_file()for x in D['tests']))
OUT={'formal_report_sha256':H,'formal_txt_sha256':hashlib.sha256((ROOT/'formal_report.txt').read_bytes()).hexdigest(),'checks':CHECKS,'all_passed':True,'software_tests_added':0,'QC_calls':0,'product_or_formal_edits':False}
(R/'qa.json').write_text(json.dumps(OUT,indent=2)+'\n',encoding='utf-8')
(R/'qa.txt').write_text('Runtime final report read-only QA passed25/25.\nBound formal_report.json SHA256 '+H+'\nBound formal_report.txt SHA256 '+OUT['formal_txt_sha256']+'\nFixed runtime versions; Research13 vsLEAN7; pending identity/no real terminal; current10/57 corrected count; first10/8/2 retained; direct parser/bridge/static counts and provenance scope all match.\nNo new product tests,QC calls,product edits or report edits.\n\n'+json.dumps(OUT,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checks':len(CHECKS),'all_passed':True,'formal_report_sha256':H}))
