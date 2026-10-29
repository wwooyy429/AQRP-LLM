from pathlib import Path
from hashlib import sha256
import json,ast,sys
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent;R=D.parent
TARGET='3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470'
raw=(R/'formal_report.json').read_bytes();report=json.loads(raw);own=json.loads((D/'report.json').read_text(encoding='utf-8'))
checks=[];issues=[]
def check(name,value,details=None):
    checks.append({'name':name,'passed':bool(value),'details':details})
    if not value:issues.append({'name':name,'details':details})
check('frozen_report_SHA256',sha256(raw).hexdigest()==TARGET)
check('fixed_source',report['reviewed_source_commit']=='c2e63ac5f19901bd95e127069b5998452f7f9864')
check('failed_baseline',report['baseline_commit']=='2d1d3060dbc7eb136c1dee61f0647977528b8aad')
check('fixed_materials',report['evidence_commits']['materials']=='f698a38a99c3ed8388c9403f2eda723b579c5eaf')
w=report['WR29_resolution']
check('WR29_id_priority',w['id']=='WR-29' and w['original_priority']=='P1')
check('closed_only_fixed_new_SHA',w['status']=='fixed_verified_closed' and w['fixed_source_commit']==report['reviewed_source_commit'])
check('original_failed_source_preserved',w['original_source_commit']==report['baseline_commit'] and w['original_line']==469)
check('original_success_expectations_kept',w['original_expected_exits']==[0,0,0] and w['original_script_and_success_expectations_unchanged'] is True)
check('old_actual_0_2_2',w['original_actual_exits']==own['WR29']['original_actual_exits']==[0,2,2])
check('new_actual_0_0_0',w['fixed_actual_exits']==own['WR29']['fixed_actual_exits']==[0,0,0])
check('old_MRE_assertion_failed',w['original_MRE_assertion_exit']==1)
check('new_MRE_assertion_passed',w['fixed_MRE_assertion_exit']==0)
check('not_granted_bounds',len(w['not_granted'])==4 and any('倒改' in s for s in w['not_granted']) and any('完整阶段2' in s for s in w['not_granted']))
t={item['name']:item for item in report['tests']}
for name,methods,scenes in [('original_independent_stdio',15,61),('original_independent_stdio_supplement',4,12),('new_independent_entrypoints',8,51)]:
    item=t[name]
    check('methods_'+name,item['methods']==methods)
    check('scenarios_'+name,item['scenarios']==scenes)
    check('all_final_outcomes_'+name,item['passed']==methods and item['failures']==item['errors']==item['skips']==0 and item['actually_executed'] is True)
    check('first_run_'+name,item['first_run']=='passed')
check('no_new_confirmed_product_finding',report['findings']==[])
check('phase2_not_passed',report['software_acceptance']['stage2_overall']=='未通过')
check('real_host_not_accepted',report['software_acceptance']['real_factory_transport_scheduler']=='未验收')
check('local_scope_finite','有限' in report['software_acceptance']['local_CLI_stdio_API'])
check('financial_false',report['financial_evidence'] is False)
for key in ('formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled'):
    check('gate_'+key,report['software_acceptance'][key] is False)
for key in ('QC_calls','Research_executions','LEAN_submissions','compile_calls','market_or_model_calls','production_automation','authoritative_budget_or_production_writes'):
    check('zero_'+key,report['tool_capabilities'][key]==0)
cases=json.loads((D/'independent_entrypoints_results.json').read_text(encoding='utf-8'))['cases']
check('strict_factory_three_mode_evidence',sum(s.startswith('strict_factory_reject_') for s in cases)==24)
check('fresh_realUTC_three_mode_evidence',sum(s.startswith('fresh_pending_real_UTC_') for s in cases)==3)
check('cross_entrypoint_recovery_evidence','script_to_module_unknown_no_redispatch' in cases and 'late_discovery_canonical_response_resumes_once' in cases)
check('actual_process_race_evidence','script_module_actual_concurrent_processes_single_discovery' in cases)
check('directory_does_not_grant_read','native_directory_terminal_does_not_grant_chat_read' in cases)
check('handoff_not_Registry_settlement','native_raw_not_stored_and_no_Registry_settlement' in cases)
check('entry_sources_match_root',report['version_consistency']['source_raw_files']==own['source_guard']['source']['files'] and report['version_consistency']['materials_raw_files']==own['source_guard']['materials']['files'])
nodes=[n for n in ast.parse((R/'source/tools/followup_host.py').read_text(encoding='utf-8-sig')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
names=[n.name for n in nodes]
check('AST_10_top_level_definitions',len(nodes)==10)
check('AST_3_private_named_helpers',sorted(n for n in names if n.startswith('_'))==['_attempt','_hash','_status'])
check('precise_AST_label_top_level_not_public',report['version_consistency'].get('top_level_function_class_ASTs_unchanged')==10 and '10个顶层函数/类AST' in w['repair'],{'resolved_original_wording':'Final report correctly labels10 top-level definitions, including3 private-named helpers. The original wording issue is preserved in formal_QA.json; it is not a product finding.'})
txt=(R/'formal_report.txt').read_text(encoding='utf-8')
piece=txt.split('完整机器报告：',1)[1].lstrip();obj,end=json.JSONDecoder().raw_decode(piece)
check('TXT_embedded_JSON_semantically_equal',obj==report)
check('TXT_minimum_code_separate','from pathlib import Path' in piece[end:])
check('TXT_finite_closure_and_stage2_open','原CLI/stdio合法factory缺陷范围' in txt and '阶段2整体仍未通过' in txt)
qa={'formal_report_sha256':sha256(raw).hexdigest(),'expected_sha256':TARGET,'static_checks':len(checks),'passed_checks':sum(c['passed'] for c in checks),'checks':checks,'issues':issues,'kind':'readonly_existing_evidence_QA_not_new_unit_tests','report_or_source_writes':0,'test_reruns':0}
(D/'formal_QA_final.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'static_checks':qa['static_checks'],'passed':qa['passed_checks'],'issues':issues},ensure_ascii=False))
