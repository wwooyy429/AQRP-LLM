from pathlib import Path
import json,sys,hashlib
O=Path(__file__).resolve().parent;R=O.parent
raw=(R/'formal_report.json').read_bytes();doc=json.loads(raw);text_raw=(R/'formal_report.txt').read_bytes();text=text_raw.decode('utf-8-sig')
expected=sys.argv[1] if len(sys.argv)>1 else 'aad0c66f970efe90f53e1877028ab4dbda07778651de66868f4774266b9e82ad'
checks=[]
def check(name,condition,details=None):checks.append({'name':name,'passed':bool(condition),'details':details})
check('expected_formal_report_hash',hashlib.sha256(raw).hexdigest()==expected)
check('embedded_text_JSON_semantically_identical',json.loads(text.split('完整机器报告：',1)[1])==doc)
check('fixed_source_975',doc['reviewed_source_commit']=='975f676d62b561689909744f9e7236290e3f5fcb')
check('fixed_materials_a6',doc['evidence_commits']['materials']=='a6a5a165d87c172535cdea6cf495e3c1a850e6e4')
tests={r['name']:r for r in doc['tests']}
for name,m,c in [('historical_numeric_time',16,84),('historical_Pearson',10,896),('historical_IC_summary',11,716),('historical_certification',13,43),('historical_carriers',15,80),('WR25_WR26_MRE',None,7),('historical_WR28_audit',11,None)]:
    t=tests[name];check(name+'_counts_and_outcomes',t['methods']==m and t['scenarios']==c and t['actually_executed'] is True and t['failures']==t['errors']==t['skips']==0)
check('counting_overlap_not_unique_grand_total','不合计独有' in doc['counting'])
h=doc['historical_findings']
check('28_original_WRs_25_reports',h['WR_count']==28 and h['original_reports_checked']==25)
check('not_all_old_independent_suites_reexecuted',h['all_original_independent_suites_rerun'] is False)
check('WR_matrix_references_actual_file',(R/h['per_WR_original_SHA_scope_current_tests_and_limits']).is_file())
check('all28_WR_scope_lines_in_text',all(('WR-'+str(i).zfill(2)+'：') in text for i in range(1,29)))
check('WR28_original_frozen_only','122' in h['WR28_replay_scope'] and '48-event' in h['WR28_replay_scope'] and 'does not assert current changed' in h['WR28_replay_scope'])
check('1582_static_not_method_claim',h['static_metadata_checks']==1582)
check('selected_archive_not_complete_external_ZIP',h['selected_archive_is_complete_original_bundle'] is False and any('未全量' in u and 'ZIP' in u for u in doc['unverified']))
c=doc['reviewer_corrections']['carrier_first_run']
check('carrier_first44_second14_retained',c['errors']==44 and c['second_errors']==14 and doc['reviewer_corrections']['all_first_scripts_logs_and_diffs_preserved'] is True)
check('carrier_fixture_change_count_precise','一处' in c['adaptation'] and '两处' in c['adaptation'] and '三处completion' not in c['adaptation'], 'Actual final diff has1 baseline-reference replacement and2 payload-manifest additions;3 changed sites total.')
check('summary_helper_correction_disclosed','重复全树哈希' in doc['reviewer_corrections']['history_summary_helper'] and 'IC结果文件名' in doc['reviewer_corrections']['history_summary_helper'])
b=doc['budget_replay']
check('journal_71_and_raw_SHA',b['events']==71 and b['journal_sha256']=='cea800e0fe5a0facc5f2aed238d105a6f3d1c80db40c1dc4b674efd3026cd48a')
check('prior69_prefix_exact',b['prior_prefix_raw_preserved'] is True and b['prior69_prefix_sha256']=='2d3131a32864434d22635f058ec3de8062e9b1b610a90185bf6ba6cf9c637934')
check('cycle3_13_lifetime16',b['configuration_cycle']=={'used':3,'limit':13} and b['lifetime_configurations']==16)
check('Research17_20_LEAN3_16_round008closed',b['Research']=={'used':17,'limit':20} and b['LEAN']=={'used':3,'limit':16} and b['round008']=='closed')
check('no_budget_writes_or_refunds',b['new_events']==b['new_debits']==b['refunds']==0)
check('original_human_authorization_not_independently_obtained',b['original_human_authorization_dialogue_independently_obtained'] is False)
p=doc['platform_evidence_level'];v=doc['version_consistency']
check('old_platform_archive_not_live','归档' in p['grade'] and '离线' in p['grade'] and '未独立访问QC' in p['grade'])
check('historical_b1a_not_new975',p['historical_runtime_commit']=='b1a4041ce98867047294b8f0830292af5d7ec56e' and p['historical_runtime_commit']!=doc['reviewed_source_commit'])
check('old_native13_7_zeroorders',p['Research_checks_passed']==13 and p['LEAN_checks_passed']==7 and p['historical_orders']==0)
check('old_PROJECT43_Research0_LEAN43_false_raw_identity',p['PROJECT_raw_source_files']==43 and p['Research_worker_EOF_normalized_files']==0 and p['LEAN_worker_EOF_normalized_files']==43 and p['LEAN_original_source_identity_match'] is False)
check('old43_current44_distinct',v['historical_cloud_files']==43 and v['current_deployment_files']==44)
check('no_push_observed_no_newrun',p['automatic_push_observed'] is False and p['new_candidate_cloud_run'] is None and p['new_candidate_orders'] is None)
a=doc['software_acceptance']
check('phase2_overall_not_accepted',a['stage2_overall']=='未通过' and '整体未通过' in doc['conclusion'])
check('all_execution_gates_closed',all(a[k] is False for k in ('formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled')))
check('no_financial_evidence_or_metrics',doc['financial_evidence'] is False and all(x is None for x in doc['financial_metrics'].values()))
issues=[{'name':x['name'],'details':x['details']} for x in checks if not x['passed']]
result={'kind':'read_only_history_specialist_formal_report_QA','formal_report_sha256':hashlib.sha256(raw).hexdigest(),'formal_text_sha256':hashlib.sha256(text_raw).hexdigest(),'expected_formal_report_sha256':expected,'static_checks':len(checks),'passed_checks':len(checks)-len(issues),'issues':issues,'checks':checks,'product_tests_rerun':False,'formal_report_or_product_modified':False}
(O/'formal_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
