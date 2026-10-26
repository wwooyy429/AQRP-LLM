from pathlib import Path
from hashlib import sha256
import ast,json
R=Path(__file__).resolve().parent;S=R.parent/'source';OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-e513c66-20261026\source')
result=json.loads((R/'first_results.json').read_text(encoding='utf-8'))
commands=json.loads((R/'command_log.json').read_text(encoding='utf-8'))
locations={}
for rel in ['tools/collection_task_cli.py','tools/stage2_collection.py']:
    for n in ast.walk(ast.parse((S/rel).read_text(encoding='utf-8-sig'))):
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):locations[rel+':'+n.name]=[n.lineno,n.end_lineno]
protected={rel:sha256((S/rel).read_bytes()).hexdigest()==sha256((OLD/rel).read_bytes()).hexdigest()
           for rel in ['cloud/qresearch/registry.py','cloud/qresearch/collection_tasks.py',
                       'cloud/qresearch/engineering_tasks.py','cloud/qresearch/collection_execution.py']}
report={
 'reviewed_commit':result['commit'],'baseline':'e513c66e5965133fbe83fb0ab987eae853f96260',
 'verdict_in_scope':'WR12 recovery fix passes independently tested scope; no new confirmed recovery/admission defect.',
 'methods':result['methods'],'passed_methods':result['passed_methods'],'subcases':result['subcases'],
 'failed_methods':result['failed_methods'],'error_methods':result['error_methods'],'skipped':result['skipped'],
 'first_failure_records':result['failure_records'],'first_error_records':result['error_records'],
 'original_script':'independent_recovery.py','original_script_sha256':result['original_script_sha256'],
 'first_results':'first_results.json','first_output':'first_output.txt','command_log':'command_log.json',
 'root_command':result['command'],'actual_child_commands':len(commands),
 'child_successes':sum(x['returncode']==0 for x in commands),'child_expected_rejections':sum(x['returncode']!=0 for x in commands),
 'child_expected_nonzero_are_not_test_failures':True,'new_minimal_failing_reproduction':None,
 'accurate_source_function_ranges':locations,'unchanged_shared_admission_implementation_raw_bytes':protected,
 'evidence':[
  'All cases use a full copied source tree (891 original files), actual tools/stage2_collection.py subprocess entry points and actual FilesystemArtifactStore/Registry. Source manifests, current catalog reads, Registry opening, usage exports and CLI branches were not mocked.',
  'The independently generated task A consumes configuration/Research in the isolated copy only (6/9/1 -> 7/10/1). Production worker code runs a six-row, two-window synthetic source and produces a valid native-shaped final report, with two source fetch calls, two missing dollar_volume observations and cache-only replay zero calls.',
  'A->freeze B->settle A completes through the standard CLI using original identity; a repeat completes with identical journal bytes and no new charge.',
  'Current catalog change, source-file change, pointer deletion, malformed pointer, missing catalog and combined changes all permit old valid settlement after real subprocess restarts. task-status --attempt remains readable.',
  'Existing prepared input returns the same admission/bytes after source and current-pointer changes. Deleting the local input still permits digest-checked settlement from the original admission record without recreating any file.',
  'A separately preserved never-prepared snapshot has no admission or input file. Source, deployment or catalog drift each prevents prepare-task from creating either artifact, with unchanged journal and charge. Current register-task/claim-task likewise still reject stale source or current-catalog mismatch.',
  'Frozen but unregistered documents, invented attempt IDs, configuration hashes used as attempts and existing old non-collection LEAN attempts cannot authorize recovery. Rewriting the already registered catalog fails configuration hash/replay verification.',
  'Twelve admission mutations cover payload attempt/config/plan/report path, manifest digest/traversal, deployment input/source hashes, input/cloud destination, extra fields and noncanonical bytes. Payload cases recompute the easy input digest; the stronger immutable binding still rejects them before any lifecycle transition.',
  'Missing/malformed admission and extra/changed local input bytes reject settlement. Wrong project, attempt/config in the cloud report and report destination reject settlement. All refused cases preserve the precharged started attempt, journal and quota.',
  'Completed attempts cannot prepare a new remote input, even when a prior admission record exists.'
 ],
 'trust_boundary_assessment':{
  'frozen_catalog':'bridge_for_attempt only reconstructs catalog after finding a charged canonical attempt in verified Registry replay, checking immutable configuration bytes/hash and exact collection package, reconstructing its canonical plan and binding exact operation via bridge._record. It does not use this original catalog to register or claim a new task.',
  'admitted_input':'Existing immutable admission is trusted metadata from the dispatcher/store. It is validated against the charged configuration, expected payload, frozen deployment-manifest hash, exact input text/hash and optional existing local bytes. It is not a signed authorization token, and arbitrary code able to fabricate self-consistent trusted-store records or call SDKs directly is outside this declared boundary.',
  'new_inputs':'Without an existing admission record, prepare_task rechecks current execution source and current deployment before writing. This was dynamically verified using an actual never-prepared snapshot, not by deleting a record after preparation.',
  'shared_admission':'Registry, CollectionTaskPlan/Bridge, EngineeringTaskBridge and worker/parser files are byte-identical to e513. Original 24/36 replay belongs to root reviewer; this report does not claim it as a new run.'
 },
 'observations':result['observations'],'production_source_bytes_unchanged':result['production_source_bytes_unchanged'],
 'actual_external_calls':0,'developer_test_helpers_imported':False,
 'limits':['All native Research observations and source rows were synthetic; no actual SDK, provider, project, task or platform operation was executed.',
           'The independently identified receipt annotation issue WR13 is assigned to the other reviewer and does not convert this WR12 scope into full bridge acceptance.',
           'No real budget/configuration/source file was modified; synthetic copy 7/10/1 is not production usage.',
           'No real data certification, stage2 whole-system acceptance or financial validity is inferred.'],
 'artifact_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in R.glob('*') if p.is_file() and p.name!='review_report.json'}
}
(R/'review_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'methods':report['methods'],'subcases':report['subcases'],'child_commands':len(commands),'confirmed_new_recovery_findings':0}))
