from pathlib import Path
from hashlib import sha256
import json
R=Path(__file__).resolve().parent
main=json.loads((R/'current_execution.json').read_text(encoding='utf-8'))
extra=json.loads((R/'parser_first_results.json').read_text(encoding='utf-8'))
original=json.loads((R/'first_results.json').read_text(encoding='utf-8'))
old_commands=json.loads((R/'command_log.json').read_text(encoding='utf-8'))
new_commands=json.loads((R/'parser_command_log.json').read_text(encoding='utf-8'))
report={
 'reviewed_source_commit':'4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7',
 'baseline':'dc49f0f3037918f3ce4413665c59b164a8d6e2b7',
 'verdict_in_tested_scope':'Original recovery/shared-task compatibility remains passing; specified fractional-clock receipts now complete after context drift; no new recovery defect confirmed.',
 'original_recovery_replay':{k:main[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','skipped','failure_records','error_records','exit_code','command','cwd','elapsed_seconds']},
 'new_fractional_parser_recovery':{k:extra[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','skipped','failure_records','error_records','exit_code','command']},
 'separate_overlapping_suites_not_a_unique_case_sum':True,
 'current_execution_identity':main,
 'historical_literal_note':'Original independent_recovery.py and its be944 literal are preserved byte-for-byte. Current source binding is the new script path, ROOT.parent/source, actual 4a source copies, command log and this outer current_execution record; the historical literal does not identify the executed source.',
 'evidence':[
  'The original independent recovery script is byte-identical to the dc round copy. It actually runs against 4a source through full source copies, production CLI subprocesses, real source-manifest checks and Filesystem Registry, with no author fixture or mocked CLI/manifest/Registry.',
  'Original 12 methods/36 subcases cover A->B, catalog/source changes, absent or corrupt current pointer, process restart, old-input settlement, identity/admission/deployment/local-byte tampering, never-prepared stale-input rejection, current register/claim identity gates, completed-input refusal and free idempotent settlement.',
  'Four new positive fractional clocks (.5/.12/.1234/.12345) are embedded in lastModified on nested native TextContent nodes. Each actual standard CLI settlement completes the original A attempt after B is frozen and current source/catalog are changed, with no extra charge.',
  'Three new refusal controls are unknown rows annotation, invalid calendar date 2025-02-29 and invalid timezone offset +24:00. Each rejects before state transition, preserves started/journal/quota and does not store the synthetic row sentinel; correcting the receipt then completes that same attempt without a new debit.',
  'CLI entry, collection_task_cli, Registry, CollectionTaskPlan/Bridge, EngineeringTaskBridge, worker/parser file, collector and source adapter are raw-byte identical to dc49. The changing shared annotation parser is checked through the public recovery pipeline rather than by replacing admission logic.'
 ],
 'new_parser_observations':extra['observations'],'original_base_observations':original['observations'],
 'actual_child_commands':{
  'original':{'count':len(old_commands),'success':sum(c['returncode']==0 for c in old_commands),'expected_rejections':sum(c['returncode']!=0 for c in old_commands)},
  'new_parser':{'count':len(new_commands),'success':sum(c['returncode']==0 for c in new_commands),'expected_rejections':sum(c['returncode']!=0 for c in new_commands)}},
 'confirmed_new_recovery_findings':[],'minimal_new_failing_reproduction':None,
 'accurate_source_function_ranges':main['source_function_locations'],
 'limits':[
  'Synthetic source rows and native-shaped observations only; no real SDK, market, Research, LEAN, model, deployment or platform operation.',
  'Already charged immutable configuration/admitted-input metadata remains within the declared trusted dispatcher/store boundary and is not a signed execution token.',
  'Full source bytes before/after replay are unchanged. Copy-only 7/10/1 state is synthetic; production 6/9/1 is not modified.',
  'No full platform envelope certification, real source coverage, financial validity or full stage2/whole-system acceptance follows from this compatibility result.',
  'The old 24/36 admission suite and wider annotation/worker replays are assigned to root or other reviewers and are not claimed as additional runs here.',
  'Package scripts, reports and logs only; cases/ and parser_cases/ are reconstructable repeated source copies. Run original replay before supplemental probe.'
 ],
 'artifacts':['current_execution.json','first_results.json','first_output.txt','command_log.json','replay_stdout.txt','replay_stderr.txt',
              'parser_first_results.json','parser_first_output.txt','parser_command_log.json','independent_recovery.py','new_parser_recovery.py'],
 'actual_external_calls':0,'author_fixture_imports':False,
 'artifact_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in R.glob('*') if p.is_file() and p.name!='review_report.json'}
}
(R/'review_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'original_methods':main['methods'],'original_subcases':main['subcases'],'new_methods':extra['methods'],'new_subcases':extra['subcases'],'new_findings':0}))
