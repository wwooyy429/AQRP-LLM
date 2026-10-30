"""Read-only QA of assembled report; no new behavior tests."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;F=R.parent/'formal_report.json';T=R.parent/'formal_report.txt'
def j(p):return json.loads(p.read_text(encoding='utf-8'))
f=j(F);p=j(R/'report.json');a=f['actually_executed'];b=p['publication_concurrency'];checks=[]
def check(name,value):checks.append({'name':name,'passed':bool(value)})
check('fixed44676db actual source bound',f['reviewed_source_commit']==p['fixed_commit']=='44676db609b3b7c2175fa7fa4f19c8ccf8165458')
e=a['entry_publication'];check('5methods21scenarios281custom',e['methods']==b['methods']==5 and e['scenarios']==b['subcases']==21 and e['custom_check_calls']==b['custom_check_calls']==281)
check('180ordinary16concurrent27finish0worker',e['ordinary_CLI']==b['stats']['actual_CLI_processes']==180 and e['concurrent_CLI']==b['parallel_CLI_processes']==16 and e['synthetic_finish']==b['stats']['synthetic_metadata_finish_calls']==27 and e['worker']==b['stats']['actual_worker_executions']==0)
check('v1v2 four process prepare and dispatch uniquepermit',e['plan_versions']==[1,2]and e['processes_per_prepare_race']==e['processes_per_dispatch_race']==4 and e['only_one_permission_each'])
n=p['native_and_recovery_totals'];check('native193CLI12direct18finish',a['native_recovery_actual_CLI']==n['ordinary_CLI']==193 and a['native_recovery_direct_processes']==n['direct_freeze_processes']==12 and a['native_recovery_synthetic_finish']==n['synthetic_finish']==18)
check('manual8 separate',a['legacy_native_manual_chains']==n['manual_chains']==8)
check('f5d25CLI separately',a['native_Research_failure_CLI']==n['native_Research_failure_CLI_separate']==25)
m=p['original_WR23'];m2=a['original_WR23_candidate'];check('originalWR23 exit0 5CLI1finish originalbytes',m2['exit']==m['outer_exit']==0 and m2['CLI']==m['stats']['actual_CLI_processes']==5 and m2['synthetic_finish']==m['stats']['synthetic_metadata_finish_calls']==1 and m['test_raw_equal_previous']and m['helper_raw_equal_previous'])
w=p['WR21'];w2=a['WR21_recognized_legacy_fixture'];check('recognizedWR21 exit0 17CLI assertions intact',w2['exit']==w['outer_exit']==0 and w2['CLI']==w['command_count']==17 and w2['assertions_unchanged']and w['assertions_AST_equal_previous_original']and w['test_raw_equal_previous_accepted_adapter'])
check('WR21 bound legacy positives and new no-dispatch negative preserved',w['bound_positive']==w['legacy_positive']=='completed' and w['new_no_dispatch_rejected'])
expected={'WR23 publication and concurrency':(5,21),'native LEAN':(6,62),'completion compatibility':(3,28),'engineering recovery legal fixture':(5,46),'native Research failure':(6,91)}
for name,(m,c)in expected.items():
 rows=[x for x in f['tests']if x['suite']==name];check('suite '+name,len(rows)==1 and rows[0]['methods']==rows[0]['passed']==m and rows[0]['subcases']==c and rows[0]['failed']==rows[0]['errors']==0)
check('no new findings and limited offline pass',f['findings']==[]and f['software_acceptance']['overall_status']=='本轮已测离线软件范围通过'and f['software_acceptance']['full_phase2_accepted']is False)
check('no OS-kill cloud wholephase financial expansion',any('OS kill' in s for s in f['unverified'])and f['platform']['candidate_deployed_or_executed']is False and f['financial_evidence']is False and f['tool_capabilities']['current_QC_calls']==f['tool_capabilities']['authoritative_registry_writes']==0)
reason=next(x['reason']for x in a['first_results_preserved']if x['scope']=='recognized prior fixture adapters')
check('old literal tags distinguished from actual new execution identity',('literal'in reason or '标签'in reason)and ('argv'in reason or '外层'in reason))
check('new binding and source script records referenced',all(x in a['records']for x in ['protocol_agent/outer_execution_records.json','protocol_agent/script_bindings.json']))
check('readable report contains exact machine report',json.dumps(f,ensure_ascii=False,indent=2)in T.read_text(encoding='utf-8'))
report={'qa_scope':'Read-only protocol report QA, no behavior test execution','formal_report_sha256':hashlib.sha256(F.read_bytes()).hexdigest(),'checks':checks,'passed':all(x['passed']for x in checks),'issues':[x['name']for x in checks if not x['passed']]}
(R/'qa.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode());(R/'qa.txt').write_bytes(('协议侧正式报告只读QA：'+('通过'if report['passed']else'数值/范围已通过，尚有说明项待补')+'。\n正式报告SHA256：'+report['formal_report_sha256']+'\n'+'\n'.join(('PASS 'if x['passed']else'NOTE ')+x['name']for x in checks)+'\n无新行为测试、未改正式稿。\n').encode());print(json.dumps({'passed':report['passed'],'checks':len(checks),'issues':report['issues']}))
