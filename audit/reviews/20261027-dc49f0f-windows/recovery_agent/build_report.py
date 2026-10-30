from pathlib import Path
from hashlib import sha256
import json
R=Path(__file__).resolve().parent
main=json.loads((R/'current_execution.json').read_text(encoding='utf-8'))
extra=json.loads((R/'parser_first_results.json').read_text(encoding='utf-8'))
original=json.loads((R/'first_results.json').read_text(encoding='utf-8'))
main_commands=json.loads((R/'command_log.json').read_text(encoding='utf-8'))
extra_commands=json.loads((R/'parser_command_log.json').read_text(encoding='utf-8'))
report={
 'reviewed_source_commit':main['reviewed_source_commit'],
 'verdict_in_scope':'WR11/WR12 recovery and shared-task compatibility remain passing in the tested scope; no new recovery defect confirmed.',
 'unchanged_original_recovery_replay':{key:main[key] for key in ['methods','passed_methods','failed_methods','error_methods','subcases','skipped','failure_records','error_records','exit_code','command','cwd','elapsed_seconds']},
 'new_parser_recovery_interaction':{key:extra[key] for key in ['methods','passed_methods','failed_methods','error_methods','subcases','skipped','failure_records','error_records','exit_code','command']},
 'counts_are_separate_overlapping_suites':True,
 'current_execution_identity':main,
 'original_suite_literal_commit_note':'The prior script is intentionally byte-identical. Its first_results.json commit literal says be944, but actual source path, copied file location, whole source hashes, command log and this outer record bind this execution to dc49. The historical literal must not be used as current execution identity.',
 'evidence':[
  'Original be944 independent_recovery.py is byte-identical (SHA256 9e3643e9b9fd177f50edf9e275942d3bcbcbfbb6689b6acbd3c73e481bfdb4a4) and was actually run once against dc49 source via ROOT.parent/source.',
  'Original replay used complete dc49 source copies (1088 files), actual production CLI subprocesses, actual source-manifest calculation and Filesystem Registry. No CLI, Registry or manifest checks were mocked.',
  'Original 12 methods / 36 subcases retain A->B settlement, catalog/source changes, missing/corrupt current pointer, restarts, identity/input/deployment/canonical-bytes tampering rejection, current source gates for never-prepared input, completed-input refusal and free idempotent settlement.',
  'Six new cases run within A->B plus source and catalog drift. Three nested annotations with unknown rows/error/outputs each fail before transition, retain started and identical journal/quota, then the corrected receipt completes the same original attempt without another charge.',
  'Three legal annotations (None, empty object and registered audience/priority/lastModified) complete through the same old-attempt recovery path after source/catalog drift.',
  'Both supplemental methods / six subcases passed on first execution. Original and supplemental outputs and command logs are separate; no failed record or original script was overwritten.',
  'CLI entry, collection_task_cli, Registry, CollectionTaskPlan/Bridge, EngineeringTaskBridge and collection worker/parser are raw-byte identical to be944, as are snapshot collector and source adapter. Shared authoritative accounting implementation was not changed by this commit.'
 ],
 'new_parser_observations':extra['observations'],
 'original_base_observations':original['observations'],
 'actual_child_command_counts':{
  'original':{'commands':len(main_commands),'success':sum(x['returncode']==0 for x in main_commands),'expected_refusals':sum(x['returncode']!=0 for x in main_commands)},
  'new_parser':{'commands':len(extra_commands),'success':sum(x['returncode']==0 for x in extra_commands),'expected_refusals':sum(x['returncode']!=0 for x in extra_commands)}},
 'confirmed_new_recovery_findings':[],'minimal_new_failing_reproduction':None,
 'accurate_source_ranges':main['source_function_locations'],
 'risk_and_scope_boundaries':[
  'Synthetic native-shaped observations only. No real SDK, market, Research, LEAN, model, deployment or project operation was called.',
  'Recovery trusts already charged immutable configuration and admitted-input metadata in the dispatcher/store boundary; these are not cryptographic authorization tokens. Recovery grants no new claim or execution.',
  'Original source tree all 1088 raw files is unchanged before/after replay. All mutations are confined to new independently copied test workspaces.',
  '7/10/1 usage is isolated-copy state after one new synthetic task; production 6/9/1 is untouched.',
  'This task does not certify all annotations, all native platform envelopes, current cloud execution, historical coverage, whole stage2 completion or financial validity.',
  'The prior 24/36 admission suite is assigned to root for its own replay; it is not claimed as an additional execution in this subreport.',
  'cases/ and parser_cases/ are reconstructable test workspaces. Package the scripts/results/logs, not those repeated source copies. Run original recovery replay before supplemental probe so its generated prepared fixture exists in the local command log.'
 ],
 'actual_external_calls':0,'author_fixture_imports':False,
 'artifact_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in R.glob('*') if p.is_file() and p.name!='review_report.json'}
}
(R/'review_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'original_methods':main['methods'],'original_subcases':main['subcases'],'new_methods':extra['methods'],'new_subcases':extra['subcases'],'findings':0}))
