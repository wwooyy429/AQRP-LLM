"""Three independent defect reproducers; synthetic data, no platform calls."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,sys,threading
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'source/cloud'),str(ROOT/'source/tools')]
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge
from qresearch.evaluation import daily_rank_ic
from qresearch.point_in_time import causal_window
from qresearch.contracts import RECORD_COLUMNS
from stage2 import _limits

budget={'configurations':{'total':12,'normal':8,'reserve':4},
        'research':{'total':20,'normal':12,'reserve':8},
        'lean':{'total':16,'normal':8,'reserve':8}}
registry=Registry(MemoryArtifactStore(),budget)
def make_bridge(name):
    d=json.loads((ROOT/'source/config/engineering.json').read_text(encoding='utf-8-sig'))
    d.update(plan_id=name,project_id=101,source_manifest_hash='1'*64,deployment_hash='2'*64)
    d['request_template']['universe_hash']='3'*64
    plan=EngineeringTaskPlan.from_dict(d,discovered_project_ids=[101])
    return EngineeringTaskBridge(registry,plan)
make_bridge('already-used').register()
barrier=threading.Barrier(2)
def contender(name):
    b=make_bridge(name)
    _limits(b,'configurations')
    barrier.wait(5)
    return b.register()
with ThreadPoolExecutor(max_workers=2) as executor:
    list(executor.map(contender,['contender-a','contender-b']))
print('WR-04 expected maximum=2, actual=',registry.snapshot()['usage']['configurations']['total'])

t=pd.Timestamp('2018-06-04 09:00',tz='America/New_York')
frame=pd.DataFrame({'formation_at':[t]*3,'sid':['A','B','C'],
                   'prediction':[1e-200,2e-200,3e-200],'label':[.1,.2,.3]})
print('WR-05 expected RankIC=1, actual=',daily_rank_ic(frame).ic.iloc[0])

event=pd.Timestamp('2018-06-01 16:00',tz='America/New_York')
records=pd.DataFrame([['A','close',event,event,7.,'v1']],columns=RECORD_COLUMNS)
membership=pd.DataFrame(True,index=pd.DatetimeIndex([t]),columns=['A'])
try:
    causal_window(records,[t],['A'],{'close':'exact_session'},{t:event},membership=membership)
    print('WR-06 equivalent NY timezone accepted')
except ValueError as exc:
    print('WR-06 expected accepted, actual=',str(exc))
