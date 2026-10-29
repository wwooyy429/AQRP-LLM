"""Read-only registration checks; does not grant a new software acceptance."""
import argparse
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
from stages import source_manifest
from qresearch.artifacts import decode_events

SOURCE='c2e63ac5f19901bd95e127069b5998452f7f9864'
HASH='9d0d6da95815ee77d993d823df616d575a3ec4f00f5e40e859a7858de02dad5f'
ORIGINAL='2d1d3060dbc7eb136c1dee61f0647977528b8aad'
PREFIX='audit/review_packages/wr29_closure/'
ARCHIVE='audit/reviews/20261029-c2e63ac-wr29-closure/'
SCOPE='WR29 original factory identity defect; independently tested local CLI/stdio/API finite range only'

def require(condition,label):
    if not condition:raise ValueError(label)
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
def blob(commit,name):return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)

def validate_resolution(value):
    require(value['id']=='WR-29' and value['status']=='fixed_verified_closed','No independent WR29 closure')
    require(value['fixed_source_commit']==SOURCE and value['original_source_commit']==ORIGINAL,'Wrong closure versions')
    for name,expected in [('original_expected_exits',[0,0,0]),('original_actual_exits',[0,2,2]),('fixed_actual_exits',[0,0,0])]:
        require(type(value[name]) is list and all(type(n) is int for n in value[name]) and value[name]==expected,'Original expectation or result changed')
    require(value['original_script_and_success_expectations_unchanged'] is True,'Original success expectation must remain')

def validate_scope(result,ready,tracking,package):
    validate_resolution(result['WR29_resolution'])
    require(result['source_commit']==SOURCE and result['source_manifest_hash']==HASH,'Wrong approved code')
    require(result['new_findings']==[] and result['acceptance_scope']==SCOPE,'Closure scope was broadened')
    require(ready['candidate_independent_acceptance'] is True and ready['candidate_independent_acceptance_scope']==SCOPE,'Ambiguous local approval')
    require(ready['candidate_runtime_source_commit']==SOURCE and ready['candidate_cloud_deployed'] is False,'No new runtime deployment')
    require(tracking['known_open_findings']==[] and tracking['software_acceptance_bound_to_commit']==SOURCE,'Stale current finding/source')
    require(tracking['actual_review_task']==result['actual_review_task']
            and result['actual_review_task']['completed_turn_id']=='01a1879e-1025-7ce2-bfef-06fea9080a7c','Stale actual review turn')
    require(package['WR29_independently_closed'] is True and package['source_commit']==SOURCE,'Wrong active package')
    for value in (result,ready,tracking,package):
        require(value['stage2_accepted'] is False and value['financial_evidence'] is False,'Whole-stage or financial approval prohibited')
    for value in (result,tracking,package):
        require(value['metadata_archive_independently_accepted'] is False,'New registration is not independently approved')
    require(result['final_test_enabled'] is False and package['final_test_enabled'] is False
            and tracking['final_evaluation_enabled'] is False,'Final gate must remain closed')
    require(all(v is False for v in ready['execution_gates'].values()),'Execution gates must remain closed')
    require(ready['automatic_retry_enabled'] is False and ready['new_submit_allowed'] is False,'No retry/submit authorization')

def verify():
    manifest=source_manifest(ROOT)
    require(manifest['source_hash']==HASH,'Managed source changed after independent review')
    for name,expected in manifest['source_files'].items():
        text=blob(SOURCE,name).decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
        require(sha256(text.encode()).hexdigest()==expected,'Source blob differs: '+name)
    archive=read(ARCHIVE+'archive_manifest.json')
    require(archive['selected_archive_not_complete_original_bundle'] is True,'Archive scope enlarged')
    for name,entry in archive['files'].items():
        raw=(ROOT/(ARCHIVE+name)).read_bytes()
        require(len(raw)==entry['bytes'] and sha256(raw).hexdigest()==entry['sha256'],'Selected representation differs: '+name)
    for name,entry in archive['original_artifacts'].items():
        raw=base64.b64decode((ROOT/(ARCHIVE+entry['raw_base64_path'])).read_bytes()) if 'raw_base64_path' in entry else (ROOT/(ARCHIVE+entry['readable_path'])).read_bytes()
        require(len(raw)==entry['original_bytes'] and sha256(raw).hexdigest()==entry['original_sha256'],'Original recovery differs: '+name)
    expected_set=set(archive['files'])|{'archive_manifest.json'}
    actual={p.relative_to(ROOT/ARCHIVE).as_posix() for p in (ROOT/ARCHIVE).rglob('*') if p.is_file() and '.baiduyun.' not in p.name}
    require(actual==expected_set,'Selected membership differs; only declared Sync sidecars excluded')
    item=archive['original_artifacts']['formal_report.json']
    raw=base64.b64decode((ROOT/(ARCHIVE+item['raw_base64_path'])).read_bytes()) if 'raw_base64_path' in item else (ROOT/(ARCHIVE+item['readable_path'])).read_bytes()
    require(sha256(raw).hexdigest()=='3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470','Original formal report changed')
    formal=json.loads(raw);validate_resolution(formal['WR29_resolution'])
    result,ready,tracking,package=(read(n) for n in ['audit/review_results/wr29.json','audit/stage2_current_readiness.json','audit/review_tracking.json','audit/current_review_package.json'])
    validate_scope(result,ready,tracking,package)
    require(result['WR29_resolution']==formal['WR29_resolution'],'Registration differs from original closure')
    require(formal['findings']==[] and formal['software_acceptance']['stage2_overall']=='未通过','Independent outcome enlarged')
    require(package['kind']=='WR29_exact_source_closure_registration','Wrong current registration package')
    proof=read(PREFIX+'protected_history.json')
    for name,record in proof['files'].items():
        previous=blob(proof['prior_commit'],name);current=(ROOT/name).read_bytes()
        require(sha256(previous).hexdigest()==record['prior_git_sha256'],'Prior protection hash changed')
        if name=='audit/data_exposure.json':require(json.loads(current)==json.loads(previous),'Exposure facts changed')
        else:require(current==previous,'Budget/ledger original bytes changed')
    require(len(decode_events((ROOT/'audit/runtime/registry/events.jsonl').read_bytes()))==71,'New budget events')
    budget=read('config/budget.json')
    require(budget['configuration_cycle']['usage']['total']==3 and budget['usage']['configuration_budget_charges']==16
            and budget['usage']['research_execution_attempts']==17 and budget['usage']['lean_submission_attempts']==3,'Quota changed')
    require(budget['limits']['full_configurations']==13 and budget['limits']['research_execution_attempts']==20
            and budget['limits']['lean_submission_attempts']==16,'Caps changed')
    next_work=read(PREFIX+'next_work.json')
    require(next_work['dispatch_enabled'] is False and next_work['new_round_registered'] is False
            and next_work['project_id'] is None and next_work['attempt_id'] is None and next_work['backtest_id'] is None,'Prepared work became execution authority')
    # Preserve the original open/failure and pending records by fixed immutable Git.
    for name in ['audit/review_results/host010.json','audit/review_handoffs/wr29.json']:
        require((ROOT/name).read_bytes()==blob(proof['prior_commit'],name),'Historical failure/handoff changed')
    packet=read(PREFIX+'packet_manifest.json')
    for name,expected in packet['raw_files'].items():require(sha256((ROOT/name).read_bytes()).hexdigest()==expected,'Packet bytes changed: '+name)
    print(json.dumps({'source_commit':SOURCE,'source_hash':HASH,'source_files':len(manifest['source_files']),
        'WR29_independently_closed':True,'closure_scope':SCOPE,'review_originals_restored':len(archive['original_artifacts']),
        'packet_files':len(packet['raw_files']),'stage2_accepted':False,'metadata_archive_independently_accepted':False,
        'journal_events':71,'configuration_cycle':'3/13','lifetime_configurations':16,'Research':'17/20','LEAN':'3/16',
        'new_cloud_calls':0,'financial_evidence':False,'final_test_enabled':False}))

class ClosureBoundaryTests(unittest.TestCase):
    def resolution(self):return {'id':'WR-29','status':'fixed_verified_closed','fixed_source_commit':SOURCE,'original_source_commit':ORIGINAL,
        'original_expected_exits':[0,0,0],'original_actual_exits':[0,2,2],'fixed_actual_exits':[0,0,0],'original_script_and_success_expectations_unchanged':True}
    def fixture(self):
        task={'completed_turn_id':'01a1879e-1025-7ce2-bfef-06fea9080a7c'}
        r={'actual_review_task':deepcopy(task),'WR29_resolution':self.resolution(),'source_commit':SOURCE,'source_manifest_hash':HASH,'new_findings':[],'acceptance_scope':SCOPE,'stage2_accepted':False,'financial_evidence':False,'metadata_archive_independently_accepted':False,'final_test_enabled':False}
        d={'candidate_independent_acceptance':True,'candidate_independent_acceptance_scope':SCOPE,'candidate_runtime_source_commit':SOURCE,'candidate_cloud_deployed':False,'stage2_accepted':False,'financial_evidence':False,'execution_gates':{'final_test_enabled':False},'automatic_retry_enabled':False,'new_submit_allowed':False}
        t={'actual_review_task':deepcopy(task),'known_open_findings':[],'software_acceptance_bound_to_commit':SOURCE,'stage2_accepted':False,'financial_evidence':False,'metadata_archive_independently_accepted':False,'final_evaluation_enabled':False}
        p={'WR29_independently_closed':True,'source_commit':SOURCE,'stage2_accepted':False,'financial_evidence':False,'metadata_archive_independently_accepted':False,'final_test_enabled':False}
        return r,d,t,p
    def test_valid_scoped_closure(self):validate_scope(*self.fixture())
    def test_wrong_source(self):
        values=self.fixture();values[0]['WR29_resolution']['fixed_source_commit']=ORIGINAL
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_open_is_not_closure(self):
        values=self.fixture();values[0]['WR29_resolution']['status']='implemented_pending_independent_recheck'
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_stale_review_turn(self):
        values=self.fixture();values[2]['actual_review_task']['completed_turn_id']='obsolete_turn'
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_expectation_not_rewritten(self):
        values=self.fixture();values[0]['WR29_resolution']['original_expected_exits']=[0,2,2]
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_bool_is_not_exit_code(self):
        values=self.fixture();values[0]['WR29_resolution']['fixed_actual_exits']=[False,False,False]
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_no_whole_stage_approval(self):
        values=self.fixture();values[1]['stage2_accepted']=True
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_approval_requires_precise_scope(self):
        values=self.fixture();values[1]['candidate_independent_acceptance_scope']='passed'
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_new_registration_not_independently_approved(self):
        values=self.fixture();values[3]['metadata_archive_independently_accepted']=True
        with self.assertRaises(ValueError):validate_scope(*values)
    def test_final_and_submit_stay_closed(self):
        for path in ['final','submit']:
            with self.subTest(path=path):
                values=self.fixture()
                if path=='final':values[1]['execution_gates']['final_test_enabled']=True
                else:values[1]['new_submit_allowed']=True
                with self.assertRaises(ValueError):validate_scope(*values)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:unittest.main(argv=[sys.argv[0]],verbosity=2)
    else:verify()
