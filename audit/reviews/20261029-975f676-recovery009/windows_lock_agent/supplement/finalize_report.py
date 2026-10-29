from pathlib import Path
import hashlib,json,sys,platform
O=Path(__file__).resolve().parent
R=O.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
previous=O.parent/'report.json'
assert sha(previous)=='db046704ec8a3ea242adbee32aa689e76b6b51d79b7f8d4cf315cfbc2c491c39'
raw=json.loads((O/'first_results.json').read_bytes())
assert raw['methods']==7 and raw['named_scenarios']==28
assert raw['failures']==raw['errors']==raw['skipped']==0
manifest=json.loads((R/'source_git_manifest.json').read_bytes())['source']
changed=[name for name,item in manifest['files'].items() if not (R/'source'/name).is_file() or sha(R/'source'/name)!=item['sha256']]
assert not changed,changed
execution={'argv':[r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe','-B',str(O/'independent_cycles_rounds.py')],
           'exit_code':int((O/'first.exit').read_text().strip()),'unittest_elapsed_seconds':15.175,
           'started_at':None,'finished_at':None,'timestamp_note':'Precise process timestamps not instrumented; duration from preserved unittest output.',
           'stdout':'first.stdout','stderr':'first.stderr',
           'sha256':{name:sha(O/name) for name in ['independent_cycles_rounds.py','first.stdout','first.stderr','first.exit','first_results.json']}}
(O/'execution_records.json').write_text(json.dumps([execution],ensure_ascii=False,indent=2),encoding='utf-8')
report={
 'review_id':'AQRP-20261029-975F676-LOCK-SUPPLEMENT-NEW-CYCLE-SCHEMA4',
 'source_commit':manifest['commit'],'materials_commit':'a6a5a165d87c172535cdea6cf495e3c1a850e6e4',
 'prior_report_sha256':sha(previous),'prior_report_bytes_unchanged':True,
 'environment':{'os':platform.platform(),'python':sys.version,'executable':sys.executable},
 'status':'passed_for_independently_executed_revision_cycle_schema4_reservation_and_preflight_scope',
 'actually_executed':True,'methods':7,'methods_passed':7,'named_scenarios':28,'failures':0,'errors':0,'skipped':0,
 'first_execution_passed':True,'reviewer_corrections':[],'findings':[],
 'evidence_grade':['reviewer_actual_native_Windows_multiprocess_synthetic_tests','reviewer_actual_production_CLI_synthetic_preflight','static_archived_authorization_metadata_review'],
 'revision_and_cycle':{
  'revision':'One configuration reserve slot added; normal configuration limit and all Research/LEAN limits unchanged; existing usage never refunded.',
  'cycle':'Only active configuration allowance reset. Lifetime configs, prior cycle usage/origins and journal prefix preserved. Research/LEAN counters remain3/3 in positive known-answer scenario.',
  'idempotency':'Duplicate revision/cycle and old config reuse append no event or debit, including after activity and restart.',
  'refusals':['two config reserve increment','Research reserve increment','stale previous state','revision after cycle','cycle with started/pending/ambiguous task','cycle with open schema4 round']
 },
 'schema4_and_round':{
  'plan_schema':4,'round_schema':2,'round_limits':{'configurations':1,'research':1,'lean':1},
  'current_cycle_bound':True,'same_parent_processes':4,'claim_requests':4,'execution_permissions':1,
  'configuration_binding_cap':'Second same-project plan cannot consume a second configuration slot.',
  'failure_close_restart':'Failed Research remains charged. Retry bound0 refuses new attempt; closing and reopening neither resets usage nor permits reauthorization to reopen; same config and failed operation reuse remain free.',
  'LEAN':'Verified completed same-plan Research prerequisite was NOT fabricated. A missing successful Research cannot charge LEAN. This supplement does not claim a newly exercised positive schema4 Research-to-LEAN completion chain.'
 },
 'cross_project_global_reservations':{
  'projects':[6601,6602],'processes':2,'global_research_used_before':5,'global_research_limit':6,
  'authorized_1_1_1_rounds_granted':1,'concurrent_grants_denied_BudgetExceeded':1,
  'winner_research_used_after':6,'failed_winner_closed_round':True,
  'alternative_project_or_round_after_close_still_denied':True,'LEAN_usage_unchanged':4,
  'interpretation':'A grant binds one exact project; competing projects therefore race in the shared grant reservation transaction, not by using a foreign project in one grant.'
 },
 'preflight':{
  'source_known_answer':'BMP CJK+CRLF+BOM is4 UTF16 code units and8 UTF8 bytes, without normalization.',
  'source_negative_cases':['one character over','nonBMP character','boolean limit','NUL character'],
  'actual_stage2_functions':['freeze','main register','main claim research'],
  'source_over_limit_and_invalid_followup_policy':'Each rejected before any private Registry mutation or export_usage; valid registration between failures succeeds and remains charged exactly once.',
  'network_or_cloud_actions':0
 },
 'metadata_semantics_read':[
  'audit/runtime/budget-revisions/user-authorizations/52815c7267b1b0224e18f958eca373b40ae547abb33c7f562903d3b760caff5c.json',
  'audit/runtime/budget-cycles/user-authorizations/6490582cd34826d60a8989d712ba33a9e45d3ec8757890bee761001e42370347.json',
  'audit/runtime/engineering/rounds/authorizations/* stage2-storage-repair-round-008'
 ],
 'authorization_boundary':'Read authorization transcriptions as untrusted audit metadata only. They did not authorize any actual budget update. All constructed authorizations explicitly say SYNTHETIC and operate only in temporary private stores.',
 'independence':'No developer test or fixture imports. Own plan builder uses production schema4 pilot and source catalog with synthetic project/source/config identifiers; retained legacy descriptors validate policy shape only, not native origin or real data.',
 'static_locations':[
  {'file':'cloud/qresearch/registry.py','line':344,'function':'authorize_budget_revision'},
  {'file':'cloud/qresearch/registry.py','line':376,'function':'_effective_usage'},
  {'file':'cloud/qresearch/registry.py','line':439,'function':'authorize_configuration_cycle'},
  {'file':'cloud/qresearch/registry_engineering.py','line':77,'function':'_charge_reserved'},
  {'file':'cloud/qresearch/registry_engineering.py','line':121,'function':'_validate_round_authorization'},
  {'file':'tools/stage2.py','line':63,'function':'local_deployment_preflight'},
  {'file':'tools/stage2.py','line':274,'function':'joint_preflight'},
  {'file':'cloud/qresearch/source_limits.py','line':64,'function':'validate_source_sizes'}
 ],
 'source_files_checked':len(manifest['files']),'source_raw_changes':changed,
 'real_budget_or_registry_writes':0,'cloud_calls':0,'financial_evidence':False,
 'unverified':['No new actual cloud execution, MCP scheduling or native market/financial result.','Positive schema4 LEAN admission after a fully verified synthetic Research completion is outside this supplement.','Synthetic authorization validity does not authenticate a human instruction or grant permission to update the real ledger.'],
 'artifacts':{'test':'independent_cycles_rounds.py','results':'first_results.json','commands':'execution_records.json','stdout':'first.stdout','stderr':'first.stderr'}
}
(O/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report_sha256':sha(O/'report.json'),'methods':7,'named_scenarios':28,'previous_report_unchanged':True,'source_files_raw_unchanged':len(manifest['files'])}))
