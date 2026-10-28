"""Independent metadata-only settlement frontier fixtures; no platform I/O."""
from pathlib import Path
import copy,json,os,sys
SOURCE=Path(os.environ.get('AQRP_REVIEW_SOURCE',str(Path(__file__).resolve().parent.parent/'source'))).resolve()
sys.dont_write_bytecode=True
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.artifacts import MemoryArtifactStore,FilesystemArtifactStore,canonical_json,content_hash,ArtifactConflict
from qresearch.registry import Registry,RegistryError,BudgetExceeded
from qresearch.engineering_tasks import EngineeringTaskBridge,EngineeringTaskPlan,EngineeringTaskError
ATTEMPT='37dc855045e14ca49c88fd9d75f40cf7'
ROUND='stage2-normal-repair-round-004'
EXPECTED={'configurations':{'total':12,'normal':8,'reserve':4},'research':{'total':15,'normal':8,'reserve':7},'lean':{'total':2,'normal':2,'reserve':0}}
def copied_context(store=None):
 store=MemoryArtifactStore()if store is None else store
 for p in(SOURCE/'audit/runtime').rglob('*'):
  if p.is_file():store.write_once(p.relative_to(SOURCE/'audit/runtime').as_posix(),p.read_bytes())
 baseline=json.loads((SOURCE/'audit/runtime/registry/baseline.json').read_bytes())
 registry=Registry(store,baseline)
 return store,registry,*task_context(registry)
def task_context(registry):
 record=next(x for x in registry.snapshot()['attempts']if x['attempt_id']==ATTEMPT)
 package=json.loads(registry.store.read_bytes('configurations/'+record['config_id']+'.json'))
 plan=EngineeringTaskPlan.from_dict(package['plan'],discovered_project_ids=[package['plan']['project_id']])
 return EngineeringTaskBridge(registry,plan),record
def reopen(store):
 return Registry(store,json.loads((SOURCE/'audit/runtime/registry/baseline.json').read_bytes()))
def synthetic_terminal(task,record,status='completed',count=2):
 payload=task.payload(ATTEMPT)
 platform={'identity':dict(payload['identity'],external_id=record['external_id']),
  'terminal':True,'status':status,'deployment':record['details']['deployment'],
  'raw_receipt':{'independent_synthetic_terminal':True}}
 if status!='completed':return {'platform':platform}
 report={'schema_version':1,'identity':payload['identity'],'status':'completed','terminal':True,
  'checks':{key:True for key in payload['plan']['required_checks']['lean']},
  'statistics':{'data_event_count':count,'orders_submitted':0,'runtime_error_count':0,'dividend_event_count':1},
  'resolution':copy.deepcopy(payload['research_resolution']),
  **{key:False for key in('market_values_exported','economic_factor_tested','final_data_accessed','full_US200_coverage_certified','actual_availability_verified')}}
 return {'platform':platform,'cloud_report':report,'report_ref':{'key':payload['report_key'],'sha256':content_hash(report)}}
def rows(registry):
 return [json.loads(line)['event']for line in registry.store.read_bytes(registry.JOURNAL).splitlines()]
def store_bytes(store):
 if isinstance(store,MemoryArtifactStore):return dict(store._data)
 return {p.relative_to(store.root).as_posix():p.read_bytes()for p in store.root.rglob('*')if p.is_file()}
class FaultStore(MemoryArtifactStore):
 def __init__(self):super().__init__();self.target=None;self.mode=None;self.fired=False
 def arm(self,target,mode):self.target=target;self.mode=mode;self.fired=False
 def write_once(self,key,data):
  hit=not self.fired and self.target and self.target[0]=='write' and key.startswith(self.target[1])
  if hit:self.fired=True
  if hit and self.mode=='before':raise OSError('Synthetic pre-write fault')
  result=super().write_once(key,data)
  if hit and self.mode=='after':raise OSError('Synthetic post-write fault')
  return result
 def append_event(self,key,event):
  hit=not self.fired and self.target and self.target[0]=='event' and event.get('kind')==self.target[1]
  if hit:self.fired=True
  if hit and self.mode=='before':raise OSError('Synthetic pre-event fault')
  result=super().append_event(key,event)
  if hit and self.mode=='after':raise OSError('Synthetic post-event fault')
  return result
