from pathlib import Path
from hashlib import sha256
import json,sys
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent;R=D.parent
raw=(R/'formal_report.json').read_bytes();report=json.loads(raw)
expected='224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14'
checks=[]
def check(name,value): checks.append({'name':name,'passed':bool(value)})
check('frozen_formal_sha256',sha256(raw).hexdigest()==expected)
check('fixed_reviewed_source',report['reviewed_source_commit']=='2d1d3060dbc7eb136c1dee61f0647977528b8aad')
f=[x for x in report['findings'] if x['id']=='WR-29'][0]
for key,value in {'priority':'P1','file':'tools/followup_host.py','line':469,'minimum_expected_exit':0,'minimum_script_assertion_exit':1}.items():check('finding_'+key,f[key]==value)
check('finding_related_lines',f['related_lines']==[468,469,470])
check('both_CLI_launches_actual2',f['minimum_actual_cli_exits']=={'script':2,'module':2})
check('ordinary_import_factory_trigger','normally imports FollowupHost from followup_host' in f['trigger'])
check('zero_attempt_empty_stdin_trigger','Empty stdin is sufficient' in f['trigger'])
check('module_identity_root_cause','__main__.FollowupHost' in f['actual'] and 'followup_host.FollowupHost' in f['actual'])
check('canonical_import_control_scope','Imported product.main' in f['independent_control'] and 'real CLI remains rejected' in f['independent_control'])
check('impact_not_permission_bypass','not a permission bypass' in f['impact'])
check('minimum_fix_retains_gates','strict enabled/controller/authority' in f['minimal_fix'] and 'default-off' in f['minimal_fix'])
check('regressions_actual_subprocess',any('Actual subprocess' in x for x in f['required_regressions']))
check('regressions_bad_factory',any('Malformed/incompatible/disabled' in x for x in f['required_regressions']))
t=[x for x in report['tests'] if x['name']=='independent_stdio_CLI'][0]
for key,value in {'methods':19,'passed':17,'failures':2,'errors':0,'skips':0,'successfully_completed_scenarios':69,'actually_executed':True}.items():check('stdio_'+key,t[key]==value)
check('no_new_total_count_claim','重叠' in report['counting'] or 'overlap' in report['counting'])
own=json.loads((D/'report.json').read_text(encoding='utf-8'))
check('own_method_counts_match',own['distinct_method_total']==t['methods'] and own['passed_methods']==t['passed'] and own['failed_methods']==t['failures'])
check('own_successful_scenarios_match',own['completed_successful_named_scenarios']==t['successfully_completed_scenarios'])
c=report['reviewer_corrections']['stdio']
check('first_run_failures_retained','2失败/1错误' in c)
check('size_fixture_correction_disclosed','400000' in c and '700000' in c and '1.2MB' in c)
check('JSON_followon_error_disclosed','JSON' in c and '退出码' in c)
check('valid_factory_expected_unchanged','合法factory期望' in c and '仍2产品失败' in c)
s=report['software_acceptance']
check('CLI_failed',s['new_host_enabled_CLI_stdio']=='失败_WR29')
check('host_overall_not_accepted',s['new_host_component_overall']=='不通过')
check('API_finite_pass',s['new_host_Python_API']=='已测合成范围通过')
check('phase2_not_accepted',s['stage2_overall']=='未通过')
check('real_host_not_accepted',s['real_host_engineering_chain']=='未验收')
check('all_four_gates_closed',all(s[key] is False for key in ('formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled')))
check('unreached_CLI_steps_not_certified',any('WR29阻断' in x and '时钟' in x for x in report['unverified']))
check('financial_evidence_false',report['financial_evidence'] is False)
text=(R/'formal_report.txt').read_text(encoding='utf-8')
anchor=text.index('"review_id"');start=text.rfind('{',0,anchor)
embedded,end=json.JSONDecoder().raw_decode(text[start:])
check('text_embedded_JSON_semantically_equal',embedded==report)
check('remaining_text_contains_minimum',bool(text[start+end:].strip()))
check('product_defect_still_in_text','WR-29' in text and '469' in text)
result={'report_sha256':sha256(raw).hexdigest(),'text_sha256':sha256((R/'formal_report.txt').read_bytes()).hexdigest(),'logical_static_checks':len(checks),'passed':sum(x['passed'] for x in checks),'checks':checks,'issues':[x['name'] for x in checks if not x['passed']],'unit_tests_rerun':0,'formal_or_product_writes':0}
(D/'formal_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('report_sha256','logical_static_checks','passed','issues')}))
sys.exit(bool(result['issues']))
