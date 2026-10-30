from pathlib import Path
from hashlib import sha256
import json,sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent;R=OUT.parent
EXPECTED='45cf5e358d210d65945bfa56a6f0ab3568f7c28f9978ce5f13577dafa3add81a'
checks=[]
def check(value,label):checks.append({'label':label,'passed':bool(value)})
raw=(R/'formal_report.json').read_bytes();report=json.loads(raw)
check(sha256(raw).hexdigest()==EXPECTED,'final_report_hash_frozen')
check(report['reviewed_source_commit']=='c2e63ac5f19901bd95e127069b5998452f7f9864','exact_source')
check(report['evidence_commits']['materials']=='f698a38a99c3ed8388c9403f2eda723b579c5eaf','exact_materials')
check(report['baseline_commit']=='2d1d3060dbc7eb136c1dee61f0647977528b8aad','old_failed_baseline_retained')
table={t['name']:t for t in report['tests']}
for name,methods,scenarios in [('original_independent_API',12,63),('original_independent_API_supplement',6,26),('new_independent_append_recovery',3,28)]:
    row=table[name]
    check(row['methods']==methods,name+'_methods')
    check(row['scenarios']==scenarios,name+'_scenarios')
    check(row['passed']==methods and row['failures']==row['errors']==row['skips']==0,name+'_outcome')
    check(row['actually_executed'] is True,name+'_actual_execution')
check(table['original_independent_API']['first_run']=='passed','API_original_first_run_passed')
check(table['original_independent_API_supplement']['first_run']=='passed','API_supplement_first_run_passed')
check('reviewer_OS_field' in table['new_independent_append_recovery']['first_run'],'append_first_reviewer_error_disclosed')
native=report['native_append_recovery']
check(native['new_methods']==3 and native['named_scenarios']==28,'fault_counts')
check(native['actual_CLI_processes']==4,'four_actual_child_CLI_processes')
check(native['actual_Win32_share_denial_error']==32,'native_Win32_error32')
check(native['Python_CRT_errno']==13,'Python_CRT_errno13')
check(native['Python_CRT_winerror'] is None,'Python_CRT_winerrorNone')
check(native['does_not_authenticate_original_developer_incident_cause'] is True,'equivalent_case_not_historical_cause_proof')
check(len(native['synthetic_cases'])==3,'three_fault_windows_listed')
check('原response' in native['observed'] and '账本不变' in native['observed'],'same_original_response_and_budget_guard')
reviewer=report['reviewer_corrections']
check('首跑' in reviewer['new_append_probe'] and 'winerrorNone' in reviewer['new_append_probe'],'initial_OS_expectation_correction_preserved')
check(reviewer['product_changed_by_reviewer'] is False,'product_not_changed')
aux=report['developer_auxiliary_history']
check('79/84' in aux['initial'] and '2项晚响应失败无trace' in aux['initial'],'first_developer_round_not_greenwashed')
check('89/90' in aux['corrected'] and 'EACCES' in aux['corrected'],'corrected_developer_round_not_greenwashed')
check('8/8' in aux['recorded_recovery'] and '10/10' in aux['recorded_recovery'],'old_recovery_counts_as_recorded_only')
check(aux['original_store_recovery_and_clone_independently_replayed'] is False,'original8_and10_not_claimed_executed')
check(aux['two_untraced_failures_same_cause_proven'] is False,'first_two_causes_not_invented')
check(aux['all_auxiliary_runs_retroactively_passed'] is False,'historical_failure_not_retroapproved')
check(aux['new_equivalent_fault_tests_are_separate'] is True,'new_equivalent_tests_separate')
check('未归档' in aux['reason'],'missing_initial_stores_disclosed')
scope=report['WR29_resolution']
check(scope['status']=='fixed_verified_closed' and scope['fixed_source_commit']==report['reviewed_source_commit'],'WR29_closure_fixed_to_new_source')
check(scope['original_actual_exits']==[0,2,2] and scope['fixed_actual_exits']==[0,0,0],'old_failure_and_new_MRE_observation_retained')
check(scope['original_script_and_success_expectations_unchanged'] is True,'original_success_expectations_unchanged')
check(any('阶段2' in s for s in scope['not_granted']),'closure_not_phase2')
check(report['software_acceptance']['stage2_overall']=='未通过','stage2_not_accepted')
check(report['software_acceptance']['real_factory_transport_scheduler']=='未验收','no_real_transport_claim')
check(report['software_acceptance']['final_test_enabled'] is False and report['financial_evidence'] is False,'final_and_financial_closed')
check(report['findings']==[],'no_new_confirmed_product_finding')
check(all(report['tool_capabilities'][name]==0 for name in ('QC_calls','Research_executions','LEAN_submissions','compile_calls','market_or_model_calls','authoritative_budget_or_production_writes')),'no_real_external_operations')
text=(R/'formal_report.txt').read_text(encoding='utf-8')
after=text.split('完整机器报告：',1)[1].lstrip()
obj,idx=json.JSONDecoder().raw_decode(after)
check(obj==report,'text_embedded_first_JSON_semantically_equal')
check('from pathlib import Path' in after[idx:],'remaining_MRE_is_separate_from_JSON')
check(sha256((OUT/'report.json').read_bytes()).hexdigest()=='bd7a271b856b54b9874a240f57fb09d8a4a6c8cffcf1d3a58beb775b25763367','own_child_report_unchanged')
issues=[row['label'] for row in checks if not row['passed']]
qa={'formal_report_sha256':sha256(raw).hexdigest(),'expected_hash':EXPECTED,'kind':'readonly_static_QA_not_new_unit_tests','checks':checks,'static_checks':len(checks),'passed':len(checks)-len(issues),'issues':issues,'product_or_formal_writes':0,'test_reruns':0}
(OUT/'formal_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'static_checks':len(checks),'passed':qa['passed'],'issues':issues,'hash':qa['formal_report_sha256']}))
raise SystemExit(bool(issues))
