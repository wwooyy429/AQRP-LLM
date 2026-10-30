from pathlib import Path
from hashlib import sha256
import ast,json,sys
R=Path(__file__).resolve().parent;S=R.parent/'source'
first=json.loads((R/'quick_first_results.json').read_text(encoding='utf-8'))
freeze=json.loads((R/'mre_freeze/result.json').read_text(encoding='utf-8'))
api=json.loads((R/'api_preflight_boundary.json').read_text(encoding='utf-8'))
locations={}
for rel in ['cloud/qresearch/registry.py','cloud/qresearch/engineering_tasks.py','tools/stage2.py']:
    for n in ast.walk(ast.parse((S/rel).read_text(encoding='utf-8-sig'))):
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):locations[rel+':'+n.name]=[n.lineno,n.end_lineno]
findings=[{
 'id':'WR-16','priority':'P2','title':'Joint v2 frozen operation, Research prerequisite and retry bounds are not enforced at direct Registry admission',
 'primary_file':'cloud/qresearch/registry.py','lines':[487,488,502,506,507,508],
 'bridge_control_file':'cloud/qresearch/engineering_tasks.py','bridge_control_lines':[388,391,407,408,409],
 'contract_evidence':[
  'Joint plan max_retries is frozen per stage. EngineeringTaskBridge rejects LEAN before a completed parent Research and rejects retry when max_retries=0.',
  'Registry is documented as the authoritative locked admission point for direct callers; existing CollectionTask operation and retry guards run there.',
  'Joint schema2 is validated/classified during registration, but begin_attempt only obtains _collection_plan and therefore omits the joint policy before its attempt_started debit.'
 ],
 'actual':[
  'A direct research call with an arbitrary operation returns should_execute=True and increments durable Research usage.',
  'A direct fixed-operation LEAN call before any Research returns should_execute=True and increments LEAN usage. Bridge claim refuses before charging.',
  'After one failed Research, a joint plan with max_retries=0 receives a second should_execute=True fixed-operation Research via direct Registry; its Bridge payload is usable. Bridge retry refuses with identical frozen plan.'
 ],
 'severity_reason':'A documented public admission route can debit scarce nonrefundable slots for work outside the frozen parent protocol. Fixed-operation retry can produce a usable payload. These are policy/ordering failures before dispatch; no real remote job was submitted.',
 'bounds':'The existing shared engineering2/2/2, global12/20/16 and allocation caps remain enforced. Wrong-operation and early-LEAN payload construction subsequently refuses, after the debit. The max0 example independently uses an empty synthetic engineering domain; the real preserved1/2 baseline would hit the aggregate cap on another retry. Do not claim actual/global budget overspending.',
 'minimal_reproduction':'python -B minimal_joint_registry.py <source-dir> (exit1; three observations, plus Bridge controls)',
 'regression_tasks':[
  'Under Registry.LOCK validate joint fixed engineering-plan operation and stage before any new charge.',
  'Require the same parent Research completed state before joint LEAN; preserve free idempotent completed/unresolved logical reuse.',
  'Enforce the frozen per-stage max_retries for direct Registry as well as Bridge, across normal/reserve and reopen/replay.',
  'Mixed v1/collection/v2 races with one remaining domain slot still allow at most one new claimant; all global and allocation caps continue applying.'
 ]
},{
 'id':'WR-17','priority':'P2','title':'Inherited v1 freeze can overwrite the settlement pointer while the project has pending old work',
 'primary_file':'tools/stage2.py','lines':[67,70,71,74,75,76,77,78,82,83,95,96],
 'downstream_file':'cloud/qresearch/engineering_tasks.py','downstream_lines':[371,377,412,413],
 'contract_evidence':'The new v2 freeze explicitly says an unresolved project input must not have its old settlement pointer replaced. The schema1 else branch writes the identical pointer without the project guard.',
 'actual':'On an isolated complete source/old-ledger copy, original current_bridge._record accepts bfd00f2611fd4496b9498d4597618a8e. Joint freeze refuses and preserves pointer. Legacy freeze succeeds, changes engineering_current.json, and actual CLI prepare --attempt for that same old identity refuses Attempt does not belong to this exact registered task plan.',
 'severity_reason':'A normal supported CLI entry evades the new pending-project freeze protection and breaks the standard current-pointer settlement/preparation context for the in-flight old task. The ledger and original configuration remain available; this is recoverable context loss, not permanent data loss or global deadlock.',
 'bounds':'This is an inherited schema1 entry inconsistent with new v2 protection. It does not invalidate historical WR12, which covered CollectionTask recovery by attempt. The reproduction only changes a new temporary source/ledger copy, keeps event bytes unchanged and makes no QC call.',
 'minimal_reproduction':'python -B minimal_pending_freeze.py <source-dir> <fresh-output-dir> (exit1; logs/result.json preserve before/control/after)',
 'regression_tasks':[
  'Apply pending-project protection to every freeze route that can replace the shared engineering_current pointer, including v1; decide harmless exact-pointer reuse separately.',
  'Verify v1/v2 started/pending/ambiguous all block replacement and preserve pointer bytes, journal and usage.',
  'Resolve old attempt settlement from its persisted original context, or otherwise retain an explicit recovery path independent of mutable current pointer.',
  'After trusted terminal reconciliation, permitted new freeze/register/claim works normally; no refunds, re-submission or clearing historical evidence.'
 ]
}]
report={
 'reviewed_source_commit':first['source_commit'],'verdict_in_scope':'failed: WR16 and WR17 reproduced',
 'unique_unit_suite':{'file':'quick_joint_probes.py','methods':first['methods'],'passed_methods':first['passed_methods'],
  'failed_methods':first['failed_methods'],'error_methods':first['error_methods'],'skipped':first['skipped'],'subcases':first['subcases']},
 'first_failure_records_preserved':True,'first_output':'quick_first_output.txt','first_results':'quick_first_results.json',
 'original_script_sha256':first['script_sha256'],'findings':findings,
 'unit_suite_count_does_not_add_reproductions':'Seven unique methods total (3 passing controls and4 failed methods); two standalone MREs are replays of the same defects, not extra unit methods. No extra race/fault suite was run just to increase counts.',
 'mre_results':{'WR16':{'exit_code':1,'stdout':'mre_registry.stdout','stderr':'mre_registry.stderr'},
                'WR17':{'exit_code':1,'stdout':'mre_freeze.stdout','stderr':'mre_freeze.stderr','detailed_result':'mre_freeze/result.json'}},
 'public_Bridge_preflight_boundary_observation':api,
 'preflight_interpretation':'Public EngineeringTaskBridge.register/submit do not invoke tools.stage2.joint_preflight. A separately executed CLI preflight rejects the synthetic stale source/deployment, while Bridge charges and invokes one deliberately stopping synthetic adapter. This is recorded as a trusted-caller/I-O boundary observation, not a successful wrong-deployment worker run or a separate unqualified third defect.',
 'accurate_source_function_ranges':locations,
 'observations':first['observations'],'freeze_impact':freeze,
 'commands':[
  [sys.executable,'-B',str(R/'quick_joint_probes.py')],
  [sys.executable,'-B',str(R/'minimal_joint_registry.py'),str(S)],
  [sys.executable,'-B',str(R/'minimal_pending_freeze.py'),str(S),str(R/'mre_freeze')],
  [sys.executable,'-B',str(R/'api_preflight_boundary.py')]],
 'actual_platform_Research_LEAN_market_model_calls':0,
 'author_test_fixtures_imported':False,
 'coverage_limits':['No claim that new v2 Windows multi-process/fault matrix was exhaustively executed. Existing atomic lock/cap code was statically traced; parent owns broader historical/repository replays.',
  'First failures are expectation failures, not imports, malformed test fixtures or reviewer exceptions: error_methods=0 and all positive controls pass.',
  'Stage2 live-pilot documents are read as a declared candidate, not execution authorization for this reviewer. All stores and project-listing shapes here are synthetic or copied metadata.',
  'Original production/source/config/budget files were not modified; only new admission_agent files and independent copies were written.',
  'No financial validity, historical data certification or overall stage2 acceptance follows from this audit.'],
 'artifact_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in R.glob('*') if p.is_file() and p.name!='review_report.json'}
}
(R/'review_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'methods':first['methods'],'pass':first['passed_methods'],'fail':first['failed_methods'],'errors':first['error_methods'],
 'subcases':first['subcases'],'findings':[x['id'] for x in findings]}))
