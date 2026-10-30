from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os,sys,json,subprocess,time,unittest
sys.dont_write_bytecode=True
import independent_stdio as base
P=base.product;D=Path(__file__).resolve().parent;S=D.parent/'source'
CASES=[];PROCESSES=[]
def mark(label):CASES.append(label)
FACTORY='''from pathlib import Path
from datetime import datetime,timezone
import os,json
from followup_host import FollowupHost,TransportAuthority
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController
import independent_stdio as base
Path(os.environ['ENTRY_MARKER']).write_text('imported',encoding='utf-8')
def controller():
    return TaskFollowupController(Registry(MemoryArtifactStore(),base.LIMITS),base.POLICY)
def valid():
    root=os.environ.get('ENTRY_STORE')
    h=base.open_host(root,read=os.environ.get('ENTRY_READ')=='1',clock=lambda:datetime(2099,1,1,tzinfo=timezone.utc)) if root else FollowupHost(controller(),authority=TransportAuthority('synthetic-entry'),enabled=True)
    Path(os.environ['ENTRY_TYPES']).write_text(json.dumps({'host':type(h).__module__,'authority':type(h.authority).__module__}),encoding='utf-8')
    return h
def disabled():return FollowupHost()
def duck():
    class Duck:enabled=True
    return Duck()
def host_subclass():
    class Host(FollowupHost):pass
    return Host(controller(),authority=TransportAuthority('synthetic-entry'),enabled=True)
def authority_subclass():
    class Authority(TransportAuthority):pass
    return FollowupHost(controller(),authority=Authority('synthetic-entry'),enabled=True)
def controller_subclass():
    class Controller(TaskFollowupController):pass
    c=Controller(Registry(MemoryArtifactStore(),base.LIMITS),base.POLICY)
    return FollowupHost(c,authority=TransportAuthority('synthetic-entry'),enabled=True)
def wrong_authority():return FollowupHost(controller(),authority=object(),enabled=True)
def wrong_controller():return FollowupHost(object(),authority=TransportAuthority('synthetic-entry'),enabled=True)
def bool_integer_enabled():return FollowupHost(controller(),authority=TransportAuthority('synthetic-entry'),enabled=1)
'''
class IndependentEntrypoints(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(dir=D);self.addCleanup(self.temp.cleanup);self.t=Path(self.temp.name)
        (self.t/'entry_factory.py').write_text(FACTORY,encoding='utf-8')
        self.env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',PYTHONPATH=os.pathsep.join([str(self.t),str(D),str(S/'tools'),str(S/'cloud')]),ENTRY_MARKER=str(self.t/'factory_imported'),ENTRY_TYPES=str(self.t/'types.json'))
    def command(self,mode,args):
        prefix={'canonical':['-c','import followup_host; raise SystemExit(followup_host.main())'],'script':[str(S/'tools/followup_host.py')],'module':['-m','followup_host']}[mode]
        return [sys.executable,'-B',*prefix,*args]
    def invoke(self,mode,args,messages=()):
        text=''.join(json.dumps(m,ensure_ascii=False)+'\n' for m in messages)
        command=self.command(mode,args);started=time.monotonic()
        r=subprocess.run(command,input=text,text=True,encoding='utf-8',capture_output=True,env=self.env,cwd=self.t,timeout=30)
        PROCESSES.append({'command':command,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'seconds':round(time.monotonic()-started,3),'input_sha256':base.digest(text)})
        return r
    def enabled(self,command='serve',kind='valid',attempt=None):
        args=[command,'--enable-dispatch','--host-factory','entry_factory:'+kind]
        if attempt is not None:args+=['--attempt',attempt]
        return args
    def success(self,mode,args,messages=()):
        r=self.invoke(mode,args,messages);self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stderr,'')
        return [json.loads(s) for s in r.stdout.splitlines()]
    def pending(self,fresh=False,read=False):
        path=self.t/'private_store';h,a=base.fixture(path,fresh=fresh,read=read)
        self.env['ENTRY_STORE']=str(path);self.env['ENTRY_READ']='1' if read else '0'
        return h,a
    def test_01_three_real_entrypoints_accept_standard_factory_and_canonical_types(self):
        for mode in ('script','module','canonical'):
            with self.subTest(mode=mode):
                self.assertEqual(self.success(mode,self.enabled()),[])
                self.assertEqual(json.loads((self.t/'types.json').read_text()),{'host':'followup_host','authority':'followup_host'})
                mark('valid_empty_standard_factory_'+mode)
    def test_02_default_off_ignores_factory_and_never_opens_store(self):
        for mode in ('script','module','canonical'):
            for command in ('plan','serve'):
                args=[command,'--host-factory','entry_factory:valid']
                if command=='plan':args+=['--attempt','a'*32]
                out=self.success(mode,args,[{'command':c,'attempt_id':'a'*32} for c in ('wake','register','sync','status')])
                self.assertTrue(all(x['action']=='dispatch_disabled' and x['should_execute'] is False for x in out))
                self.assertFalse((self.t/'factory_imported').exists());self.assertFalse((self.t/'private_store').exists())
                mark('off_no_import_no_store_'+mode+'_'+command)
    def test_03_exact_type_and_permission_constructor_gates_remain_closed(self):
        for mode in ('script','module','canonical'):
            for kind in ('disabled','duck','host_subclass','authority_subclass','controller_subclass','wrong_authority','wrong_controller','bool_integer_enabled'):
                with self.subTest(mode=mode,kind=kind):
                    r=self.invoke(mode,self.enabled(kind=kind));self.assertNotEqual(r.returncode,0)
                    self.assertEqual(r.stdout,'');self.assertFalse((self.t/'private_store').exists())
                    mark('strict_factory_reject_'+mode+'_'+kind)
    def test_04_real_UTC_for_pending_plan_serve_all_modes(self):
        h,a=self.pending(fresh=True);h.controller.register(a)
        watch='engineering/followup/'+a+'/events.jsonl'
        before=h.store.read_bytes(watch);journal=h.store.read_bytes(h.controller.registry.JOURNAL)
        for mode in ('script','module','canonical'):
            plan=self.success(mode,self.enabled('plan',attempt=a))
            serve=self.success(mode,self.enabled(),[{'command':c,'attempt_id':a} for c in ('status','wake')])
            self.assertEqual([x['action'] for x in plan+serve],['wait_for_delivery']*3)
            self.assertFalse(h.store.exists(h._stream(a)));self.assertEqual(h.store.read_bytes(watch),before)
            self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),journal)
            mark('fresh_pending_real_UTC_overrides2099_'+mode)
    def test_05_cross_entrypoint_unknown_original_response_and_read_permission(self):
        h,a=self.pending();journal=h.store.read_bytes(h.controller.registry.JOURNAL);wake={'command':'wake','attempt_id':a}
        q=self.success('script',self.enabled(),[wake])[0];self.assertEqual(q['tool_name'],P.PROJECTS)
        before=h.store.read_bytes(h._stream(a))
        status=self.success('module',self.enabled('plan',attempt=a))[0]
        unknown=self.success('module',self.enabled(),[wake])[0]
        self.assertEqual(status['failure_code'],'reserved_response_unknown');self.assertEqual(unknown['failure_code'],'reserved_response_unknown')
        self.assertEqual(h.store.read_bytes(h._stream(a)),before);mark('script_to_module_unknown_no_redispatch')
        out=self.success('canonical',self.enabled(),[base.response(q,base.projects()),wake]);self.assertEqual(out[0]['action'],'projects_observed')
        hist=out[1];self.assertEqual((hist['tool_name'],hist['arguments']),(P.HISTORY,{'projectId':base.PROJECT,'page':1}));mark('late_discovery_canonical_response_resumes_once')
        out=self.success('script',self.enabled(),[base.response(hist,base.terminal()),wake]);self.assertEqual(out[0]['action'],'history_observed')
        self.assertEqual(out[1]['failure_code'],'completed_read_not_authorized');mark('native_directory_terminal_does_not_grant_chat_read')
        status=self.success('module',self.enabled(),[{'command':c,'attempt_id':a} for c in ('register','sync','status','wake')])
        self.assertTrue(all(x['should_execute'] is False for x in status));self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),journal)
        mark('metadata_commands_no_dispatch_or_budget_transition')
    def test_06_cross_entrypoint_permitted_read_is_only_receipt_handoff(self):
        h,a=self.pending(read=True);journal=h.store.read_bytes(h.controller.registry.JOURNAL);wake={'command':'wake','attempt_id':a}
        q=self.success('module',self.enabled(),[wake])[0]
        hist=self.success('script',self.enabled(),[base.response(q,base.projects()),wake])[1]
        rd=self.success('canonical',self.enabled(),[base.response(hist,base.terminal()),wake])[1]
        self.assertEqual(rd['tool_name'],P.READ)
        native=base.native({'success':True,'backtest':{'projectId':base.PROJECT,'backtestId':base.BACKTEST,'completed':True,'status':'Completed.','progress':1,'statistics':{'Net Profit':'INDEPENDENT_PRIVATE_SENTINEL'}}})
        result=self.success('script',self.enabled(),[base.response(rd,native)])[0]
        self.assertEqual(result['action'],'awaiting_native_receipt');self.assertEqual(result['receipt_parser'],'tools/stage2.py backtest-result')
        self.assertNotIn('INDEPENDENT_PRIVATE_SENTINEL',json.dumps(result));mark('permitted_read_across_all_entries_handoff_only')
        for mode in ('script','module','canonical'):
            for x in self.success(mode,self.enabled(),[{'command':'status','attempt_id':a},wake]):
                self.assertEqual(x['action'],'awaiting_native_receipt');self.assertFalse(x['should_execute'])
            mark('no_read_redispatch_'+mode)
        events=base.decode_events(h.store.read_bytes(h._stream(a)))
        self.assertEqual([x['event']['tool_name'] for x in events if x['event']['kind']=='reserved'],[P.PROJECTS,P.HISTORY,P.READ])
        self.assertNotIn(b'INDEPENDENT_PRIVATE_SENTINEL',h.store.read_bytes(h._stream(a)))
        self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),journal);mark('native_raw_not_stored_and_no_Registry_settlement')
    def test_07_real_two_process_entries_race_dispatch_once(self):
        h,a=self.pending();journal=h.store.read_bytes(h.controller.registry.JOURNAL);wake={'command':'wake','attempt_id':a};barrier=Barrier(2)
        before=datetime.now(timezone.utc)
        def worker(mode):
            barrier.wait(timeout=10);return self.success(mode,self.enabled(),[wake])[0]
        with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(worker,('script','module')))
        after=datetime.now(timezone.utc)
        requests=[x for x in responses if x['type']=='tool_request'];self.assertEqual(len(requests),1)
        self.assertEqual(requests[0]['tool_name'],P.PROJECTS);self.assertEqual([x['action'] for x in responses if x['type']=='status'],['attention_required'])
        events=base.decode_events(h.store.read_bytes(h._stream(a)));reserved=[x['event'] for x in events if x['event']['kind']=='reserved']
        self.assertEqual(len(reserved),1);stamp=datetime.fromisoformat(reserved[0]['reserved_at']);self.assertLessEqual(before,stamp);self.assertLessEqual(stamp,after)
        self.assertEqual(stamp.tzinfo,timezone.utc);self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),journal)
        mark('script_module_actual_concurrent_processes_single_discovery');mark('reserved_time_real_UTC_not_factory2099')
        out=self.success('canonical',self.enabled(),[base.response(requests[0],base.projects()),wake])
        self.assertEqual(out[0]['action'],'projects_observed');self.assertEqual(out[1]['tool_name'],P.HISTORY);mark('original_race_response_resumes_once')
    def test_08_actual_enabled_stdin_cannot_supply_clock_or_authority(self):
        h,a=self.pending(fresh=True);h.controller.register(a);journal=h.store.read_bytes(h.controller.registry.JOURNAL)
        for mode in ('script','module','canonical'):
            bad=[{'command':'wake','attempt_id':a,'now':'2099-01-01T00:00:00Z'}, {'command':'wake','attempt_id':a,'read_grants':True}, {'command':'wake','attempt_id':a,'enabled':True}]
            out=self.success(mode,self.enabled(),bad+[{'command':'wake','attempt_id':a}])
            self.assertEqual([x['action'] for x in out],['attention_required']*3+['wait_for_delivery'])
            self.assertTrue(all(x['should_execute'] is False for x in out));self.assertFalse(h.store.exists(h._stream(a)))
            self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),journal);mark('enabled_stdin_no_clock_or_authority_'+mode)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentEntrypoints))
    (D/'independent_entrypoints_results.json').write_text(json.dumps({'methods':result.testsRun,'named_scenarios':len(CASES),'cases':CASES,'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],'skipped':[(str(t),s) for t,s in result.skipped],'actually_executed':True},ensure_ascii=False,indent=2),encoding='utf-8')
    (D/'independent_entrypoints_subprocesses.json').write_text(json.dumps(PROCESSES,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(not result.wasSuccessful())
