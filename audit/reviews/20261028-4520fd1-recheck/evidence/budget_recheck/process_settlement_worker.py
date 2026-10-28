"""One independent synthetic worker process; never an actual cloud worker."""
import argparse,json,os,time
from pathlib import Path
from frontier_support import *
p=argparse.ArgumentParser();p.add_argument('--case',type=Path,required=True);p.add_argument('--index',required=True);a=p.parse_args()
case=json.loads((a.case/'case.json').read_bytes())
store=FilesystemArtifactStore(a.case/'store',data_classification='synthetic',lock_timeout=20)
r=reopen(store);task,record=task_context(r);observed=synthetic_terminal(task,record,status=case['status'])
(a.case/('ready-'+a.index)).write_text('ready')
deadline=time.monotonic()+20
while not(a.case/'go').exists():
 if time.monotonic()>deadline:raise RuntimeError('Start barrier timed out')
 time.sleep(.01)
def delivered(_):
 (a.case/('inside-'+a.index)).write_text('inside')
 while not all((a.case/('inside-'+str(i))).exists()for i in range(2)):
  if time.monotonic()>deadline:raise RuntimeError('Reader barrier timed out')
  time.sleep(.01)
 return observed
result=task.consume_completion(ATTEMPT,completion_source=delivered)
out={'pid':os.getpid(),'os':os.name,'status':result.status,'events':len(rows(r)),'usage':r.snapshot()['usage'],'external_id':result.external_id}
(a.case/('worker-'+a.index+'.json')).write_bytes(canonical_json(out));print(json.dumps(out))
