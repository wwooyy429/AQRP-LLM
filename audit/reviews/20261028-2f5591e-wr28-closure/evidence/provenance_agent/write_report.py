from pathlib import Path
import ast,hashlib,json,platform,sys
R=Path(__file__).resolve().parent;S=R.parent/'source'
def read(p):return json.loads((R/p).read_bytes())
def h(b):return hashlib.sha256(b).hexdigest()
first=read('first/results.json');supp=read('supplement_first/results.json')
assert first['success']and supp['success']and first['methods']==8 and supp['methods']==3
manifest=json.loads((S/'audit/review_packages/deployment-eof-v2/protected_git_baseline.json').read_bytes())
expected=json.loads((R.parent/'source_git_manifest.json').read_bytes())['candidate']['files']
actual={p.relative_to(S).as_posix():h(p.read_bytes())for p in S.rglob('*')if p.is_file()};assert actual==expected and len(actual)==6379
definitions={}
for name in ['git_protection.py','build_git_protection.py']:
 p=S/'audit/review_packages/deployment-eof-v2'/name;tree=ast.parse(p.read_text(encoding='utf-8'));definitions[name]={'raw_sha256':h(p.read_bytes()),'functions':{n.name:{'line':n.lineno,'end_line':n.end_lineno}for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}}
report={
 'reviewed_source_commit':'2f5591e28c0748ac42caeae7bbf3977141d031cb',
 'baseline_commit':'1cf26578da59eebd37e138ca5d6d076991386470',
 'archive_commit':'fc0ba0ae36167a74c3e6c0c2e3c0cf33c3ba220f',
 'scope':'Independent Git-origin reconstruction for all122 protected raw files and new audit-verifier closed-schema/raw-byte boundaries; no developer test fixture imports.',
 'verdict':'Tested provenance and audit-verifier scope passed first run. All122 released new records equal independent rawGit evidence. No new provenance-scope defect confirmed. This does not independently grant fullWR28 closure or stage2/cloud/data/financial acceptance.',
 'findings':[],
 'actually_executed':[
  {'name':'independent_provenance','methods':8,'passed_methods':8,'named_scenarios':328,'unittest_subtest_count':None,'failure_records':0,'error_records':0,'skipped':0,'first_run':True,'result':'first/results.json','execution':'first_execution.json'},
  {'name':'independent_outer_provenance_and_exact_bounds','methods':3,'passed_methods':3,'named_scenarios':13,'unittest_subtest_count':None,'failure_records':0,'error_records':0,'skipped':0,'first_run':True,'result':'supplement_first/results.json','execution':'supplement_execution.json'}
 ],
 'counting':'8/328 plus3/13 are this child current independent executions. Named scenarios are explicit labels, not measured unittest-subTest counts or unique global cases. These11 methods are separate from developer11 audit tests. Explicit top-level child command records9+4 include Git, three builderCLIs and onePowerShell junction command; product helper transitiveGit subprocesses are not exhaustively counted.',
 'independent_Git_oracle':{
  'algorithm':'git archive reads original baseline raw bytes for all122paths, independently combined with three git ls-tree object maps. Direct git rev-parse independently reconstructs3treeIDs and git show reads source path-list bytes. SHA256, GitSHA1blob(header+raw), bytecount and old declared values compared for every record; no normalization.',
  'record_count':122,
  'all_records_match_current_manifest':True,
  'all_three_snapshot_OIDs_equal_for_each_protected_path':True,
  'current_export_bytes_match_raw_Git_archive':True,
  'actual_manifest_raw_sha256':h((S/'audit/review_packages/deployment-eof-v2/protected_git_baseline.json').read_bytes()),
  'path_list_source':manifest['path_list_source'],
  'snapshots':manifest['git_snapshots'],
  'new_export_verified_count':122,
  'original_wrong_legacy_declarations_retained':True,
  'legacy_declared_vs_Git_mismatch_count':3,
  'evidence':'first/independent_raw_Git_oracle.json; first/oracle_*; supplement_first/raw_*'
 },
 'tested_boundaries':[
  'Complete122-record exact equality against independent rawGit archive/SHA256/Git blobOID/bytes/old declaration; no three-file-only shortcut.',
  'Closed envelope/schema/kind/policy/count/source path-list metadata and immutable commit/tree snapshot map; bool/float/missing/extra/wrong snapshot and path aliases rejected.',
  'Closed record fields and canonical hashes/OIDs; byte counts bool/float/negative/over16MiB, changed legacy declaration, unknown/missing fields rejected.',
  'JSON duplicate keys/nonfinite values/BOM/nonUTF8/nesting/oversized bytes rejected. Original path-list BOM/line-ending/byte changes rejected. Valid whitespace outside JSON accepted.',
  'Private no.git protected-only view validates all122; each one-byte protected-file mutation independently rejects. All3 original disputed files also rejectCRLF and BOM changes. Pristine restored view still valid.',
  'Private no-checkout Git clone with deliberately changed worktree audit/data_exposure.json still reconstructs manifest from original immutable objects. Builder creates identical raw output, is idempotent for identical output and refuses a conflicting existing file without overwriting it.',
  'Unsafe traversal/absolute/drive/backslash/control/device/path-size names rejected; missing protected file rejected. Actual Windows junction to an owned sibling outside the protected root is rejected.',
  'Known empty Git blobOID and exact16MiB raw/hash and JSON bounds validated; overflow and mutable bytearray reject with static error messages.',
  'Nested Git directory, nongit directory and missing repository all reject; Git builder requires exact repository top-level.'
 ],
 'trust_boundary':{
  'published_manifest_must_be_pinned_to_reviewed_commit':True,
  'self_consistent_modified_manifest_and_modified_file_can_pass_offline_byte_checker':True,
  'interpretation':'Explicitly demonstrated and recorded as declared trust boundary, not a newWR. Offline verify_export trusts the independently pinned manifest table and is not a remote signature. A self-consistent invented table is exposed by independent fixedGit reconstruction; original published table rejects the same mutated file.',
  'actual_positive_negative_checks':['first test07 self-consistent invented table records protected122','first test07 M.build_manifest(G,RAW) differs from invented table','first test07 published original manifest rejects the mutated protected file']
 },
 'first_results':{'main_exit_code':read('first_execution.json')['exit_code'],'supplement_exit_code':read('supplement_execution.json')['exit_code'],'all_first_outputs_preserved':True,'harness_or_product_failures':[],'product_or_expected_hash_edits':False},
 'source_guard':{'raw_files':6379,'all_equal_root_fixed_Git_manifest':True,'before_after_both_suites_equal':True,'bytecode_created_in_source':False,'original_source_modified':False},
 'actual_recorded_child_commands':{'first':9,'supplement':4,'not_transitive_total':True,'evidence':['first/execution_records.json','supplement_first/execution_records.json']},
 'exact_source_definitions':definitions,
 'environment':{'python':sys.version,'os':platform.platform(),'native_Windows':True},
 'real_actions':{'QC_calls':0,'Research_executions':0,'LEAN_submissions':0,'platform_compile_calls':0,'market_provider_calls':0,'model_API_calls':0,'authoritative_budget_writes':0,'new_configuration_registrations':0,'production_source_edits':0,'private_synthetic_Git_clone_created':True},
 'unverified':['Source pinning and rawGit provenance are not remote signatures or independent supplier data authentication.','Full official candidate end-to-end Git exports/LF-checkout/newfixture replay and imported historical review preservation are separately owned by root/repro/archive agents; this child does not count them as its own execution.','No cloud v2 worker, real financial values/performance, fullUS200, financial vintage/publication/delivery/ingestion or final-test acceptance.','Native Windows junction rejection does not certify every filesystem race, OS-kill, network filesystem or power-loss condition.'],
 'WR28_scope':'The newly published122-record raw manifest fixes the rawGit declaration mismatch within this tested provenance scope; parent must combine clean whole-checker reproductions and preservation checks before closingWR28. Overallphase2 remains unaccepted.',
 'financial_evidence':False
}
(R/'report.json').write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
(R/'report.txt').write_text('WR28 rawGit provenance scope:8 methods/328 scenarios plus3/13 all first-run passed; no new finding.\nAll122records independently reconstructed; original3wronglegacy declarations remain as historical evidence.\nTrust boundary explicitly tested: pinned manifest required, hashes alone do not authenticate a self-consistent forged corpus.\n'+json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'report_sha256':h((R/'report.json').read_bytes()),'methods':11,'named_scenarios':341,'source_files':len(actual)}))
