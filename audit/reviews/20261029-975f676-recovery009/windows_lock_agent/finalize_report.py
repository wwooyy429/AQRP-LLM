from pathlib import Path
import json, hashlib, sys, platform, datetime
R=Path(__file__).resolve().parents[1]
O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
first=json.loads((O/'first_results.json').read_bytes())
manifest=json.loads((R/'source_git_manifest.json').read_bytes())['source']
changes=[]
for name,item in manifest['files'].items():
    path=R/'source'/name
    if not path.is_file() or sha(path)!=item['sha256']: changes.append(name)
assert not changes,changes
assert first['methods']==18 and first['named_scenarios']==37
assert first['failures']==first['errors']==first['skipped']==0
record={
 'argv':[r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe','-B',str(O/'independent_windows_lock.py')],
 'shell_redirection':{'stdout':str(O/'first.stdout'),'stderr':str(O/'first.stderr')},
 'exit_code':int((O/'first.exit').read_text().strip()),
 'unittest_elapsed_seconds':6.303,
 'tool_wall_seconds':9.3045997,
 'started_at':None,'finished_at':None,
 'record_note':'Exact timestamps were not instrumented; duration is from retained unittest output and tool return.',
 'sha256':{name:sha(O/name) for name in ['independent_windows_lock.py','first.stdout','first.stderr','first.exit','first_results.json']}
}
(O/'execution_records.json').write_text(json.dumps([record],ensure_ascii=False,indent=2),encoding='utf-8')
report={
 'review_id':'AQRP-20261029-975F676-NATIVE-WINDOWS-LOCK',
 'source_commit':manifest['commit'],
 'materials_commit':'a6a5a165d87c172535cdea6cf495e3c1a850e6e4',
 'status':'passed_for_independently_executed_native_lock_and_shared_admission_scope',
 'environment':{'os':platform.platform(),'python':sys.version,'executable':sys.executable},
 'evidence_grade':['static_source_review','reviewer_actual_native_Win32_synthetic_tests','reviewer_actual_Windows_spawn_process_synthetic_tests'],
 'methods':18,'methods_passed':18,'named_scenarios':37,'failures':0,'errors':0,'skipped':0,
 'actually_executed':True,'first_execution_passed':True,'reviewer_corrections':[],
 'findings':[],
 'native_Win32':{
  'methods':3,'actually_executed':True,
  'OS_mechanism':'CreateFileW opens existing synthetic lock with GENERIC_READ and FILE_SHARE_READ|FILE_SHARE_WRITE, excluding FILE_SHARE_DELETE; normal Path.unlink observes native WinError32.',
  'positive':'Delayed real CloseHandle permits library release; body entered once and immutable publication retained.',
  'exhaustion':'Actual .12s lock timeout raises WinError32, owner bytes remain; measured whole context .141s; later explicit same-owner release after closing handle succeeds without body rerun.',
  'body_failure':'Actual shared handle released after delay; original body RuntimeError object propagates unchanged.'
 },
 'bounded_and_owner_tests':{
  'scope':'Full canonical captured payload validation, current real PID, lowercase32-hex nonce, exact key hash leaf and same on-disk bytes; replacement/disappearance/read error after denial fail closed.',
  'platform_and_code_gate':'Only Windows flag plus exact winerror32 retries; code5/code33/plain errno13 and nonWindows flag do not sleep/retry.',
  'time_boundaries':[0,.07,2,20],
  'actual_6_second_wait':False,
  'simulated_clock_time_bound':'sleep sum <=min(lock_timeout,6), at most120 backoffs; no-advance clock independently bounded at121 unlink attempts including initial call.',
  'separate_windows':'A critical body advancing synthetic clock100s does not consume fresh release budget.',
  'nonretry_failure':'Release error keeps body error as Python exception context.'
 },
 'multiprocess':{
  'single_dispatch':{'processes':6,'requests':18,'winning_execution_permissions':1,'unique_attempt_ids':1,'synthetic_research_debits':1,'all_process_exit_codes':0,'unresolved_lock_files_afterwards':0},
  'WR04':{'processes':2,'different_projects':[5501,5502],'separate_store_and_Registry_instances':True,'research_before':1,'competing_requests':2,'new_execution_permissions':1,'denied_BudgetExceeded':1,'research_after':2,'first_failed_attempt_retained':True,'same_operation_reuse_additional_debits':0},
  'scope_note':'Synthetic local Registry admission permissions only. No submit adapter or real provider was called.'
 },
 'static_source_locations':[
  {'file':'cloud/qresearch/artifacts.py','line':248,'function':'_release_lock'},
  {'file':'cloud/qresearch/artifacts.py','line':306,'function':'locked'},
  {'file':'cloud/qresearch/registry.py','line':581,'function':'begin_attempt'},
  {'file':'cloud/qresearch/registry.py','line':623,'purpose':'engineering limit inside shared transaction'},
  {'file':'cloud/qresearch/registry_engineering.py','line':424,'function':'_enforce_engineering_limit'}
 ],
 'independence':'No developer test/fixture imports. Only actual production modules, a copied production engineering schema with synthetic hashes/projects, stdlib-controlled boundary stimuli and private stores are used.',
 'preservation':{'all_fixed_source_files_checked':len(manifest['files']),'raw_changes':changes,'source_write_attempts':0,'real_registry_budget_writes':0,'cloud_calls':0},
 'unverified':['Not a proof against arbitrary hostile replacement in the read/unlink TOCTOU interval or all filesystem races.','No power-loss, hard OS termination or filesystem corruption durability certification.','No external MCP host scheduling, actual cloud deployment, vendor data provenance or financial validation.','WR04 test covers initial legacy fixed2 shared engineering stop across projects, not all later authorized-round/cycle states.'],
 'artifacts':{'test':'independent_windows_lock.py','raw_results':'first_results.json','commands':'execution_records.json','stdout':'first.stdout','stderr':'first.stderr'},
 'financial_evidence':False
}
(O/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report_sha256':sha(O/'report.json'),'methods':18,'named_scenarios':37,'all_source_files_unchanged':len(manifest['files']),'findings':0}))
