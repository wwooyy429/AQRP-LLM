"""Mixed old/new engineering admission review: no author test helpers or I/O SDK."""
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace as NS
from hashlib import sha256
from uuid import uuid4
from unittest.mock import patch
import ast,io,json,multiprocessing as mp,os,sys,threading,traceback,unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'source';RUN=ROOT/'stores'/uuid4().hex
sys.path.insert(0,str(SOURCE/'cloud'));sys.path.insert(0,str(SOURCE/'tools'))
from qresearch.artifacts import MemoryArtifactStore,FilesystemArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry,RegistryError,BudgetExceeded
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,EngineeringTaskError
from qresearch.collection_tasks import CollectionTaskPlan,CollectionTaskBridge
from qresearch.workflow import SubmissionRejected
import collection_task_cli as cli
import research

CAT={'dollar_volume':{'kind':'number','role':'independent_liquidity','unit':'USD','period_accessor':None},
     'has_fundamental_data':{'kind':'boolean','role':'independent_coverage','unit':'boolean','period_accessor':None}}

def budget(usage=None):
    return {'limits':{'full_configurations':12,'research_execution_attempts':20,'lean_submission_attempts':16},
      'allocations':{'full_configurations':{'total':12,'normal':8,'reserve':4},
        'research_execution_attempts':{'total':20,'normal':12,'reserve':8},
        'lean_submission_attempts':{'total':16,'normal':8,'reserve':8}},'usage':{} if usage is None else usage}

def old_plan(name='old-A',project=4101,retries=2):
    return EngineeringTaskPlan.from_dict({'schema_version':1,'plan_id':name,'scope':'engineering','project_id':project,
      'source_manifest_hash':'a'*64,'deployment_hash':'b'*64,'request_mode':'resolved',
      'data_request':{'dataset':'us_equity_daily','fields':['close'],'start':'2018-01-01T00:00:00-05:00',
        'end':'2019-01-01T00:00:00-05:00','sids':['independent-old-A','independent-old-B'],
        'data_version':'independent-old-v1','universe_hash':'c'*64,'normalization':'raw','timezone':'America/New_York'},
      'observation_window':{'start':'2018-02-01T00:00:00-05:00','end_exclusive':'2018-02-06T00:00:00-05:00'},
      'required_checks':{'research':['cache_reused'],'lean':['no_orders']},'max_retries':{'research':retries,'lean':retries},
      'report_namespace':'independent/old','orders_enabled':False,'financial_metrics_enabled':False,
      'economic_factor':None,'economic_model':None},discovered_project_ids=[project])

def new_raw(name='new-B',project=4202,retries=1):
    return {'schema_version':1,'task_kind':'historical_collection','scope':'engineering','plan_id':name,'project_id':project,
      'source_manifest_hash':'d'*64,'deployment_hash':'e'*64,'report_namespace':'independent/collection','max_retries':retries,
      'field_catalog':deepcopy(CAT),'collection_plan':{'schema_version':1,'plan_id':'window-'+name,'scope':'engineering',
        'source':'quantconnect_fundamental_universe','data_version':'independent-collection-v1',
        'start':'2022-10-11T00:00:00-04:00','end_exclusive':'2022-10-13T00:00:00-04:00',
        'timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':1,'max_batch_records':3,
        'max_records_per_window':7,'source_manifest_hash':'d'*64}}

def new_plan(name='new-B',project=4202,retries=1):
    return CollectionTaskPlan.from_dict(new_raw(name,project,retries),discovered_project_ids=[project],field_catalog=CAT)
def old_bridge(r,name='old-A',project=4101,retries=2):return EngineeringTaskBridge(r,old_plan(name,project,retries))
def new_bridge(r,name='new-B',project=4202,retries=1,**kw):return CollectionTaskBridge(r,new_plan(name,project,retries),**kw)
def eng_count(r,kind):
    state=r.snapshot();ids={x for x in state['config_ids'] if json.loads(r.store.read_bytes('configurations/'+x+'.json')).get('engineering_task_schema_version')==1}
    return len(ids) if kind=='configurations' else sum(a['config_id'] in ids and a['stage']==kind for a in state['attempts'])
def outcome(fn):
    try:
        value=fn()
        if isinstance(value,str):return {'kind':'registered','config_id':value}
        return {'kind':'permit' if value.should_execute else 'reuse','attempt_id':value.attempt_id,'status':value.status}
    except Exception as e:return {'kind':'rejected','error':type(e).__name__,'message':str(e)}

def race(functions):
    gate=threading.Barrier(len(functions))
    def run(fn):gate.wait(timeout=15);return outcome(fn)
    with ThreadPoolExecutor(max_workers=len(functions)) as pool:return list(pool.map(run,functions))

@contextmanager
def cli_context(path):
    # Trusted source/deployment discovery is synthetic here; actual CLI freezing,
    # Registry opening, command branching and usage export are not replaced.
    fixed={'source_files':{'cloud/independent-admission.py':'f'*64,'config/budget.json':'0'*64}}
    with patch.object(research,'ROOT',Path(path)),patch.object(cli,'ROOT',Path(path)),patch.object(cli,'source_manifest',lambda:deepcopy(fixed)):
        yield

def create_cli(path):
    path=Path(path);(path/'config').mkdir(parents=True);(path/'audit').mkdir()
    (path/'config/budget.json').write_bytes(canonical_json(budget()))
    (path/'audit/deployment.json').write_bytes(canonical_json({'source_files':{'independent.py':'b'*64}}))
    with cli_context(path):
        cli.freeze_task(new_raw(),{'success':True,'projects':[{'projectId':4202}]},field_catalog=CAT)
        cli.execute_metadata_command(NS(command='register-task',allocation='normal'),field_catalog=CAT)
        return cli.current_bridge(field_catalog=CAT)

def process_contender(store_path,document,kind,which,gate,q):
    try:
        r=Registry(FilesystemArtifactStore(store_path,data_classification='synthetic'),document)
        old=old_bridge(r);new=new_bridge(r,project=4101 if kind=='project' else 4202)
        q.put({'kind':'ready','pid':os.getpid()});gate.wait(20)
        if kind=='configurations':
            fn=(lambda:old_bridge(r,'old-C',4303).register(allocation='reserve')) if which=='old' else (lambda:r.register_config(new.package))
        elif kind=='research':
            initial=r.snapshot()['attempts'][0]['attempt_id']
            fn=(lambda:old.claim('research',allocation='reserve',retry_of=initial,reason='independent repaired input')) if which=='old' else (lambda:r.begin_attempt(new.config_id,'research',operation_key=new._operation('research')))
        else:
            fn=(lambda:r.begin_attempt(old.config_id,'research',operation_key=old._operation('research'))) if which=='old' else (lambda:new.claim())
        q.put({'kind':'result','which':which,'pid':os.getpid(),'outcome':outcome(fn)})
    except BaseException as e:q.put({'kind':'process_error','error':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()})

OBS={}
class AdmissionTests(unittest.TestCase):
    def registry(self,path=None,document=None):return Registry(MemoryArtifactStore() if path is None else FilesystemArtifactStore(path,data_classification='synthetic'),budget() if document is None else document)
    def pair(self,r,same=False):
        old=old_bridge(r);new=new_bridge(r,project=4101 if same else 4202);old.register();new.register();return old,new

    def test_plan_catalog_discovery_and_identity_are_frozen(self):
        p=new_plan();before=p.hash;request=p.request_hash;copy=p.to_dict();copy['field_catalog']['dollar_volume']['unit']='shares'
        copy['collection_plan']['fields'].clear();self.assertEqual(p.hash,before);self.assertEqual(p.request_hash,request)
        for change in ['project','source','catalog','retry','scope','lean-kind']:
            with self.subTest(change=change):
                raw=new_raw()
                if change=='project':raw['project_id']=4999
                elif change=='source':raw['collection_plan']['source_manifest_hash']='0'*64
                elif change=='catalog':raw['field_catalog']['dollar_volume']['unit']='shares'
                elif change=='retry':raw['max_retries']=3
                elif change=='scope':raw['scope']='research'
                else:raw['task_kind']='lean'
                with self.assertRaises((EngineeringTaskError,ValueError)):
                    CollectionTaskPlan.from_dict(raw,discovered_project_ids=[4202],field_catalog=CAT)

    def test_direct_registry_rejects_reserved_shape_mutations_without_charging(self):
        for change in ['marker-missing','marker-bool','marker-zero','scope','kind','missing-catalog','extra-envelope','unfrozen-fields']:
            with self.subTest(change=change):
                r=self.registry();package=new_bridge(r).package
                if change=='marker-missing':del package['engineering_task_schema_version']
                elif change=='marker-bool':package['engineering_task_schema_version']=True
                elif change=='marker-zero':package['engineering_task_schema_version']=0
                elif change=='scope':package['plan']['scope']='research'
                elif change=='kind':package['plan']['task_kind']='generic'
                elif change=='missing-catalog':del package['plan']['field_catalog']
                elif change=='extra-envelope':package['metadata']='additional'
                else:package['plan']['collection_plan']['fields'].reverse()
                with self.assertRaises((RegistryError,EngineeringTaskError,ValueError)):r.register_config(package)
                self.assertEqual(r.snapshot()['usage']['configurations']['total'],0)

    def test_configuration_cap_is_mixed_and_reserve_rename_restart_does_not_reset(self):
        path=RUN/'configuration-cap';r=self.registry(path);old=old_bridge(r);new=new_bridge(r);old.register();new.register(allocation='reserve')
        restarted=self.registry(path);before=restarted.snapshot()['usage']
        with self.assertRaises(BudgetExceeded):old_bridge(restarted,'different-old-name',4505).register()
        with self.assertRaises(BudgetExceeded):new_bridge(restarted,'different-new-name',4606).register(allocation='reserve')
        self.assertEqual(eng_count(restarted,'configurations'),2);self.assertEqual(restarted.snapshot()['usage'],before)
        self.assertEqual(new_bridge(restarted).register(),new.config_id)

    def test_failed_mixed_research_keeps_shared_charge_across_projects_and_allocations(self):
        r=self.registry();old,new=self.pair(r);a=old.claim('research');r.fail(a,'synthetic failure')
        b=new.claim(allocation='reserve');r.fail(b,'synthetic failure')
        self.assertEqual(r.snapshot()['usage']['research'],{'total':2,'normal':1,'reserve':1})
        with self.assertRaises(BudgetExceeded):old.claim('research',retry_of=a.attempt_id,reason='known repair')
        self.assertEqual(eng_count(r,'research'),2)

    def test_fixed_operation_and_research_only_are_rechecked_in_direct_registry(self):
        r=self.registry();new=new_bridge(r);new.register()
        for stage,operation in [('lean',new._operation('research')),('research','default'),('research','random-new-operation'),('research','engineering-plan:'+new.plan.hash+':research')]:
            with self.subTest(stage=stage,operation=operation),self.assertRaises(RegistryError):
                r.begin_attempt(new.config_id,stage,operation_key=operation)
        self.assertEqual(r.snapshot()['usage']['research']['total'],0);self.assertEqual(r.snapshot()['usage']['lean']['total'],0)
        self.assertTrue(new.claim().should_execute)

    def test_same_project_open_states_block_collection_registration_without_charge(self):
        for status in ['started','pending','ambiguous']:
            with self.subTest(status=status):
                r=self.registry();old=old_bridge(r);old.register();a=old.claim('research')
                if status=='pending':r.pending(a,external_id='independent-task')
                if status=='ambiguous':r.ambiguous(a,reason='transport timeout')
                before=r.snapshot()['usage']
                with self.assertRaises(RegistryError):new_bridge(r,project=4101).register()
                self.assertEqual(r.snapshot()['usage'],before)

    def test_both_directions_same_project_guard_is_independent_of_stage_and_interface(self):
        for first_kind,stage,status in [('old','research','started'),('old','lean','pending'),('new','research','ambiguous')]:
            with self.subTest(first_kind=first_kind,stage=stage,status=status):
                r=self.registry();old,new=self.pair(r,same=True)
                first=old if first_kind=='old' else new;other=new if first_kind=='old' else old
                a=r.begin_attempt(first.config_id,stage,operation_key=first._operation(stage))
                if status=='pending':r.pending(a,external_id='independent-pending')
                elif status=='ambiguous':r.ambiguous(a,reason='unknown synthetic dispatch')
                before=r.snapshot()['usage']
                with self.assertRaises(RegistryError):r.begin_attempt(other.config_id,'research',operation_key=other._operation('research'))
                with self.assertRaises((RegistryError,EngineeringTaskError)):other.claim('research')
                self.assertEqual(r.snapshot()['usage'],before)

    def test_collection_retry_zero_one_and_two_never_bypass_shared_stop(self):
        for retry_limit in [0,1,2]:
            with self.subTest(retry_limit=retry_limit):
                r=self.registry();new=new_bridge(r,retries=retry_limit);new.register();a=new.claim();r.fail(a,'synthetic failed')
                self.assertFalse(new.claim().should_execute)
                for previous,reason in [('wrong-attempt','repair'),(a.attempt_id,''),(a.attempt_id,None)]:
                    with self.subTest(previous=previous,reason=reason),self.assertRaises(RegistryError):
                        new.claim(retry_of=previous,reason=reason)
                if retry_limit==0:
                    with self.assertRaises(RegistryError):new.claim(retry_of=a.attempt_id,reason='explicit repair')
                    self.assertEqual(eng_count(r,'research'),1)
                else:
                    b=new.claim(allocation='reserve',retry_of=a.attempt_id,reason='explicit repair');self.assertTrue(b.should_execute);r.fail(b,'second synthetic failure')
                    with self.assertRaises((RegistryError,BudgetExceeded)):new.claim(retry_of=b.attempt_id,reason='another repair')
                    self.assertEqual(eng_count(r,'research'),2)

    def test_completed_reuse_is_free_after_other_plan_opens_same_project(self):
        r=self.registry();old,new=self.pair(r,same=True);a=new.claim();r.complete(a,{'synthetic_verified':True})
        b=old.claim('research');self.assertTrue(b.should_execute);before=r.snapshot()['usage']
        again=new.claim();self.assertFalse(again.should_execute);self.assertEqual(again.attempt_id,a.attempt_id)
        self.assertEqual(new.read_result(a),{'synthetic_verified':True});self.assertEqual(r.snapshot()['usage'],before)

    def test_submit_checks_adapter_before_charge_and_unknown_is_not_auto_retried(self):
        r=self.registry();new=new_bridge(r);new.register()
        with self.assertRaises(EngineeringTaskError):new.submit()
        self.assertEqual(eng_count(r,'research'),0)
        class Unknown:
            calls=0
            def submit_research(self,*a,**k):self.calls+=1;raise TimeoutError('PRIVATE-SYNTHETIC-DETAIL')
        adapter=Unknown();new.adapter=adapter;a=new.submit();self.assertEqual(a.status,'ambiguous')
        again=new.submit(retry_of=a.attempt_id,reason='not reconciliation');self.assertFalse(again.should_execute)
        self.assertEqual(adapter.calls,1);self.assertEqual(eng_count(r,'research'),1)
        self.assertNotIn('PRIVATE-',json.dumps(r.snapshot()))
        with self.assertRaises(RegistryError):r.fail(a,'guess failure')

    def test_rejected_submission_charged_before_callback_and_not_refunded(self):
        r=self.registry();observed=[]
        class Rejected:
            def submit_research(self,payload,**k):
                observed.append(r.snapshot()['usage']['research']['total']);raise SubmissionRejected('synthetic rejection')
        new=new_bridge(r,adapter=Rejected());new.register();a=new.submit();self.assertEqual(a.status,'failed')
        self.assertEqual(observed,[1]);self.assertFalse(new.submit().should_execute)
        b=new.submit(allocation='reserve',retry_of=a.attempt_id,reason='synthetic repaired transport')
        self.assertEqual(b.status,'failed');self.assertEqual(observed,[1,2]);self.assertEqual(eng_count(r,'research'),2)

    def test_global_quota_also_applies_without_resetting_initial_usage(self):
        doc=budget({'research':{'total':19,'normal':12,'reserve':7}});r=self.registry(document=doc)
        old,new=self.pair(r);a=new.claim(allocation='reserve');r.fail(a,'synthetic failure')
        with self.assertRaises(BudgetExceeded):old.claim('research',allocation='reserve')
        self.assertEqual(r.snapshot()['usage']['research']['total'],20);self.assertEqual(eng_count(r,'research'),1)

    def do_thread_race(self,kind,disk):
        path=RUN/(kind+'-thread-'+str(disk));r=self.registry(path if disk else None);old=old_bridge(r);old.register()
        if kind in ['research','project']:
            new=new_bridge(r,project=4101 if kind=='project' else 4202);new.register()
            if kind=='research':seed=old.claim('research');r.fail(seed,'seeded synthetic failure')
        def reopen():return self.registry(path) if disk else Registry(r.store,budget())
        r1,r2=reopen(),reopen();a=old_bridge(r1);b=new_bridge(r2,project=4101 if kind=='project' else 4202)
        if kind=='configurations':
            functions=[lambda:old_bridge(r1,'old-C',4303).register(allocation='reserve'),lambda:r2.register_config(b.package)]
        elif kind=='research':
            functions=[lambda:a.claim('research',allocation='reserve',retry_of=seed.attempt_id,reason='explicit synthetic repair'),
                       lambda:r2.begin_attempt(b.config_id,'research',operation_key=b._operation('research'))]
        else:functions=[lambda:a.claim('research'),lambda:b.claim()]
        out=race(functions);accepted='registered' if kind=='configurations' else 'permit'
        self.assertEqual(sum(x['kind']==accepted for x in out),1,out)
        self.assertEqual(sum(x['kind']=='rejected' for x in out),1,out)
        self.assertEqual(eng_count(r,'configurations' if kind=='configurations' else 'research'),1 if kind=='project' else 2)
        OBS['thread_'+kind+'_'+str(disk)]=out

    def test_thread_mixed_registration_remaining_one_slot_memory(self):self.do_thread_race('configurations',False)
    def test_thread_mixed_registration_remaining_one_slot_separate_store(self):self.do_thread_race('configurations',True)
    def test_thread_mixed_research_remaining_one_slot_memory(self):self.do_thread_race('research',False)
    def test_thread_mixed_research_remaining_one_slot_separate_store(self):self.do_thread_race('research',True)
    def test_thread_mixed_same_project_claim_memory(self):self.do_thread_race('project',False)
    def test_thread_mixed_same_project_claim_separate_store(self):self.do_thread_race('project',True)

    def do_process_race(self,kind):
        path=RUN/(kind+'-process');doc=budget();r=self.registry(path);old=old_bridge(r);old.register()
        if kind in ['research','project']:
            new=new_bridge(r,project=4101 if kind=='project' else 4202);new.register()
            if kind=='research':a=old.claim('research');r.fail(a,'independent process-race seed')
        context=mp.get_context('spawn');gate=context.Event();q=context.Queue()
        jobs=[context.Process(target=process_contender,args=(str(path),doc,kind,which,gate,q)) for which in ['old','new']]
        for p in jobs:p.start()
        ready=[q.get(timeout=25) for _ in jobs];self.assertTrue(all(x['kind']=='ready' for x in ready),ready);gate.set()
        answers=[q.get(timeout=25) for _ in jobs]
        for p in jobs:p.join(25);self.assertEqual(p.exitcode,0)
        self.assertTrue(all(x['kind']=='result' for x in answers),answers)
        accepted='registered' if kind=='configurations' else 'permit'
        self.assertEqual(sum(x['outcome']['kind']==accepted for x in answers),1,answers)
        self.assertEqual(sum(x['outcome']['kind']=='rejected' for x in answers),1,answers)
        self.assertEqual(eng_count(r,'configurations' if kind=='configurations' else 'research'),1 if kind=='project' else 2)
        OBS['process_'+kind]={'ready':ready,'answers':answers,'usage':r.snapshot()['usage']}

    def test_windows_process_mixed_registration_remaining_one_slot(self):self.do_process_race('configurations')
    def test_windows_process_mixed_research_remaining_one_slot(self):self.do_process_race('research')
    def test_windows_process_mixed_same_project(self):self.do_process_race('project')

    def test_cli_real_store_claim_races_old_bridge_on_remaining_slot(self):
        path=RUN/'cli-workspace';new=create_cli(path)
        with cli_context(path):
            old=old_bridge(research.open_registry());old.register();a=old.claim('research');old.registry.fail(a,'seeded prior failed execution')
            digest_before=cli.execution_source_manifest()['source_hash']
            def claim_cli():
                value=cli.execute_metadata_command(NS(command='claim-task',allocation='normal',retry_of=None,reason=None),field_catalog=CAT)
                return NS(**value)
            results=race([claim_cli,lambda:old.claim('research',allocation='reserve',retry_of=a.attempt_id,reason='explicit repair')])
            self.assertEqual(sum(x['kind']=='permit' for x in results),1,results)
            self.assertEqual(sum(x['kind']=='rejected' for x in results),1,results)
            final=research.open_registry();self.assertEqual(eng_count(final,'research'),2)
            self.assertEqual(cli.execution_source_manifest()['source_hash'],digest_before)
            self.assertEqual(cli.execute_metadata_command(NS(command='task-status'),field_catalog=CAT)['usage'],final.snapshot()['usage'])
            OBS['cli_mixed_race']=results

    def test_cli_collection_registration_refuses_old_pending_on_same_project(self):
        path=RUN/'cli-project-workspace';path.mkdir(parents=True);(path/'config').mkdir();(path/'audit').mkdir()
        (path/'config/budget.json').write_bytes(canonical_json(budget()))
        (path/'audit/deployment.json').write_bytes(canonical_json({'source_files':{'independent.py':'b'*64}}))
        with cli_context(path):
            r=research.open_registry();old=old_bridge(r,project=4202);old.register();a=old.claim('research');r.pending(a,external_id='observed-synthetic-pending')
            cli.freeze_task(new_raw(),{'success':True,'projects':[{'projectId':4202}]},field_catalog=CAT)
            before=r.snapshot()['usage']
            with self.assertRaises(RegistryError):cli.execute_metadata_command(NS(command='register-task',allocation='normal'),field_catalog=CAT)
            self.assertEqual(r.snapshot()['usage'],before)

    def test_original_ledger_copy_preserves_inflight_guard_and_shared_remaining_slot(self):
        store=MemoryArtifactStore();runtime=Path(os.environ['AQRP_REVIEW_HISTORICAL_RUNTIME'])
        for p in runtime.rglob('*'):
            if p.is_file():store.write_once(p.relative_to(runtime).as_posix(),p.read_bytes())
        doc=json.loads(store.read_bytes('registry/baseline.json'));r=Registry(store,doc);initial=r.snapshot();oldids=[]
        for identity in initial['config_ids']:
            package=json.loads(store.read_bytes('configurations/'+identity+'.json'))
            if package.get('engineering_task_schema_version')==1:oldids.append((identity,package))
        self.assertEqual(len(oldids),1);project=oldids[0][1]['plan']['project_id'];before=deepcopy(initial['usage'])
        with self.assertRaises(RegistryError):new_bridge(r,'same-old-project',project).register()
        self.assertEqual(r.snapshot()['usage'],before)
        fresh=new_bridge(r,'new-in-independent-copy',project+1000000);fresh.register();a=fresh.claim();self.assertTrue(a.should_execute)
        self.assertEqual(eng_count(r,'configurations'),2);self.assertEqual(eng_count(r,'research'),2)
        with self.assertRaises(BudgetExceeded):new_bridge(r,'another-copy-plan',project+2000000).register(allocation='reserve')
        self.assertEqual(r.snapshot()['usage']['lean'],before['lean'])
        OBS['original_copy']={'initial_usage':before,'final_usage':r.snapshot()['usage'],'source_files_untouched':True}

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)

def main():
    output=io.StringIO();r=unittest.TextTestRunner(stream=output,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(AdmissionTests))
    text=output.getvalue();(ROOT/'first_output.txt').write_text(text,encoding='utf-8')
    def method(t):return getattr(t,'test_case',t).id()
    failed={method(t) for t,_ in r.failures};errored={method(t) for t,_ in r.errors}
    locations={}
    for rel in ['cloud/qresearch/registry.py','cloud/qresearch/collection_tasks.py','cloud/qresearch/engineering_tasks.py','tools/collection_task_cli.py']:
        for n in ast.walk(ast.parse((SOURCE/rel).read_text(encoding='utf-8-sig'))):
            if isinstance(n,(ast.FunctionDef,ast.ClassDef)):locations[rel+':'+n.name]=[n.lineno,n.end_lineno]
    result={'commit':'e513c66e5965133fbe83fb0ab987eae853f96260','methods':r.testsRun,
      'passed_methods':r.testsRun-len(failed|errored),'failed_methods':len(failed),'error_methods':len(errored),
      'subcases':r.subcases,'skipped':len(r.skipped),'failure_records':len(r.failures),'error_records':len(r.errors),
      'failures':[{'method':method(t),'traceback':tb} for t,tb in r.failures],
      'errors':[{'method':method(t),'traceback':tb} for t,tb in r.errors],
      'observations':OBS,'source_locations':locations,'python':sys.version,'actual_external_calls':0,
      'developer_fixture_imports':False,'command':[sys.executable,'-B',str(Path(__file__).resolve())],
      'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'first_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(text);print(json.dumps({k:result[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}))
    return result['exit_code']
if __name__=='__main__':mp.freeze_support();raise SystemExit(main())
