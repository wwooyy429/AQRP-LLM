from pathlib import Path
from hashlib import sha256
import json
R=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
raw=(R/'formal_report.json').read_bytes();formal=json.loads(raw);own=read(A/'report.json')
checks=[]
def check(name,condition):checks.append({'name':name,'passed':bool(condition)})
expected='3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470'
check('frozen_JSON_hash',sha256(raw).hexdigest()==expected)
check('fixed_source',formal['reviewed_source_commit']==own['source_commit'])
check('baseline_failed2d',formal['baseline_commit']=='2d1d3060dbc7eb136c1dee61f0647977528b8aad')
check('fixed_materials','f698a38a99c3ed8388c9403f2eda723b579c5eaf' in json.dumps(formal['evidence_commits']))
ar=formal['archive_verification']
check('45370_static',ar['static_file_blob_metadata_checks']==own['static_logical_checks']==45370)
check('four_additional_raw_proofs',ar['additional_representation_checks']==4)
check('static_not_unit',ar['static_checks_are_not_unit_methods'] is True)
check('complete_old_ZIP',ar['old_complete_ZIP']==own['old_complete_ZIP'])
check('selected161_counts',ar['selected_archive']==own['selected_archive'])
check('selected_not_full',ar['selected_archive_is_complete_original_bundle'] is False)
check('guard348_5CRLF',ar['developer_guard']==own['developer_guard'])
check('original_report_sha',ar['original_formal_sha256']=='224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14')
check('old_failure_scripts_preserved',ar['old_failure_and_first_scripts_outputs_preserved'] is True)
budget=formal['budget_replay']; ob=own['budget']
check('journal71',budget['events']==ob['events']==71)
check('journal_rawhash',budget['journal_sha256']==ob['journal_sha256'])
check('prior69_hash',budget['prior69_prefix_sha256']==ob['prior69_prefix_sha256'])
check('prior_prefix_preserved',budget['prior69_prefix_raw_preserved'] is True)
check('cycle3of13',budget['configuration_cycle']=={'used':3,'limit':13})
check('lifetime16',budget['lifetime_configurations']==16)
check('Research17of20',budget['Research']=={'used':17,'limit':20})
check('LEAN3of16',budget['LEAN']=={'used':3,'limit':16})
check('008closed',budget['round008']=='closed')
for k in ('new_events','new_debits','refunds'):check('budget_zero_'+k,budget[k]==0)
check('no_original_human_auth',budget['original_human_authorization_dialogue_independently_obtained'] is False)
ver=formal['version_consistency']
for key,n in [('source_raw_files',7448),('materials_raw_files',7766),('managed_identity_files',218),('baseline_managed_files',216),('deployment_files',44)]:check(key,ver[key]==n)
check('cloud_deployment_unchanged',ver['deployment_raw_unchanged_from2d'] is True)
check('source_materials_equal',ver['source_materials_managed_equal'] is True)
check('fixed_trees_untouched',ver['immutable_source_materials_changed'] is False)
check('only_generated_report_changed',ver['scratch_changes']==['audit/stage_verification.json'])
check('added_identity_two',ver['added_managed']==['docs/review/wr29.md','tests/test_followup_host_entrypoints.py'])
check('changed_identity_two',ver['changed_managed']==['docs/followup_host.md','tools/followup_host.py'])
tests={r['name']:r for r in formal['tests']}
for name,methods,scenarios in [('prior_Windows_lock',18,37),('prior_notification_main',12,79),('prior_notification_supplement',6,27),('prior_cycles_rounds',7,28)]:
    row=tests[name];check('historical_'+name,row['methods']==row['passed']==methods and row['scenarios']==scenarios and row['failures']==row['errors']==row['skips']==0 and row['first_run']=='passed' and row['actually_executed'] is True)
aux=formal['developer_auxiliary_history']
check('first79of84_preserved','79/84' in aux['initial'] and '2' in aux['initial'])
check('second89of90_preserved','89/90' in aux['corrected'] and 'EACCES' in aux['corrected'])
check('recovery8_clones10_preserved','8/8' in aux['recorded_recovery'] and '10/10' in aux['recorded_recovery'])
check('original_stores_not_independently_rerun',aux['original_store_recovery_and_clone_independently_replayed'] is False)
check('untraced_not_same_cause',aux['two_untraced_failures_same_cause_proven'] is False)
check('not_retroactive_all_green',aux['all_auxiliary_runs_retroactively_passed'] is False)
check('new_fault_tests_separate',aux['new_equivalent_fault_tests_are_separate'] is True)
resolution=formal['WR29_resolution']
check('WR29_fixed_source',resolution['fixed_source_commit']==own['source_commit'])
check('WR29_closed_only_new',resolution['status']=='fixed_verified_closed' and resolution['original_source_commit']=='2d1d3060dbc7eb136c1dee61f0647977528b8aad')
check('old_new_expected_outcomes',resolution['original_expected_exits']==[0,0,0] and resolution['original_actual_exits']==[0,2,2] and resolution['fixed_actual_exits']==[0,0,0])
check('old_failure_assertion_retained',resolution['original_MRE_assertion_exit']==1 and resolution['fixed_MRE_assertion_exit']==0 and resolution['original_script_and_success_expectations_unchanged'] is True)
check('no_retroactive_old_pass','2d1d306' in resolution['not_granted'][0])
check('WR29_history_same_object',formal['historical_findings']['WR29_new_resolution']==resolution)
check('prior_scope_retained','975' in json.dumps(formal['historical_findings']))
accept=formal['software_acceptance']
check('stage2_not_accepted',accept['stage2_overall']=='未通过')
check('real_host_not_accepted',accept['real_factory_transport_scheduler']=='未验收')
for k in ('formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled'):check('closed_'+k,accept[k] is False)
check('financial_false',formal['financial_evidence'] is False and all(v is None for v in formal['financial_metrics'].values()))
check('no_QC_or_budget_write',all(formal['tool_capabilities'][k]==0 for k in ('QC_calls','Research_executions','LEAN_submissions','compile_calls','market_or_model_calls','production_automation','authoritative_budget_or_production_writes','PR_push_approval_merge')))
check('old_b1a_no_inheritance','不继承' in formal['platform_evidence_level']['historical_b1a'])
check('new_cloud_null',formal['platform_evidence_level']['new_source_cloud_run'] is None and formal['platform_evidence_level']['new_source_orders'] is None)
text=(R/'formal_report.txt').read_text(encoding='utf-8')
embedded,end=json.JSONDecoder().raw_decode(text[text.index('{'):])
check('TXT_first_JSON_matches',embedded==formal)
check('TXT_after_JSON_MRE_separate',bool(text[text.index('{')+end:].strip()))
check('no_new_confirmed_findings',formal['findings']==[])
result={'scope':'read-only formal report QA, not additional unit tests','report_sha256':sha256(raw).hexdigest(),'text_sha256':sha256((R/'formal_report.txt').read_bytes()).hexdigest(),'checks':checks,'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'issues':[c['name'] for c in checks if not c['passed']],'source_or_report_writes':0,'test_reruns':0}
(A/'formal_QA_final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=True))
assert not result['issues'],result['issues']
