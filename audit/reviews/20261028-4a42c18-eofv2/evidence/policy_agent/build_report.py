from pathlib import Path
import ast,hashlib,json,platform,sys
R=Path(__file__).resolve().parent;ROOT=R.parent;S=ROOT/'source'
def read(p):return json.loads((R/p).read_bytes())
def H(b):return hashlib.sha256(b).hexdigest()
first=read('first/results.json');suppfirst=read('supplement_first/results.json');supp=read('supplement_corrected/results.json')
assert first['success']and first['methods']==13 and first['named_scenarios']==509
assert supp['success']and supp['methods']==3 and supp['named_scenarios']==20
maps=json.loads((ROOT/'source_git_manifest.json').read_bytes());guard={}
for name in ['candidate','baseline']:
 d=ROOT/maps[name]['directory'];actual={p.relative_to(d).as_posix():H(p.read_bytes())for p in d.rglob('*')if p.is_file()}
 assert actual==maps[name]['files'];guard[name]={'raw_files':len(actual),'all_equal_fixed_Git':True}
refs={}
for name in ['cloud/qresearch/deployment_sources.py','cloud/qresearch/engineering_data.py','cloud/qresearch/deployment_observation.py']:
 data=(S/name).read_bytes();tree=ast.parse(data.decode('utf-8'))
 refs[name]={'raw_sha256':H(data),'definitions':{n.name:{'start':n.lineno,'end':n.end_lineno}for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}}
doc={
 'reviewed_source_commit':'4a42c18f0b78bea2068d589bc12f1615712354c6',
 'baseline_commit':'8d65c290773547c83549c098172f1eb8c3376cd7',
 'archive_commit':'1cf26578da59eebd37e138ca5d6d076991386470',
 'scope':'Independent synthetic byte/encoding/syntax/manifest/filesystem/diagnostic core source-policy checks. No candidate-wide artifact or platform acceptance.',
 'verdict':'Tested core source-policy scope passed after one disclosed supplemental reviewer-filesystem-label correction. No core product defect confirmed.',
 'candidate_wide_acceptance':'Not granted by this scoped report. Parent independently reports WR28/P2 protected-manifest delivery reproduction failure; this core result does not close that finding or accept phase2.',
 'findings':[],
 'actually_executed':[
  {'name':'independent_policy_core','methods':13,'passed_methods':13,'named_scenarios':509,'unittest_subtest_count':None,'failure_records':0,'error_records':0,'skipped':0,'first_run':True,'result':'first/results.json','execution':'first_execution.json'},
  {'name':'strict_digest_and_legacy_diagnostics_supplement','methods':3,'passed_methods':3,'named_scenarios':20,'unittest_subtest_count':None,'failure_records':0,'error_records':0,'skipped':0,'first_run':False,'result':'supplement_corrected/results.json','execution':'supplement_corrected_execution.json'},
  {'name':'same_manual_v2_manifest_baseline_candidate_MRE','Python_processes':2,'unit_methods':0,'results':['mre_baseline/mre_result.json','mre_candidate/mre_result.json'],'execution':'mre_execution.json'},
  {'name':'native_Windows_junction_containment','PowerShell_child_processes':1,'unit_methods_added':0,'result':'first/results.json metadata.junction','exit_code':0}
 ],
 'counting':'13/509 plus3/20 are separate current suites; named scenarios are logged labels, not a measured unittest-subTest or unique global assertion count. Two MRE processes and the actual Windows-junction process add no unit methods. The initial supplemental attempt is preserved and not counted again as passing.',
 'first_results_preserved':{
  'core':'All13 methods/509 labeled scenarios passed first run.',
  'supplement':{'methods':3,'passed_methods':2,'error_methods':1,'failure_records':0,'error_records':1,'named_scenarios_reached':18,'exit_code':1,'result':'supplement_first/results.json','execution':'supplement_execution.json'},
  'reason':'Synthetic filesystem directory label nul is a Windows reserved device name; writing nul/a.py raised FileNotFoundError before that case reached the product verifier.',
  'correction':'Only fixture directory label nul changed to zero-byte-source in a separate corrected script. NUL source bytes, all assertions and product source remained unchanged.',
  'files':['diagnostic_supplement.py','diagnostic_supplement_corrected.py','supplement_fixture_correction.diff','supplement_first.stdout','supplement_first.stderr','supplement_corrected.stdout','supplement_corrected.stderr']
 },
 'independent_oracles':[
  '325 direct SHA known-answer pairs: frozen LF counts0,1,2,7,64 against every worker count0..64. Worker canonical acceptance and strict original rejection distinguished.',
  'Direct normalized UTF-8 byte/hash answers for BOM/no-BOM and LF/CRLF/CR; non-ASCII literal preserved. Original identity means inherited UTF8-sig/universal-newline strict identity, not physical raw-byte equality.',
  '11 valid Python bodies including empty/comment/backslash/multiline string/future import/continuation/coding aliases; source compilation never executed code.',
  'Same-AST whitespace/comments/parentheses still change body digest and are refused; values/imports/interior newlines/trailing spaces not erased.',
  'Explicit terminal continuation unsafe normalization, invalid UTF8/NUL, foreign coding cookies, future-import placement and warning literals fail closed or remain silent with static errors.',
  'Exact schema/policy/types, record fields/counts/hashes and copied records; full wrapper hash cannot be replaced by files-map or strict index hash; independently self-consistent different original LF is a different manifest.',
  'Traversal/control/device/generated-input names, casefold aliases and file/ancestor collisions rejected before source reads. Real native Windows junction resolves outside the scratch source root and is refused before Path.read_bytes.',
  '2MiB original raw-byte bound, LF64/65,512/513 managed files and1024/1025 UTF8 path-byte bounds; legacy v1 original hashing and worker verification retain no new AST/size/EOF limits.',
  'Three-file observation returns exact full manifest hash, original identity status and actual2-file EOF-normalized count; strict PROJECT mode rejects EOF changes; legacy rejects them too.',
  'Diagnostic supplement forces strict SHA unequal to canonical SHA using frozen0/2/64 LFs and observed0/2 LFs; expected/observed mismatch digests are actual strict identities, never canonical labels.',
  'v1 default diagnostic schema1 and explicitly requested controlled schema2 preserved, including UTF8 decode errors and bounded format counts; no raw source literal or absolute scratch path in exported messages.',
  'Closed v2 summary is bound to original manifest/file count and worker mode; false counts, bool counters, missing fields, project mode and legacy-v2 claim refused.'
 ],
 'manual_MRE':{
  'same_manifest_sha256':'b725ed9ae1c246f6d1ecd27836bd7e56c34c15d24c0b397e4b254ca275ebb0a0',
  'baseline':read('mre_baseline/mre_result.json'),
  'candidate':read('mre_candidate/mre_result.json'),
  'interpretation':'Old v1 exact-original remains accepted and extraLF remains rejected in both versions. The exact same hand-built explicit-v2 manifest is unsupported/rejected by baseline and accepts extraLF only in candidate. Body alteration rejected in both. Both programs exit0 because their expected observations differ; do not call baseline legacy behavior a failed regression.',
  'command_template':'python -B manual_eof_mre.py --source <fixed-source> --out <new-synthetic-output> --expected-v2 yes|no'
 },
 'source_guard':guard,
 'source_exact_definitions':refs,
 'commands_and_output_hashes':['first_execution.json','supplement_execution.json','supplement_corrected_execution.json','mre_execution.json'],
 'environment':{'python':sys.version,'os':platform.platform(),'native_Windows':True},
 'real_actions':{'QC_calls':0,'Research_executions':0,'LEAN_submissions':0,'compile_service_calls':0,'market_calls':0,'model_API_calls':0,'original_Git_source_edits':0,'authoritative_budget_writes':0,'new_configuration_registrations':0},
 'limitations':[
  'All programs used independently synthetic byte streams and private filesystem fixtures; compile() only validates local syntax and never executes supplied source.',
  'Windows junction containment was physically tested, not every filesystem/symlink race, network filesystem, OS-kill or power-loss durability condition.',
  'Source-policy success is not a remote platform signature, complete project inventory, market-data provenance or certification of exact historical worker packaging.',
  'No independent candidate-wide protected-manifest acceptance here; parent WR28 remains open. No candidate cloud deployment/real worker success tested.',
  'Old failed3e688 task, global12/15/2 budget, missing historicalUS200/SID/financial/vintage/actual-delivery certification and closed final test remain outside this core acceptance.'
 ],
 'financial_evidence':False
}
(R/'report.json').write_text(json.dumps(doc,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
(R/'report.txt').write_text('Core source-policy bounded scope passed; candidate-wide acceptance NOT granted.\n13 methods/509 named scenarios first pass; supplemental3/20 pass after disclosed Windows fixture-label correction.\nTwo manual baseline/candidate programs and one real Windows junction subprocess are separate populations.\nNo core product finding; parent WR28 protected manifest failure remains unclosed. No real platform/market/model or original source/budget writes.\n\n'+json.dumps(doc,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
hashes={p.relative_to(R).as_posix():H(p.read_bytes())for p in R.rglob('*')if p.is_file()and'cases'not in p.relative_to(R).parts and p.name!='deliverable_hashes.json'}
(R/'deliverable_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8');print(json.dumps({'report_sha256':H((R/'report.json').read_bytes()),'guard':guard,'methods':[13,3],'named_scenarios':[509,20]}))
