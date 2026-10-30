"""Observe CLI preflight versus public Bridge call paths; synthetic I/O only."""
from pathlib import Path
import json,sys
sys.dont_write_bytecode=True
import quick_joint_probes as h
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge
from qresearch.registry import Registry
from qresearch.artifacts import MemoryArtifactStore
from qresearch.workflow import SubmissionRejected
import stage2

catalog=json.loads((h.SOURCE/'config/source_catalog.json').read_text(encoding='utf-8'))['fields']
raw=h.joint().to_dict();raw['collection_probe']['field_catalog']={k:catalog[k] for k in raw['collection_probe']['field_catalog']}
plan=EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[raw['project_id']],probe_field_catalog=catalog)
r=Registry(MemoryArtifactStore(),h.budget());calls=[]
class Adapter:
    def submit_research(self,payload,**kwargs):
        calls.append({'identity':payload['identity'],'usage_before_callback':r.snapshot()['usage']})
        raise SubmissionRejected('Synthetic adapter stops here; no remote service called')
b=EngineeringTaskBridge(r,plan,adapter=Adapter());preflight=None
try:stage2.joint_preflight(b)
except (ValueError,RuntimeError) as e:preflight={'type':type(e).__name__,'message':str(e)}
before=r.snapshot()['usage'];b.register();result=b.submit('research')
data={'preflight_refusal':preflight,'before':before,'after':r.snapshot()['usage'],'result':vars(result),'synthetic_adapter_calls':calls,
      'actual_remote_calls':0,'scope':'The public Bridge does not itself invoke tools.stage2.joint_preflight. Trusted caller/adapter boundary remains; this is not a successful wrong-deployment worker execution.'}
target=Path(__file__).with_name('api_preflight_boundary.json');target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(data,ensure_ascii=False,indent=2))
