from pathlib import Path
import ast,hashlib,json,platform,sys
R=Path(__file__).resolve().parent;S=R.parent/'source'
def read(p):return json.loads((R/p).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
first=read('first/results.json');extra=read('additional_first/results.json')
assert first['success']and extra['success']
catalog=json.loads((S/'config/source_catalog.json').read_bytes())
caps=json.loads((R/'capabilities.stdout').read_bytes())
source_manifest=json.loads((R.parent/'source_git_manifest.json').read_bytes())
actual={p.relative_to(S).as_posix():sha(p)for p in S.rglob('*')if p.is_file()}
assert actual==source_manifest['files']
calls=[]
for parent in ['cloud','tools']:
 for p in (S/parent).rglob('*.py'):
  for n in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
   if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='audit_data_certification':calls.append({'path':p.relative_to(S).as_posix(),'line':n.lineno})
cited=['cloud/qresearch/collection.py','cloud/qresearch/historical_source.py','cloud/qresearch/ingestion.py','cloud/qresearch/data_certification.py','tools/data_certification.py','config/source_catalog.json','docs/collection_observations.md']
static={
 'catalog_fields':len(catalog['fields']),
 'financial_numeric_catalog_count':sum(v.get('role')=='as_reported_financial_value'for v in catalog['fields'].values()),
 'capabilities_cli':caps,
 'canonical_cli_commands':['capabilities','validate-plan'],
 'certification_computation_kernel':'Implemented bounded audit_data_certification and summarize_certification_scope; this is distinct from charged native-worker dispatch integration.',
 'charged_certification_worker_native_bridge':'No canonical dispatch command; capabilities ready_to_dispatch=false and budget_admission_performed=false. Existing internal audit call only from scope-summary replay. Phase2 native certification task bridge remains missing.',
 'direct_audit_calls_in_cloud_tools':calls,
 'source_exact_line_evidence':{
  'collection_occurrences_and_sequence':'cloud/qresearch/collection.py:303-331',
  'collection_cache_revalidation':'cloud/qresearch/collection.py:372-421',
  'collection_no_auto_retry':'cloud/qresearch/collection.py:445-482',
  'native_DST_crop_and_retention':'cloud/qresearch/historical_source.py:273-318',
  'native_physical_request_window':'cloud/qresearch/historical_source.py:131-151',
  'v2_unique_converter_refusal':'cloud/qresearch/historical_source.py:340-343',
  'unknown_actual_receipts_preserved':'cloud/qresearch/historical_source.py:365-370',
  'unknown_PIT_refusal':'cloud/qresearch/ingestion.py:358-371',
  'catalog_capability_numeric_role':'cloud/qresearch/data_certification.py:724-738',
  'canonical_metadata_only_CLI':'tools/data_certification.py:14-33',
  'ambiguity_documented':'docs/collection_observations.md:33-43'},
 'cited_source_raw_sha256':{p:sha(S/p)for p in cited},
 'full_fixed_source_unchanged':True,'full_fixed_source_files_checked':len(actual),
 'static_matrix_adds_unit_methods':0}
(R/'static_report.json').write_text(json.dumps(static,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
report={
 'reviewed_source_commit':source_manifest['commit'],
 'scope':'New independent synthetic occurrence-v2/historical-source/cache/unique-converter/PIT adversarial tests and current certification-capability inspection.',
 'conclusion':'All newly executed bounded software scopes passed on first run. No new product defect confirmed. Data certification and overall phase2 remain unaccepted.',
 'actually_executed':[
  {'suite':'adversarial_occurrence','methods':first['methods'],'passed_methods':first['passed_methods'],'named_scenario_checks':first['named_scenario_checks'],'unittest_subcases':None,'failure_records':first['failure_records'],'error_records':first['error_records'],'skipped':first['skipped'],'result':'first/results.json','execution':'first_execution.json','first_run':True},
  {'suite':'additional_closed_contracts','methods':extra['methods'],'passed_methods':extra['passed_methods'],'named_scenario_checks':extra['named_scenario_checks'],'unittest_subcases':None,'failure_records':extra['failure_records'],'error_records':extra['error_records'],'skipped':extra['skipped'],'result':'additional_first/results.json','execution':'additional_execution.json','first_run':True},
  {'kind':'metadata_only_capabilities_CLI','CLI_processes':1,'unit_methods':0,'execution':'capabilities_execution.json','result':'capabilities.stdout'}],
 'new_independent_methods':13,'new_named_scenario_checks':109,
 'cases':[
  '64 seeded combinations:16 deterministic seeds x4 batch sizes;3 snapshots including both fall-DST01:30 offsets; per-row retention, direct-comparison duplicate/conflict/missing oracle, exact batch counts and read-only cache replay.',
  '8 ordinal input mutants:reset/gap/negative/bool/float/numpy integer/start1/boundary overflow, failure intent retained and no retry.',
  '8 canonical rehashed manifest mutations:duplicate/conflict/missing/count type/certification/provider calls/unknown data/policy.',
  '10 content-rehashed batch mutations:ordinal/SID/unknown field/missing field/numeric boolean/text/date sentinel/batch order/end boundary/schema type.',
  'Partial second-window failure preserves completed first window and partial immutable objects; both producer retry and read-only replay stop at unfinished intent without fetching.',
  'Exact and overflowing same-snapshot limits plus cross-snapshot total-window limits.',
  'Synthetic native QB interface through actual QuantConnectSnapshotSource and collector:expanded-left crop avoids poison value access; both DST clocks retain source ordinals and duplicate/conflict counts.',
  'v1 native duplicate refusal, v2 snapshot bound, narrow0x0 sentinel accepted, named empty frame rejected.',
  'Occurrence row refused by unique-liquidity converter; legitimate3-column observation preserves unknown receipts and is blocked from causal liquidity_asof.',
  'Plan identity changes for source hash, bounds, data version and catalog role; other-plan read-only miss performs no store write.',
  'Equivalent UTC instants normalize to NY and share ordinal sequence; noncanonical stored UTC aliases rejected even after content rehash.',
  'Unselected supplier property is never accessed; no implicit HasFundamentalData exclusion; duplicate observations remain retained.'
 ],
 'counting':'13 methods and109 named scenarios are this agent\'s current executions, not unique global cases. Scenario records are explicitly not measured unittest-subTest count. Seed variants and batch variants overlap semantically.1 capabilities CLI is metadata execution, not an additional software unit method.',
 'prior_evidence':'Earlier data_agent14/54+3/18 and8-date daily-file model are not rerun or counted here. Current fixed source raw bytes equal the same SHA reviewed previously; earlier finite conclusions may be separately cited by parent.',
 'static':static,
 'findings':[],
 'first_failures':{'product_failures':[],'harness_failures':[],'all_first_outputs_preserved':True},
 'unverified':[
  'No real SDK/QC/market/model/LEAN worker executed or platform state read by this agent. The fake QB interface demonstrates actual source-adapter logic only.',
  'Permanent-SID economic ambiguity, historicalUS200 and financial-vintage/publication/delivery/ingestion authenticity not certified.',
  'Rehashed semantic-inconsistency detection is not external authenticity or tamper-proof storage certification; a self-consistent forged corpus cannot establish true vendor evidence.',
  'Numeric financial field catalog remains0; bounded certification computation exists, canonical charged native certification dispatch bridge remains absent.',
  'No real row-level cloud recount, financial IC/return/cost/risk/NAV or independent final-window evaluation.'
 ],
 'source_unchanged':True,
 'real_actions':{'QC_calls':0,'market_calls':0,'model_calls':0,'Research_executions':0,'LEAN_submissions':0,'LEAN_terminal_or_log_reads':0,'authoritative_budget_writes':0,'production_edits':0},
 'financial_evidence':False,
 'environment':{'python':sys.version,'platform':platform.platform()},
 'evidence_hashes':{p.relative_to(R).as_posix():sha(p)for p in R.rglob('*')if p.is_file()and p.name not in {'report.json','report.txt'}}}
(R/'report.json').write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
(R/'report.txt').write_text('Independent phase2 data recheck:13 methods/109 named scenario checks, first-run all pass; no new finding.\nMetadata-only capabilities CLI executed once; financial numeric catalog0 and no ready-to-dispatch certification bridge.\nNo actual QC/market/model/LEAN or production/budget actions. Overall phase2 and data/financial certification remain unaccepted.\n\n'+json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'methods':13,'named_scenarios':109,'findings':[],'source_files_unchanged':len(actual),'report_sha256':sha(R/'report.json')}))
