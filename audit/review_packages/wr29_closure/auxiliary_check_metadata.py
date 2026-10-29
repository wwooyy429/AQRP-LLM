"""Developer auxiliary read-only closure consistency; no new independent acceptance."""
from pathlib import Path
import base64
import hashlib
import json
import subprocess
import sys

root = Path.cwd()
evidence = root / '.git' / 'repair-work' / 'wr29-close-scope'
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / 'tools'))
from stages import source_manifest

def read(name):
    return json.loads((root / name).read_text(encoding='utf-8-sig'))

checks = []
def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})

source = 'c2e63ac5f19901bd95e127069b5998452f7f9864'
source_hash = '9d0d6da95815ee77d993d823df616d575a3ec4f00f5e40e859a7858de02dad5f'
materials = 'f698a38a99c3ed8388c9403f2eda723b579c5eaf'
formal_path = root.parent / 'LLM审核' / 'review-c2e63ac-20261029' / 'formal_report.json'
formal = json.loads(formal_path.read_text(encoding='utf-8-sig'))
result = read('audit/review_results/wr29.json')
status = read('audit/current_review_status.json')
package = read('audit/current_review_package.json')
tracking = read('audit/review_tracking.json')
ready = read('audit/stage2_current_readiness.json')
closure = read('audit/wr29_closure_report.json')
next_work = read('audit/review_packages/wr29_closure/next_work.json')
initial = read('.git/repair-work/wr29-close-scope/initial_scope_snapshot.json')

check('formal report raw identity', hashlib.sha256(formal_path.read_bytes()).hexdigest() == '3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470')
check('fixed formal source and material', formal['reviewed_source_commit'] == source and formal['evidence_commits']['materials'] == materials)
manifest = source_manifest(root)
check('218 managed sources and unchanged source hash', len(manifest['source_files']) == 218 and manifest['source_hash'] == source_hash)
check('latest result version identity', result['source_commit'] == source and result['materials_commit'] == materials and result['source_manifest_hash'] == source_hash)
check('registered independent tests exactly match original formal tests', result['independent_tests'] == formal['tests'])
check('registered stage results exactly match original formal stages', result['stage_results'] == formal['stage_results'] and tracking['stage_acceptance'] == formal['stage_results'])
check('closed resolution exactly matches formal', result['WR29_resolution'] == formal['WR29_resolution'] == closure['WR29_resolution'] == status['closed_findings'][0] == tracking['closed_findings'][0] == ready['closed_software_findings_from_independent_reports'][0])
check('no new product finding in reviewed range', result['new_findings'] == formal['findings'] == status['known_open_findings'] == tracking['known_open_findings'] == ready['known_open_software_findings_from_independent_reports'] == [])
check('current pointers and source', status['latest_completed_review'] == package['latest_independent_result'] == tracking['latest_independent_result'] == 'audit/review_results/wr29.json' and status['latest_reviewed_source_commit'] == tracking['software_acceptance_bound_to_commit'] == source)
scope = result['acceptance_scope']
check('all current true approval flags carry the same precise finite scope', 'finite range only' in scope and ready['candidate_independent_acceptance'] is True and tracking['current_candidate']['independent_acceptance'] is True and ready['candidate_independent_acceptance_scope'] == ready['new_candidate_independent_acceptance_scope'] == tracking['current_candidate']['independent_acceptance_scope'] == status['software_acceptance_scope'] == tracking['acceptance_scope'] == scope)
check('only accepted stages 0 and 1', tracking['accepted_stages'] == [0, 1])
check('stage 2 and stages 3 through 7 remain unaccepted', result['stage_results'][2]['verdict'] == '局部软件通过；整体未通过' and all(x['verdict'] == '未验收' for x in result['stage_results'] if x['stage'] >= 3))
check('new registration not an independent acceptance', all(obj['metadata_archive_independently_accepted'] is False for obj in [result, status, package, tracking, closure]))
check('whole stage and finance remain false', all(obj['stage2_accepted'] is False and obj['financial_evidence'] is False for obj in [result, status, package, tracking, ready, closure]))
check('final and production execution gates remain false', all(value is False for value in ready['execution_gates'].values()) and all(obj['final_test_enabled'] is False for obj in [result, status, package, closure]) and tracking['final_evaluation_enabled'] is False and status['production_dispatch_enabled'] is False)
check('no deployment retry or submit enabled', ready['candidate_cloud_deployed'] is False and tracking['current_candidate']['cloud_deployed'] is False and ready['automatic_retry_enabled'] is False and ready['new_submit_allowed'] is False and ready['followup']['real_host_dispatch_integration_accepted'] is False)
check('registration did not rerun product tests', result['tests_repeated_this_registration'] is False and result['product_code_changed_this_registration'] is False and closure['source_code_changed'] is False and closure['tests_repeated_this_registration'] is False)
check('test counts explicitly overlap', result['test_counts_overlap_do_not_sum'] is True and closure['counts_overlap_do_not_sum'] is True)
budget = tracking['budget_usage']
check('registered budget values match formal without reading production Registry', budget['configuration_cycle'] == {'used': 3, 'limit': 13} and budget['lifetime_configurations'] == 16 and budget['research'] == {'used': 17, 'limit': 20} and budget['lean'] == {'used': 3, 'limit': 16} and budget['journal_events'] == 71 and ready['global_usage'] == {'configurations':16,'research':17,'lean':3} and ready['journal_events'] == 71)
check('old round remains closed', tracking['current_engineering_round']['status'] == next_work['old008_round_status'] == 'closed' and ready['current_round_closed'] is True)
check('new preparation has no dispatch authority or invented task IDs', next_work['dispatch_enabled'] is False and next_work['automatic_retry_enabled'] is False and next_work['new_round_registered'] is False and next_work['project_id'] is None and next_work['attempt_id'] is None and next_work['backtest_id'] is None)
check('active preparation points to current scoped work', ready['next_engineering_preparation'] == 'audit/review_packages/wr29_closure/next_work.json')
check('current review did not inherit prior host010 completion turn', tracking['actual_review_task'].get('completed_turn_id') != '01a18688-4f78-79e1-b014-83ff4ca9b3ae')
check('prior exposure facts preserved', tracking['prior_2024_2025_exposure_preserved'] is True and ready['prior_2024_2025_exposure_preserved'] is True and tracking['year2026_independence'] == ready['year2026_independence'] == 'not_certified')
for name in ['audit/review_results/host010.json', 'audit/review_handoffs/wr29.json']:
    check('historical file raw unchanged: ' + name, hashlib.sha256((root / name).read_bytes()).hexdigest() == initial['pending_paths_raw_sha256'][name])
for previous in ['previous_current_review_status', 'previous_current_review_package', 'previous_review_tracking', 'previous_stage2_current_readiness']:
    snapshot = root / 'audit' / 'review_packages' / 'wr29_closure' / (previous + '.snapshot.json')
    if snapshot.exists():
        name = {'previous_current_review_status':'audit/current_review_status.json','previous_current_review_package':'audit/current_review_package.json','previous_review_tracking':'audit/review_tracking.json','previous_stage2_current_readiness':'audit/stage2_current_readiness.json'}[previous]
        check('old active record snapshot preserved: ' + name, hashlib.sha256(snapshot.read_bytes()).hexdigest() == initial['pending_paths_raw_sha256'][name])

for name in ['developer_auxiliary_history', 'native_append_recovery', 'historical_findings', 'reviewer_corrections']:
    check('original formal limitations preserved in archived report: ' + name, json.loads(base64.b64decode((root / result['original_report_reference']).read_bytes()))[name] == formal[name])

out = {'kind':'developer_auxiliary_readonly_closure_consistency', 'new_independent_acceptance':False, 'passed':all(item['passed'] for item in checks), 'checks':checks, 'source_hash':manifest['source_hash'], 'source_files':len(manifest['source_files']), 'checked_metadata_raw_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['audit/review_results/wr29.json','audit/current_review_status.json','audit/current_review_package.json','audit/review_tracking.json','audit/stage2_current_readiness.json','audit/wr29_closure_report.json']}, 'new_cloud_calls':0, 'production_store_or_registry_reads_by_this_check':0, 'production_writes':0}
dest = evidence / ('metadata_check' + ('_' + sys.argv[1] if len(sys.argv)>1 else '') + '.json')
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=True))
