from pathlib import Path
import base64, copy, hashlib, importlib.util, io, json, os, subprocess, sys, tempfile, time, unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent / 'source'
sys.path[:0] = [str(SOURCE/'cloud'), str(SOURCE/'tools')]
from qresearch.artifacts import MemoryArtifactStore, FilesystemArtifactStore, canonical_json, content_hash, decode_events
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge, EngineeringTaskError
from qresearch.engineering_receipts import backtest_observation, ReceiptParseError
from qresearch.task_followup import TaskFollowupController, TaskFollowupError, validate_policy
import task_followup as CLI

POLICY = {'schema_version':1,'notification_grace_seconds':1800,'max_history_pages':3}
LIMITS = {k: {'total':8,'normal':6,'reserve':2} for k in ('configurations','research','lean')}
START = datetime(2026,1,20,6,0,tzinfo=timezone.utc)
DEAD = START + timedelta(seconds=1800)
PROJECT = 9321
BACKTEST = 'independent-accepted-task-only'
CASES=[]
COMMANDS=[]

def scenario(name):
    CASES.append(name)

def plan():
    # Independent literal pre-resolved contract; no developer fixtures imported.
    return EngineeringTaskPlan.from_dict({
      'schema_version':1,'plan_id':'reviewer-independent-notification-v1',
      'scope':'engineering','project_id':PROJECT,
      'source_manifest_hash':hashlib.sha256(b'independent source').hexdigest(),
      'deployment_hash':hashlib.sha256(b'independent deployment').hexdigest(),
      'request_mode':'resolved','data_request':{
        'dataset':'US Equities','fields':['close'],
        'sids':['reviewer-permanent-sid-a','reviewer-permanent-sid-b'],
        'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00',
        'data_version':'independent-synthetic-no-provider',
        'universe_hash':hashlib.sha256(b'independent universe').hexdigest(),
        'normalization':'raw','timezone':'America/New_York'},
      'observation_window':{'start':'2018-03-01T00:00:00-05:00','end_exclusive':'2018-03-02T00:00:00-05:00'},
      'required_checks':{'research':['raw_data_received','second_prefetch_no_history'],
                         'lean':['raw_data_received','no_orders']},
      'max_retries':{'research':0,'lean':0},'report_namespace':'independent-notifications',
      'orders_enabled':False,'financial_metrics_enabled':False,
      'economic_factor':None,'economic_model':None},discovered_project_ids=[PROJECT])

def deployment(payload):
    return {k: payload['identity'][k] for k in ('source_manifest_hash','deployment_hash')} | {
      'input_hash':hashlib.sha256(b'independent input').hexdigest()}

def receipt(payload):
    i=payload['identity']; ext=BACKTEST if i['stage']=='lean' else f"qc-research:{PROJECT}:{i['attempt_id']}"
    return {'identity':i,'identity_kind':payload['external_identity_kind'],
      'accepted':True,'status':'submitted','external_id':ext,'deployment':deployment(payload),
      'raw_receipt':{'success':True,'backtestId':ext} if i['stage']=='lean' else {'success':True,'logical_id':ext}}

def wrapper(payload):
    stage=payload['identity']['stage']
    report={'schema_version':1,'identity':payload['identity'],'status':'completed','terminal':True,
      'checks':{key:True for key in payload['plan']['required_checks'][stage]},
      'statistics':{'record_count':3,'history_calls_first':1,'history_calls_second':0} if stage=='research'
        else {'data_event_count':3,'orders_submitted':0,'runtime_error_count':0},
      'market_values_exported':False,'economic_factor_tested':False,'final_data_accessed':False,
      'full_US200_coverage_certified':False,'actual_availability_verified':False}
    return {'cloud_report':report,'report_ref':{'key':payload['report_key'],'sha256':content_hash(report)}}

def completion(payload):
    rec=receipt(payload)
    return {'platform':{'identity':dict(payload['identity'],external_id=rec['external_id']),
      'terminal':True,'status':'completed','deployment':rec['deployment'],'raw_receipt':{'success':True}},**wrapper(payload)}

def fixture(path=None):
    store=MemoryArtifactStore() if path is None else FilesystemArtifactStore(path,lock_timeout=10)
    with patch('qresearch.registry.datetime') as clock:
        clock.now.return_value=START
        reg=Registry(store,LIMITS)
        bridge=EngineeringTaskBridge(reg,plan())
        bridge.register()
        research=bridge.claim('research')
        bridge.record_submission(research,receipt(bridge.payload(research)))
        bridge.consume_completion(research,completion_source=completion)
        lean=bridge.claim('lean')
        bridge.record_submission(lean,receipt(bridge.payload(lean)))
    return store,reg,bridge,lean.attempt_id,TaskFollowupController(reg,POLICY)

def envelope(native, project=PROJECT,page=1):
    return {'tool_name':'mcp__quantconnect__list_backtests','arguments':{'projectId':project,'page':page},
       'result':{'structuredContent':copy.deepcopy(native),'content':[{'type':'text','text':json.dumps(native)}]}}

def history(status='Completed.',progress=1,page=1,total=1,target=True):
    return envelope({'success':True,'backtests':[{'backtestId':BACKTEST if target else 'unrelated-'+str(page),
       'status':status,'progress':progress,'netProfit':818181.818181}],'totalPages':total},page=page)

def request(controller,attempt,when=DEAD,ids=(PROJECT,)):
    return controller.next_action(attempt,now=when,discovered_project_ids=ids)

def native_terminal(payload, **changes):
    native={'success':True,'backtest':{'projectId':PROJECT,'backtestId':BACKTEST,
       'completed':True,'status':'Completed.','progress':1,'hasInitializeError':False,
       'error':None,'statistics':{'Total Orders':'0','Net Profit':'SYNTHETIC_SENTINEL_272727'},
       'runtimeStatistics':{'Equity':'SYNTHETIC_SENTINEL_272727'},'charts':[]}}
    native['backtest'].update(changes)
    return {'tool_name':'mcp__quantconnect__read_backtest','arguments':{'projectId':PROJECT,'backtestId':BACKTEST},
       'result':{'content':[{'type':'text','text':json.dumps(native)}],'structuredContent':native}}

def log_envelopes(payload, mutate=None):
    value=wrapper(payload)
    if mutate: mutate(value)
    encoded=base64.b64encode(canonical_json(value)).decode()
    chunks=[encoded[i:i+400] for i in range(0,len(encoded),400)]
    lines=[f"2018-03-02 00:00:00 AQRP_ENGINEERING {payload['identity']['attempt_id']} {i+1}/{len(chunks)} {chunk}"
       for i,chunk in enumerate(chunks)]
    native={'success':True,'logs':lines,'totalPages':1}
    return [{'tool_name':'mcp__quantconnect__search_backtest_logs',
       'arguments':{'projectId':PROJECT,'backtestId':BACKTEST,'query':'AQRP_ENGINEERING '+payload['identity']['attempt_id'],'page':1},
       'result':{'structuredContent':native,'content':[{'type':'text','text':json.dumps(native)}]}}]

class Tests(unittest.TestCase):
    def test_01_closed_policy(self):
        self.assertEqual(validate_policy(POLICY),POLICY)
        bad=[{},[],None,dict(POLICY,x=1),dict(POLICY,schema_version=True),
          dict(POLICY,notification_grace_seconds=1799),dict(POLICY,notification_grace_seconds=1800.),
          dict(POLICY,max_history_pages=4),dict(POLICY,max_history_pages=0)]
        for i,item in enumerate(bad):
            scenario(f'policy-invalid-{i}')
            with self.assertRaises(TaskFollowupError): validate_policy(item)
        scenario('policy-valid')

    def test_02_original_pending_boundary_and_clock(self):
        store,reg,bridge,a,c=fixture(); before=store.read_bytes(reg.JOURNAL)
        self.assertEqual(c.register(a)['deadline'],'2026-01-20T06:30:00+00:00')
        c=TaskFollowupController(Registry(store,LIMITS),POLICY)
        for when in (START,DEAD-timedelta(microseconds=1),DEAD.astimezone(timezone(timedelta(hours=8)))-timedelta(microseconds=1)):
            scenario('before-boundary-'+when.isoformat())
            self.assertFalse(request(c,a,when)['should_execute'])
        for when in (START-timedelta(microseconds=1),datetime(2026,1,20,6),None,True):
            scenario('bad-clock-'+repr(when))
            with self.assertRaises(TaskFollowupError): request(c,a,when)
        got=request(c,a,DEAD)
        self.assertTrue(got['should_execute']); self.assertEqual(got['tool_request']['arguments'],{'projectId':PROJECT,'page':1})
        self.assertEqual(store.read_bytes(reg.JOURNAL),before); scenario('exact-deadline-no-registry-debit')
        with self.assertRaises(TaskFollowupError): request(c,a,DEAD-timedelta(microseconds=1))
        scenario('post-reservation-rollback')

    def test_03_project_discovery_and_cli_shape(self):
        store,reg,bridge,a,c=fixture(); self.assertEqual(request(c,a,ids=())['action'],'list_projects')
        for ids in ((PROJECT+1,),(True,),('9321',),(-1,),{PROJECT}):
            scenario('invalid-projects-'+repr(ids))
            with self.assertRaises(TaskFollowupError): request(c,a,ids=ids)
        self.assertFalse(store.exists(c._stream(a)))
        native={'success':True,'projects':[{'projectId':PROJECT,'name':'independent','language':'Py'}]}
        packet={'tool_name':'mcp__quantconnect__list_projects','arguments':{},'result':{'structuredContent':native}}
        self.assertEqual(CLI.project_ids(packet),(PROJECT,)); scenario('actual-shaped-list-projects')
        edits=[lambda p:p.update(tool_name='mcp__quantconnect__read_project'),
          lambda p:p['arguments'].update(page=True),lambda p:p['result']['structuredContent']['projects'].append(copy.deepcopy(p['result']['structuredContent']['projects'][0])),
          lambda p:p['result']['structuredContent']['projects'][0].update(projectId=True),
          lambda p:p['result']['structuredContent'].update(rows=[1])]
        for i,edit in enumerate(edits):
            q=copy.deepcopy(packet); edit(q); scenario('project-packet-invalid-'+str(i))
            with self.assertRaises((TaskFollowupError,ValueError)):CLI.project_ids(q)

    def test_04_three_pages_one_read_real_parser_bridge_completion(self):
        store,reg,bridge,a,c=fixture(); usage=reg.snapshot()['usage']; journal=store.read_bytes(reg.JOURNAL)
        for page in (1,2,3):
            got=request(c,a); self.assertTrue(got['should_execute']); self.assertEqual(got['tool_request']['arguments']['page'],page)
            observed=c.record_history(a,history(page=page,total=3,target=page==3))
            self.assertFalse(observed['should_execute']); scenario('history-page-'+str(page))
        got=request(c,a); self.assertTrue(got['should_execute']); self.assertEqual(got['action'],'read_completed_backtest')
        self.assertEqual(got['tool_request']['arguments'],{'projectId':PROJECT,'backtestId':BACKTEST})
        self.assertEqual(store.read_bytes(reg.JOURNAL),journal)
        self.assertEqual(request(c,a)['action'],'attention_required'); scenario('terminal-summary-not-settlement')
        payload=bridge.payload(a); parsed=backtest_observation(payload,deployment(payload),BACKTEST,native_terminal(payload),log_envelopes(payload))
        self.assertEqual(bridge.consume_completion(a,completion_source=lambda _:parsed).status,'completed')
        self.assertEqual(c.sync(a)['action'],'finished'); self.assertEqual(c.status(a)['status'],'completed')
        self.assertFalse(request(c,a,DEAD+timedelta(days=100))['should_execute'])
        self.assertEqual(reg.snapshot()['usage'],usage)
        self.assertNotIn(b'818181',store.read_bytes(c._stream(a))); self.assertNotIn(b'SYNTHETIC_SENTINEL_272727',store.read_bytes(reg.JOURNAL))
        scenario('native-parser-bridge-registry-completion-without-financial-leak')

    def test_05_runtime_failure_no_refund_or_new_attempt(self):
        store,reg,bridge,a,c=fixture(); usage=reg.snapshot()['usage']; request(c,a)
        c.record_history(a,history(status='Runtime Error',progress=.3)); self.assertTrue(request(c,a)['should_execute'])
        payload=bridge.payload(a)
        parsed=backtest_observation(payload,deployment(payload),BACKTEST,native_terminal(payload,status='Runtime Error',progress=.3,error='synthetic runtime failure'),[])
        self.assertEqual(bridge.consume_completion(a,completion_source=lambda _:parsed).status,'failed')
        self.assertEqual(c.sync(a)['status'],'failed'); self.assertEqual(reg.snapshot()['usage'],usage)
        self.assertEqual(len(reg.snapshot()['attempts']),2); self.assertFalse(request(c,a)['should_execute'])
        scenario('native-runtime-failure-settles-original-without-refund')

    def test_06_attention_matrix(self):
        native_cases=[('running',{'success':True,'backtests':[{'backtestId':BACKTEST,'status':'In Progress...','progress':.4}],'totalPages':2}),
          ('queued',{'success':True,'backtests':[{'backtestId':BACKTEST,'status':'In Queue...','progress':0}],'totalPages':1}),
          ('missing',{'success':True,'backtests':[],'totalPages':1}),
          ('no-pagination',{'success':True,'backtests':[]}),
          ('failure',{'success':False,'errors':['synthetic failure']})]
        for name,native in native_cases:
            store,reg,bridge,a,c=fixture(); request(c,a); before=store.read_bytes(reg.JOURNAL)
            c.record_history(a,envelope(native))
            for days in (0,10000):
                result=request(TaskFollowupController(reg,POLICY),a,DEAD+timedelta(days=days))
                self.assertFalse(result['should_execute']); self.assertEqual(result['action'],'attention_required')
            self.assertEqual(store.read_bytes(reg.JOURNAL),before); scenario('attention-'+name)
        store,reg,bridge,a,c=fixture()
        for page in (1,2,3):
            request(c,a); c.record_history(a,history(page=page,total=8,target=False))
        self.assertFalse(request(c,a)['should_execute']); self.assertEqual(request(c,a)['action'],'attention_required')
        scenario('three-page-hard-stop')

    def test_07_unknown_response_restart_and_late_response(self):
        with tempfile.TemporaryDirectory(dir=OUT) as p:
            store,reg,bridge,a,c=fixture(p); self.assertTrue(request(c,a)['should_execute'])
            reg=Registry(FilesystemArtifactStore(p,lock_timeout=10),LIMITS); c=TaskFollowupController(reg,POLICY)
            for call in (lambda:c.register(a),lambda:c.sync(a),lambda:c.status(a),lambda:request(c,a,DEAD+timedelta(days=365))):
                self.assertFalse(call()['should_execute'])
            scenario('durable-unknown-not-reissued-after-restart')
            c.record_history(a,history()); self.assertTrue(request(c,a)['should_execute'])
            self.assertFalse(request(c,a)['should_execute']); scenario('original-late-response-settles-only-reservation')

    def test_08_bad_history_has_no_read_authority(self):
        native={'success':True,'backtests':[{'backtestId':BACKTEST,'status':'Completed.','progress':1}],'totalPages':1}
        edits=[lambda n:n.update(success=1),lambda n:n.update(secretRows=[1]),lambda n:n.update(totalPages=True),
          lambda n:n.update(totalPages=0),lambda n:n['backtests'][0].update(status='completed'),
          lambda n:n['backtests'][0].update(progress=True),lambda n:n['backtests'][0].update(progress=.99),
          lambda n:n['backtests'][0].update(progress=float('nan')),lambda n:n['backtests'][0].update(rows=[1]),
          lambda n:n['backtests'].append(copy.deepcopy(n['backtests'][0])),lambda n:n['backtests'][0].update(alpha=float('inf')),
          lambda n:n['backtests'][0].update(parameters=True),lambda n:n['backtests'][0].update(parameterSet={'x':float('inf')}),
          lambda n:n.update(errors=['actual error on success'])]
        for i,edit in enumerate(edits):
            store,reg,bridge,a,c=fixture(); request(c,a); before=store.read_bytes(c._stream(a)); n=copy.deepcopy(native); edit(n)
            with self.assertRaises((TaskFollowupError,ValueError)): c.record_history(a,envelope(n))
            self.assertEqual(before,store.read_bytes(c._stream(a))); self.assertFalse(request(c,a)['should_execute'])
            scenario('malformed-history-'+str(i))
        store,reg,bridge,a,c=fixture(); request(c,a); q=envelope(native); q['result']['content'][0]['text']='{"success":false}'
        with self.assertRaises(TaskFollowupError):c.record_history(a,q)
        self.assertFalse(request(c,a)['should_execute']); scenario('hidden-carrier-conflict')
        for name,q in [('wrong-project',history()),('unreserved-page',history(page=2,total=2))]:
            if name=='wrong-project':q['arguments']['projectId']=PROJECT+1
            with self.assertRaises(TaskFollowupError):c.record_history(a,q)
            scenario(name)

    def test_09_identity_and_terminal_parser_rejects(self):
        store,reg,bridge,a,c=fixture();request(c,a); c.record_history(a,history());request(c,a)
        payload=bridge.payload(a); before=store.read_bytes(reg.JOURNAL)
        native_edits=[{'backtestId':'wrong-external'},{'projectId':PROJECT+1},{'completed':False},
          {'status':'In Progress...','completed':False,'progress':.4},{'statistics':{'Total Orders':'1'}}]
        for i,changes in enumerate(native_edits):
            with self.assertRaises(ReceiptParseError):backtest_observation(payload,deployment(payload),BACKTEST,native_terminal(payload,**changes),log_envelopes(payload))
            scenario('native-terminal-reject-'+str(i))
        with self.assertRaises(ReceiptParseError):backtest_observation(payload,deployment(payload),BACKTEST,native_terminal(payload),[])
        scenario('missing-log-rejected')
        for key,value in [('attempt_id','9'*32),('source_manifest_hash','0'*64),('project_id',PROJECT+1)]:
            logs=log_envelopes(payload,lambda w:w['cloud_report']['identity'].update({key:value}))
            with self.assertRaises(ReceiptParseError):backtest_observation(payload,deployment(payload),BACKTEST,native_terminal(payload),logs)
            scenario('log-identity-'+key)
        self.assertEqual(store.read_bytes(reg.JOURNAL),before);self.assertEqual(bridge._record(a)['status'],'pending')

    def test_10_thread_and_process_once(self):
        store,reg,bridge,a,c=fixture()
        with ThreadPoolExecutor(max_workers=8) as pool:
            answers=list(pool.map(lambda _:request(c,a),range(24)))
        self.assertEqual(sum(v['should_execute'] for v in answers),1); scenario('24-thread-requests-one-permission')
        with tempfile.TemporaryDirectory(dir=OUT) as p:
            store,reg,bridge,a,c=fixture(p); before=store.read_bytes(reg.JOURNAL)
            procs=[]
            for i in range(6):
                cmd=[sys.executable,'-B',str(Path(__file__)), '--worker',p,a]
                out=OUT/f'process-{i}.stdout';err=OUT/f'process-{i}.stderr'
                procs.append((subprocess.Popen(cmd,stdout=out.open('wb'),stderr=err.open('wb')),out,err,cmd))
            all_results=[]
            for process,out,err,cmd in procs:
                code=process.wait(timeout=60);COMMANDS.append({'command':cmd,'exit_code':code,'stdout':out.name,'stderr':err.name})
                self.assertEqual(code,0,err.read_text()); all_results.extend(json.loads(out.read_text()))
            self.assertEqual(len(all_results),18);self.assertEqual(sum(x['should_execute'] for x in all_results),1)
            self.assertEqual(store.read_bytes(reg.JOURNAL),before);scenario('6-processes-18-requests-one-permission')

    def test_11_reservation_faults_fail_closed(self):
        for durable in (False,True):
            store,reg,bridge,a,c=fixture(); original=store.append_event
            def faulty(key,event):
                if key==c._stream(a) and event['kind']=='history_reserved':
                    if durable:original(key,event)
                    raise OSError('independent injected crash')
                return original(key,event)
            with patch.object(store,'append_event',side_effect=faulty):
                with self.assertRaises(OSError):request(c,a)
            answer=request(TaskFollowupController(reg,POLICY),a)
            self.assertEqual(answer['should_execute'],not durable)
            self.assertFalse(request(c,a)['should_execute']);scenario('reservation-crash-durable-'+str(durable))

    def test_12_cli_uses_UTC_and_metadata_actions_cannot_dispatch(self):
        store,reg,bridge,a,c=fixture(); request(c,a)
        for name in ('register','sync','status'):
            with patch.object(CLI,'open_registry',return_value=reg),patch.object(CLI,'read_json',return_value=POLICY),redirect_stdout(io.StringIO()):
                got=CLI.main([name,'--attempt',a])
            self.assertFalse(got['should_execute']);scenario('CLI-'+name+'-no-dispatch')
        with patch.object(CLI,'open_registry',side_effect=AssertionError('should not open registry')),redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):CLI.main(['next','--attempt',a,'--now','2026-01-20T07:00:00Z'])
        scenario('CLI-no-operator-clock-override')
        now=CLI.utc_now();self.assertEqual(now.utcoffset(),timedelta(0));scenario('CLI-clock-aware-UTC')

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        reg=Registry(FilesystemArtifactStore(sys.argv[2],lock_timeout=15),LIMITS)
        controller=TaskFollowupController(reg,POLICY)
        print(json.dumps([request(controller,sys.argv[3]) for _ in range(3)]))
        return 0
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    (OUT/'first_results.json').write_text(json.dumps({'methods':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
       'skips':len(result.skipped),'named_scenarios':len(CASES),'scenarios':CASES,'subprocesses':COMMANDS,
       'source_commit':'975f676d62b561689909744f9e7236290e3f5fcb','cloud_calls':0},indent=2),encoding='utf-8')
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
