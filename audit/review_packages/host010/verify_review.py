"""Read-only checks for the host010 candidate and the prior scoped review.

No Registry is opened; no provider is contacted. Identity checks do not issue
independent acceptance. Run from a complete fixed Git checkout of this packet.
"""
import argparse
import base64
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

APPROVED='975f676d62b561689909744f9e7236290e3f5fcb'
ARCHIVE='audit/reviews/20261029-975f676-recovery009/'
PREFIX='audit/review_packages/host010/'

def require(condition, label):
    if not condition: raise ValueError(label)

def read(name): return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
def git_blob(commit,name): return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)

def validate_scope(result, readiness, tracking):
    require(result['source_commit']==APPROVED,'Prior scope must pin the original approved source')
    require(result['verdict']=='passed_in_independently_tested_offline_scope','Unreviewed approval type')
    require(result['actual_review_task']['kind']=='codex'
            and result['previous_chatgpt_task_was_handoff_only'] is True,'Review execution provenance changed')
    for document in (result,readiness,tracking):
        require(document['stage2_accepted'] is False and document['financial_evidence'] is False,'Whole-system approval prohibited')
    require(result['final_test_enabled'] is False
            and readiness['execution_gates']['final_test_enabled'] is False
            and tracking['final_evaluation_enabled'] is False,'Final test must remain closed')
    require(result['new_host_implementation_inherits_this_acceptance'] is False,'New source cannot inherit old approval')
    require(readiness['candidate_independent_acceptance'] is False
            and tracking['current_candidate']['independent_acceptance'] is False,'New host awaits its own review')
    require(readiness['candidate_cloud_deployed'] is False
            and tracking['current_candidate']['cloud_deployed'] is False,'No new cloud evidence')
    require(tracking['reviewed_source_commit']==APPROVED
            and tracking['software_acceptance_bound_to_commit']==APPROVED,'Approval was rebound')


def verify():
    package=read('audit/current_review_package.json')
    require(package['kind']=='host010_offline_software_candidate','Wrong current packet')
    source=package['source_commit']
    require(type(source) is str and len(source)==40,'Missing fixed candidate source')
    manifest=source_manifest(ROOT)
    require(manifest['source_hash']==package['source_manifest_hash'],'Current candidate source differs')
    for name,expected in manifest['source_files'].items():
        normalized=git_blob(source,name).decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
        require(sha256(normalized).hexdigest()==expected,'Pinned source differs: '+name)
    archive=read(ARCHIVE+'archive_manifest.json')
    require(archive['selected_archive_not_complete_original_bundle'] is True,'Archive scope enlarged')
    for name,record in archive['files'].items():
        raw=(ROOT/(ARCHIVE+name)).read_bytes()
        require(len(raw)==record['bytes'] and sha256(raw).hexdigest()==record['sha256'],'Archive representation differs: '+name)
    for name,record in archive['original_artifacts'].items():
        raw=base64.b64decode((ROOT/(ARCHIVE+record['raw_base64_path'])).read_bytes(),validate=False) if 'raw_base64_path' in record else (ROOT/(ARCHIVE+record['readable_path'])).read_bytes()
        require(len(raw)==record['original_bytes'] and sha256(raw).hexdigest()==record['original_sha256'],'Original recovery differs: '+name)
    original=base64.b64decode((ROOT/(ARCHIVE+'formal_report.json.raw.base64')).read_bytes())
    require(sha256(original).hexdigest()=='ef0fa58a5e87d0930ed7b6c6ddbd11a1b96ecc0ea56678dd7989dbee2a890057','Original report changed')
    formal=json.loads(original)
    require(formal['findings']==[] and formal['reviewed_source_commit']==APPROVED,'Independent result mismatch')
    result,ready,tracking=(read(n) for n in ('audit/review_results/recovery009.json','audit/stage2_current_readiness.json','audit/review_tracking.json'))
    validate_scope(result,ready,tracking)
    proof=read(PREFIX+'protected_history.json')
    for name,record in proof['files'].items():
        previous=git_blob(proof['prior_commit'],name)
        raw=(ROOT/name).read_bytes()
        require(sha256(previous).hexdigest()==record['prior_git_sha256'],'Prior protection hash changed')
        require(git_blob(source,name)==previous,'Protected candidate Git bytes changed: '+name)
        if name=='audit/data_exposure.json': require(json.loads(raw)==json.loads(previous),'Exposure facts changed')
        else: require(raw==previous,'Budget or journal raw bytes changed: '+name)
    events=decode_events((ROOT/'audit/runtime/registry/events.jsonl').read_bytes())
    require(len(events)==71,'New Registry events added')
    budget=read('config/budget.json')
    require(budget['configuration_cycle']['usage']['total']==3
            and budget['usage']['configuration_budget_charges']==16
            and budget['usage']['research_execution_attempts']==17
            and budget['usage']['lean_submission_attempts']==3,'Real quota changed')
    plan=read(PREFIX+'next_engineering_preparation.json')
    require(plan['execution_enabled'] is False and plan['registered'] is False
            and plan['no_admission_or_debit_performed'] is True,'Proposed work is not an authorization')
    require(plan['attempt_id'] is None and plan['external_backtest_id'] is None and plan['project_id'] is None,'Invented future task identity')
    tests=read(package['test_report'])
    require(tests['passed'] is True and tests['source_manifest_hash']==manifest['source_hash'],'Test/source mismatch')
    packet=read(package['packet_manifest'])
    for name,expected in packet['raw_files'].items():
        require(sha256((ROOT/name).read_bytes()).hexdigest()==expected,'Packet bytes changed: '+name)
    print(json.dumps({'candidate_source':source,'source_hash':manifest['source_hash'],
        'source_files':len(manifest['source_files']),'review_originals_restored':len(archive['original_artifacts']),
        'packet_files':len(packet['raw_files']),'prior_approved_source':APPROVED,
        'prior_approved_scope':'independently tested offline range only',
        'new_host_independent_acceptance':False,'stage2_accepted':False,
        'registry_events':71,'configuration_cycle':'3/13','lifetime_configurations':16,
        'research':'17/20','lean':'3/16','financial_evidence':False,'final_test_enabled':False}))


class ScopeBoundaryTests(unittest.TestCase):
    def fixture(self):
        r={'source_commit':APPROVED,'verdict':'passed_in_independently_tested_offline_scope','actual_review_task':{'kind':'codex'},'previous_chatgpt_task_was_handoff_only':True,'stage2_accepted':False,'financial_evidence':False,'final_test_enabled':False,'new_host_implementation_inherits_this_acceptance':False}
        d={'stage2_accepted':False,'financial_evidence':False,'execution_gates':{'final_test_enabled':False},'candidate_independent_acceptance':False,'candidate_cloud_deployed':False}
        t={'stage2_accepted':False,'financial_evidence':False,'final_evaluation_enabled':False,'current_candidate':{'independent_acceptance':False,'cloud_deployed':False},'reviewed_source_commit':APPROVED,'software_acceptance_bound_to_commit':APPROVED}
        return r,d,t
    def test_known_valid_scope(self): validate_scope(*self.fixture())
    def test_rebound_source(self):
        r,d,t=self.fixture();t['software_acceptance_bound_to_commit']='f'*40
        with self.assertRaises(ValueError): validate_scope(r,d,t)
    def test_unearned_new_candidate_approval(self):
        r,d,t=self.fixture();d['candidate_independent_acceptance']=True
        with self.assertRaises(ValueError): validate_scope(r,d,t)
    def test_whole_stage_cannot_pass(self):
        r,d,t=self.fixture();d['stage2_accepted']=True
        with self.assertRaises(ValueError): validate_scope(r,d,t)
    def test_final_stays_closed(self):
        r,d,t=self.fixture();d['execution_gates']['final_test_enabled']=True
        with self.assertRaises(ValueError): validate_scope(r,d,t)
    def test_wrong_execution_provenance(self):
        r,d,t=self.fixture();r['actual_review_task']['kind']='chatgpt'
        with self.assertRaises(ValueError): validate_scope(r,d,t)
    def test_prior_approval_not_inherited(self):
        r,d,t=self.fixture();r['new_host_implementation_inherits_this_acceptance']=True
        with self.assertRaises(ValueError): validate_scope(r,d,t)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test: unittest.main(argv=[sys.argv[0]],verbosity=2)
    else: verify()
