"""New independent WR18 artifact/contract consistency cases. No developer fixture imports."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4
import io,json,sys,unittest
sys.dont_write_bytecode=True
import independent_wr16_boundaries as old
from qresearch.artifacts import MemoryArtifactStore,FilesystemArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry,RegistryError,BudgetExceeded
from qresearch.engineering_tasks import EngineeringTaskBridge,EngineeringTaskError

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'source'
RUN=ROOT/'new_contract_stores'/uuid4().hex[:8]
OBS={}
def seed(store=None,retries=0):
    r,b=old.setup(store=store,retries=retries)
    a=b.claim('research');submission,observed=old.observation(b,a)
    b.record_submission(a,submission)
    return r,b,a,submission,observed

def summary(r,b,a):return json.loads(r.store.read_bytes(b._submission_key(a.attempt_id)))
def put_summary(r,b,a,s):
    # Deliberate synthetic corruption injection, never a production write.
    r.store._data[b._submission_key(a.attempt_id)]=canonical_json(s)
def rebind_receipt(r,b,a,edit):
    s=summary(r,b,a);receipt=json.loads(r.store.read_bytes(s['receipt_ref']['key']))
    edit(receipt);digest=content_hash(receipt)
    key='engineering/evidence/'+a.attempt_id+'/submission/'+digest+'.json'
    r.store.write_once(key,canonical_json(receipt));s['receipt_ref']={'key':key,'sha256':digest};put_summary(r,b,a,s)
def publish(r,b,a,sub,obs,result_edit=None,journal_external=None):
    digest=content_hash(obs);key='engineering/evidence/'+a.attempt_id+'/completion/'+digest+'.json'
    r.store.write_once(key,canonical_json(obs))
    result={'scope':'engineering','identity':b.payload(a)['identity'],'external_id':sub['external_id'],
       'cloud_report':obs['cloud_report'],'report_ref':obs['report_ref'],
       'platform_evidence_ref':{'key':key,'sha256':digest},'financial_evidence':False}
    if result_edit:result_edit(result)
    r.complete(a,result,external_id=sub['external_id'] if journal_external is None else journal_external)
def clone(r,b):
    store=MemoryArtifactStore();store._data=dict(r.store._data)
    rr=Registry(store,old.h.budget());return rr,EngineeringTaskBridge(rr,b.plan)

def mutate(r,b,a,obs,kind):
    if kind.startswith('summary_'):
        s=summary(r,b,a)
        if kind=='summary_missing':r.store._data.pop(b._submission_key(a.attempt_id));return
        if kind=='summary_extra':s['accepted']=True
        if kind=='summary_identity':s['identity']['stage']='lean'
        if kind=='summary_kind':s['identity_kind']='quantconnect_backtest_id'
        if kind=='summary_external':s['external_id']='qc-research:931001:'+'0'*32
        if kind=='summary_deployment':s['deployment']['input_hash']='e'*64
        put_summary(r,b,a,s)
        if kind=='summary_noncanonical':r.store._data[b._submission_key(a.attempt_id)]=json.dumps(s,indent=2).encode()
    elif kind.startswith('receipt_'):
        s=summary(r,b,a);key=s['receipt_ref']['key']
        if kind=='receipt_missing':r.store._data.pop(key);return
        if kind=='receipt_hash_mismatch':
            v=json.loads(r.store.read_bytes(key));v['raw_receipt']={'synthetic_changed':True};r.store._data[key]=canonical_json(v);return
        if kind=='receipt_noncanonical':
            r.store._data[key]=json.dumps(json.loads(r.store.read_bytes(key)),indent=2).encode();return
        if kind=='receipt_wrong_path':
            other='engineering/evidence/'+'0'*32+'/submission/'+s['receipt_ref']['sha256']+'.json'
            r.store.write_once(other,r.store.read_bytes(key));s['receipt_ref']['key']=other;put_summary(r,b,a,s);return
        edits={
         'receipt_rejected':lambda x:x.update(accepted=False),
         'receipt_empty_raw':lambda x:x.update(raw_receipt={}),
         'receipt_identity':lambda x:x['identity'].update(attempt_id='0'*32),
         'receipt_deployment':lambda x:x['deployment'].update(input_hash='e'*64),
         'receipt_illegal_carrier':lambda x:x.update(raw_receipt={'annotations':{'rows':[{'synthetic':1}]}})}
        rebind_receipt(r,b,a,edits[kind])
    elif kind=='completion_input':obs['platform']['deployment']['input_hash']='e'*64
    elif kind=='completion_empty_raw':obs['platform']['raw_receipt']={}
    elif kind=='completion_illegal_carrier':obs['platform']['raw_receipt']={'annotations':{'rows':[{'synthetic':1}]}}
    elif kind=='completion_extra':obs['platform']['unregistered']=True
    elif kind=='completion_external':obs['platform']['identity']['external_id']='foreign-execution'
    elif kind=='completion_stage':obs['platform']['identity']['stage']='lean'
    elif kind=='completion_nonterminal':obs['platform']['terminal']=False
    elif kind=='completion_pending':obs['platform']['status']='pending'
    elif kind=='report_reference_path':obs['report_ref']['key']='synthetic/foreign-report.json'
    elif kind=='report_reference_hash':obs['report_ref']['sha256']='0'*64
    else:raise AssertionError(kind)

class ContractBoundaries(unittest.TestCase):
    def denied_pair(self,kind):
        r,b,a,sub,obs=seed();mutate(r,b,a,obs,kind)
        before=dict(r.store._data);calls=[]
        with self.assertRaises(EngineeringTaskError) as bridge_error:
            b.consume_completion(a,completion_source=lambda _:calls.append(True) or deepcopy(obs))
        self.assertEqual(r.store._data,before,'Rejected completion persisted evidence or an event')
        if kind.startswith(('summary_','receipt_')):self.assertEqual(calls,[],'Original submission was not rejected before reading completion')
        publish(r,b,a,sub,obs)
        before=dict(r.store._data);usage=r.snapshot()['usage']
        with self.assertRaises(RegistryError) as registry_error:
            r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
        self.assertEqual(r.store._data,before,'Rejected dependency changed artifacts/events')
        self.assertEqual(r.snapshot()['usage'],usage)
        OBS[kind]={'bridge_error':str(bridge_error.exception),'registry_error':str(registry_error.exception),
                   'completion_reader_calls':len(calls),'lean_usage':usage['lean'],'unchanged_after_refusal':True}

    def test_submission_summary_faults_match_both_paths(self):
        for kind in ['summary_missing','summary_extra','summary_identity','summary_kind','summary_external','summary_deployment','summary_noncanonical']:
            with self.subTest(case=kind):self.denied_pair(kind)

    def test_original_submission_reference_and_body_faults_match_both_paths(self):
        for kind in ['receipt_missing','receipt_hash_mismatch','receipt_noncanonical','receipt_wrong_path','receipt_rejected','receipt_empty_raw','receipt_identity','receipt_deployment','receipt_illegal_carrier']:
            with self.subTest(case=kind):self.denied_pair(kind)

    def test_completion_faults_match_both_paths_without_persisting_rejected_observation(self):
        for kind in ['completion_input','completion_empty_raw','completion_illegal_carrier','completion_extra','completion_external','completion_stage','completion_nonterminal','completion_pending','report_reference_path','report_reference_hash']:
            with self.subTest(case=kind):self.denied_pair(kind)

    def test_submission_status_absent_and_completed_are_still_pending_until_terminal(self):
        for status in [None,'completed','submitted']:
            with self.subTest(submission_status=status):
                r,b=old.setup();a=b.claim('research');sub,obs=old.observation(b,a)
                if status is None:sub.pop('status')
                else:sub['status']=status
                saved=b.record_submission(a,sub);self.assertEqual(saved.status,'pending')
                self.assertEqual(r.snapshot()['usage']['lean']['total'],0)
                self.assertEqual(b.consume_completion(a,completion_source=lambda _:deepcopy(obs)).status,'completed')
                lean=r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'));self.assertTrue(lean.should_execute)
                self.assertFalse(b.claim('lean').should_execute);self.assertEqual(r.snapshot()['usage']['lean']['total'],1)

    def test_failed_native_terminals_settle_but_cannot_unlock_lean(self):
        for status in ['failed','runtime_error','compile_error']:
            with self.subTest(status=status):
                r,b,a,sub,obs=seed();obs['platform']['status']=status
                rr,bb=clone(r,b)
                final=b.consume_completion(a,completion_source=lambda _:deepcopy(obs));self.assertEqual(final.status,'failed')
                self.assertEqual(r.snapshot()['usage']['research']['total'],1)
                with self.assertRaises(RegistryError):r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
                publish(rr,bb,a,sub,obs);before=dict(rr.store._data)
                with self.assertRaises(RegistryError):rr.begin_attempt(bb.config_id,'lean',operation_key=bb._operation('lean'))
                self.assertEqual(rr.store._data,before);self.assertEqual(rr.snapshot()['usage']['lean']['total'],0)
                OBS['native_'+status]={'bridge_status':final.status,'direct_completed_result_unlocks_lean':False,'research_refund':False}

    def test_completed_platform_with_failed_cloud_checks_is_not_dependency(self):
        for kind in ['false_check','zero_records','failed_cloud_status']:
            with self.subTest(case=kind):
                r,b,a,sub,obs=seed()
                if kind=='false_check':obs['cloud_report']['checks']['collection_nonempty']=False
                if kind=='zero_records':obs['cloud_report']['statistics']['record_count']=0
                if kind=='failed_cloud_status':obs['cloud_report']['status']='failed'
                obs['report_ref']['sha256']=content_hash(obs['cloud_report']);rr,bb=clone(r,b)
                self.assertEqual(b.consume_completion(a,completion_source=lambda _:deepcopy(obs)).status,'failed')
                publish(rr,bb,a,sub,obs);before=dict(rr.store._data)
                with self.assertRaises(RegistryError):rr.begin_attempt(bb.config_id,'lean',operation_key=bb._operation('lean'))
                self.assertEqual(rr.store._data,before);self.assertEqual(rr.snapshot()['usage']['lean']['total'],0)

    def test_stored_completion_reference_and_journal_external_id_still_bind(self):
        for kind in ['wrong_completion_path','missing_completion','wrong_completion_hash','wrong_journal_external']:
            with self.subTest(case=kind):
                r,b,a,sub,obs=seed()
                edit=None;external=None
                if kind=='wrong_completion_path':edit=lambda x:x['platform_evidence_ref'].update(key='synthetic/foreign-completion.json')
                if kind=='missing_completion':edit=lambda x:x['platform_evidence_ref'].update(key='engineering/evidence/'+a.attempt_id+'/completion/'+'0'*64+'.json',sha256='0'*64)
                if kind=='wrong_completion_hash':edit=lambda x:x['platform_evidence_ref'].update(sha256='0'*64)
                if kind=='wrong_journal_external':external='synthetic-wrong-execution'
                publish(r,b,a,sub,obs,result_edit=edit,journal_external=external);before=dict(r.store._data)
                with self.assertRaises(RegistryError):r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
                self.assertEqual(r.store._data,before);self.assertEqual(r.snapshot()['usage']['lean']['total'],0)

    def test_max1_second_retry_refused_by_registered_bound_before_global_cap(self):
        r,b=old.setup(retries=1);a=b.claim('research');r.fail(a,'synthetic first failure')
        retry=r.begin_attempt(b.config_id,'research',operation_key=b._operation('research'),retry_of=a.attempt_id,reason='synthetic repair',allocation='reserve')
        self.assertTrue(retry.should_execute);r.fail(retry,'synthetic retry failure');before=dict(r.store._data)
        with self.assertRaises(RegistryError) as error:
            r.begin_attempt(b.config_id,'research',operation_key=b._operation('research'),retry_of=retry.attempt_id,reason='unregistered second repair',allocation='reserve')
        self.assertNotIsInstance(error.exception,BudgetExceeded)
        self.assertIn('retry bound',str(error.exception));self.assertEqual(r.store._data,before)
        self.assertEqual(r.snapshot()['usage']['research']['total'],2)

    def test_filesystem_reopen_qualified_dependency_and_reuse_without_lock_reentry(self):
        path=RUN/'completed-reopen'
        r,b,a,sub,obs=seed(FilesystemArtifactStore(path,data_classification='synthetic',lock_timeout=.15))
        self.assertEqual(b.consume_completion(a,completion_source=lambda _:deepcopy(obs)).status,'completed')
        rr=Registry(FilesystemArtifactStore(path,data_classification='synthetic',lock_timeout=.15),old.h.budget())
        bb=EngineeringTaskBridge(rr,b.plan)
        lean=rr.begin_attempt(bb.config_id,'lean',operation_key=bb._operation('lean'));self.assertTrue(lean.should_execute)
        reopened=Registry(FilesystemArtifactStore(path,data_classification='synthetic',lock_timeout=.15),old.h.budget())
        again=reopened.begin_attempt(bb.config_id,'lean',operation_key=bb._operation('lean'))
        self.assertFalse(again.should_execute);self.assertEqual(again.attempt_id,lean.attempt_id)
        self.assertEqual(reopened.snapshot()['usage']['lean']['total'],1)

class Counted(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)
def main():
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractBoundaries))
    method=lambda t:getattr(t,'test_case',t).id()
    failed={method(t) for t,_ in result.failures};errors={method(t) for t,_ in result.errors}
    data={'actual_source_commit':'81fbe5294055423e88ee5aeae48ca6223e7971da','source_root':str(SOURCE),
      'methods':result.testsRun,'passed_methods':result.testsRun-len(failed|errors),'failed_methods':len(failed),'error_methods':len(errors),
      'subcases':result.subcases,'skipped':len(result.skipped),'failure_records':len(result.failures),'error_records':len(result.errors),
      'failures':[{'method':method(t),'traceback':tb} for t,tb in result.failures],'errors':[{'method':method(t),'traceback':tb} for t,tb in result.errors],
      'observations':OBS,'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'actual_worker_invocations':0,'actual_platform_market_model_calls':0,
      'developer_fixture_imports':False,'synthetic_artifact_fault_injection':True,'exit_code':0 if result.wasSuccessful() else 1}
    (ROOT/'new_contract_first_results.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(stream.getvalue());print(json.dumps({k:data[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}))
    return data['exit_code']
if __name__=='__main__':raise SystemExit(main())
