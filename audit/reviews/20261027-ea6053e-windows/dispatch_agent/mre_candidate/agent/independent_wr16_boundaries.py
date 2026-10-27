"""New WR16 strict-evidence, positive retry, filesystem and process boundaries."""
from pathlib import Path
from copy import deepcopy
from contextlib import contextmanager
from uuid import uuid4
from hashlib import sha256
import io,json,multiprocessing as mp,sys,time,unittest
sys.dont_write_bytecode=True
import quick_joint_probes as h
from qresearch.artifacts import MemoryArtifactStore,FilesystemArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry,RegistryError,BudgetExceeded
from qresearch.engineering_tasks import EngineeringTaskBridge,EngineeringTaskPlan
from qresearch.collection import HistoricalCollectionPlan

ROOT=Path(__file__).resolve().parent;RUN=ROOT/'new_stores'/uuid4().hex[:8];OBS={}
def setup(store=None,retries=0):
    r=Registry(MemoryArtifactStore() if store is None else store,h.budget())
    b=EngineeringTaskBridge(r,h.joint(retries=retries));b.register();return r,b
def observation(b,a):
    payload=b.payload(a);identity=payload['identity'];document=b.plan.to_dict();external='qc-research:'+str(document['project_id'])+':'+a.attempt_id
    deployment={'source_manifest_hash':document['source_manifest_hash'],'deployment_hash':document['deployment_hash'],'input_hash':'d'*64}
    refs={'resolved_registry_ref':{'key':'independent/resolution/registry.json','sha256':'1'*64},
          'resolved_request_ref':{'key':'independent/resolution/request.json','sha256':'2'*64}}
    resolution={'resolved_request_hash':'2'*64,'resolved_registry_hash':'1'*64,'resolution_artifact_hash':content_hash(refs),
                'tickers':['AAPL','MSFT'],'ticker_count':2,'permanent_sid_count':2,'method':document['symbol_resolution']['method'],**refs}
    child=document['collection_probe'];cp=HistoricalCollectionPlan.from_dict(child['collection_plan'],field_catalog=child['field_catalog'])
    probe={'schema_version':1,'plan_hash':cp.hash,'receipt_ref':{'key':document['report_namespace']+'/collection-probes/'+b.plan.hash+'/'+a.attempt_id+'.json','sha256':'3'*64},
       'window_count':40,'record_count':40,'source_fetch_calls':40,'reused_windows':0,'empty_windows':0,'cache_only_source_fetch_calls':0,
       'missing_values':{field:0 for field in h.CAT},
       **{f:False for f in ['full_historical_US200_certified','actual_availability_certified','research_certified','row_values_exported','financial_vintage_certified']}}
    report={'schema_version':1,'identity':identity,'status':'completed','terminal':True,
       'checks':{name:True for name in document['required_checks']['research']},
       'statistics':{'record_count':2,'history_calls_first':1,'history_calls_second':0,'expected_formation_count':1},
       'resolution':resolution,'evidence':{'collection_probe':probe},
       **{f:False for f in ['market_values_exported','economic_factor_tested','final_data_accessed','full_US200_coverage_certified','actual_availability_verified']}}
    raw={'synthetic_observation':'independent-only','response_sha256':'f'*64}
    submitted={'identity':identity,'identity_kind':payload['external_identity_kind'],'external_id':external,'accepted':True,'status':'submitted','deployment':deployment,'raw_receipt':raw}
    observed={'platform':{'identity':dict(identity,external_id=external),'terminal':True,'status':'completed','deployment':deployment,'raw_receipt':raw},
              'cloud_report':report,'report_ref':{'key':payload['report_key'],'sha256':content_hash(report)}}
    return submitted,observed
def checked_research(r,b):
    a=b.claim('research');submission,observed=observation(b,a);b.record_submission(a,submission)
    final=b.consume_completion(a,completion_source=lambda _:deepcopy(observed))
    assert final.status=='completed';return a,submission,observed
def direct_complete(r,b,mutation):
    a=b.claim('research');submission,observed=observation(b,a)
    if mutation!='missing_submission':b.record_submission(a,submission)
    if mutation=='input_hash_conflict':observed['platform']['deployment']['input_hash']='e'*64
    if mutation=='empty_raw':observed['platform']['raw_receipt']={}
    if mutation=='wrong_report_identity':observed['cloud_report']['identity']=dict(observed['cloud_report']['identity'],source_manifest_hash='0'*64)
    if mutation=='failed_platform':observed['platform']['status']='failed'
    if mutation=='wrong_parent_probe':observed['cloud_report']['evidence']['collection_probe']['plan_hash']='0'*64
    observed['report_ref']['sha256']=content_hash(observed['cloud_report'])
    encoded=canonical_json(observed);digest=sha256(encoded).hexdigest();key='engineering/evidence/'+a.attempt_id+'/completion/'+digest+'.json'
    if mutation!='missing_evidence':r.store.write_once(key,encoded)
    result={'scope':'engineering','identity':b.payload(a)['identity'],'external_id':submission['external_id'],
            'cloud_report':observed['cloud_report'],'report_ref':observed['report_ref'],
            'platform_evidence_ref':{'key':key,'sha256':digest},'financial_evidence':False}
    r.complete(a,result,external_id=submission['external_id']);return a,result
def old_plan():
    raw=h.joint(project=932002,name='independent-old-domain',retries=1).to_dict();raw['schema_version']=1;del raw['collection_probe']
    return EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[932002])
def process_claim(path,gate,q,kind):
    try:
        r=Registry(FilesystemArtifactStore(path,data_classification='synthetic'),h.budget())
        b=EngineeringTaskBridge(r,h.joint());old=EngineeringTaskBridge(r,old_plan())
        q.put({'kind':'ready'});gate.wait(20)
        try:
            if kind=='joint':a=r.begin_attempt(b.config_id,'research',operation_key=b._operation('research'))
            else:
                previous=next(a for a in r.snapshot()['attempts'] if a['config_id']==old.config_id)
                a=old.claim('research',retry_of=previous['attempt_id'],reason='independent fixed retry',allocation='reserve')
            q.put({'kind':'outcome','claimant':kind,'permit':a.should_execute,'attempt':a.attempt_id})
        except Exception as e:q.put({'kind':'outcome','claimant':kind,'error':type(e).__name__,'message':str(e)})
    except BaseException as e:q.put({'kind':'worker_error','error':type(e).__name__,'message':str(e)})

class NewBoundaries(unittest.TestCase):
    def test_valid_complete_parent_research_allows_lean_and_reuse(self):
        r,b=setup();a,_,_=checked_research(r,b);before=r.snapshot()['usage']
        lean=r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
        self.assertTrue(lean.should_execute);self.assertEqual(r.snapshot()['usage']['research'],before['research'])
        again=r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'));self.assertFalse(again.should_execute)
        self.assertEqual(again.attempt_id,lean.attempt_id);self.assertEqual(r.snapshot()['usage']['lean']['total'],1)

    def test_max_one_retry_is_legitimate_after_failure_and_restart(self):
        path=RUN/'retry';r,b=setup(FilesystemArtifactStore(path,data_classification='synthetic'),retries=1)
        a=b.claim('research');r.fail(a,'synthetic verified failure')
        reopened=Registry(FilesystemArtifactStore(path,data_classification='synthetic'),h.budget());bridge=EngineeringTaskBridge(reopened,h.joint(retries=1))
        retry=reopened.begin_attempt(bridge.config_id,'research',allocation='reserve',operation_key=bridge._operation('research'),retry_of=a.attempt_id,reason='independent repair')
        self.assertTrue(retry.should_execute);self.assertEqual(reopened.snapshot()['usage']['research'],{'total':2,'normal':1,'reserve':1})
        self.assertFalse(bridge.claim('research').should_execute)

    def test_filesystem_verified_lean_does_not_reacquire_transaction_lock(self):
        r,b=setup(FilesystemArtifactStore(RUN/'no-lock-reentry',data_classification='synthetic',lock_timeout=.1))
        checked_research(r,b);started=time.monotonic()
        self.assertTrue(r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean')).should_execute)
        self.assertLess(time.monotonic()-started,1)

    def test_nonreentrant_transaction_store_accepts_valid_dependency(self):
        class Nonreentrant(MemoryArtifactStore):
            entered=False
            @contextmanager
            def locked(self,key):
                if key==Registry.LOCK:
                    if self.entered:raise AssertionError('Registry transaction lock reentered')
                    self.entered=True
                    try:
                        with super().locked(key):yield
                    finally:self.entered=False
                else:
                    with super().locked(key):yield
        r,b=setup(Nonreentrant());checked_research(r,b)
        self.assertTrue(r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean')).should_execute)

    def test_strict_identity_and_missing_completion_evidence_refuse_before_charge(self):
        for mutation in ['wrong_report_identity','failed_platform','wrong_parent_probe','missing_evidence']:
            with self.subTest(mutation=mutation):
                r,b=setup();direct_complete(r,b,mutation);before=r.snapshot()['usage']
                with self.assertRaises(RegistryError):r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
                self.assertEqual(r.snapshot()['usage'],before)

    def assert_incomplete_refused(self,mutation):
        r,b=setup();a,result=direct_complete(r,b,mutation);before=r.snapshot()['usage'];error=None;lean=None
        try:lean=r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
        except RegistryError as e:error=str(e)
        OBS[mutation]={'research_attempt':a.attempt_id,'before':before,'after':r.snapshot()['usage'],'refusal':error,
                       'lean':None if lean is None else vars(lean),'stored_result':result}
        self.assertIsNotNone(error,'Incomplete or contradictory checked Research evidence was admitted as the LEAN dependency')
        self.assertEqual(r.snapshot()['usage'],before)
    def test_input_hash_conflicting_with_recorded_submission_must_refuse(self):self.assert_incomplete_refused('input_hash_conflict')
    def test_empty_native_receipt_must_not_be_verified_research(self):self.assert_incomplete_refused('empty_raw')
    def test_no_recorded_submission_must_not_be_verified_research(self):self.assert_incomplete_refused('missing_submission')

    def test_windows_process_race_shares_last_research_slot(self):
        path=RUN/'process';r=Registry(FilesystemArtifactStore(path,data_classification='synthetic'),h.budget())
        old=EngineeringTaskBridge(r,old_plan());b=EngineeringTaskBridge(r,h.joint());old.register();b.register()
        a=old.claim('research');r.fail(a,'known seeded failure')
        context=mp.get_context('spawn');gate=context.Event();q=context.Queue()
        workers=[context.Process(target=process_claim,args=(str(path),gate,q,kind)) for kind in ['joint','old']]
        for p in workers:p.start()
        ready=[q.get(timeout=20) for _ in workers];self.assertTrue(all(x['kind']=='ready' for x in ready),ready);gate.set()
        outcomes=[q.get(timeout=20) for _ in workers]
        for p in workers:p.join(20);self.assertEqual(p.exitcode,0)
        self.assertEqual(sum(x.get('permit') is True for x in outcomes),1,outcomes)
        self.assertEqual(sum(x.get('error')=='BudgetExceeded' for x in outcomes),1,outcomes)
        self.assertEqual(r.snapshot()['usage']['research']['total'],2);OBS['process_last_slot']=outcomes

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)
def main():
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewBoundaries))
    def method(t):return getattr(t,'test_case',t).id()
    failed={method(t) for t,_ in r.failures};errors={method(t) for t,_ in r.errors}
    data={'reviewed_source_commit':'ae2b8985f3799c246e90341370f86d80483f63ed','methods':r.testsRun,'passed_methods':r.testsRun-len(failed|errors),
      'failed_methods':len(failed),'error_methods':len(errors),'subcases':r.subcases,'skipped':len(r.skipped),
      'failure_records':len(r.failures),'error_records':len(r.errors),'failures':[{'method':method(t),'traceback':tb} for t,tb in r.failures],
      'errors':[{'method':method(t),'traceback':tb} for t,tb in r.errors],'observations':OBS,'command':[sys.executable,'-B',str(Path(__file__).resolve())],
      'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'actual_external_calls':0,'author_fixture_imports':False,
      'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'new_first_results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'new_first.stdout').write_text(stream.getvalue(),encoding='utf-8');print(stream.getvalue())
    print(json.dumps({k:data[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}));return data['exit_code']
if __name__=='__main__':mp.freeze_support();raise SystemExit(main())
