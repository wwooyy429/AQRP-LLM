from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent
def J(p):return json.loads((R/p).read_bytes())
first=J('first/first_results.json');new=J('corrected/first_results.json');archive=J('archive_inspection.json')
assert new['success']and new['methods']==10 and new['named_scenario_records']==57 and new['source_raw_unchanged']
report={
 'reviewed_source_commit':'4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8',
 'scope':'Independent current-run native parser/bridge synthetic recheck and fresh offline archived native metadata inspection, under documented trusted dispatcher boundary.',
 'verdict':'Tested current scope passed after disclosed reviewer oracle/helper corrections; actual newLEAN remains pending in fixed archive; no new product finding confirmed.',
 'findings':[],
 'current_executions':{
  'corrected_independent_suite':{k:new[k]for k in ['methods','passed_methods','failure_records','error_records','skipped','named_scenario_records','counts','seconds','source_raw_unchanged']},
  'evidence':'corrected/first_results.json; corrected_execution.json; corrected.stdout; corrected.stderr',
  'static_archived_checks':{'checks':35,'passed':35,'methods':0,'records':3,'evidence':'archive_inspection.json; archive_inspection_execution.json'},
  'first_run':{k:first[k]for k in ['methods','passed_methods','failure_records','error_records','skipped','named_scenario_records','success']},
  'first_result_evidence':'first/first_results.json; first/first_unittest.txt; first_execution.json',
  'actual_CLI_processes':0,'actual_QC_workers':0,'actual_QC_calls':0,'actual_LEAN_terminal_or_log_reads':0,'market_or_model_calls':0,'source_or_authoritative_budget_writes':0
 },
 'first_results_explanation':{
  'mutable_test_helper':'native() initially returned the packet structuredContent object itself. A negative-case mutation changed only that mirror, so the next helper call detected mirror mismatch before calling the product. Corrected by deepcopy; all original script/output bytes retained.',
  'overstrong_remote_provenance_oracle':'The first test incorrectly required an nbformat error response with the same project/cell to independently identify its originating attempt/source. It carries no such field. Under the explicitly documented operational trust boundary, the supplied trusted dispatcher binding provides context; a pure parser cannot certify remote origin or detect an operator swapping such a response. This is now recorded as a limitation, not silently claimed to pass the original rejection expectation.',
  'actual_guard_test':'The corrected suite separately demonstrates old/different error receipts cannot replace the original completed or failed Research terminal; original submission/evidence hashes reject both with no metadata writes.',
  'artifacts':'independent_runtime_recheck_first.py; independent_runtime_recheck_corrected.py; reviewer_scope_correction.diff; reviewer_scope_correction.txt'
 },
 'covered_current_cases':[
  'Three original frozen admissions, exact physical input byte/hash,32 managed files,13 Research vs7LEAN checks, fixed37dc task packet population.',
  'Four exact original completed/failed Research replays after redirecting mutable current pointer to unrelated invalid content; all46-event Memory metadata bytes unchanged.',
  'Success mirrored JSON semantics/key ordering; two exact native error texts plus matching structuredContent and supported fractional-time annotations; mismatched duplicate annotations rejected.',
  'Fresh rehashed joint-probe window/fetch/reuse/empty/record arithmetic mutants rejected, legitimate mixed-cache window partition accepted.',
  'Cross-attempt report/binding rejection; native-error provenance limitation explicitly demonstrated; changed original Research terminals refused.',
  'Explicit synthetic deliveredLEAN terminal with7 checks,0 actual/synthetic-engine orders,dividend1 and native Decimal-zero representations; one privateMemory pending-to-completed transition46-to47 events with unchanged usage.',
  'All7 requiredLEAN checks individually false and4 boundary count failures cannot pass the Bridge contract.',
  'Complete reversed native log pages accepted; missing/duplicated/inconsistent pages,foreign attempt and duplicate chunks rejected.',
  'Wrong external/project, running/unknown/incomplete/bool progress and nonzero/nonfinite/bool native order counts rejected.',
  'Explicit synthetic runtime-error receipt accepted without logs; transport timeout rejected as nonterminal; separate pristine actual snapshot remains pending.'
 ],
 'archived_evidence':{
  'level':'Developer-archived native packets independently decoded and checked offline. Not reviewer live platform retrieval, remote signature, or cloud-row recount.',
  'diagnostic':archive['archived_native_records'][0],
  'repaired_Research':archive['archived_native_records'][1],
  'LEAN':archive['archived_native_records'][2],
  'compile':'Only developer compile.success/updated-files summary in existing materials; original normal004 native compile packet not independently obtained.',
  'source_at_execution':'32 files per frozen deployment independently matched local Git42b/662 normalized hashes. This does not certify exact historical worker packaging or a full current cloud inventory.',
  'prior_cloud_readback':'Prior root review obtained35 live source-only QC calls (2list+32managed files+LEANinput); preserved historical evidence, not calls or fresh cloud state obtained in this recheck.'
 },
 'reviewer_metadata_correction':{
  'prior_review':'Previous sealed formal_report.unverified used13 when discussing the undelivered newLEAN engineering checks.',
  'correct_value':'Frozen plan requires13 Research checks and7LEAN checks. NewLEAN7 remain unobserved at real runtime.',
  'classification':'Reviewer reporting metadata correction, not a production software WR; prior sealed package unchanged.'
 },
 'historical_reference_not_newly_executed':{
  'prior_runtime_agent':'Previous35 native manual scenarios,18 collection bridge scenarios and protocol/recovery suites are historical references only; not recounted as new executions.',
  'prior_full_scope':'Other earlier numeric/admission/source-worker tests are not represented as new current runtime executions.'
 },
 'acceptance':{'tested_parser_bridge_scope':'passed_under_declared_trusted_dispatcher_contract_with_disclosed_reviewer_scope_correction','real_Research_engineering':'archived native13-check result supported at metadata level','real_LEAN_terminal':'not_obtained_or_read; fixed ledger pending','phase2_overall':'not_accepted','data_certification':False,'financial_evidence':False},
 'unverified':[
  'A delivered original newLEAN terminal plus logs,7 fixed checks, actual0 orders and complete source/input identity reconciliation are absent from fixed source.',
  'Native response provenance depends on trusted dispatcher actual I/O; hashes and context do not remotely authenticate an error originating from an exact attempt.',
  'No live QC read,compile,Research,LEAN or model execution this recheck; synthetic completed/failedLEAN fixtures are not real platform terminal evidence.',
  'Research aggregate counters208223/27/0/13 reflect selected4-field program metadata, not a fresh row recount or full historicalUS200/financial-vintage/actual availability certification.',
  'No finance effectiveness or independent final test; configuration budget is full; no extra executions or quota changes authorized.',
  'Fault injection and in-memory replay do not certify OS kill,power loss or all physical storage failures.'
 ],
 'execution_records':[J('first_execution.json'),J('corrected_execution.json'),J('archive_inspection_execution.json')],
 'counts_overlap':True,
 'source_raw_unchanged':True
}
(R/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
(R/'report.txt').write_text('Runtime recheck: tested current scope passed, actual newLEAN pending, no new product finding.\n10 methods /57 named scenario records corrected pass;35 static archived checks,0 extra methods.\nFirst10 methods:8passed,2failure records; all first scripts/outputs retained; helper and overstrong provenance oracle corrections disclosed.\nDirect Research parser13 +6 bridge settlement calls;LEAN parser34;4 original terminal replays;1 pure synthetic privateMemoryLEAN completion; all real QC/market/model calls0.\nRequired checks: Research13,LEAN7. Previous sealed report13-for-LEAN statement is reviewer metadata error; old package preserved.\n\n'+json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'report_sha256':hashlib.sha256((R/'report.json').read_bytes()).hexdigest(),'methods':10,'named_scenarios':57,'static_checks':35,'findings':[]}))
