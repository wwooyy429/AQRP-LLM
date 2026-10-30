from pathlib import Path
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from tempfile import TemporaryDirectory
from unittest.mock import patch
import io, os, json, sys, subprocess, unittest, copy, time
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent
R=D.parent
S=R/'source'
sys.path[:0]=[str(S/'tools'),str(S/'cloud')]
from qresearch.artifacts import FilesystemArtifactStore, canonical_json, decode_events, content_hash
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.task_followup import TaskFollowupController
import followup_host as product

PROJECT=880031
BACKTEST='e'*32
POLICY={'schema_version':1,'notification_grace_seconds':1800,'max_history_pages':3}
LIMITS={name:{'total':maximum,'normal':maximum,'reserve':0} for name,maximum in [('configurations',12),('research',20),('lean',16)]}
CASES=[];PROCESSES=[]
def mark(name): CASES.append(name)
def digest(text): return sha256(text.encode()).hexdigest()
def plan():
    return EngineeringTaskPlan.from_dict({
        'schema_version':1,'plan_id':'independent-stdio-existing-job','scope':'engineering','project_id':PROJECT,
        'source_manifest_hash':digest('independent stdio source'),'deployment_hash':digest('independent stdio deployment'),
        'request_mode':'resolved','data_request':{'dataset':'US Equities','fields':['close'],'sids':['independent-sid-A','independent-sid-B'],
            'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00','data_version':'independent-synthetic-v1',
            'universe_hash':digest('independent stdio universe'),'normalization':'raw','timezone':'America/New_York'},
        'observation_window':{'start':'2018-02-01T00:00:00-05:00','end_exclusive':'2018-02-02T00:00:00-05:00'},
        'required_checks':{'research':['raw_data_received','second_prefetch_no_history'],'lean':['raw_data_received','no_orders']},
        'max_retries':{'research':0,'lean':0},'report_namespace':'independent-stdio',
        'orders_enabled':False,'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None},discovered_project_ids=[PROJECT])

def deployment(payload): return {k:payload['identity'][k] for k in ('source_manifest_hash','deployment_hash')}|{'input_hash':digest('independent input')}
def submission(payload):
    i=payload['identity'];ext=BACKTEST if i['stage']=='lean' else f"qc-research:{PROJECT}:{i['attempt_id']}"
    return {'identity':i,'identity_kind':payload['external_identity_kind'],'accepted':True,'status':'submitted','external_id':ext,
        'deployment':deployment(payload),'raw_receipt':{'success':True,'backtestId':ext} if i['stage']=='lean' else {'success':True,'logical_id':ext}}
def completion(payload):
    report={'schema_version':1,'identity':payload['identity'],'status':'completed','terminal':True,
        'checks':{k:True for k in payload['plan']['required_checks'][payload['identity']['stage']]},
        'statistics':{'record_count':2,'history_calls_first':1,'history_calls_second':0},'market_values_exported':False,
        'economic_factor_tested':False,'final_data_accessed':False,'full_US200_coverage_certified':False,'actual_availability_verified':False}
    return {'platform':{'identity':dict(payload['identity'],external_id=submission(payload)['external_id']),'terminal':True,'status':'completed','deployment':deployment(payload),'raw_receipt':{'success':True}},
        'cloud_report':report,'report_ref':{'key':payload['report_key'],'sha256':content_hash(report)}}

def fixture(root,*,fresh=False,read=False):
    store=FilesystemArtifactStore(root,lock_timeout=5)
    reg=Registry(store,LIMITS)
    now=datetime.now(timezone.utc)
    stamp=now if fresh else datetime(2026,10,28,tzinfo=timezone.utc)
    with patch('qresearch.registry.datetime') as clock:
        clock.now.return_value=stamp
        bridge=EngineeringTaskBridge(reg,plan());bridge.register()
        research=bridge.claim('research');bridge.record_submission(research,submission(bridge.payload(research)))
        bridge.consume_completion(research,completion_source=completion)
        lean=bridge.claim('lean');bridge.record_submission(lean,submission(bridge.payload(lean)))
    (Path(root)/'independent_attempt.txt').write_text(lean.attempt_id)
    return open_host(root,read=read,clock=lambda:stamp+timedelta(hours=1)),lean.attempt_id

def open_host(root,*,read=False,clock=None):
    reg=Registry(FilesystemArtifactStore(root,lock_timeout=5),LIMITS)
    attempt=(Path(root)/'independent_attempt.txt').read_text()
    grant=(product.ReadGrant(attempt,PROJECT,BACKTEST,'historical_user_reference',digest('trusted synthetic historical reference')),) if read else ()
    authority=product.TransportAuthority('independent-synthetic-stdio',frozenset({attempt}),frozenset({attempt}),'chat_connector',grant)
    return product.FollowupHost(TaskFollowupController(reg,POLICY),authority=authority,enabled=True,clock=clock)

def trusted_factory():
    root=Path(os.environ['SYNTHETIC_STDIO_STORE'])
    (root/'factory_called.txt').write_text('trusted fixture factory called')
    return open_host(root,read=os.environ.get('SYNTHETIC_STDIO_READ')=='1',clock=lambda:datetime(2099,1,1,tzinfo=timezone.utc))

def native(value): return {'structuredContent':value,'content':[{'type':'text','text':json.dumps(value)}]}
def response(request,result): return {k:request[k] for k in ('attempt_id','correlation_id','tool_name','arguments')}|{'command':'response','result':result}
def projects():return native({'success':True,'projects':[{'projectId':PROJECT,'name':'independent-synthetic','language':'Py'}]})
def terminal():return native({'success':True,'backtests':[{'backtestId':BACKTEST,'status':'Completed.','progress':1}],'totalPages':1})
def prime_history(host,attempt):
    discovery=host.prepare(attempt);assert discovery['tool_name']==product.PROJECTS
    assert host.accept_response(response(discovery,projects()))['action']=='projects_observed'
    history=host.prepare(attempt);assert history['tool_name']==product.HISTORY
    return history
def prime_read(host,attempt):
    history=prime_history(host,attempt)
    assert host.accept_response(response(history,terminal()))['action']=='history_observed'
    request=host.prepare(attempt);assert request['tool_name']==product.READ
    return request

def cli(args,text='',env_add=None,timeout=20):
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',PYTHONPATH=os.pathsep.join([str(D),str(S/'cloud'),str(S/'tools')]))
    env.update(env_add or {})
    command=[sys.executable,'-B',str(S/'tools/followup_host.py')]+args
    start=time.monotonic();p=subprocess.run(command,input=text,text=True,encoding='utf-8',capture_output=True,env=env,timeout=timeout,cwd=D)
    PROCESSES.append({'command':command,'input_sha256':sha256(text.encode()).hexdigest(),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'seconds':round(time.monotonic()-start,3)})
    return p

class StdioBoundary(unittest.TestCase):
    def test_01_default_off_never_loads_factory_or_controller(self):
        with TemporaryDirectory(dir=D) as root:
            env={'SYNTHETIC_STDIO_STORE':root}
            for args in [['plan','--attempt','a'*32],['plan','--attempt','a'*32,'--host-factory','independent_stdio:trusted_factory'],['serve','--host-factory','does_not_exist:factory']]:
                with self.subTest(args=args):
                    p=cli(args,json.dumps({'command':'wake','attempt_id':'a'*32})+'\n',env)
                    self.assertEqual(p.returncode,0,p.stderr)
                    self.assertEqual(json.loads(p.stdout)['action'],'dispatch_disabled')
                    self.assertEqual(list(Path(root).iterdir()),[])
                    mark('default_off_'+args[0]+'_'+str(len(args)))
        class Explode:
            @property
            def store(self):raise AssertionError('controller touched while off')
        h=product.FollowupHost(Explode(),enabled=False)
        self.assertEqual(h.command({'command':'wake','attempt_id':'a'*32})['action'],'dispatch_disabled');mark('default_off_python_no_store')
    def test_02_cli_authority_and_clock_flags_rejected(self):
        for args in [['plan','--attempt','a'*32,'--enable-dispatch'],['plan','--attempt','a'*32,'--enable-dispatch','--host-factory','missingseparator'],['plan','--attempt','a'*32,'--now','2099-01-01']]:
            p=cli(args);self.assertNotEqual(p.returncode,0);self.assertEqual(p.stdout,'');mark('CLI_gate_'+str(args[-1]))
    def test_03_bad_json_frames_redacted_and_next_frame_retained(self):
        bad=['{"command":"wake","command":"status","attempt_id":"'+'a'*32+'"}',
             '{"command":"wake","attempt_id":"'+'a'*32+'","v":NaN}',
             '{"command":"wake","attempt_id":"'+'a'*32+'","v":Infinity}',
             '{"command":"wake","attempt_id":"'+'a'*32+'","v":1e10000}',
             'null','[]','true','1','"sensitive-sentinel-input"','{"command":',
             '\ufeff{"command":"wake","attempt_id":"'+'a'*32+'"}',
             '{"command":"wake","attempt_id":"'+'a'*32+'"} {}','',
             '{"command":"wake","attempt_id":"'+'a'*32+'","authority":{"read_mode":"completion_reads_permitted"}}',
             '{"command":"wake","attempt_id":"'+'a'*32+'","now":"2099-01-01"}']
        stream='\n'.join(bad)+'\n'+json.dumps({'command':'wake','attempt_id':'a'*32})+'\n'
        p=cli(['serve'],stream);self.assertEqual(p.returncode,0,p.stderr)
        output=[json.loads(x) for x in p.stdout.splitlines()]
        self.assertEqual(len(output),len(bad)+1)
        for i,item in enumerate(output[:-1]):
            self.assertEqual(item['action'],'attention_required');self.assertFalse(item['should_execute']);mark('bad_frame_'+str(i))
        self.assertEqual(output[-1]['action'],'dispatch_disabled');self.assertNotIn('sensitive-sentinel-input',p.stdout+p.stderr)
    def test_04_line_framing_and_UTF8_size(self):
        valid=json.dumps({'command':'wake','attempt_id':'a'*32})+'\n'
        for label,first,expected in [('no_newline',valid.rstrip('\n'),1),('UTF8_over_limit',json.dumps({'secret':'中'*700000},ensure_ascii=False)+'\n'+valid,2),('ASCII_truncated_tail','x'*(product.MAX_LINE+3)+'\n'+valid,1)]:
            out=io.StringIO();product.serve(product.FollowupHost(),io.StringIO(first),out)
            results=[json.loads(x) for x in out.getvalue().splitlines()];self.assertEqual(len(results),expected,label)
            self.assertEqual(results[0]['action'],'attention_required');self.assertNotIn('中',out.getvalue())
            if expected==2:self.assertEqual(results[1]['action'],'dispatch_disabled')
            mark('framing_'+label)
        p=cli(['serve'],valid+valid);self.assertEqual(len(p.stdout.splitlines()),2);mark('actual_stdio_multiple_frames')
    def test_05_strict_nested_duplicate_and_nonfinite(self):
        for text in ['{"v":{"a":1,"a":2}}','{"v":[NaN]}','{"v":-Infinity}']:
            with self.assertRaises(ValueError):product.strict_json(text)
            mark('strict_json_'+text)
        self.assertEqual(product.strict_json('{"s":"雪","n":0,"b":false}'),{'s':'雪','n':0,'b':False});mark('strict_valid_unicode')
    def test_06_production_CLI_replaces_factory_clock(self):
        with TemporaryDirectory(dir=D) as root:
            host,a=fixture(root,fresh=True)
            p=cli(['serve','--enable-dispatch','--host-factory','independent_stdio:trusted_factory'],json.dumps({'command':'wake','attempt_id':a})+'\n',{'SYNTHETIC_STDIO_STORE':root})
            self.assertEqual(p.returncode,0,p.stderr);self.assertTrue((Path(root)/'factory_called.txt').exists())
            self.assertEqual(json.loads(p.stdout)['action'],'wait_for_delivery');self.assertFalse(host.store.exists(host._stream(a)))
            mark('CLI_clock_factory_future_replaced_by_real_UTC')
    def test_07_actual_stdio_discovery_response_and_unknown_after_restart(self):
        with TemporaryDirectory(dir=D) as root:
            host,a=fixture(root)
            args=['serve','--enable-dispatch','--host-factory','independent_stdio:trusted_factory']
            env={'SYNTHETIC_STDIO_STORE':root}
            first=cli(args,json.dumps({'command':'wake','attempt_id':a})+'\n',env)
            self.assertEqual(first.returncode,0,first.stderr)
            req=json.loads(first.stdout);self.assertEqual(req['tool_name'],product.PROJECTS)
            restart=cli(args,json.dumps({'command':'status','attempt_id':a})+'\n'+json.dumps({'command':'wake','attempt_id':a})+'\n',env)
            for result in map(json.loads,restart.stdout.splitlines()):self.assertEqual(result['action'],'attention_required');self.assertFalse(result['should_execute'])
            recovered=cli(args,json.dumps(response(req,projects()))+'\n'+json.dumps({'command':'wake','attempt_id':a})+'\n',env)
            results=[json.loads(x) for x in recovered.stdout.splitlines()];self.assertEqual(results[0]['action'],'projects_observed');self.assertEqual(results[1]['tool_name'],product.HISTORY)
            mark('actual_cli_unknown_discovery_visible');mark('actual_cli_original_response_after_restart');mark('actual_cli_next_history_precisely_bound')
    def test_08_exact_response_bindings_and_idempotent_rejection(self):
        changes={'correlation':lambda m:m.__setitem__('correlation_id','b'*32),'tool':lambda m:m.__setitem__('tool_name',product.READ),'page':lambda m:m['arguments'].__setitem__('page',2),'bool_page':lambda m:m['arguments'].__setitem__('page',True),'extra_arg':lambda m:m['arguments'].__setitem__('query','secret'),'extra_message':lambda m:m.__setitem__('authority',True),'command':lambda m:m.__setitem__('command','wake')}
        for label,change in changes.items():
            with TemporaryDirectory(dir=D) as root:
                h,a=fixture(root);req=h.prepare(a);m=response(req,projects());change(m)
                before=h.store.read_bytes(h.controller.registry.JOURNAL)
                r=h.accept_response(m);self.assertEqual(r['action'],'attention_required');self.assertEqual(r['failure_code'],'response_binding_rejected')
                encoded=h.store.read_bytes(h._stream(a));self.assertEqual(h.accept_response(m),r);self.assertEqual(h.store.read_bytes(h._stream(a)),encoded)
                self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),before);self.assertEqual(h.inspect(a)['action'],'attention_required')
                mark('bound_rejection_'+label)
    def test_09_wrong_attempt_does_not_bind_foreign_stream(self):
        with TemporaryDirectory(dir=D) as root:
            h,a=fixture(root);req=h.prepare(a);m=response(req,projects());m['attempt_id']='0'*32
            before=h.store.read_bytes(h._stream(a))
            with self.assertRaises(ValueError):h.accept_response(m)
            self.assertEqual(h.store.read_bytes(h._stream(a)),before);self.assertFalse(h.store.exists(h._stream('0'*32)))
            mark('foreign_attempt_no_stream')
    def test_10_direct_API_size_gate_is_before_store_and_no_echo(self):
        with TemporaryDirectory(dir=D) as root:
            h,a=fixture(root);req=h.prepare(a);before=h.store.read_bytes(h._stream(a));m=response(req,{'structuredContent':{'sensitive':'中'*700000}})
            r=h.accept_response(m);self.assertEqual(r['failure_code'],'response_too_large');self.assertEqual(h.store.read_bytes(h._stream(a)),before)
            self.assertNotIn('sensitive',json.dumps(r));self.assertEqual(h.inspect(a)['failure_code'],'reserved_response_unknown');mark('direct_API_canonical_UTF8_limit')
    def test_11_native_carrier_conflicts_and_unknown_data_not_saved(self):
        for label,edit in [('conflict',lambda x:x['content'][0].__setitem__('text','{"success":false}')),('unknown',lambda x:x['structuredContent'].__setitem__('hidden_rows',[123.4])),('nonfinite',lambda x:x['structuredContent'].__setitem__('v',float('nan')))]:
            with TemporaryDirectory(dir=D) as root:
                h,a=fixture(root);req=h.prepare(a);raw=projects();edit(raw)
                m=response(req,raw)
                try:r=h.accept_response(m)
                except ValueError:r={'action':'attention_required'}
                self.assertEqual(r['action'],'attention_required');content=h.store.read_bytes(h._stream(a))
                self.assertNotIn(b'hidden_rows',content);self.assertNotIn(b'123.4',content);mark('native_reject_'+label)
    def test_12_read_no_stdin_grant_and_only_awaits_receipt(self):
        with TemporaryDirectory(dir=D) as root:
            h,a=fixture(root,read=False);req=prime_history(h,a);h.accept_response(response(req,terminal()))
            denied=h.prepare(a);self.assertEqual(denied['failure_code'],'completed_read_not_authorized')
            self.assertEqual(h.controller.registry.snapshot()['attempts'][-1]['status'],'pending')
            mark('directory_terminal_never_authorizes_chat_read')
        with TemporaryDirectory(dir=D) as root:
            h,a=fixture(root,read=True);request=prime_read(h,a);journal=h.store.read_bytes(h.controller.registry.JOURNAL)
            result=native({'success':True,'backtest':{'projectId':PROJECT,'backtestId':BACKTEST,'completed':True,'status':'Completed.','progress':1,'statistics':{'Net Profit':'sensitive-financial-sentinel'}}})
            got=h.accept_response(response(request,result));self.assertEqual(got['action'],'awaiting_native_receipt');self.assertEqual(got['receipt_parser'],'tools/stage2.py backtest-result')
            self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),journal);self.assertEqual(h.inspect(a)['action'],'awaiting_native_receipt');self.assertEqual(h.prepare(a)['action'],'awaiting_native_receipt')
            self.assertNotIn(b'sensitive-financial-sentinel',h.store.read_bytes(h._stream(a)))
            self.assertNotIn('sensitive-financial-sentinel',json.dumps(got));mark('completed_read_no_settlement_and_no_raw_native_storage')
    def test_13_completed_response_bad_identity_values_refused(self):
        modifications={'project_bool':lambda b:b.__setitem__('projectId',True),'foreign_project':lambda b:b.__setitem__('projectId',PROJECT+1),'foreign_task':lambda b:b.__setitem__('backtestId','f'*32),'not_complete':lambda b:b.__setitem__('completed',False),'progress_bool':lambda b:b.__setitem__('progress',True),'progress_half':lambda b:b.__setitem__('progress',.5),'unknown_status':lambda b:b.__setitem__('status','done')}
        for label,edit in modifications.items():
            with TemporaryDirectory(dir=D) as root:
                h,a=fixture(root,read=True);req=prime_read(h,a)
                b={'projectId':PROJECT,'backtestId':BACKTEST,'completed':True,'status':'Completed.','progress':1};edit(b)
                before=h.store.read_bytes(h.controller.registry.JOURNAL);r=h.accept_response(response(req,native({'success':True,'backtest':b})))
                self.assertEqual(r['failure_code'],'invalid_native_response');self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),before);mark('read_reject_'+label)
    def test_14_malicious_authority_and_clock_stdin_no_rights(self):
        with TemporaryDirectory(dir=D) as root:
            h,a=fixture(root,read=False)
            messages=[{'command':'wake','attempt_id':a,'enabled':True},{'command':'wake','attempt_id':a,'now':'2099-01-01T00:00:00+00:00'},{'command':'wake','attempt_id':a,'read_grants':[{'basis':'delivered_terminal_notification'}]},{'command':'response','attempt_id':a,'correlation_id':'a'*32,'tool_name':product.READ,'arguments':{'projectId':PROJECT,'backtestId':BACKTEST},'result':projects(),'TransportAuthority':True}]
            output=io.StringIO();before=h.store.read_bytes(h.controller.registry.JOURNAL);product.serve(h,io.StringIO(''.join(json.dumps(m)+'\n' for m in messages)),output)
            for item in map(json.loads,output.getvalue().splitlines()):self.assertFalse(item['should_execute']);self.assertEqual(item['action'],'attention_required')
            self.assertFalse(h.store.exists(h._stream(a)));self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),before)
            for i in range(len(messages)):mark('stdin_authority_injection_'+str(i))
    def test_15_accepted_duplicate_and_conflict(self):
        with TemporaryDirectory(dir=D) as root:
            h,a=fixture(root);req=h.prepare(a);m=response(req,projects());one=h.accept_response(m);raw=h.store.read_bytes(h._stream(a))
            self.assertEqual(h.accept_response(copy.deepcopy(m)),one);self.assertEqual(h.store.read_bytes(h._stream(a)),raw);mark('identical_accepted_response_no_event')
            second=copy.deepcopy(m);second['result']=native({'success':True,'projects':[{'projectId':PROJECT,'name':'different','language':'Py'}]})
            self.assertEqual(h.accept_response(second)['failure_code'],'response_conflict');self.assertEqual(h.prepare(a)['action'],'attention_required');mark('conflicting_accepted_response_fail_closed')

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(StdioBoundary)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (D/'results.json').write_text(json.dumps({'methods':result.testsRun,'named_scenarios':len(CASES),'cases':CASES,'failures':[(str(t),s)for t,s in result.failures],'errors':[(str(t),s)for t,s in result.errors],'skips':[(str(t),s)for t,s in result.skipped],'actually_executed':True},ensure_ascii=False,indent=2),encoding='utf-8')
    (D/'subprocess_records.json').write_text(json.dumps(PROCESSES,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(not result.wasSuccessful())
