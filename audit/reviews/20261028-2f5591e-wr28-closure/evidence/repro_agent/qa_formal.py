"""Read-only formal-report QA; not additional product execution."""
from pathlib import Path
from hashlib import sha256
import json
R=Path(__file__).resolve().parents[1];OUT=R/'repro_agent'
raw=(R/'formal_report.json').read_bytes();d=json.loads(raw);mine=json.loads((OUT/'report.json').read_bytes())
expected='b60ea3474d297a7b23b027cb3c6b5885736a9a9d840d4ffe5265e9ce28220934'
checks=[]
def check(name,condition):
 checks.append({'name':name,'passed':bool(condition)});assert condition,name
c=d['independent_CLI'];p=d['platform_evidence_level'];s=d['software_acceptance'];t=d['tool_capabilities']
check('exact_final_report_binding',sha256(raw).hexdigest()==expected)
check('fixed_delivery_2f',d['reviewed_source_commit']=='2f5591e28c0748ac42caeae7bbf3977141d031cb')
check('production4a_kept_distinct',d['production_source_commit']=='4a42c18f0b78bea2068d589bc12f1615712354c6')
check('new_method7_and_named34',c['methods']==7 and c['named_scenarios']==34)
check('methods_match_actual_first_result',mine['actually_executed']['unit_methods']==c['methods']and mine['actually_executed']['named_scenarios']==c['named_scenarios'])
check('checker28_and_Git1',c['checker_processes']==28 and c['Git_blob_processes']==1)
check('correct_process_population_sum',c['candidate_no_git_positive']+c['original_baseline_expected_failure']+c['isolated_candidate_mutations_rejected']+c['self_consistent_altered_manifest_and_source_accepted_as_trust_boundary']==28)
check('two_no_git_positives_one_denied_subprocess',c['candidate_no_git_positive']==2 and c['one_positive_denied_all_subprocess']is True)
check('old_failure_is_preserved',c['original_baseline_expected_failure']==1)
check('24_current_negative_rejections',c['isolated_candidate_mutations_rejected']==24)
check('accepted_forged_corpus_not_mislabeled_as_rejection',c['self_consistent_altered_manifest_and_source_accepted_as_trust_boundary']==1 and 'internal raw-byte consistency'in d['trust_boundary']and'not a remote signature'in d['trust_boundary'])
check('fixture_exact_original_bytes',c['fixture_raw_bytes']==3561 and c['fixture_SHA256']=='33ffa365d6b54d0a823574eaba5831c2f53c6aae7f2dff2c885b1d7ac0c9ca90')
check('fixture_not_worker_observation',p['fixture_is_new_worker_observation']is False)
check('legacy_worker_strict_body_known_answers',c['v1_strict_v2_worker_local_strict_body_rejection_known_answers_passed']is True)
check('five_actual_test_paths_exist',len(d['tests'])==5 and all((R/x['evidence']).is_file()for x in d['tests']))
check('independent_CLI_test_record_not_replaced',next(x for x in d['tests']if x['name']=='independent_no_git_CLI_and_fixture')['evidence']=='repro_agent/first/results.json')
check('first_execution_all_pass_disclosed',d['first_results']['CLI'].startswith('7/34 all passed first run'))
check('WR28_closed_only_raw_audit_delivery',d['WR28_resolution']['status']=='fixed_verified_closed'and d['WR28_resolution']['scope']=='Raw Git protection declarations and reproducible audit delivery only')
check('old_wrong_three_declarations_not_rewritten',d['WR28_resolution']['original_legacy_mismatches_retained']==3 and d['WR28_resolution']['new_records_verified']==122)
check('no_new_findings',d['findings']==[])
check('actual_lean_failed_null_checks_orders',p['old_platform_status']=='Runtime Error'and p['old_ledger_status']=='failed'and p['actual_successful_LEAN_checks']is None and p['actual_orders']is None)
check('v2_not_deployed_or_successful',p['EOF_v2_registered_or_deployed']is False and p['new_cloud_success']is None)
check('overall_phase2_still_not_accepted',s['phase2_overall']=='not_accepted'and s['cloud_initialization_fix_verified']is False)
check('all_real_calls_and_authority_writes_zero',all(t[x]==0 for x in ['QC_calls','Research_executions','LEAN_submissions','platform_compile_calls','live_terminal_or_log_reads','market_provider_calls','model_API_calls','new_configuration_registration','authoritative_budget_or_production_writes']))
check('closed_formal_GPT_orders_final',all(s[x]is False for x in ['formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled']))
check('financial_evidence_false_and_metrics_null',d['financial_evidence']is False and all(v is None for v in d['financial_metrics'].values()))
check('count_overlap_explicit','overlap'in d['counting'].lower())
check('root_minimum_file_exists',(R/'minimal_wr28_fixed.py').is_file())
qa={'kind':'readonly_static_formal_report_QA_not_product_tests','report_sha256':expected,'report_txt_sha256':sha256((R/'formal_report.txt').read_bytes()).hexdigest(),'checks':checks,'checks_passed':len(checks),'product_tests_added':0,'platform_calls_added':0,'source_or_formal_report_modified':False}
(OUT/'qa.json').write_text(json.dumps(qa,indent=2)+'\n',encoding='utf-8')
(OUT/'qa.txt').write_text('CLI/fixture scoped QA passed '+str(len(checks))+'/'+str(len(checks))+'.\nReport SHA256 '+expected+'\nTXT SHA256 '+qa['report_txt_sha256']+'\nNo new product tests, calls, source or formal-report changes.\n\n'+json.dumps(qa,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checks':len(checks),'passed':len(checks),'report_sha256':expected}))
