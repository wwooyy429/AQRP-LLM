"""Read-only report QA. No production functions or new behavior tests."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;F=R.parent/'formal_report.json';T=R.parent/'formal_report.txt'
def j(p):return json.loads(p.read_text(encoding='utf-8'))
f=j(F);own=j(R/'report.json');b=j(R/'boundaries_first/results.json');a=f['actually_executed'];checks=[]
def check(name,value):checks.append({'name':name,'passed':bool(value)})
check('WR23 original MRE ea1 candidate0, bytes unchanged',a['original_WR23_MRE']=={'ea_exit':1,'candidate_exit':0,'original_bytes_unchanged':True} and own['WR23']['unchanged_original_script'] and own['WR23']['unchanged_original_helper'])
check('WR23 5 methods21scenarios, not all assertions mislabeled',a['entry_publication']['methods']==b['methods']==5 and a['entry_publication']['scenarios']==b['subcases']==21 and a['entry_publication']['custom_check_calls']==b['individual_checks']==281)
check('New actual ordinary180 concurrent16 finish27 worker0',a['entry_publication']['ordinary_CLI']==b['ordinary_stats']['actual_CLI_processes']==180 and a['entry_publication']['concurrent_CLI']==b['parallel_CLI_processes']==16 and a['entry_publication']['synthetic_finish']==b['ordinary_stats']['synthetic_metadata_finish_calls']==27 and a['entry_publication']['worker']==0)
check('v1v2 four-process firstprepare and dispatch, one permit',a['entry_publication']['plan_versions']==[1,2] and a['entry_publication']['processes_per_prepare_race']==a['entry_publication']['processes_per_dispatch_race']==4 and a['entry_publication']['only_one_permission_each'])
s=own['historical_regressions'];native_cli=sum(x['stats']['actual_CLI_processes']for x in s[:4]);recovery_cli=s[4]['stats']['actual_CLI_processes'];finish=sum(x['stats']['synthetic_metadata_finish_calls']for x in s[:5])
check('Native117 + recovery76 =193CLI',native_cli==117 and recovery_cli==76 and a['native_recovery_actual_CLI']==193==native_cli+recovery_cli)
check('Direct12 and syntheticfinish18, not worker executions',a['native_recovery_direct_processes']==s[4]['stats']['direct_freeze_processes']==12 and a['native_recovery_synthetic_finish']==finish==18)
check('Research native6/91 and25CLI separately',a['native_Research_failure_CLI']==s[5]['stats']['actual_CLI_processes']==25 and s[5]['methods']==6 and s[5]['subcases']==91 and s[5]['success'])
check('Manual chains8 separate from testmethods',a['legacy_native_manual_chains']==s[2]['subcases']+s[3]['subcases']==8 and s[2]['methods']==s[3]['methods']==0)
expect={'native LEAN':(6,62),'completion compatibility':(3,28),'engineering recovery legal fixture':(5,46),'native Research failure':(6,91),'new WR23 publication and concurrency':(5,21)}
for name,(m,n)in expect.items():
    rows=[x for x in f['tests']if x['suite']==name];check('suite counts '+name,len(rows)==1 and rows[0]['methods']==rows[0]['passed']==m and rows[0]['subcases']==n and rows[0]['failed']==rows[0]['errors']==0)
first=a['first_results_preserved'][0];reason=first['reason'];check('WR21 old fixture failure retained, 12 logged repeat then17CLI legalshape adapter',first['scope']=='WR21 unchanged original fixture'and first['exit_code']==1 and all(v in reason for v in ['inline','12CLI','17CLI','AST']) and own['WR21']['assertion_AST_identical']and own['WR21']['adapted_exit']==0 and own['WR21']['logged_unchanged_repeat_command_count']==12 and own['WR21']['adapted_full_chain_CLI_processes']==17)
check('F5d normal15→17→17 and write18 not charged',f['platform']['normal_failure_replay']==[15,17,17]and f['platform']['write_failure_replay']==[15,16,18,18]and f['platform']['extra_pending_not_new_charge'])
check('WR23 closure only synchronous/actualprocess scope',all(v in f['historical_findings']['WR23']for v in ['原触发','同步发布','进程并发','范围']) and any('OS kill' in v for v in f['unverified']))
check('No cloud/wholePhase2 expansion',f['platform']['candidate_deployed_or_executed']is False and f['software_acceptance']['full_phase2_accepted']is False and f['tool_capabilities']['current_QC_calls']==0 and f['tool_capabilities']['authoritative_registry_writes']==0 and f['financial_evidence']is False)
check('Readable report mirrors machine report',json.dumps(f,ensure_ascii=False,indent=2)in T.read_text(encoding='utf-8'))
report={'qa_scope':'Read-only protocol report QA, no new test execution','formal_report_sha256':hashlib.sha256(F.read_bytes()).hexdigest(),'checks':checks,'passed':all(x['passed']for x in checks),'issues':[]if all(x['passed']for x in checks)else[x['name']for x in checks if not x['passed']],'reviewer_setup_note':'First ad-hoc QA reader omitted encoding=utf-8 and failed GBK decoding; corrected explicit UTF8 reader. No report or product was changed.'}
(R/'qa.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode())
text='协议侧正式报告只读QA：'+('通过'if report['passed']else'存在不一致')+'。\n'+'\n'.join(('PASS 'if x['passed']else'FAIL ')+x['name']for x in checks)+'\n先前QA临时读取未指定UTF8导致GBK解码失败；已纠正读取，不属于产品问题。\n'
(R/'qa.txt').write_bytes(text.encode());print(json.dumps({'passed':report['passed'],'checks':len(checks),'issues':report['issues']}))
