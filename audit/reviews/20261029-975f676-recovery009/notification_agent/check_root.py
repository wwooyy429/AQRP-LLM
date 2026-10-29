from pathlib import Path
from hashlib import sha256
import json,re
R=Path(__file__).resolve().parent.parent
Q=[]
def read(p):return json.loads((R/p).read_text(encoding='utf-8'))
def check(name,condition,detail=None):
    Q.append({'check':name,'passed':bool(condition),'detail':detail})
    if not condition:raise AssertionError(name)
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
report_before=sha256((R/'notification_agent/report.json').read_bytes()).hexdigest()
check('own_original_report_hash',report_before=='bb9b909746905a930901efa0aee21b3884860d122aed3d3b1c56c4cf3ec5cb42')
records=read('root_execution_records.json')
check('six_root_commands',len(records)==6)
check('all_root_commands_exit_zero',all(x['exit_code']==0 for x in records))
for label in ('build_first','build_second','repository_verify'):
    check('root_fixed_working_copy_'+label,next(x for x in records if x['label']==label)['cwd']==str(R/'work_source'))
b1=read('build_first.stdout');b2=read('build_second.stdout')
check('two_builds_equal',b1==b2)
check('two_builds_idempotent',b1['config_changed'] is False and b2['config_changed'] is False)
identity=read('independent_identity.json');check('current_managed_count',identity['source_files']==213)
check('current_deployment_count',identity['deployment_files']==44 and b1['source_files']==44)
check('current_source_hash',identity['source_manifest_hash']=='d5a5ca0b1426c4333061932e280de08976762c801e6e26ff9c33cdcc74f2ef01')
check('current_configuration_hash',identity['configuration_hash']==b1['configuration_hash'])
repo=read('repository_verification.json');console=read('repository_verify.stdout')
check('repository_987_actual_output',bool(re.search(r'Ran 987 tests in [\d.]+s\n\nOK\n',repo['test_output'])))
check('repository_output_matches_stdout',repo['test_output']==console['test_output'])
check('repository_flags_and_source',repo['local_tests_passed'] is True and repo['financial_evidence'] is False and repo['source_hash']==identity['source_manifest_hash'])
check('repository_source_map_count',len(repo['source_files'])==213)
check('root_test_5_methods_26_scenarios',read('independent_storage_identity_result.json')['methods']==5 and read('independent_storage_identity_result.json')['named_scenarios']==26)
root_tests=read('independent_storage_identity_result.json')
check('root_test_no_fail_error_skip',not root_tests['failures'] and not root_tests['errors'] and not root_tests['skips'] and root_tests['actually_executed'] is True)
check('root_test_scenario_count_distinct',len(root_tests['scenarios'])==len(set(root_tests['scenarios']))==26)
test_script=(R/'independent_storage_identity.py').read_text()
check('root_tests_use_production_code',all(n in test_script for n in ['from qresearch.received_manifest import build_received_manifest','from qresearch.storage_capacity import check_capacity','sha256(canonical(rows)).hexdigest()']))
check('root_tests_no_developer_test_fixture_import',not re.search(r'from test_|import test_',test_script))
new_records={}
for name,hash_value in repo['source_files'].items():
    raw=(R/'source'/name).read_bytes()
    normalized=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')
    check('managed_raw_matches_materials_'+name,raw==(R/'materials'/name).read_bytes())
    check('managed_hash_'+name,sha256(normalized).hexdigest()==hash_value)
    new_records[name]=sha256(normalized).hexdigest()
check('independent_source_identity_rehash',sha256(canonical(new_records)).hexdigest()==identity['source_manifest_hash'])
dep=read('source/audit/deployment.json')
check('current_deployment_hash',sha256(canonical(dep['deployment_manifest'])).hexdigest()==identity['deployment_hash'])
for name,digest in dep['source_files'].items():
    raw=(R/'source/cloud'/name).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')
    check('deployment_source_'+name,sha256(raw).hexdigest()==digest)
old=read('source/audit/review_packages/storage-repair008/terminal/lean_summary.json')
check('old_43_worker_counts',old['deployment_verification']['declared_file_count']==old['deployment_verification']['verified_file_count']==old['deployment_verification']['eof_normalized_file_count']==43)
check('old_worker_not_raw_match',old['deployment_verification']['original_source_identity_match'] is False)
check('old_worker_distinct_deployment_and_source',old['identity']['source_manifest_hash']!=identity['source_manifest_hash'] and old['identity']['deployment_hash']!=identity['deployment_hash'])
materials=read('verify_materials.stdout')
check('materials_fixed_source',materials['source_commit']=='975f676d62b561689909744f9e7236290e3f5fcb')
check('materials_source_identity',materials['source_hash']==identity['source_manifest_hash'] and materials['source_files']==213)
check('materials_packet_and_budget',materials['packet_files']==38 and materials['journal_events']==71 and materials['configuration_cycle']=='3/13' and materials['lifetime_configurations']==16 and materials['research']=='17/20' and materials['lean']=='3/16')
check('materials_protection_and_gates',materials['protected_git_bytes_unchanged'] is True and materials['identity_and_recorded_invariants_passed'] is True and materials['independent_acceptance'] is False and materials['new_cloud_calls']==0 and materials['final_test_enabled'] is False)
guard=read('root_guard.json')
check('original_source_and_materials_guard',guard['source']=={'files':7045,'changed':[]} and guard['materials']=={'files':7076,'changed':[]})
check('only_generated_work_report_changed',guard['work_source']['changed']==['audit/stage_verification.json'])
maps=read('source_git_manifest.json')
for mode in ('source','materials'):
    mismatches=[p for p,expected in maps[mode]['files'].items() if sha256((R/mode/p).read_bytes()).hexdigest()!=expected['sha256']]
    check('fresh_full_raw_guard_'+mode,not mismatches,{'files':len(maps[mode]['files']),'mismatches':mismatches})
check('own_report_unchanged',report_before==sha256((R/'notification_agent/report.json').read_bytes()).hexdigest())
out={'scope':'Read-only root cross-check; no test rerun, no cloud calls, no change to original report.',
     'static_or_output_crosschecks':len(Q),'passed':sum(q['passed'] for q in Q),'findings':[],
     'own_report_sha256':report_before,'checks':Q}
(R/'notification_agent/root_crosscheck.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ['static_or_output_crosschecks','passed','findings']},indent=2))
