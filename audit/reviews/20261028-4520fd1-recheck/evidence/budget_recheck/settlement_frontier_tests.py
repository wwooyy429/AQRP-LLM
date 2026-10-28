"""New independent full-capacity settlement tests, not a rerun of prior12 tests."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy,hashlib,io,json,os,subprocess,sys,threading,time,unittest
from frontier_support import *
R=Path(__file__).resolve().parent;WORK=R/'work';WORK.mkdir(exist_ok=True)
scenarios=[];processes=[]
def note(name,detail=None):scenarios.append({'name':name,'detail':detail})
class Frontier(unittest.TestCase):
 def reject_no_write(self,store,r,call,errors=(RegistryError,EngineeringTaskError,ValueError)):
  before=store_bytes(store);usage=r.snapshot()['usage']
  with self.assertRaises(errors):call()
  self.assertEqual(store_bytes(store),before);self.assertEqual(r.snapshot()['usage'],usage)
 def no_callback(self,_):raise AssertionError('Terminal attempt called completion source again')
 def terminal_check(self,store,r,task,status):
  self.assertEqual(r.snapshot()['usage'],EXPECTED)
  self.assertEqual(next(x for x in r.snapshot()['attempts']if x['attempt_id']==ATTEMPT)['status'],status)
  self.assertEqual(sum(x['kind']==status and x.get('attempt_id')==ATTEMPT for x in rows(r)),1)
  self.assertEqual(len(rows(r)),47)
  saved=store_bytes(store)
  replay=task.consume_completion(ATTEMPT,completion_source=self.no_callback)
  self.assertEqual(replay.status,status);self.assertEqual(store_bytes(store),saved)
  self.assertFalse(task.claim('lean',allocation='normal').should_execute)
  self.assertEqual(store_bytes(store),saved)
 def test01_actual46_full_budget_pending_is_not_result_and_existing_claim_has_no_debit(self):
  store,r,task,record=copied_context();self.assertEqual(r.snapshot()['usage'],EXPECTED);self.assertEqual(len(rows(r)),46)
  self.assertEqual(record['status'],'pending');self.assertEqual(record['external_id'],'3e68866a46ca88ff16481c31b3c2c822')
  self.assertEqual(r.engineering_rounds_snapshot()[ROUND]['usage'],{'configurations':2,'research':2,'lean':1})
  self.assertEqual(r.engineering_rounds_snapshot()[ROUND]['grant']['limits'],{'configurations':2,'research':4,'lean':2})
  self.assertEqual(len(task.plan.to_dict()['required_checks']['lean']),7);self.assertEqual(len(task.plan.to_dict()['required_checks']['research']),13)
  before=store_bytes(store)
  for allocation in('normal','reserve'):
   restored=reopen(store);t,_=task_context(restored);claimed=t.claim('lean',allocation=allocation)
   self.assertFalse(claimed.should_execute);self.assertEqual(claimed.attempt_id,ATTEMPT)
   self.assertEqual(store_bytes(store),before);note('existing pending claim no debit '+allocation)
  self.reject_no_write(store,r,lambda:task.read_result(ATTEMPT));note('pending result unavailable at full capacity')
  for allocation in('normal','reserve'):
   self.reject_no_write(store,r,lambda allocation=allocation:r.register_config({'independent_new_semantics':allocation},allocation=allocation));note('new configuration full-cap rejection '+allocation)
  self.assertEqual(task.register(allocation='normal'),record['config_id']);self.assertEqual(store_bytes(store),before);note('existing exact registration no debit')
 def test02_full_configuration_does_not_block_original_synthetic_success_settlement(self):
  store,r,task,record=copied_context();observed=synthetic_terminal(task,record)
  result=task.consume_completion(ATTEMPT,completion_source=lambda _:copy.deepcopy(observed));self.assertEqual(result.status,'completed')
  self.terminal_check(store,r,task,'completed');self.assertIs(task.read_result(ATTEMPT)['financial_evidence'],False)
  saved=store_bytes(store);already=task.claim('lean',allocation='normal',retry_of=ATTEMPT,reason='Successful operation remains idempotent')
  self.assertEqual(already.status,'completed');self.assertFalse(already.should_execute);self.assertEqual(store_bytes(store),saved)
  note('success47 events no debit; repeated success/cached claim stays47')
 def test03_native_failure_kinds_keep_charge_and_existing_explicit_retry_bound(self):
  for status in('failed','runtime_error','compile_error'):
   with self.subTest(status=status):
    store,r,task,record=copied_context();observed=synthetic_terminal(task,record,status)
    result=task.consume_completion(ATTEMPT,completion_source=lambda _:observed);self.assertEqual(result.status,'failed')
    self.terminal_check(store,r,task,'failed');self.reject_no_write(store,r,lambda:task.read_result(ATTEMPT))
    self.reject_no_write(store,r,lambda:task.claim('lean',allocation='normal',retry_of=ATTEMPT,reason=''))
    retry=task.claim('lean',allocation='normal',retry_of=ATTEMPT,reason='Independent synthetic fixed-input retry only')
    self.assertTrue(retry.should_execute);self.assertEqual(r.snapshot()['usage']['configurations'],EXPECTED['configurations'])
    self.assertEqual(r.snapshot()['usage']['lean'],{'normal':3,'reserve':0,'total':3});self.assertEqual(len(rows(r)),48)
    r.fail(retry,'Synthetic retry failed');self.reject_no_write(store,r,lambda:task.claim('lean',allocation='normal',retry_of=retry.attempt_id,reason='Beyond max_retries1'))
    self.assertEqual(len(rows(r)),49);note('synthetic '+status+' then one unchanged-config retry; third rejected')
 def test04_bound_terminal_mutants_reject_before_any_write_at_full_budget(self):
  mutants=[('external',lambda o:o['platform']['identity'].update(external_id='foreign')),
   ('input',lambda o:o['platform']['deployment'].update(input_hash='0'*64)),
   ('source',lambda o:o['platform']['identity'].update(source_manifest_hash='0'*64)),
   ('not_terminal',lambda o:o['platform'].update(terminal=False)),
   ('submitted',lambda o:o['platform'].update(status='submitted')),
   ('empty_receipt',lambda o:o['platform'].update(raw_receipt={})),
   ('future_cert',lambda o:o['cloud_report'].update(actual_availability_verified=True)),
   ('row_export',lambda o:o.update(rows=[1]))]
  for label,mutate in mutants:
   with self.subTest(label=label):
    store,r,task,record=copied_context();observed=synthetic_terminal(task,record);mutate(observed)
    if 'cloud_report'in observed:observed['report_ref']['sha256']=content_hash(observed['cloud_report'])
    self.reject_no_write(store,r,lambda:task.consume_completion(ATTEMPT,completion_source=lambda _:observed));note('bound invalid '+label)
 def test05_publication_and_terminal_event_faults_recover_without_new_debits(self):
  cases=[('completed',('write','engineering/evidence/'+ATTEMPT+'/completion/')),
   ('completed',('write','results/')),('completed',('event','completed')),
   ('runtime_error',('write','engineering/evidence/'+ATTEMPT+'/completion/')),
   ('runtime_error',('event','failed'))]
  for status,target in cases:
   for mode in('before','after'):
    with self.subTest(status=status,target=target,mode=mode):
     store,r,task,record=copied_context(FaultStore());observed=synthetic_terminal(task,record,status);store.arm(target,mode)
     with self.assertRaises(OSError):task.consume_completion(ATTEMPT,completion_source=lambda _:copy.deepcopy(observed))
     self.assertTrue(store.fired);self.assertEqual(r.snapshot()['usage'],EXPECTED)
     # A fresh registry/bridge, same copied physical store, repairs only publication.
     restored=reopen(store);t,_=task_context(restored)
     final=t.consume_completion(ATTEMPT,completion_source=lambda _:copy.deepcopy(observed))
     expected='completed'if status=='completed'else'failed';self.assertEqual(final.status,expected)
     self.terminal_check(store,restored,t,expected);note('publication fault '+status+' '+str(target)+' '+mode)
 def test06_six_concurrent_store_handles_settle_same_terminal_once(self):
  for status in('completed','runtime_error'):
   with self.subTest(status=status):
    store,r,task,record=copied_context();barrier=threading.Barrier(6);observed=synthetic_terminal(task,record,status)
    def deliver(_):barrier.wait(timeout=15);return copy.deepcopy(observed)
    def worker(_):
     reg=reopen(store);t,_=task_context(reg);return t.consume_completion(ATTEMPT,completion_source=deliver).status
    with ThreadPoolExecutor(max_workers=6)as pool:results=list(pool.map(worker,range(6)))
    expected='completed'if status=='completed'else'failed';self.assertEqual(results,[expected]*6)
    self.terminal_check(store,r,task,expected);note('6 concurrent registry handles '+status)
 def test07_two_native_Windows_processes_different_stores_settle_once(self):
  self.assertEqual(os.name,'nt')
  for status in('completed','runtime_error'):
   case=WORK/status;case.mkdir(exist_ok=False);store=FilesystemArtifactStore(case/'store',data_classification='synthetic');_,r,task,record=copied_context(store)
   (case/'case.json').write_bytes(canonical_json({'status':status}));workers=[]
   for index in range(2):
    command=[sys.executable,'-B',str(R/'process_settlement_worker.py'),'--case',str(case),'--index',str(index)]
    workers.append((command,subprocess.Popen(command,cwd=R,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)))
   deadline=time.monotonic()+25
   while not all((case/('ready-'+str(i))).exists()for i in range(2)):
    if any(p.poll()is not None for _,p in workers)or time.monotonic()>deadline:break
    time.sleep(.01)
   (case/'go').write_text('go');outputs=[]
   for index,(command,process)in enumerate(workers):
    stdout,stderr=process.communicate(timeout=25);(case/('worker-'+str(index)+'.stdout')).write_bytes(stdout);(case/('worker-'+str(index)+'.stderr')).write_bytes(stderr)
    processes.append({'command':command,'cwd':str(R),'pid':process.pid,'exit_code':process.returncode,'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest()})
    self.assertEqual(process.returncode,0,stderr.decode(errors='replace'));outputs.append(json.loads((case/('worker-'+str(index)+'.json')).read_bytes()))
   self.assertEqual(len({x['pid']for x in outputs}),2);self.assertTrue(all(x['os']=='nt'for x in outputs))
   expected='completed'if status=='completed'else'failed';self.assertEqual([x['status']for x in outputs],[expected]*2)
   restored=reopen(store);t,_=task_context(restored);self.terminal_check(store,restored,t,expected);note('2 nativeWindows processes '+status)
if __name__=='__main__':
 stream=io.StringIO();start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Frontier);result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
 out={'fixed_commit':'4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8','methods':result.testsRun,'passed_methods':result.testsRun-len({str(t)for t,_ in result.failures+result.errors}),'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'named_scenarios':len(scenarios),'scenarios':scenarios,'native_Windows_processes':len(processes),'thread_workers':12,'seconds':time.monotonic()-start,'failures':[{'test':str(t),'traceback':tb}for t,tb in result.failures],'errors':[{'test':str(t),'traceback':tb}for t,tb in result.errors],'actual_QC_Research_LEAN_model_orders_source_or_authoritative_budget_writes':0,'financial_evidence':False}
 (R/'first_unittest.txt').write_text(stream.getvalue(),encoding='utf-8');(R/'first_results.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');(R/'process_execution_records.json').write_text(json.dumps(processes,indent=2)+'\n',encoding='utf-8')
 print(stream.getvalue());print(json.dumps({k:v for k,v in out.items()if k not in['scenarios','failures','errors']}));sys.exit(0 if result.wasSuccessful()else 1)
