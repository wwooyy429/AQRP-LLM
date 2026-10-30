from pathlib import Path
from hashlib import sha256
import json,sys,platform
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent;R=D.parent
def read(name):return json.loads((D/name).read_text(encoding='utf-8'))
main,supp,new=read('results.json'),read('supplement_results.json'),read('independent_entrypoints_results.json')
assert all(not r['failures'] and not r['errors'] and not r.get('skips',r.get('skipped',[])) for r in (main,supp,new))
records=read('replay_execution.json')
assert [x['actual_exit'] for x in records]==[0,0,0,1]
for name in ('independent_stdio.py','supplement_stdio.py','minimal_cli_factory_repro.py'):
    original=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029\stdio_agent')/name
    assert original.read_bytes()==(D/name).read_bytes()
guard={}
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
for folder,item in maps.items():
    changed=[p for p,v in item['files'].items() if sha256((R/folder/p).read_bytes()).hexdigest()!=v['sha256']]
    assert not changed,changed
    guard[folder]={'files':len(item['files']),'changed':changed}
oldroot=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029')
oldmap=json.loads((oldroot/'source_git_manifest.json').read_text(encoding='utf-8'))['source']['files']
changes=[p for p,v in oldmap.items() if sha256((oldroot/'source'/p).read_bytes()).hexdigest()!=v['sha256']]
assert not changes,changes
guard['old2d_source']={'files':len(oldmap),'changed':changes}
(D/'source_guard.json').write_text(json.dumps(guard,ensure_ascii=False,indent=2),encoding='utf-8')
newraw=json.loads((D/'original_minimum_new.stdout').read_text(encoding='utf-8'))
oldraw=json.loads((D/'original_minimum_old.stdout').read_text(encoding='utf-8'))
assert newraw['control_factory_exit']==0 and [x['actual_exit'] for x in newraw['cases']]==[0,0]
assert oldraw['control_factory_exit']==0 and [x['actual_exit'] for x in oldraw['cases']]==[2,2]
commands={'replays':records,'new_independent':{'command':[sys.executable,'-B',str(D/'independent_entrypoints.py')],'cwd':r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核','actual_exit':0,'stdout':'entry_first.stdout','stderr':'entry_first.stderr','result':'independent_entrypoints_results.json','unittest_seconds':63.667,'actually_executed':True}}
(D/'execution_records.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')
report={
 'reviewed_source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','materials_commit':'f698a38a99c3ed8388c9403f2eda723b579c5eaf',
 'baseline_source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','scope':'WR29 canonical executable entrypoints, preserved original independent stdio boundaries, new private synthetic process/factory/clock/restart permission checks',
 'environment':{'platform':platform.platform(),'python':sys.version,'executable':sys.executable},
 'WR29':{'status':'fixed_verified_within_original_enabled_CLI_stdio_factory_scope','original_expected_exits':[0,0,0],'original_actual_exits':[0,2,2],'original_MRE_assertion_exit':1,'fixed_actual_exits':[0,0,0],'fixed_MRE_assertion_exit':0,'original_success_expectations_unchanged':True,'standard_factory_import':'from followup_host import FollowupHost','does_not_require_factory_importing___main__':True,'canonical_import_main_also_actually_invoked':True,'historical_failure_preserved':True},
 'tests':[
    {'name':'original_independent_stdio_replayed_without_script_changes','methods':15,'named_scenarios':61,'passed_methods':15,'failures':0,'errors':0,'skipped':0,'first_run_passed':True,'actually_executed':True},
    {'name':'original_independent_stdio_supplement_replayed_without_script_changes','methods':4,'named_scenarios':12,'passed_methods':4,'failures':0,'errors':0,'skipped':0,'first_run_passed':True,'actually_executed':True},
    {'name':'new_independent_actual_entrypoint_tests','methods':8,'named_scenarios':51,'passed_methods':8,'failures':0,'errors':0,'skipped':0,'first_run_passed':True,'actually_executed':True}
 ],
 'distinct_method_total':27,'named_scenario_total':124,'actual_subprocess_records':{'original_suite':len(read('subprocess_records.json')),'new_suite':len(read('independent_entrypoints_subprocesses.json'))},
 'counting':'Methods, subscenarios, process invocations, original/candidate MREs and repository coverage overlap; no unique grand total.0/2/2 old MRE is preserved expected historical product failure, not a new candidate failure. New8 and original19 methods total27 different methods, but semantic coverage overlaps.',
 'coverage':[
  'Actual script, -m and canonical-import processes accept ordinary public-module factory and empty stdin with exit0 and host/authority module followup_host.',
  'Default-off plan/serve on all3 forms does not import installed candidate factory, open private Registry/store or grant a request.',
  'All3 entrypoints reject disabled, duck, host subclass, authority subclass, controller subclass, wrong authority/controller and enabled integer factories; exact gates remain.',
  'All3 actual pending plan/serve processes replace factory2099 clock with productionUTC; original watch and Registry bytes remain unchanged, no early request.',
  'Actual script/module/canonical processes exchange original project response across restarts, expose outstanding response unknown, never reissue it; late original response can resume once.',
  'Actual script+module processes started concurrently share host lock; exactly1 project-discovery request, one attention result, UTC reservation inside actual invocation interval; original response resumes once.',
  'Directory Completed does not authorize chat read; metadata register/sync/status never grant dispatch. Granted read only awaits original native receipt parser, without Registry settlement or native raw sentinel storage.',
  'Actual enabled stdin frames cannot inject a future now, read_grants or enabled flag. Original strict JSON/UTF8/binding/idempotency/native-error boundary methods preserved and passed.'
 ],
 'findings':[],'reviewer_corrections_this_round':[],'source_guard':guard,
 'verdict':'WR29 may close only at fixed c2e63ac for original enabled entrypoint defect; actually tested local CLI/stdio boundaries passed. Full real host/phase2/data/financial acceptance not granted.',
 'unverified':['No production factory, actual MCP transport, live scheduler/native notification/cloud execution or financial test.','No complete automatic original native log/order receipt collector or Registry settlement by this bridge; original stage2 parser remains required.','No all-OS/power-loss/hostile filesystem race certification.','Synthetic permission grants only test trusted-dispatch boundaries and do not authenticate remote observations or authorize live operations.'],
 'external_calls':{'QC':0,'Research':0,'LEAN':0,'compile':0,'market':0,'model':0,'production_automation':0},'real_budget_or_production_writes':0,'financial_evidence':False,
 'artifacts':{'commands':'execution_records.json','original_scripts':['independent_stdio.py','supplement_stdio.py','minimal_cli_factory_repro.py'],'original_raw_replay_outputs':['original_stdio15.stdout','original_stdio15.stderr','original_supplement4.stdout','original_supplement4.stderr','original_minimum_new.stdout','original_minimum_new.stderr','original_minimum_old.stdout','original_minimum_old.stderr'],'new_script':'independent_entrypoints.py','new_stdout':'entry_first.stdout','new_stderr':'entry_first.stderr','new_result':'independent_entrypoints_results.json','new_processes':'independent_entrypoints_subprocesses.json','guard':'source_guard.json'}
}
(D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'methods':27,'scenarios':124,'report_sha256':sha256((D/'report.json').read_bytes()).hexdigest(),'WR29':report['WR29']['status']}))
