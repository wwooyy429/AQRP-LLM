"""Read-only report QA; no product tests or platform calls."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;ROOT=R.parent
raw=(ROOT/'formal_report.json').read_bytes();d=json.loads(raw);own=json.loads((R/'report.json').read_bytes());checks=[]
def ck(name,passed):checks.append({'name':name,'passed':bool(passed)})
ck('exact_report_hash',hashlib.sha256(raw).hexdigest()=='b60ea3474d297a7b23b027cb3c6b5885736a9a9d840d4ffe5265e9ce28220934')
a=d['archive_preservation'];b=d['budget_replay'];v=d['version_consistency'];p=d['platform_evidence_level'];w=d['WR28_resolution']
ck('review_fixed2f5591e',d['reviewed_source_commit']=='2f5591e28c0748ac42caeae7bbf3977141d031cb')
ck('production_code_stays4a42c18',d['production_source_commit']=='4a42c18f0b78bea2068d589bc12f1615712354c6')
ck('source_bf19_unchanged',d['source_manifest_hash']=='bf19f3027e5fa21ded361c4cbb1edc6264a06def00c306b72d62c52ce8af9b5a')
ck('three_source_population_counts',[v['candidate_files'],v['baseline_files'],v['archive_files']]==[6379,6180,6414])
ck('audit_only_and287',v['cloud_config_tools_tests_docs_README_changes']==[]and v['main_production_history_budget_exposure_union_raw_files_unchanged']==287)
ck('static58_metadata5_not_unit',a['logical_static_checks']==a['static_passed']==58 and a['private_Memory_metadata_checks']==5 and a['unit_methods']==0)
ck('copy167_original_bytes700596',a['copied_original_non_source_files']==167 and a['copied_original_bytes']==700596)
ck('supplement1_plus_index168',a['additional_user_delivery_text_files']==1 and a['compact_copied_index_count']==168)
ck('seal173_actual174',a['compact_seal_entries']==173 and a['compact_actual_files']==174)
ck('original_zip_hash_exact',a['original_ZIP_SHA256']==own['compact_archive']['original_zip_sha256'])
ck('zip18685CRC_and18517_Git_maps',a['original_ZIP_manifest_entries_verified']==18685 and a['original_ZIP_CRC_passed']is True and a['original_three_Git_source_blobs_verified']==18517)
ck('omission_documented_duplicate_trees_and_maps','18517'in a['omitted_only']and'two large maps'in a['omitted_only']and'All167'in a['omitted_only'])
ck('old_bad_manifest_and_result_unchanged',a['original_bad_manifest_unchanged']is True and a['original_reconciliation_result_unchanged']is True and a['original_failed_checker_kept']is True)
ck('later_archive_originals9_unchanged',a['candidate_to_archive_originals_files_identical']==9 and a['compact_candidate_to_archive_raw_equal']is True)
ck('old_open_status_preserved',a['old_review_status_preserved']=='confirmed_open_at_original_SHA')
old_path=ROOT/'source/audit/reviews/20261028-4a42c18-eofv2/evidence/formal_report.json';old=json.loads(old_path.read_bytes())
ck('actual_old_json_still_open_failed',old['findings'][0]['status']=='confirmed_open'and old['software_acceptance']['candidate_delivery_validation']=='failed_WR28'and hashlib.sha256(old_path.read_bytes()).hexdigest()==own['compact_archive']['original_formal_report_sha256'])
ck('new_close_scoped_to2f_only',w['status']=='fixed_verified_closed'and w['fixed_delivery_commit']==d['reviewed_source_commit']and w['scope']=='Raw Git protection declarations and reproducible audit delivery only')
ck('old_review_not_retroapproved',any('Retroactive approval'in x for x in w['not_granted']))
ck('48_event_current_hash',b['events']==48 and b['journal_sha256']==own['budget']['journal_sha256'])
ck('46_prefix_preserved',b['original46_raw_bytes_preserved']is True and b['original46_prefix_sha256']==own['budget']['old46_sha256'])
ck('usage_caps_closed_unchanged',b['usage']==dict(configurations=12,research=15,lean=2)and b['limits']==dict(configurations=12,research=20,lean=16)and b['round_status']=='closed')
ck('no_event_debit_refund_new_config',b['new_events']==b['new_debits']==b['refunds']==b['configuration_capacity_remaining']==0 and b['new_configuration_registered']is False)
ck('old_admission_failed_runtime_retained',b['old_failed_admission_unchanged']is True and p['old_ledger_status']=='failed'and p['old_runtime_source']=='662ccd876b67ca0949f921a53c4c33df37cfbbf1'and p['old_manifest_schema']==1)
ck('actual_checks_orders_and_new_success_null',p['actual_successful_LEAN_checks']is None and p['actual_orders']is None and p['new_cloud_success']is None and p['EOF_v2_registered_or_deployed']is False)
ck('all3_reviewer_stops_disclosed',all(x in d['first_results']['archive_reviewer_errors']for x in ['250','287','user_delivery','readiness key','58 static+5']))
ck('first_error_files_preserved',all((R/n).is_file()for n in own['first_results_preserved']['files']))
ck('phase2_not_upgraded',d['software_acceptance']['phase2_overall']=='not_accepted'and d['software_acceptance']['cloud_initialization_fix_verified']is False)
ck('financial_and_final_closed',d['financial_evidence']is False and all(x is None for x in d['financial_metrics'].values())and d['software_acceptance']['final_test_enabled']is False)
ck('no_live_or_real_mutation',all(d['tool_capabilities'][x]==0 for x in ['QC_calls','Research_executions','LEAN_submissions','platform_compile_calls','live_terminal_or_log_reads','market_provider_calls','model_API_calls','authoritative_budget_or_production_writes']))
ck('all5_test_evidence_exist',len(d['tests'])==5 and all((ROOT/t['evidence']).is_file()for t in d['tests']))
ck('original_source_maps_and_no_product_edits_reported',v['reviewer_changed_original_Git_files']is False and d['first_results']['product_source_or_original_expected_hashes_changed_by_reviewer']is False)
out={'formal_report_sha256':hashlib.sha256(raw).hexdigest(),'formal_text_sha256':hashlib.sha256((ROOT/'formal_report.txt').read_bytes()).hexdigest(),'checks':checks,'checks_passed':sum(c['passed']for c in checks),'checks_total':len(checks),'all_passed':all(c['passed']for c in checks),'QA_kind':'Readonly static cross-check only; no new product tests or platform calls','source_or_report_edits':False}
(R/'qa.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
lines=['Archive/budget formal-report readonly QA',out['formal_report_sha256'],f"{out['checks_passed']}/{out['checks_total']} static QA checks passed; no product tests/platform calls.",out['formal_text_sha256']]
lines.extend(c['name']+': '+str(c['passed'])for c in checks)
(R/'qa.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items()if k!='checks'}));assert out['all_passed']
