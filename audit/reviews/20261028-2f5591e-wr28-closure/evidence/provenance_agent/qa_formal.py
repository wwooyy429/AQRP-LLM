from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;P=R.parent;S=P/'source'
def read(path):return json.loads(path.read_bytes())
def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()
report=read(P/'formal_report.json');mine=read(R/'report.json');first=read(R/'first/results.json');supp=read(R/'supplement_first/results.json');checks=[]
def check(name,value):checks.append({'name':name,'passed':bool(value)})
expected='b60ea3474d297a7b23b027cb3c6b5885736a9a9d840d4ffe5265e9ce28220934'
check('exact_final_formal_hash',h(P/'formal_report.json')==expected)
check('fixed_delivery_SHA',report['reviewed_source_commit']=='2f5591e28c0748ac42caeae7bbf3977141d031cb')
check('production_SHA_distinct',report['production_source_commit']=='4a42c18f0b78bea2068d589bc12f1615712354c6')
p=report['independent_provenance'];m=mine['independent_Git_oracle']
check('all122_Git_records',p['raw_records_verified']==m['record_count']==122)
check('complete_actual_records_match',m['all_records_match_current_manifest']and m['all_three_snapshot_OIDs_equal_for_each_protected_path']and m['current_export_bytes_match_raw_Git_archive'])
check('manifest_raw_SHA',p['manifest_raw_sha256']==m['actual_manifest_raw_sha256']==h(S/'audit/review_packages/deployment-eof-v2/protected_git_baseline.json'))
check('pathlist_raw_SHA',p['old_path_list_raw_sha256']==m['path_list_source']['sha256']==h(S/'audit/review_packages/deployment-eof-v2/protected_before.json'))
check('pathlist_blobOID',p['old_path_list_Git_blob']==m['path_list_source']['git_blob_oid']=='2988aa67d03d862d4544abfad98145f355d2cccb')
check('all_three_exact_snapshots',p['fixed_snapshots']==m['snapshots'])
check('first8_methods328_scenarios',first['methods']==8 and first['named_scenarios']==328 and first['success']and first['failure_records']==first['error_records']==first['skipped']==0)
check('supplement3_methods13_scenarios',supp['methods']==3 and supp['named_scenarios']==13 and supp['success']and supp['failure_records']==supp['error_records']==supp['skipped']==0)
check('own_totals11_341',p['methods']==11 and p['named_scenarios']==341 and p['first_run_passed'])
rows={x['name']:x for x in report['tests']}
check('main_test_row8_328',rows['independent_provenance']['methods']==8 and rows['independent_provenance']['named_scenarios']==328 and rows['independent_provenance']['result']=='passed_first_run')
check('supplement_row3_13',rows['independent_outer_provenance_and_exact_bounds']['methods']==3 and rows['independent_outer_provenance_and_exact_bounds']['named_scenarios']==13 and rows['independent_outer_provenance_and_exact_bounds']['result']=='passed_first_run')
check('developer11_separate_population',rows['developer_audit_boundaries']['methods']==11 and rows['developer_audit_boundaries']['kind']=='developer_suite_independently_executed'and rows['independent_provenance']['kind']=='new_independent_synthetic_and_Git')
check('explicit_counting_limit','Independent11 provenance methods are separate from developer11 audit methods'in report['counting'])
check('all_reported_test_evidence_exists',all((P/x['evidence']).is_file()for x in report['tests']))
check('old3wrong_declarations_retained',report['WR28_resolution']['original_legacy_mismatches_retained']==m['legacy_declared_vs_Git_mismatch_count']==3 and m['original_wrong_legacy_declarations_retained'])
check('new_delivery_only_closure',report['WR28_resolution']['fixed_delivery_commit']==report['reviewed_source_commit']and report['WR28_resolution']['production_code_commit']==report['production_source_commit']and report['WR28_resolution']['scope']=='Raw Git protection declarations and reproducible audit delivery only')
check('old_failure_not_retroactively_approved','Retroactive approval of old4a42c18 delivery checker'in report['WR28_resolution']['not_granted'])
check('phase2_not_accepted',report['software_acceptance']['phase2_overall']=='not_accepted')
check('no_cloud_success_inferred',report['platform_evidence_level']['new_cloud_success']is None and not report['software_acceptance']['cloud_initialization_fix_verified'])
check('truth_boundary_qualified','changing both the manifest'in report['trust_boundary']and'fixedGit exposes'in report['trust_boundary']and'not a remote signature'in report['trust_boundary'])
check('self_consistent_acceptance_not_false_rejection',mine['trust_boundary']['self_consistent_modified_manifest_and_modified_file_can_pass_offline_byte_checker']and report['independent_CLI']['self_consistent_altered_manifest_and_source_accepted_as_trust_boundary']==1)
check('no_new_findings_from_our_scope',mine['findings']==[]and report['findings']==[])
check('financial_false_and_nulls',report['financial_evidence']is False and all(v is None for v in report['financial_metrics'].values()))
check('real_actions_zero',all(report['tool_capabilities'][k]==0 for k in ['QC_calls','Research_executions','LEAN_submissions','platform_compile_calls','market_provider_calls','model_API_calls','authoritative_budget_or_production_writes']))
check('final_gates_closed',all(report['software_acceptance'][k]is False for k in ['formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled']))
qa={'scope':'Readonly formal report QA for independent Git-provenance scope; no new product tests','formal_report_sha256':expected,'formal_report_txt_sha256':h(P/'formal_report.txt'),'child_report_sha256':h(R/'report.json'),'logical_static_checks':len(checks),'passed':sum(x['passed']for x in checks),'unit_methods_added':0,'checks':checks,'all_passed':all(x['passed']for x in checks),'product_or_formal_report_changed':False,'real_QC_calls':0}
(R/'qa.json').write_text(json.dumps(qa,indent=2)+'\n',encoding='utf-8')
text='Readonly provenance/formal QA '+str(qa['passed'])+'/'+str(qa['logical_static_checks'])+' passed.\nFormal JSON SHA256 '+expected+'\nFormal TXT SHA256 '+qa['formal_report_txt_sha256']+'\nAll122 records/raw manifest/path-list/GitOID/three snapshots match independently reconstructed evidence.8/328 plus3/13 first-pass and developer11 remain separate. Trust boundary and limitedWR28 closure accurate; phase2/cloud/data/financial acceptance not expanded.\nNo new product test, platform call, source or formal-report edit.\n'
(R/'qa.txt').write_text(text,encoding='utf-8');print(json.dumps({k:v for k,v in qa.items()if k!='checks'}));assert qa['all_passed']
