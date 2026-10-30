from pathlib import Path
import base64, copy, hashlib, json, os, subprocess, sys, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
SOURCE=ROOT/'source'
sys.path[:0]=[str(SOURCE/'cloud'),str(SOURCE/'tools')]
from qresearch.artifacts import MemoryArtifactStore, FilesystemArtifactStore, canonical_json, content_hash, decode_events
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.engineering_receipts import backtest_observation
from qresearch.task_followup import TaskFollowupController
import followup_host as H

START=datetime(2026,2,11,5,30,tzinfo=timezone.utc)
DEAD=START+timedelta(seconds=1800)
PROJECT=9437
BACKTEST='independent-host-api-native'
POLICY={'schema_version':1,'notification_grace_seconds':1800,'max_history_pages':3}
LIMITS={k:{'total':8,'normal':6,'reserve':2} for k in ('configurations','research','lean')}
SCENARIOS=[]
PROCESS_COMMANDS=[]
def scenario(label):SCENARIOS.append(label)
def digest(label):return hashlib.sha256(label.encode()).hexdigest()
def plan():
    return EngineeringTaskPlan.from_dict({'schema_version':1,'plan_id':'independent-host-api-plan',
      'scope':'engineering','project_id':PROJECT,'source_manifest_hash':digest('independent-host-source'),
      'deployment_hash':digest('independent-deployment'),'request_mode':'resolved','data_request':{
      'dataset':'US Equities','fields':['close'],'sids':['independent-sid-a','independent-sid-b'],
      'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00',
      'data_version':'synthetic-independent-host','universe_hash':digest('independent-universe'),
      'normalization':'raw','timezone':'America/New_York'},
      'observation_window':{'start':'2018-03-01T00:00:00-05:00','end_exclusive':'2018-03-02T00:00:00-05:00'},
      'required_checks':{'research':['raw_data_received','second_prefetch_no_history'],'lean':['raw_data_received','no_orders']},
      'max_retries':{'research':0,'lean':0},'report_namespace':'independent-host-native',
      'orders_enabled':False,'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None},discovered_project_ids=[PROJECT])
def deployment(payload):return {k:payload['identity'][k] for k in ('source_manifest_hash','deployment_hash')}|{'input_hash':digest('input')}
def receipt(payload):
    i=payload['identity'];external=BACKTEST if i['stage']=='lean' else f"qc-research:{PROJECT}:{i['attempt_id']}"
    return {'identity':i,'identity_kind':payload['external_identity_kind'],'accepted':True,'status':'submitted','external_id':external,'deployment':deployment(payload),'raw_receipt':{'success':True,'backtestId':external} if i['stage']=='lean' else {'success':True,'logical_id':external}}
def report_wrapper(payload):
    stage=payload['identity']['stage'];report={'schema_version':1,'identity':payload['identity'],'status':'completed','terminal':True,
      'checks':{key:True for key in payload['plan']['required_checks'][stage]},
      'statistics':{'record_count':3,'history_calls_first':1,'history_calls_second':0} if stage=='research' else {'data_event_count':3,'orders_submitted':0,'runtime_error_count':0},
      'market_values_exported':False,'economic_factor_tested':False,'final_data_accessed':False,'full_US200_coverage_certified':False,'actual_availability_verified':False}
    return {'cloud_report':report,'report_ref':{'key':payload['report_key'],'sha256':content_hash(report)}}
def completion(payload):return {'platform':{'identity':dict(payload['identity'],external_id=receipt(payload)['external_id']),'terminal':True,'status':'completed','deployment':deployment(payload),'raw_receipt':{'success':True}},**report_wrapper(payload)}
def fixture(path=None):
    store=MemoryArtifactStore() if path is None else FilesystemArtifactStore(path,lock_timeout=15)
    with patch('qresearch.registry.datetime') as clock:
        clock.now.return_value=START
        reg=Registry(store,LIMITS);bridge=EngineeringTaskBridge(reg,plan());bridge.register()
        research=bridge.claim('research');bridge.record_submission(research,receipt(bridge.payload(research)));bridge.consume_completion(research,completion_source=completion)
        lean=bridge.claim('lean');bridge.record_submission(lean,receipt(bridge.payload(lean)))
    controller=TaskFollowupController(reg,POLICY)
    return store,reg,bridge,lean.attempt_id,controller
def authority(attempt,*,discovery=True,history=True,mode='chat_connector',basis='delivered_terminal_notification',grant=True,project=PROJECT,backtest=BACKTEST):
    return H.TransportAuthority('independent-synthetic-transport',frozenset([attempt]) if discovery else frozenset(),frozenset([attempt]) if history else frozenset(),mode,
       (H.ReadGrant(attempt,project,backtest,basis,digest('trusted-transport-proof')),) if grant else ())
def host(c,a,**kw):return H.FollowupHost(c,authority=authority(a,**kw),enabled=True,clock=lambda:DEAD)
def native(value):return {'structuredContent':copy.deepcopy(value),'content':[{'type':'text','text':json.dumps(value)}]}
def projects(ids=(PROJECT,)):return native({'success':True,'projects':[{'projectId':i,'name':'independent','language':'Py'} for i in ids],'page':1,'totalPages':1,'nextPage':None})
def history(page=1,total=1,*,target=True,status='Completed.',progress=1):
    return native({'success':True,'backtests':[{'backtestId':BACKTEST if target else 'independent-other-'+str(page),'status':status,'progress':progress,'netProfit':987654.123456}],'totalPages':total})
def terminal():return native({'success':True,'backtest':{'projectId':PROJECT,'backtestId':BACKTEST,'completed':True,'progress':1,'status':'Completed.','statistics':{'Total Orders':'0','Net Profit':'SYNTHETIC-NATIVE-SENTINEL'},'runtimeStatistics':{'Equity':'SYNTHETIC-NATIVE-SENTINEL'},'charts':[],'hasInitializeError':False,'error':None}})
def message(request,result):return {k:request[k] for k in ('attempt_id','correlation_id','tool_name','arguments')}|{'command':'response','result':result}
def discover(h,a):
    q=h.prepare(a);assert q['tool_name']==H.PROJECTS
    assert h.accept_response(message(q,projects()))['action']=='projects_observed'
    return q
def target_observed(h,a):
    discover(h,a);q=h.prepare(a);assert q['tool_name']==H.HISTORY
    assert h.accept_response(message(q,history()))['action']=='history_observed'
    return q
def native_logs(payload):
    encoded=base64.b64encode(canonical_json(report_wrapper(payload))).decode()
    chunks=[encoded[i:i+500] for i in range(0,len(encoded),500)]
    lines=[f"2018-03-02 00:00:00 AQRP_ENGINEERING {payload['identity']['attempt_id']} {i}/{len(chunks)} {chunk}" for i,chunk in enumerate(chunks)]
    return [{'tool_name':'mcp__quantconnect__search_backtest_logs','arguments':{'projectId':PROJECT,'backtestId':BACKTEST,'query':'AQRP_ENGINEERING '+payload['identity']['attempt_id'],'page':1},'result':native({'success':True,'logs':lines,'totalPages':1})}]

class Tests(unittest.TestCase):
    def test_01_default_off_and_metadata_no_permissions(self):
        class Bomb:
            def __getattribute__(self,name):raise AssertionError('Unexpected access '+name)
        disabled=H.FollowupHost(Bomb(),authority=Bomb())
        a='a'*32
        for command in ('wake','status','register','sync'):
            self.assertEqual(disabled.command({'command':command,'attempt_id':a})['action'],'dispatch_disabled');scenario('disabled-'+command)
        for enabled in (0,1,None,'true'):
            with self.assertRaises(ValueError):H.FollowupHost(enabled=enabled)
            scenario('strict-enabled-'+repr(enabled))
        store,reg,bridge,a,c=fixture();h=host(c,a)
        for command in ('register','sync','status'):
            self.assertFalse(h.command({'command':command,'attempt_id':a})['should_execute']);scenario('metadata-no-dispatch-'+command)
        self.assertFalse(store.exists(h._stream(a)))
    def test_02_original_deadline_and_discovery_once(self):
        store,reg,bridge,a,c=fixture();h=host(c,a);raw=store.read_bytes(reg.JOURNAL)
        h.clock=lambda:DEAD-timedelta(microseconds=1)
        self.assertEqual(h.prepare(a)['action'],'wait_for_delivery');scenario('deadline-minus-microsecond')
        h=host(c,a);q=h.prepare(a);self.assertEqual(q['arguments'],{'page':1});scenario('deadline-exact-discovery')
        for accessor in (h.inspect,h.prepare,host(c,a).prepare):
            self.assertEqual(accessor(a)['action'],'attention_required');scenario('unanswered-discovery-visible')
        self.assertEqual(h.accept_response(message(q,projects()))['action'],'projects_observed')
        h2=host(c,a);q2=h2.prepare(a);self.assertEqual(q2['tool_name'],H.HISTORY);scenario('restart-retains-project-observation')
        self.assertEqual(store.read_bytes(reg.JOURNAL),raw)
    def test_03_authority_is_explicit_and_exact_task(self):
        for kw,expected in [({'discovery':False},'discovery_not_authorized'),({'history':False},'history_not_authorized')]:
            store,reg,bridge,a,c=fixture();h=host(c,a,**kw)
            if kw.get('history') is False:discover(h,a)
            before=store.read_bytes(reg.JOURNAL);got=h.prepare(a)
            self.assertEqual(got['failure_code'],expected)
            first=store.read_bytes(h._stream(a));self.assertEqual(h.prepare(a)['failure_code'],expected);self.assertEqual(first,store.read_bytes(h._stream(a)))
            self.assertEqual(before,store.read_bytes(reg.JOURNAL));scenario(expected)
        store,reg,bridge,a,c=fixture()
        for basis in ('directory_completed','LLM_true',''):
            with self.assertRaises(ValueError):authority(a,basis=basis)
            scenario('invalid-grant-basis-'+basis)
        identity={'attempt_id':a,'project_id':PROJECT,'backtest_id':BACKTEST}
        variants=[({'grant':False},False),({'mode':'disabled'},False),({'basis':'transport_completed_reads'},False),({'mode':'completion_reads_permitted','basis':'transport_completed_reads'},True),({'basis':'historical_user_reference'},True),({'project':PROJECT+1},False),({'backtest':'other'},False)]
        for kw,expected in variants:
            self.assertEqual(authority(a,**kw).permits_read(identity),expected);scenario('grant-binding-'+repr(kw))
    def test_04_binding_conflicts_and_duplicate_idempotence(self):
        mutations={'correlation':lambda m:m.update(correlation_id='f'*32),'tool':lambda m:m.update(tool_name=H.READ),'args':lambda m:m.update(arguments={'page':2}),'extra':lambda m:m.update(allow_read=True),'bool_page':lambda m:m.update(arguments={'page':True})}
        for label,edit in mutations.items():
            store,reg,bridge,a,c=fixture();h=host(c,a);q=h.prepare(a);m=message(q,projects());edit(m)
            got=h.accept_response(m);self.assertEqual(got['failure_code'],'response_binding_rejected')
            first=store.read_bytes(h._stream(a));h.accept_response(m);self.assertEqual(store.read_bytes(h._stream(a)),first);self.assertEqual(h.prepare(a)['action'],'attention_required');scenario('binding-'+label)
        store,reg,bridge,a,c=fixture();h=host(c,a);q=h.prepare(a);m=message(q,projects());h.accept_response(m)
        before=store.read_bytes(h._stream(a));self.assertEqual(h.accept_response(m)['action'],'projects_observed');self.assertEqual(before,store.read_bytes(h._stream(a)));scenario('duplicate-identical-free')
        changed=message(q,projects((PROJECT,PROJECT+1)));self.assertEqual(h.accept_response(changed)['failure_code'],'response_conflict');self.assertEqual(h.prepare(a)['action'],'attention_required');scenario('conflicting-original-response-stops')
    def test_05_bad_discovery_is_not_authority(self):
        values=[projects(()),projects((PROJECT+1,)),native({'success':True,'projects':[{'projectId':True}]}),native({'success':True,'projects':[{'projectId':PROJECT},{'projectId':PROJECT}]}),native({'success':False,'errors':['synthetic error']})]
        for i,result in enumerate(values):
            store,reg,bridge,a,c=fixture();h=host(c,a);q=h.prepare(a);h.accept_response(message(q,result));self.assertEqual(h.prepare(a)['action'],'attention_required');scenario('bad-projects-'+str(i))
    def test_06_directory_terminal_never_overrides_connector(self):
        for kwargs in ({'grant':False},{'mode':'disabled'},{'basis':'transport_completed_reads'},{'project':PROJECT+1},{'backtest':'other'}):
            store,reg,bridge,a,c=fixture();h=host(c,a,**kwargs);target_observed(h,a);before=store.read_bytes(reg.JOURNAL)
            self.assertEqual(h.prepare(a)['failure_code'],'completed_read_not_authorized')
            self.assertNotIn(b'completed_read_reserved',store.read_bytes(c._stream(a)))
            self.assertEqual(reg.snapshot()['attempts'][-1]['status'],'pending');self.assertEqual(before,store.read_bytes(reg.JOURNAL));scenario('directory-no-read-'+repr(kwargs))
    def test_07_three_pages_read_and_original_parser_settlement(self):
        store,reg,bridge,a,c=fixture();h=host(c,a);before=store.read_bytes(reg.JOURNAL);usage=reg.snapshot()['usage'];discover(h,a)
        for page in (1,2,3):
            q=h.prepare(a);self.assertEqual(q['arguments'],{'projectId':PROJECT,'page':page});h.accept_response(message(q,history(page,3,target=page==3)));scenario('bounded-page-'+str(page))
        q=h.prepare(a);self.assertEqual(q['tool_name'],H.READ);result=terminal();m=message(q,result)
        self.assertEqual(h.accept_response(m)['action'],'awaiting_native_receipt');self.assertEqual(host(c,a).prepare(a)['action'],'awaiting_native_receipt');self.assertEqual(before,store.read_bytes(reg.JOURNAL));scenario('read-does-not-settle')
        self.assertNotIn(b'SYNTHETIC-NATIVE-SENTINEL',store.read_bytes(h._stream(a)));self.assertNotIn(b'987654',store.read_bytes(c._stream(a)));scenario('native-raw-not-persisted')
        payload=bridge.payload(a)
        observed=backtest_observation(payload,deployment(payload),BACKTEST,{'tool_name':H.READ,'arguments':q['arguments'],'result':result},native_logs(payload))
        bridge.consume_completion(a,completion_source=lambda _:observed)
        self.assertEqual(c.sync(a)['action'],'finished');self.assertEqual(h.inspect(a)['action'],'finished');self.assertEqual(h.prepare(a)['action'],'finished');self.assertEqual(reg.snapshot()['usage'],usage);scenario('full-parser-bridge-registry-watch')
    def test_08_running_missing_pagination_and_page_cap_stop(self):
        for status,progress in [('In Queue...',0),('In Progress...',.4)]:
            store,reg,bridge,a,c=fixture();h=host(c,a);discover(h,a);q=h.prepare(a);h.accept_response(message(q,history(status=status,progress=progress)));self.assertEqual(h.prepare(a)['action'],'attention_required');scenario('nonterminal-'+status)
        store,reg,bridge,a,c=fixture();h=host(c,a);discover(h,a)
        for page in (1,2,3):q=h.prepare(a);h.accept_response(message(q,history(page,4,target=False)))
        self.assertEqual(h.prepare(a)['action'],'attention_required');scenario('three-pages-cap-no-target')
        store,reg,bridge,a,c=fixture();h=host(c,a);discover(h,a);q=h.prepare(a);h.accept_response(message(q,native({'success':True,'backtests':[]})));self.assertEqual(h.prepare(a)['action'],'attention_required');scenario('missing-page-count')
        store,reg,bridge,a,c=fixture();h=host(c,a);discover(h,a);q=h.prepare(a);h.accept_response(message(q,history(1,3,target=False)));q=h.prepare(a);h.accept_response(message(q,history(2,4,target=False)));self.assertEqual(h.prepare(a)['action'],'attention_required');scenario('pagination-conflict')
    def test_09_run_once_unknown_response_never_reissues(self):
        store,reg,bridge,a,c=fixture();h=host(c,a)
        class Lost:
            calls=0
            def call_tool(self,name,args):self.calls+=1;raise TimeoutError('SYNTHETIC private response-loss text')
        client=Lost();self.assertEqual(h.run_once(a,client)['failure_code'],'reserved_response_unknown')
        for _ in range(3):self.assertEqual(host(c,a).run_once(a,client)['action'],'attention_required')
        self.assertEqual(client.calls,1);scenario('client-timeout-consumes-reservation')
        reserved=[x['event'] for x in decode_events(store.read_bytes(h._stream(a))) if x['event']['kind']=='reserved'][0]
        request=dict(reserved,attempt_id=a)
        self.assertEqual(h.accept_response(message(request,projects()))['action'],'projects_observed');scenario('original-late-response-admissible')
    def test_10_crash_between_controller_and_host_reservations(self):
        store,reg,bridge,a,c=fixture();h=host(c,a);discover(h,a);original=store.append_event
        def crash(key,event):
            if key==h._stream(a) and event.get('kind')=='reserved' and event.get('tool_name')==H.HISTORY:raise OSError('synthetic crash before host reservation')
            return original(key,event)
        with patch.object(store,'append_event',side_effect=crash):
            with self.assertRaises(OSError):h.prepare(a)
        self.assertEqual(host(c,a).prepare(a)['action'],'attention_required')
        self.assertEqual(len([x for x in decode_events(store.read_bytes(c._stream(a))) if x['event']['kind']=='history_reserved']),1);scenario('controller-reserved-host-missing-crash')
    def test_11_threads_and_completed_read_only_once(self):
        store,reg,bridge,a,c=fixture();h=host(c,a)
        with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(lambda _:host(c,a).prepare(a),range(24)))
        qs=[r for r in results if r['type']=='tool_request'];self.assertEqual(len(qs),1);h.accept_response(message(qs[0],projects()));scenario('thread-projects24-one')
        q=h.prepare(a);h.accept_response(message(q,history()))
        with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(lambda _:host(c,a).prepare(a),range(24)))
        qs=[r for r in results if r['type']=='tool_request'];self.assertEqual(len(qs),1);self.assertEqual(qs[0]['tool_name'],H.READ);scenario('thread-read24-one')
    def test_12_six_native_processes_one_discovery(self):
        with tempfile.TemporaryDirectory(prefix='host-api-',dir=OUT) as d:
            store,reg,bridge,a,c=fixture(d);before=store.read_bytes(reg.JOURNAL);processes=[]
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
            for index in range(6):
                cmd=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker',d,a]
                PROCESS_COMMANDS.append(cmd)
                processes.append(subprocess.Popen(cmd,cwd=OUT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
            permits=0
            for index,p in enumerate(processes):
                out,err=p.communicate(timeout=60);(OUT/f'process-{index}.stdout').write_bytes(out);(OUT/f'process-{index}.stderr').write_bytes(err)
                self.assertEqual(p.returncode,0,err.decode(errors='replace'));data=json.loads(out);permits+=sum(x['type']=='tool_request' for x in data)
            self.assertEqual(permits,1);self.assertEqual(store.read_bytes(reg.JOURNAL),before);scenario('native6process18-requests-one-discovery')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        store=FilesystemArtifactStore(sys.argv[2],lock_timeout=15);reg=Registry(store,LIMITS);a=sys.argv[3];c=TaskFollowupController(reg,POLICY)
        print(json.dumps([host(c,a).prepare(a) for _ in range(3)]));raise SystemExit(0)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'methods':result.testsRun,'named_scenarios':len(SCENARIOS),'scenarios':SCENARIOS,'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],'skips':[(str(t),s) for t,s in result.skipped],'actually_executed':True,'source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','process_commands':PROCESS_COMMANDS,'financial_evidence':False}
    (OUT/'corrected_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(not result.wasSuccessful())
