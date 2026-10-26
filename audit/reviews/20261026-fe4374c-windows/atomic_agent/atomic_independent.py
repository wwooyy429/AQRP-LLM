"""Independent WR-04 audit. Synthetic metadata only; no developer fixtures.

Plans are constructed from the production schema template, with explicit
synthetic identities. Terminal records used to meet LEAN's prerequisite are
synthetic Registry completions; this file audits admission, not remote receipts.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib,io,json,multiprocessing as mp,os,platform,sys,tempfile,threading,unittest

ROOT=Path(__file__).resolve().parent
SOURCE=Path(os.environ.get('AQRP_AUDIT_SOURCE',str(ROOT.parent/'source')))
OUTPUT_ROOT=Path(os.environ.get('AQRP_ATOMIC_OUTPUT',str(ROOT)))
REVIEW_SHA=os.environ.get('AQRP_AUDIT_SHA','fe4374cee054fb8053706074be913ad7068c4484')
sys.path[:0]=[str(SOURCE/'cloud'),str(SOURCE/'tools')]
from qresearch.artifacts import MemoryArtifactStore,FilesystemArtifactStore,canonical_json,CorruptEventStream
from qresearch.registry import Registry,BudgetExceeded,CorruptRegistry,RegistryError
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,EngineeringTaskError
from qresearch.workflow import SubmissionRejected
from stage2 import _limits

LIMITS={'configurations':{'total':12,'normal':8,'reserve':4},
        'research':{'total':20,'normal':12,'reserve':8},
        'lean':{'total':16,'normal':8,'reserve':8}}
OBS=[]

def document(name,project):
    d=json.loads((SOURCE/'config/engineering.json').read_text(encoding='utf-8-sig'))
    d.update(plan_id=name,project_id=project,source_manifest_hash='a'*64,deployment_hash='b'*64)
    d['request_template']['data_version']='independent-atomic-synthetic'
    d['request_template']['universe_hash']='c'*64
    return d

def make_bridge(registry,doc,adapter=None):
    plan=EngineeringTaskPlan.from_dict(doc,discovered_project_ids=[101,102,103])
    return EngineeringTaskBridge(registry,plan,adapter=adapter)

def complete_prerequisite(registry,bridge):
    a=bridge.claim('research')
    registry.complete(a,{'cloud_report':{'resolution':{'synthetic':'admission-only'}}})

def compete(registry,doc,kind,gate,entry):
    b=make_bridge(registry,doc)
    _limits(b,kind)
    gate.wait(20)
    try:
        if kind=='configurations':
            identity=b.register() if entry=='bridge' else registry.register_config(b.package)
            return {'outcome':'admitted','config_id':identity}
        if entry=='bridge': a=b.claim(kind)
        else:a=registry.begin_attempt(b.config_id,kind,operation_key='independent-competing-task')
        return {'outcome':'admitted' if a.should_execute else 'reuse','attempt_id':a.attempt_id}
    except BudgetExceeded as exc:
        return {'outcome':'rejected','exception':type(exc).__name__,'reason':str(exc)}

def worker(directory,doc,kind,gate,queue,entry):
    try:
        reg=Registry(FilesystemArtifactStore(directory,lock_timeout=20),LIMITS)
        queue.put(compete(reg,doc,kind,gate,entry))
    except BaseException as exc:
        queue.put({'outcome':'unexpected','type':type(exc).__name__,'message':str(exc)})

class Admission(unittest.TestCase):
    def race(self,kind,style):
        with tempfile.TemporaryDirectory(prefix='independent-admission-') as directory:
            store=MemoryArtifactStore() if style=='memory' else FilesystemArtifactStore(directory,lock_timeout=20)
            reg=Registry(store,LIMITS)
            docs=[document('candidate-a',101),document('candidate-b',102)]
            if kind=='configurations':make_bridge(reg,document('first-used-slot',103)).register()
            else:
                for doc in docs:
                    b=make_bridge(reg,doc);b.register()
                    if kind=='lean':complete_prerequisite(reg,b)
                seed=reg.begin_attempt(make_bridge(reg,docs[0]).config_id,kind,operation_key='seed-used-slot')
                reg.fail(seed,'synthetic failure retained, no refund')
            if style=='processes':
                ctx=mp.get_context('spawn');gate=ctx.Barrier(2);q=ctx.Queue()
                children=[ctx.Process(target=worker,args=(directory,doc,kind,gate,q,entry))
                          for doc,entry in zip(docs,['bridge','registry'])]
                try:
                    for p in children:p.start()
                    results=[q.get(timeout=45) for _ in children]
                    for p in children:p.join(10);self.assertEqual(p.exitcode,0)
                finally:
                    for p in children:
                        if p.is_alive():p.terminate();p.join()
                    q.close();q.join_thread()
            else:
                gate=threading.Barrier(2)
                def run(pair):
                    doc,entry=pair
                    other=reg if style=='memory' else Registry(FilesystemArtifactStore(directory,lock_timeout=20),LIMITS)
                    return compete(other,doc,kind,gate,entry)
                with ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(run,zip(docs,['bridge','registry'])))
            snapshot=reg.snapshot();OBS.append({'case':self.id(),'resource':kind,'surface':style,
                'results':results,'final_usage':snapshot['usage']})
            self.assertCountEqual([r['outcome'] for r in results],['admitted','rejected'])
            self.assertEqual(snapshot['usage'][kind]['total'],2)
            restarted=Registry(store if style=='memory' else FilesystemArtifactStore(directory),LIMITS)
            self.assertEqual(restarted.snapshot(),snapshot)

    def test_configuration_memory(self):self.race('configurations','memory')
    def test_configuration_separate_stores(self):self.race('configurations','filesystem')
    def test_configuration_native_processes(self):self.race('configurations','processes')
    def test_research_memory(self):self.race('research','memory')
    def test_research_separate_stores(self):self.race('research','filesystem')
    def test_research_native_processes(self):self.race('research','processes')
    def test_lean_memory(self):self.race('lean','memory')
    def test_lean_separate_stores(self):self.race('lean','filesystem')
    def test_lean_native_processes(self):self.race('lean','processes')

    def test_renamed_project_and_allocation_cannot_reset_config_stop(self):
        r=Registry(MemoryArtifactStore(),LIMITS)
        for i,alloc in [(101,'normal'),(102,'reserve')]:
            make_bridge(r,document('renamed-'+str(i),i)).register(allocation=alloc)
        before=deepcopy(r.snapshot())
        with self.assertRaises(BudgetExceeded):make_bridge(r,document('different-project',103)).register()
        self.assertEqual(r.snapshot(),before)

    def test_direct_research_different_operation_keys_share_round_limit(self):
        r=Registry(MemoryArtifactStore(),LIMITS);b=make_bridge(r,document('same',101));b.register()
        for i,alloc in [(1,'normal'),(2,'reserve')]:
            a=r.begin_attempt(b.config_id,'research',allocation=alloc,operation_key='renamed-operation-'+str(i));r.fail(a,'no refund')
        with self.assertRaises(BudgetExceeded):r.begin_attempt(b.config_id,'research',operation_key='third-name')
        self.assertEqual(r.snapshot()['usage']['research'],{'total':2,'normal':1,'reserve':1})

    def test_bridge_submit_refusal_occurs_before_third_adapter_call(self):
        class Adapter:
            calls=0
            def submit_research(self,*args,**kwargs):
                self.calls+=1;raise SubmissionRejected('synthetic refusal')
        r=Registry(MemoryArtifactStore(),LIMITS);adapter=Adapter();b=make_bridge(r,document('submit',101),adapter);b.register()
        a=b.submit('research');second=b.submit('research',allocation='reserve',retry_of=a.attempt_id,reason='explicit repair')
        other=make_bridge(r,document('changed-project',102),adapter);other.register()
        with self.assertRaises(BudgetExceeded):other.submit('research')
        self.assertEqual(adapter.calls,2);self.assertEqual(second.status,'failed')
        self.assertEqual(r.snapshot()['usage']['research']['total'],2)

    def test_completed_pending_and_ambiguous_reuse_after_cap(self):
        for status in ['completed','pending','ambiguous']:
            with self.subTest(status=status):
                store=MemoryArtifactStore();r=Registry(store,LIMITS);b=make_bridge(r,document(status,101));b.register()
                a=r.begin_attempt(b.config_id,'research',operation_key='first');r.fail(a,'failure remains charged')
                a=r.begin_attempt(b.config_id,'research',operation_key='second')
                if status=='completed':r.complete(a,{'synthetic':'done'})
                elif status=='pending':r.pending(a,external_id='synthetic-id')
                else:r.ambiguous(a,reason='unknown synthetic submission')
                before=deepcopy(r.snapshot());r=Registry(store,LIMITS)
                reused=r.begin_attempt(b.config_id,'research',operation_key='second')
                self.assertFalse(reused.should_execute);self.assertEqual(reused.status,status)
                self.assertEqual(r.snapshot(),before)
                if status=='completed':
                    with self.assertRaises(BudgetExceeded):r.begin_attempt(b.config_id,'research',operation_key='third')
                else:
                    unresolved=r.begin_attempt(b.config_id,'research',operation_key='third')
                    self.assertEqual(unresolved.attempt_id,a.attempt_id);self.assertFalse(unresolved.should_execute)

    def test_failed_reuse_and_explicit_retry_count(self):
        r=Registry(MemoryArtifactStore(),LIMITS);b=make_bridge(r,document('failure',101));b.register()
        a=b.claim('research');r.fail(a,'first')
        self.assertEqual(b.claim('research').attempt_id,a.attempt_id)
        second=b.claim('research',retry_of=a.attempt_id,reason='repair',allocation='reserve');r.fail(second,'second')
        self.assertEqual(b.claim('research').attempt_id,second.attempt_id)
        with self.assertRaises((BudgetExceeded,EngineeringTaskError)):
            b.claim('research',retry_of=second.attempt_id,reason='third try',allocation='reserve')
        self.assertEqual(r.snapshot()['usage']['research'],{'total':2,'normal':1,'reserve':1})

    def test_global_normal_and_total_caps_keep_legitimate_generic_path(self):
        r=Registry(MemoryArtifactStore(),LIMITS)
        make_bridge(r,document('a',101)).register();make_bridge(r,document('b',102)).register()
        for i in range(6):r.register_config({'independent-generic':i})
        self.assertEqual(r.snapshot()['usage']['configurations']['normal'],8)
        with self.assertRaises(BudgetExceeded):r.register_config({'independent-generic':'normal-cap'})
        for i in range(4):r.register_config({'independent-reserve':i},allocation='reserve')
        with self.assertRaises(BudgetExceeded):r.register_config({'independent-generic':'total-cap'},allocation='reserve')
        self.assertEqual(r.snapshot()['usage']['configurations']['total'],12)

    def test_missing_noninteger_marker_and_unknown_extra_field_rejected(self):
        r=Registry(MemoryArtifactStore(),LIMITS);package=make_bridge(r,document('x',101)).package
        for marker in [None,False,True,0,2,'1']:
            with self.subTest(marker=marker):
                d=deepcopy(package)
                if marker is None:d.pop('engineering_task_schema_version')
                else:d['engineering_task_schema_version']=marker
                with self.assertRaises(ValueError):r.register_config(d)
        d=deepcopy(package);d['unknown']='not allowed'
        with self.assertRaises(ValueError):r.register_config(d)
        self.assertEqual(r.snapshot()['usage']['configurations']['total'],0)

    def test_mutating_registered_package_breaks_hash_before_new_charge(self):
        store=MemoryArtifactStore();r=Registry(store,LIMITS);b=make_bridge(r,document('immutable',101));b.register()
        key='configurations/'+b.config_id+'.json';payload=json.loads(store.read_bytes(key));payload['plan']['plan_id']='edited'
        # Fault injection corrupts this isolated synthetic store only.
        store._data[key]=canonical_json(payload)
        with self.assertRaises(CorruptRegistry):r.begin_attempt(b.config_id,'research',operation_key='no-charge')

    def test_same_project_unresolved_other_plan_is_still_blocked(self):
        r=Registry(MemoryArtifactStore(),LIMITS);a=make_bridge(r,document('first',101));b=make_bridge(r,document('second',101))
        a.register();b.register();first=a.claim('research')
        with self.assertRaises(EngineeringTaskError):b.claim('research')
        self.assertEqual(r.snapshot()['usage']['research']['total'],1)
        r.fail(first,'failure reconciled');allowed=b.claim('research');self.assertTrue(allowed.should_execute)
        self.assertEqual(r.snapshot()['usage']['research']['total'],2)

    def test_preview_grants_no_execution_or_charge(self):
        r=Registry(MemoryArtifactStore(),LIMITS);b=make_bridge(r,document('preview',101))
        before=r.snapshot();_limits(b,'configurations');self.assertEqual(r.snapshot(),before)
        b.register();before=r.snapshot();_limits(b,'research');self.assertEqual(r.snapshot(),before)
        a=b.claim('research');self.assertTrue(a.should_execute)
        self.assertEqual(r.snapshot()['usage']['research']['total'],1)

class CounterResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcases=0
    def addSubTest(self,test,subtest,err):self.subcases+=1;super().addSubTest(test,subtest,err)

def main():
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Admission)
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=CounterResult).run(suite)
    text=stream.getvalue();OUTPUT_ROOT.mkdir(parents=True,exist_ok=True);(OUTPUT_ROOT/'output.txt').write_text(text,encoding='utf-8')
    def method_id(test):return getattr(test,'test_case',test).id()
    failed={method_id(t) for t,_ in result.failures}
    errors={method_id(t) for t,_ in result.errors}
    skipped={method_id(t) for t,_ in result.skipped}
    report={'reviewed_source_commit':REVIEW_SHA,'actually_executed':True,
        'methods':result.testsRun,'passed_methods':result.testsRun-len(failed|errors|skipped),
        'failures':len(failed),'errors':len(errors),'skipped':len(skipped),'subcases':result.subcases,
        'failure_records_including_subtests':len(result.failures),'error_records_including_subtests':len(result.errors),
        'observations':OBS,'failure_details':[{'test':str(t),'traceback':s} for t,s in result.failures],
        'error_details':[{'test':str(t),'traceback':s} for t,s in result.errors],
        'environment':{'os':platform.platform(),'python':sys.version},'developer_fixtures_imported':False,
        'scope':'atomic admission; no remote receipts or real market execution','exit_code':0 if result.wasSuccessful() else 1}
    (OUTPUT_ROOT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(text);print(json.dumps({k:report[k] for k in ['methods','passed_methods','failures','errors','skipped','subcases','exit_code']}))
    return report['exit_code']
if __name__=='__main__':raise SystemExit(main())
