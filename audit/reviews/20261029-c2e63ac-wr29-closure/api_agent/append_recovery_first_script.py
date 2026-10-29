from pathlib import Path
import os,sys,json,tempfile,subprocess,traceback,ctypes,hashlib,unittest
from ctypes import wintypes
from unittest.mock import patch
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'replay_context/host_api_agent'))
import independent_host_api as B
H=B.H
SCENARIOS=[];COMMANDS=[];OBSERVATIONS=[]
def scenario(label):SCENARIOS.append(label)
def events(store,key):return [v['event'] for v in B.decode_events(store.read_bytes(key))]

class AppendRecovery(unittest.TestCase):
    def test_01_refusal_before_any_response_bytes_recovers_exact_original(self):
        store,reg,bridge,a,c=B.fixture();h=B.host(c,a);q=h.prepare(a);m=B.message(q,B.projects())
        stream=h._stream(a);before=store.read_bytes(stream);journal=store.read_bytes(reg.JOURNAL)
        original=store.append_event
        def denied(key,event):
            if key==stream and event.get('kind')=='response':raise PermissionError(13,'reviewer injected preappend refusal',key)
            return original(key,event)
        with patch.object(store,'append_event',side_effect=denied):
            with self.assertRaises(PermissionError):h.accept_response(m)
        self.assertEqual(store.read_bytes(stream),before);scenario('injected_preappend_zero_bytes')
        for call in ('inspect','prepare'):
            got=getattr(B.host(c,a),call)(a);self.assertEqual(got['failure_code'],'reserved_response_unknown');scenario('preappend_'+call+'_unknown_no_request')
        self.assertEqual(h.accept_response(m)['action'],'projects_observed');scenario('original_response_recovered')
        recovered=store.read_bytes(stream);self.assertEqual(h.accept_response(m)['action'],'projects_observed');self.assertEqual(recovered,store.read_bytes(stream));scenario('original_response_idempotent')
        next_request=h.prepare(a);self.assertEqual(next_request['tool_name'],H.HISTORY);self.assertEqual(next_request['arguments']['page'],1);scenario('one_next_history_after_recovery')
        self.assertEqual([e['tool_name'] for e in events(store,stream) if e['kind']=='reserved'],[H.PROJECTS,H.HISTORY]);self.assertEqual(store.read_bytes(reg.JOURNAL),journal);scenario('no_discovery_or_budget_reexecution')
    def test_02_durable_response_then_exception_and_controller_then_host_gap(self):
        store,reg,bridge,a,c=B.fixture();h=B.host(c,a);q=h.prepare(a);m=B.message(q,B.projects());stream=h._stream(a);journal=store.read_bytes(reg.JOURNAL);original=store.append_event
        def after_durable(key,event):
            result=original(key,event)
            if key==stream and event.get('kind')=='response':raise OSError('reviewer injected post-full-append acknowledgement loss')
            return result
        with patch.object(store,'append_event',side_effect=after_durable):
            with self.assertRaises(OSError):h.accept_response(m)
        self.assertEqual([e['kind'] for e in events(store,stream)],['bound','reserved','response']);scenario('post_full_append_event_is_durable')
        raw=store.read_bytes(stream);self.assertEqual(B.host(c,a).accept_response(m)['action'],'projects_observed');self.assertEqual(raw,store.read_bytes(stream));scenario('postappend_original_response_idempotent')
        q=B.host(c,a).prepare(a);self.assertEqual(q['tool_name'],H.HISTORY);m=B.message(q,B.history());original=store.append_event
        def host_response_denied(key,event):
            if key==stream and event.get('kind')=='response':raise PermissionError(13,'reviewer synthetic host ack denied',key)
            return original(key,event)
        with patch.object(store,'append_event',side_effect=host_response_denied):
            with self.assertRaises(PermissionError):h.accept_response(m)
        self.assertTrue(any(e['kind']=='history_observed' for e in events(store,c._stream(a))));scenario('controller_observation_durable_before_host_ack')
        self.assertEqual(B.host(c,a).prepare(a)['failure_code'],'reserved_response_unknown');scenario('gap_no_redispatch')
        self.assertEqual(B.host(c,a).accept_response(m)['action'],'history_observed');scenario('original_history_response_recovered_idempotently')
        q=B.host(c,a).prepare(a);self.assertEqual(q['tool_name'],H.READ);self.assertEqual(reg.snapshot()['attempts'][-1]['status'],'pending');scenario('read_grant_still_required_and_no_settlement')
        self.assertEqual(store.read_bytes(reg.JOURNAL),journal);scenario('all_response_faults_budget_unchanged')
    def test_03_actual_Win32_append_denial_real_CLI_and_cross_entry_recovery(self):
        self.assertEqual(os.name,'nt')
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        with tempfile.TemporaryDirectory(prefix='native-append-',dir=OUT) as d:
            store,reg,bridge,a,c=B.fixture(d);h=B.host(c,a);q=h.prepare(a);m=B.message(q,B.projects());key=h._stream(a);path=Path(d)/key
            before=store.read_bytes(key);journal=store.read_bytes(reg.JOURNAL)
            handle=kernel.CreateFileW(str(path),0x80000000,1,None,3,0x80,None)
            self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
            trace_file=OUT/'native_api_trace.txt'
            try:
                try:h.accept_response(m)
                except PermissionError as exc:
                    trace_file.write_text(traceback.format_exc(),encoding='utf-8')
                    self.assertEqual(exc.errno,13);self.assertEqual(exc.winerror,32);self.assertEqual(Path(exc.filename),path);scenario('actual_native_PermissionError13_WinError32_at_exact_host_stream')
                else:self.fail('Expected actual native append denial')
                self.assertEqual(store.read_bytes(key),before);scenario('actual_native_denial_left_zero_response_bytes')
                self.assertEqual(h.inspect(a)['failure_code'],'reserved_response_unknown');scenario('native_denial_unknown_no_dispatch')
                source=B.SOURCE
                def run(label,entry,messages):
                    trace=OUT/(label+'.trace')
                    env=dict(os.environ,PYTHONPATH=os.pathsep.join((str(OUT),str(source/'tools'),str(source/'cloud'))),PYTHONDONTWRITEBYTECODE='1',AQRP_REVIEW_STORE=d,AQRP_REVIEW_ATTEMPT=a,AQRP_REVIEW_TRACE=str(trace))
                    command=[sys.executable,'-B',*entry,'serve','--enable-dispatch','--host-factory','io_factory:build']
                    stdin=''.join(json.dumps(x)+'\n' for x in messages)
                    completed=subprocess.run(command,cwd=source,env=env,input=stdin,text=True,capture_output=True,timeout=45)
                    (OUT/(label+'.stdin')).write_text(stdin,encoding='utf-8');(OUT/(label+'.stdout')).write_text(completed.stdout,encoding='utf-8');(OUT/(label+'.stderr')).write_text(completed.stderr,encoding='utf-8')
                    COMMANDS.append({'label':label,'command':command,'cwd':str(source),'exit_code':completed.returncode,'stdin':label+'.stdin','stdout':label+'.stdout','stderr':label+'.stderr','trace':trace.name if trace.exists() else None})
                    self.assertEqual(completed.returncode,0,completed.stderr)
                    return [json.loads(line) for line in completed.stdout.splitlines()],trace
                denied,trace=run('native_cli_denied',[str(source/'tools/followup_host.py')],[m,{'command':'wake','attempt_id':a}])
                self.assertEqual(denied[0]['failure_code'],'invalid_message_or_store_state');self.assertEqual(denied[1]['failure_code'],'reserved_response_unknown');scenario('actual_CLI_redacts_native_append_refusal_and_stops')
                raw_trace=trace.read_text(encoding='utf-8');self.assertIn('PermissionError',raw_trace);self.assertIn('path.open("ab")',raw_trace);scenario('actual_CLI_append_trace_captured')
                self.assertEqual(store.read_bytes(key),before);self.assertEqual(store.read_bytes(reg.JOURNAL),journal);scenario('failed_CLI_no_host_response_or_budget_change')
            finally:
                self.assertTrue(kernel.CloseHandle(handle))
            modes=[('recover_canonical',['-c','import followup_host; raise SystemExit(followup_host.main())']),('recover_script',[str(B.SOURCE/'tools/followup_host.py')]),('recover_module',['-m','followup_host'])]
            for i,(label,entry) in enumerate(modes):
                output,trace=run(label,entry,[m,{'command':'wake','attempt_id':a}])
                self.assertEqual(output[0]['action'],'projects_observed');scenario(label+'_same_original_response_accepted')
                if i==0:self.assertEqual(output[1]['tool_name'],H.HISTORY)
                else:self.assertEqual(output[1]['failure_code'],'reserved_response_unknown')
                self.assertFalse(trace.exists());scenario(label+'_only_first_wake_permits_history')
            self.assertEqual([e['tool_name'] for e in events(store,key) if e['kind']=='reserved'],[H.PROJECTS,H.HISTORY]);self.assertEqual(store.read_bytes(reg.JOURNAL),journal);scenario('cross_entry_recovery_one_discovery_one_history_no_budget_change')
            OBSERVATIONS.append({'actual_native_mechanism':'CreateFileW GENERIC_READ FILE_SHARE_READ (no FILE_SHARE_WRITE) denies append; API and child CLI actual PermissionError13/WinError32','original_developer_store_used':False,'new_independent_equivalent_private_case_only':True,'developer_first_two_untraced_failures_cause_proven':False})

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AppendRecovery))
    value={'methods':result.testsRun,'scenarios':SCENARIOS,'named_scenarios':len(SCENARIOS),'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],'skips':[(str(t),s) for t,s in result.skipped],'observations':OBSERVATIONS,'subprocesses':COMMANDS,'actually_executed':True,'kind':'reviewer_independent_injected_and_actual_Win32_private_append_denial'}
    (OUT/'append_recovery_results.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(not result.wasSuccessful())
