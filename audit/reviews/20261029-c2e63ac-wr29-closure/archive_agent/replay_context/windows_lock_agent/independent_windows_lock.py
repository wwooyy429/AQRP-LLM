"""Independent synthetic/native Win32 audit; never contacts a cloud service."""
from pathlib import Path
import os, sys, json, time, ctypes, threading, tempfile, traceback, hashlib
import multiprocessing as mp
import unittest
from unittest.mock import patch
from copy import deepcopy

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1] / 'source'
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'cloud'))
import qresearch.artifacts as artifacts
from qresearch.artifacts import FilesystemArtifactStore, canonical_json, ArtifactConflict, StoreBusy, decode_events
from qresearch.registry import Registry, RegistryError, BudgetExceeded
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan

OBS = []
LIMITS = {k: {'normal': 12, 'reserve': 0, 'total': 12} for k in ('configurations','research','lean')}
def note(name, **values): OBS.append({'name':name, **values})
def key_path(store, key): return store._path('.locks/' + hashlib.sha256(key.encode()).hexdigest() + '.lock')
def make_owner(key='synthetic/current'):
    return canonical_json({'owner_token':'a' * 32, 'process_id':os.getpid(), 'key':key})
def seed(store, key='synthetic/current'):
    path = key_path(store,key); path.parent.mkdir(parents=True,exist_ok=True)
    raw = make_owner(key); path.write_bytes(raw); return path,raw
def share_error(code=32):
    err = PermissionError(13,'Independent synthetic Windows denial'); err.winerror = code; return err
class Clock:
    def __init__(self, fixed=False): self.value=0.; self.sleeps=[]; self.fixed=fixed
    def monotonic(self): return self.value
    def sleep(self,n):
        self.sleeps.append(n)
        if not self.fixed: self.value += n

def win_handle(path):
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]; kernel.CloseHandle.restype = wintypes.BOOL
    # Read+write sharing, deliberately NO FILE_SHARE_DELETE.
    handle = kernel.CreateFileW(str(path),0x80000000,3,None,3,0x80,None)
    if handle == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    return handle,kernel

def child_requests(directory, config_id, operation, count, gate, queue, retry_of=None):
    try:
        registry=Registry(FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=6),LIMITS)
        gate.wait(timeout=20)
        for index in range(count):
            try:
                attempt=registry.begin_attempt(config_id,'research',operation_key=operation,
                    retry_of=retry_of,reason='Independent synthetic retry' if retry_of else None)
                queue.put({'ok':True,'should_execute':attempt.should_execute,'attempt_id':attempt.attempt_id})
            except (RegistryError,ValueError) as exc:
                queue.put({'ok':False,'type':type(exc).__name__,'message':str(exc)})
    except BaseException as exc:
        queue.put({'worker_failed':True,'type':type(exc).__name__,'traceback':traceback.format_exc()})

class IndependentWindowsLock(unittest.TestCase):
    def test_01_native_shared_handle_delayed_release_is_once_only(self):
        self.assertEqual(os.name,'nt')
        with tempfile.TemporaryDirectory(dir=OUT,prefix='native-delay-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=1)
            calls=[]; body=[]; errors=[]; real_unlink=Path.unlink; closer=[]
            def traced(path,*a,**kw):
                try: return real_unlink(path,*a,**kw)
                except PermissionError as exc:
                    if path.suffix=='.lock': errors.append(getattr(exc,'winerror',None))
                    raise
            with patch.object(Path,'unlink',traced):
                with store.locked('synthetic/native-real'):
                    path=key_path(store,'synthetic/native-real')
                    original=path.read_bytes(); handle,kernel=win_handle(path)
                    def close(): time.sleep(.18); calls.append(bool(kernel.CloseHandle(handle)))
                    thread=threading.Thread(target=close); closer.append(thread); thread.start()
                    body.append('entered')
                    self.assertTrue(store.write_once('synthetic/result.json',b'{"independent":true}'))
            for thread in closer: thread.join(timeout=2)
            self.assertEqual(body,['entered']); self.assertEqual(calls,[True]); self.assertIn(32,errors)
            self.assertFalse(path.exists()); self.assertFalse(store.write_once('synthetic/result.json',b'{"independent":true}'))
            note('native_Win32_delay',observed_winerrors=errors,body_entries=1,retry_simulated=False,owner=json.loads(original))

    def test_02_native_share_timeout_keeps_owner_then_explicit_same_owner_release(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='native-timeout-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=.12)
            handle=kernel=None; body=[]; start=time.monotonic()
            try:
                with self.assertRaises(PermissionError) as caught:
                    with store.locked('synthetic/native-timeout'):
                        path=key_path(store,'synthetic/native-timeout'); raw=path.read_bytes()
                        handle,kernel=win_handle(path); body.append(1)
                elapsed=time.monotonic()-start
                self.assertEqual(caught.exception.winerror,32); self.assertEqual(path.read_bytes(),raw)
                self.assertEqual(body,[1]); self.assertLess(elapsed,2)
            finally:
                if handle is not None: self.assertTrue(kernel.CloseHandle(handle))
            store._release_lock(path,raw); self.assertFalse(path.exists())
            note('native_Win32_exhaustion',winerror=32,elapsed_seconds=elapsed,body_entries=1,owner_preserved=True)

    def test_03_native_successful_release_preserves_original_body_exception(self):
        class IndependentBodyError(RuntimeError): pass
        with tempfile.TemporaryDirectory(dir=OUT,prefix='native-exception-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=.6)
            body_error=IndependentBodyError('Independent body failure'); threads=[]
            with self.assertRaises(IndependentBodyError) as caught:
                with store.locked('synthetic/body-error'):
                    path=key_path(store,'synthetic/body-error'); handle,kernel=win_handle(path)
                    thread=threading.Thread(target=lambda:(time.sleep(.12),kernel.CloseHandle(handle)))
                    threads.append(thread); thread.start(); raise body_error
            for thread in threads: thread.join(timeout=2)
            self.assertIs(caught.exception,body_error); self.assertFalse(path.exists())
            note('native_body_exception_not_replaced')

    def test_04_changed_on_disk_owner_is_never_deleted(self):
        variants={'pid':lambda o:o.update(process_id=os.getpid()+999),
                  'token':lambda o:o.update(owner_token='b'*32),
                  'key':lambda o:o.update(key='synthetic/elsewhere'),
                  'unknown_field':lambda o:o.update(extra=False),
                  'whitespace':lambda o:None}
        for name,change in variants.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory(dir=OUT,prefix='owner-') as directory:
                store=FilesystemArtifactStore(directory,data_classification='synthetic')
                path,raw=seed(store); owner=json.loads(raw); change(owner)
                altered=json.dumps(owner,indent=1).encode() if name=='whitespace' else canonical_json(owner)
                path.write_bytes(altered)
                with patch.object(Path,'unlink') as unlink,self.assertRaises(ArtifactConflict): store._release_lock(path,raw)
                unlink.assert_not_called(); self.assertEqual(path.read_bytes(),altered); note('on_disk_'+name)

    def test_05_captured_owner_strict_validation_and_wrong_hash_path(self):
        original=json.loads(make_owner())
        variants=[]
        for name,update in [('bool_pid',{'process_id':True}),('other_pid',{'process_id':os.getpid()+1}),
                            ('upper_token',{'owner_token':'A'*32}),('short_token',{'owner_token':'a'*31}),
                            ('unknown',{'extra':None}),('unsafe_key',{'key':'../escape'}),
                            ('wrong_key_path',{'key':'synthetic/different'})]:
            variants.append((name,canonical_json(dict(original,**update))))
        variants.extend([('whitespace',json.dumps(original,indent=1).encode()),('BOM',b'\xef\xbb\xbf'+make_owner()),('not_JSON',b'not-json')])
        for name,raw in variants:
            with self.subTest(name=name),tempfile.TemporaryDirectory(dir=OUT,prefix='capture-') as directory:
                store=FilesystemArtifactStore(directory,data_classification='synthetic'); path,_=seed(store); path.write_bytes(raw)
                with patch.object(Path,'unlink') as unlink,self.assertRaises(ArtifactConflict): store._release_lock(path,raw)
                unlink.assert_not_called(); self.assertEqual(path.read_bytes(),raw); note('captured_'+name)

    def test_06_exact_path_not_arbitrary_leaf(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='path-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic'); actual,raw=seed(store)
            alternate=store._path('.locks/not-the-hash.lock'); alternate.write_bytes(raw)
            with self.assertRaises(ArtifactConflict): store._release_lock(alternate,raw)
            self.assertEqual(alternate.read_bytes(),raw); self.assertEqual(actual.read_bytes(),raw)
            note('wrong_lock_leaf_preserved')

    def test_07_only_Windows_code32_retries(self):
        for platform,code in [(True,5),(True,33),(True,None),(False,32)]:
            with self.subTest(platform=platform,code=code),tempfile.TemporaryDirectory(dir=OUT,prefix='non32-') as directory:
                store=FilesystemArtifactStore(directory,data_classification='synthetic'); path,raw=seed(store)
                error=PermissionError(13,'Independent nonretry') if code is None else share_error(code)
                with patch.object(artifacts,'_WINDOWS_LOCK_ACCESS_RETRY',platform),patch.object(Path,'unlink',side_effect=error) as unlink,patch.object(artifacts.time,'sleep') as sleep:
                    with self.assertRaises(PermissionError) as caught: store._release_lock(path,raw)
                self.assertIs(caught.exception,error); self.assertEqual(unlink.call_count,1); sleep.assert_not_called()
                self.assertEqual(path.read_bytes(),raw); note('retry_gate_'+str(platform)+'_'+str(code))

    def test_08_replacement_after_first_realistic_denial_stops_second_delete(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='replace-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic'); path,raw=seed(store)
            replacement=canonical_json(dict(json.loads(raw),owner_token='b'*32)); calls=[]; clock=Clock()
            def refused(p,*args,**kwargs): calls.append(1); path.write_bytes(replacement); raise share_error()
            with patch.object(Path,'unlink',refused),patch.object(artifacts.time,'monotonic',clock.monotonic),patch.object(artifacts.time,'sleep',clock.sleep):
                with self.assertRaises(ArtifactConflict): store._release_lock(path,raw)
            self.assertEqual(calls,[1]); self.assertEqual(path.read_bytes(),replacement); note('replacement_during_backoff_preserved')

    def test_09_disappearance_after_denial_is_error(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='disappear-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic'); path,raw=seed(store)
            unlink=Path.unlink; calls=[]; clock=Clock()
            def removed(p,*args,**kwargs): calls.append(1); unlink(p); raise share_error()
            with patch.object(Path,'unlink',removed),patch.object(artifacts.time,'monotonic',clock.monotonic),patch.object(artifacts.time,'sleep',clock.sleep):
                with self.assertRaisesRegex(ArtifactConflict,'disappeared'): store._release_lock(path,raw)
            self.assertEqual(calls,[1]); self.assertFalse(path.exists()); note('disappearance_after_denial_not_success')

    def test_10_unreadable_owner_after_denial_is_not_retried(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='read-fail-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic'); path,raw=seed(store)
            original_read=Path.read_bytes; reads=[]; calls=[]; clock=Clock(); expected=PermissionError(13,'Independent owner read error')
            def read(p):
                if p==path:
                    reads.append(1)
                    if len(reads)>1: raise expected
                return original_read(p)
            def refused(*args,**kwargs): calls.append(1); raise share_error()
            with patch.object(Path,'read_bytes',read),patch.object(Path,'unlink',refused),patch.object(artifacts.time,'monotonic',clock.monotonic),patch.object(artifacts.time,'sleep',clock.sleep):
                with self.assertRaises(PermissionError) as caught: store._release_lock(path,raw)
            self.assertIs(caught.exception,expected); self.assertEqual(calls,[1]); self.assertEqual(original_read(path),raw)
            note('owner_read_error_preserved')

    def test_11_release_timeout_and_six_second_cap(self):
        for timeout in [0,.07,2,20]:
            with self.subTest(timeout=timeout),tempfile.TemporaryDirectory(dir=OUT,prefix='bounds-') as directory:
                store=FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=timeout); path,raw=seed(store)
                clock=Clock(); error=share_error()
                with patch.object(Path,'unlink',side_effect=error) as unlink,patch.object(artifacts.time,'monotonic',clock.monotonic),patch.object(artifacts.time,'sleep',clock.sleep):
                    with self.assertRaises(PermissionError) as caught: store._release_lock(path,raw)
                self.assertIs(caught.exception,error); self.assertLessEqual(len(clock.sleeps),120)
                self.assertLessEqual(sum(clock.sleeps),min(timeout,6)+1e-9)
                self.assertTrue(all(0<delay<=.05 for delay in clock.sleeps)); self.assertLessEqual(unlink.call_count,121)
                self.assertEqual(path.read_bytes(),raw)
                if timeout==0: self.assertEqual(unlink.call_count,1); self.assertEqual(clock.sleeps,[])
                note('bounded_timeout_'+str(timeout),attempts=unlink.call_count,backoffs=len(clock.sleeps),simulated_seconds=sum(clock.sleeps))

    def test_12_nonadvancing_clock_still_exactly_120_backoffs(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='frozen-clock-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=100); path,raw=seed(store)
            clock=Clock(fixed=True); error=share_error()
            with patch.object(Path,'unlink',side_effect=error) as unlink,patch.object(artifacts.time,'monotonic',clock.monotonic),patch.object(artifacts.time,'sleep',clock.sleep):
                with self.assertRaises(PermissionError): store._release_lock(path,raw)
            self.assertEqual(unlink.call_count,121); self.assertEqual(len(clock.sleeps),120)
            self.assertEqual(path.read_bytes(),raw); note('nonadvancing_clock_cap',attempts=121,backoffs=120)

    def test_13_release_window_starts_after_long_body(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='separate-clock-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=.1)
            clock=Clock(); real_unlink=Path.unlink; attempts=[]; body=[]
            def unlink(path,*args,**kwargs):
                attempts.append(1)
                if len(attempts)==1: raise share_error()
                return real_unlink(path,*args,**kwargs)
            with patch.object(Path,'unlink',unlink),patch.object(artifacts.time,'monotonic',clock.monotonic),patch.object(artifacts.time,'sleep',clock.sleep):
                with store.locked('synthetic/long-body'): body.append(1); clock.value+=100
            self.assertEqual(body,[1]); self.assertEqual(attempts,[1,1]); self.assertEqual(clock.sleeps,[.05]); note('release_has_independent_window')

    def test_14_nonretry_error_keeps_body_exception_as_context(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='error-context-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic'); error=share_error(5); body=RuntimeError('Independent body failure')
            with patch.object(Path,'unlink',side_effect=error):
                with self.assertRaises(PermissionError) as caught:
                    with store.locked('synthetic/body-and-release'): raise body
            self.assertIs(caught.exception,error); self.assertIs(caught.exception.__context__,body)
            note('nonretry_release_error_body_context_preserved')

    def test_15_six_processes_eighteen_requests_one_dispatch_and_one_charge(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='six-process-') as directory:
            registry=Registry(FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=6),LIMITS)
            identity=registry.register_config({'independent_synthetic':True,'case':'single-publication'})
            ctx=mp.get_context('spawn'); gate=ctx.Barrier(6); queue=ctx.Queue()
            processes=[ctx.Process(target=child_requests,args=(directory,identity,'independent-logical-operation',3,gate,queue)) for _ in range(6)]
            for process in processes: process.start()
            results=[queue.get(timeout=35) for _ in range(18)]
            for process in processes: process.join(timeout=35); self.assertEqual(process.exitcode,0)
            self.assertTrue(all(result.get('ok') for result in results),results)
            self.assertEqual(sum(result['should_execute'] for result in results),1)
            self.assertEqual(len({result['attempt_id'] for result in results}),1)
            rebuilt=Registry(FilesystemArtifactStore(directory,data_classification='synthetic'),LIMITS)
            self.assertEqual(rebuilt.snapshot()['usage']['research']['total'],1)
            self.assertEqual(len(decode_events(rebuilt.store.read_bytes(Registry.JOURNAL))),3)
            self.assertEqual(list((Path(directory)/'.locks').glob('*.lock')),[])
            note('six_process_eighteen_requests',request_count=18,processes=6,dispatches=1,research_charges=1,results=results)

    def test_16_WR04_cross_project_processes_compete_for_last_engineering_slot(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='wr04-') as directory:
            registry=Registry(FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=6),LIMITS)
            def bridge(project):
                raw=json.loads((ROOT/'config/engineering.json').read_bytes())
                raw.update(plan_id='independent-project-'+str(project),project_id=project,source_manifest_hash='a'*64,deployment_hash='b'*64)
                raw['request_template']['universe_hash']='c'*64
                plan=EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[project]); task=EngineeringTaskBridge(registry,plan); task.register(); return task
            a,b=bridge(5501),bridge(5502)
            first=a.claim('research'); registry.fail(first,'Independent synthetic first failure; no refund')
            ctx=mp.get_context('spawn'); gate=ctx.Barrier(2); queue=ctx.Queue()
            processes=[ctx.Process(target=child_requests,args=(directory,a.config_id,a._operation('research'),1,gate,queue,first.attempt_id)),
                       ctx.Process(target=child_requests,args=(directory,b.config_id,b._operation('research'),1,gate,queue))]
            for process in processes: process.start()
            results=[queue.get(timeout=35) for _ in range(2)]
            for process in processes: process.join(timeout=35); self.assertEqual(process.exitcode,0)
            self.assertEqual(sum(result.get('ok',False) and result['should_execute'] for result in results),1,results)
            denied=[result for result in results if not result.get('ok')]
            self.assertEqual(len(denied),1,results); self.assertEqual(denied[0]['type'],'BudgetExceeded')
            snapshot=Registry(FilesystemArtifactStore(directory,data_classification='synthetic'),LIMITS).snapshot()
            self.assertEqual(snapshot['usage']['research']['total'],2)
            self.assertEqual(snapshot['usage']['configurations']['total'],2)
            self.assertEqual(snapshot['attempts'][0]['status'],'failed')
            before=registry.store.read_bytes(Registry.JOURNAL)
            winner=next(result for result in results if result.get('ok'))
            config=a if winner['attempt_id']!=first.attempt_id and any(x['attempt_id']==winner['attempt_id'] and x['config_id']==a.config_id for x in snapshot['attempts']) else b
            reused=config.claim('research'); self.assertFalse(reused.should_execute); self.assertEqual(reused.attempt_id,winner['attempt_id'])
            self.assertEqual(registry.store.read_bytes(Registry.JOURNAL),before)
            note('WR04_cross_project_process_atomic_last_slot',results=results,research_used=2,first_failure_retained=True,reuse_free=True)

    def test_17_write_once_keeps_original_on_conflict(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='immutable-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic')
            self.assertTrue(store.write_once('synthetic/item',b'first'))
            self.assertFalse(store.write_once('synthetic/item',b'first'))
            with self.assertRaises(ArtifactConflict): store.write_once('synthetic/item',b'second')
            self.assertEqual(store.read_bytes('synthetic/item'),b'first'); note('write_once_original_immutable')

    def test_18_unresolved_occupied_lock_not_guessed_abandoned(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='occupied-') as directory:
            store=FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=.03)
            path,raw=seed(store); entered=[]
            with self.assertRaises(StoreBusy):
                with store.locked('synthetic/current'): entered.append(1)
            self.assertEqual(entered,[]); self.assertEqual(path.read_bytes(),raw); note('occupied_lock_not_reclaimed')

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(IndependentWindowsLock)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    payload={'source_commit':'975f676d62b561689909744f9e7236290e3f5fcb','platform':sys.platform,'python':sys.version,'methods':result.testsRun,
             'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'named_scenarios':len(OBS),'observations':OBS,
             'failure_details':[{'test':str(test),'traceback':tb} for test,tb in result.failures+result.errors],
             'cloud_calls':0,'original_source_writes':0,'real_budget_writes':0}
    (OUT/'first_results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
