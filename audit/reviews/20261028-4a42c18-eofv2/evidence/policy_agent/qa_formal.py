"""Read-only scoped QA of the parent's assembled report; no product tests."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;P=R.parent
d=json.loads((P/'formal_report.json').read_bytes());local=json.loads((R/'report.json').read_bytes());text=(P/'formal_report.txt').read_text(encoding='utf-8')
expected='78a615a11c7478eed98d98a278405be9e834ab194f0a84485da30256ae064f49';rawhash=hashlib.sha256((P/'formal_report.json').read_bytes()).hexdigest();checks=[]
def check(name,value):checks.append({'name':name,'passed':bool(value)});assert value,name
check('current_report_hash',rawhash==expected)
check('fixed_code_identity',d['reviewed_source_commit']==local['reviewed_source_commit'])
check('baseline_identity',d['baseline_commit']==local['baseline_commit'])
check('archive_identity',d['evidence_commits']['archive']==local['archive_commit'])
check('raw_Git_counts_distinct_from_deployment',d['version_consistency']['identities']['candidate']['raw_files']==6179 and d['version_consistency']['identities']['baseline']['raw_files']==6158 and d['version_consistency']['identities']['candidate']['cloud_files']==34)
check('explicit_v2_policy',d['version_consistency']['new_manifest_schema']==2 and d['version_consistency']['new_policy']=='utf8_sig_universal_newlines_terminal_lf_v1' and d['version_consistency']['legacy_manifest_schema']==1)
tests={x['name']:x for x in d['tests']}
core=tests['independent_policy_core'];supp=tests['strict_digest_and_legacy_diagnostics_supplement']
check('core13_509_first_pass',core['methods']==13 and core['named_scenarios']==509 and core['result']=='passed_first_run')
check('supp3_20_scope',supp['methods']==3 and supp['named_scenarios']==20 and supp['result']=='passed_after_reviewer_fixture_label_correction')
check('local_first_supplement_preserved',local['first_results_preserved']['supplement']['error_records']==1 and local['first_results_preserved']['supplement']['exit_code']==1 and 'Windows reserved' in local['first_results_preserved']['reason'])
check('root_first_error_honest','2 passed/1 reviewer error' in d['first_results']['policy_supplement']and'nul'in d['first_results']['policy_supplement'])
check('no_product_or_protected_expected_fix',d['first_results']['product_source_or_expected_protected_hashes_changed']is False)
check('all_test_evidence_paths_exist',all((P/x['evidence']).is_file()for x in d['tests']))
check('two_baseline_candidate_programs',d['manual_and_static_checks']['core_same_manifest_baseline_candidate_MRE_processes']==2)
check('real_Windows_junction_count',d['manual_and_static_checks']['actual_Windows_junction_processes']==1 and local['actually_executed'][3]['exit_code']==0)
check('inherited_normalization_not_raw_identity_claim','v1保持原UTF8-sig/通用换行及严格EOF规则' in text and d['version_consistency']['raw_original_Git_bytes_unchanged_by_reviewer']is True)
check('local_and_PROJECT_remain_strict','本地freeze/首次prepare/扣额前/PROJECT坚持原身份' in text)
check('old_admission_not_reinterpreted',d['software_acceptance']['old_admission_reinterpreted']is False)
check('whole_candidate_NOT_accepted',d['software_acceptance']['candidate_wide_accepted']is False and d['software_acceptance']['candidate_delivery_validation']=='failed_WR28')
check('WR28_open_not_EOF_algorithm_failure',any(x['id']=='WR-28'and x['status']=='confirmed_open'and x['invalidates_all_tested_EOF_core_paths']is False for x in d['findings']))
check('phase2_NOT_accepted',d['software_acceptance']['phase2_overall']=='not_accepted')
check('original_failed_and_real_check_counts_unknown',d['platform_evidence_level']['original_LEAN']['actual_original_ledger_status']=='failed'and d['platform_evidence_level']['original_LEAN']['actual_seven_success_checks']is None and d['platform_evidence_level']['original_LEAN']['actual_orders']is None)
check('no_new_cloud_success',d['software_acceptance']['cloud_initialization_fix_verified']is False and d['platform_evidence_level']['new_candidate']['cloud_run_performed']is False)
check('no_financial_promotion',d['financial_evidence']is False and all(v is None for v in d['financial_metrics'].values())and d['software_acceptance']['final_test_enabled']is False)
out={'formal_report_sha256':rawhash,'formal_report_txt_sha256':hashlib.sha256((P/'formal_report.txt').read_bytes()).hexdigest(),'scope':'Core source-policy identity/counts/fixture correction/normalization and no candidate-wide promotion. No new product tests or platform calls.','checks':checks,'checks_count':len(checks),'all_passed':True,'new_product_test_methods':0,'QC_calls':0}
(R/'qa.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
(R/'qa.txt').write_text('Read-only core-policy formal report QA passed '+str(len(checks))+'/'+str(len(checks))+'.\nFormal JSON SHA256 '+rawhash+'\nFormal TXT SHA256 '+out['formal_report_txt_sha256']+'\n13/509 first pass and supplemental3/20 with original Windows reserved-name fixture error disclosed correctly. Strict v1 inherited UTF8-sig/universal-newline EOF identity is distinguished from unchanged physical raw Git bytes; v2 worker tolerance is not project tolerance or cloud success. WR28 confirmed-open delivery failure and overall phase2 not accepted are retained.\nNo new test execution, platform call, source or report mutation.\n',encoding='utf-8')
print(json.dumps({'checks':len(checks),'all_passed':True,'formal_report_sha256':rawhash}))
