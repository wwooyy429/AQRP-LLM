"""Independent developer probes of the fixed Research dispatch/error boundary."""
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,subprocess,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools'),str(ROOT/'tests')]
from qresearch.artifacts import FilesystemArtifactStore,canonical_json,content_hash
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,EngineeringTaskError
from qresearch.registry import Registry
import qresearch.engineering_receipts as receipts
import stage2
from test_engineering_receipts import context,envelope
from test_wr17_engineering_recovery import SyntheticFixture

SECRET='PEER_PRIVATE_TRACEBACK_AND_MARKET_SENTINEL_917.63'
FILES=('cloud/qresearch/engineering_receipts.py','tools/stage2.py','tests/test_native_research_failure.py')
LIMITS={x:{'total':10,'normal':8,'reserve':2} for x in ('configurations','research','lean')}
def read(payload,deployment,index=3,source=None):
 source=receipts.research_cell_source(payload,deployment) if source is None else source
 return envelope('jupyter_read_cell',{'projectId':17,'index':index},{'cellType':'code','source':source.splitlines(keepends=True)})
def error(index=3,native=None,is_error=False):
 value={'output_type':'error','ename':'RuntimeError','evalue':SECRET,'traceback':['Traceback: '+SECRET,'RuntimeError: '+SECRET]} if native is None else native
 tool=envelope('jupyter_execute_cell',{'projectId':17,'index':index},value);tool['result']['isError']=is_error;return tool

def align(tool):
 tool['result']['content'][0]['text']=json.dumps(tool['result']['structuredContent']);return tool

def dispatch(f,index=3):return stage2.research_dispatch(f.bridge,f.attempt,read(f.admission['payload'],f.admission['deployment'],index))

class IndependentResearchPeer(unittest.TestCase):
 def test_exact_read_identity_mirrors_source_and_bool_aliases_before_any_write(self):
  for version in (1,2):
   with SyntheticFixture(version) as f:
    good=read(f.admission['payload'],f.admission['deployment']);saved=dict(f.store._data);before=f.registry.snapshot()
    variants=[]
    for field,value in (('projectId',True),('index',True),('index',3.0),('index',-1),('index','3')):
     t=deepcopy(good);t['arguments'][field]=value;variants.append(t)
    t=deepcopy(good);t['result']['content'][0]['text']='{}';variants.append(t)
    t=deepcopy(good);t['result']['content'].append({'type':'text','text':SECRET});variants.append(t)
    t=deepcopy(good);t['result']['content'][0]['annotations']={'rows':[SECRET]};variants.append(t)
    t=deepcopy(good);t['result']['structuredContent']['source'][-1]+='\n';align(t);variants.append(t)
    t=deepcopy(good);t['result']['structuredContent']['outputs']=[SECRET];align(t);variants.append(t)
    for flag in (True,0,1,'false'):
     t=deepcopy(good);t['result']['isError']=flag;variants.append(t)
    for t in variants:
     with self.subTest(version=version,kind=list(t)),self.assertRaises(ValueError):stage2.research_dispatch(f.bridge,f.attempt,t)
     self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)

 def test_readback_source_may_be_chunked_but_no_EOF_or_alias_retarget(self):
  with SyntheticFixture(1) as f:
   p,d=f.admission['payload'],f.admission['deployment'];t=read(p,d);source=''.join(t['result']['structuredContent']['source'])
   t['result']['structuredContent']['source']=[source[:17],source[17:100],source[100:]];align(t)
   binding=receipts.research_dispatch_binding(p,d,t)
   self.assertEqual(binding['cell_source_sha256'],hashlib.sha256(source.encode()).hexdigest())
   self.assertTrue(stage2.research_dispatch(f.bridge,f.attempt,t)['should_execute']);before=f.registry.snapshot();saved=dict(f.store._data)
   for other in (4,True,3.0):
    changed=deepcopy(t);changed['arguments']['index']=other
    with self.subTest(index=other),self.assertRaises((ValueError,EngineeringTaskError)):stage2.research_dispatch(f.bridge,f.attempt,changed)
    self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)

 def test_unknown_and_network_errors_leave_precharged_task_unchanged(self):
  with SyntheticFixture(2) as f:
   dispatch(f);before=f.registry.snapshot();saved=dict(f.store._data)
   variants=[{'success':False,'errors':['Request timed out',SECRET]}, {'status':'ok','outputs':[error()['result']['structuredContent']]},
    {'status':'error','outputs':[error()['result']['structuredContent'],{'output_type':'stream','name':'stderr','text':SECRET}]},
    {'status':'running','outputs':[error()['result']['structuredContent']]},
    {'output_type':'stream','name':'stdout','text':json.dumps(error()['result']['structuredContent'])}]
   for native in variants:
    with self.subTest(native=list(native)),self.assertRaises(ValueError):stage2.settle_research_result(f.bridge,f.attempt,error(native=native))
    self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)
   for flag in (0,1,'true',None):
    with self.subTest(flag=flag),self.assertRaises(ValueError):stage2.settle_research_result(f.bridge,f.attempt,error(is_error=flag))
    self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)

 def test_legacy_prepare_never_backfills_missing_protocol_even_with_absent_current_sources(self):
  for version in (1,2):
   with SyntheticFixture(version) as f:
    key='engineering/research-entry-protocol/'+f.attempt+'.json';del f.store._data[key]
    (f.root/'cloud/stub.py').unlink();(f.root/'audit/deployment.json').unlink();(f.root/'audit/engineering_current.json').unlink()
    before=f.registry.snapshot();saved=dict(f.store._data)
    self.assertEqual(stage2.prepare(f.bridge,f.attempt),f.admission);self.assertEqual(f.store._data,saved)
    with self.assertRaises(EngineeringTaskError):dispatch(f)
    self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)

 def test_synthetic_native_failure_receipt_is_redacted_and_repeat_is_exact(self):
  for version in (1,2):
   with SyntheticFixture(version) as f:
    dispatch(f);before=f.registry.snapshot();native=error();result=stage2.settle_research_result(f.bridge,f.attempt,native)
    self.assertEqual(result.status,'failed');after=f.registry.snapshot();saved=dict(f.store._data)
    self.assertEqual(after['usage'],before['usage']);self.assertNotIn(SECRET,str(saved))
    self.assertEqual(stage2.settle_research_result(f.bridge,f.attempt,deepcopy(native)).status,'failed')
    self.assertEqual(f.registry.snapshot(),after);self.assertEqual(f.store._data,saved)
    different=deepcopy(native);different['result']['isError']=True
    with self.assertRaises(EngineeringTaskError):stage2.settle_research_result(f.bridge,f.attempt,different)
    self.assertEqual(f.registry.snapshot(),after);self.assertEqual(f.store._data,saved)

 def test_failure_write_crashes_recover_without_extra_quota_or_success(self):
  for target in ('pointer','submission','completion','pending_event','failed_event'):
   with self.subTest(target=target),SyntheticFixture(1) as f:
    dispatch(f);before=f.registry.snapshot();write=f.store.write_once;append=f.store.append_event;injected=[]
    def maybe_write(key,data):
     hit=(target=='pointer' and key==f.bridge._submission_key(f.attempt)) or (target=='submission' and '/submission/' in key) or (target=='completion' and '/completion/' in key)
     if hit and not injected:injected.append(key);raise OSError('Synthetic peer write interruption')
     return write(key,data)
    def maybe_append(stream,event):
     if target==event.get('kind','')+'_event' and not injected:injected.append(stream);raise OSError('Synthetic peer event interruption')
     return append(stream,event)
    with patch.object(f.store,'write_once',side_effect=maybe_write),patch.object(f.store,'append_event',side_effect=maybe_append),self.assertRaises(OSError):stage2.settle_research_result(f.bridge,f.attempt,error())
    self.assertEqual(len(injected),1);self.assertEqual(f.registry.snapshot()['usage'],before['usage'])
    self.assertEqual(stage2.settle_research_result(f.bridge,f.attempt,error()).status,'failed')
    after=f.registry.snapshot();saved=dict(f.store._data);self.assertEqual(after['usage'],before['usage'])
    self.assertEqual(stage2.settle_research_result(f.bridge,f.attempt,error()).status,'failed');self.assertEqual(f.registry.snapshot(),after);self.assertEqual(f.store._data,saved)
    self.assertFalse(any(k.startswith('results/') for k in saved));self.assertNotIn(SECRET,str(saved))

 def test_many_threads_receive_one_dispatch_permission(self):
  with SyntheticFixture(2) as f:
   t=read(f.admission['payload'],f.admission['deployment']);before=f.registry.snapshot()
   with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:stage2.research_dispatch(f.bridge,f.attempt,deepcopy(t)),range(16)))
   self.assertEqual(sum(r['should_execute'] for r in results),1);self.assertEqual(f.registry.snapshot(),before)

 def test_real_Windows_processes_share_one_synthetic_dispatch_marker(self):
  with SyntheticFixture(1) as f:
   folder=f.root/'shared';store=FilesystemArtifactStore(folder)
   for key,value in f.store._data.items():store.write_once(key,value)
   before=Registry(store,LIMITS).snapshot();plan=f.root/'peer_plan.json';plan.write_bytes(canonical_json(f.plan.to_dict()))
   tool=f.root/'peer_read.json';tool.write_bytes(canonical_json(read(f.admission['payload'],f.admission['deployment'])))
   commands=[[sys.executable,'-B',str(Path(__file__).resolve()),'--dispatch-process',str(f.root),str(folder),str(plan),str(tool),f.attempt] for _ in range(4)]
   procs=[subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')) for command in commands]
   results=[]
   for process in procs:
    stdout,stderr=process.communicate(timeout=45);self.assertEqual(process.returncode,0,stderr.decode(errors='replace'));results.append(json.loads(stdout))
   self.assertEqual(sum(r['should_execute'] for r in results),1);self.assertEqual(Registry(store,LIMITS).snapshot(),before)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--dispatch-process':
  work,folder,plan,tool,attempt=sys.argv[2:];stage2.ROOT=Path(work);store=FilesystemArtifactStore(Path(folder));registry=Registry(store,LIMITS)
  bridge=EngineeringTaskBridge(registry,EngineeringTaskPlan.from_dict(json.loads(Path(plan).read_bytes()),discovered_project_ids=[17]))
  print(json.dumps(stage2.research_dispatch(bridge,attempt,json.loads(Path(tool).read_bytes()))))
 else:unittest.main(verbosity=2)
