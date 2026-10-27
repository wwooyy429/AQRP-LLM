"""WR17: actual CLI freeze can switch a pending project's settlement pointer.

Usage: python -B minimal_pending_freeze.py <source-dir> [output-directory]
Only a newly copied source/ledger is written; no QC operation is performed.
"""
from pathlib import Path
from uuid import uuid4
import json,os,shutil,subprocess,sys
sys.dont_write_bytecode=True
if len(sys.argv)>1 and sys.argv[1]=='--inspect':
    root=Path(sys.argv[2]);sys.path[:0]=[str(root/'cloud'),str(root/'tools')]
    import stage2
    print(json.dumps(stage2.current_bridge()._record(sys.argv[3])));raise SystemExit(0)
source=Path(sys.argv[1]).resolve()
output=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else Path(__file__).resolve().parent/'freeze_MRE'/uuid4().hex[:8]
case=output/'source';shutil.copytree(source,case,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
active=json.loads((case/'config/quantconnect.json').read_text(encoding='utf-8'))['active_project_id']
events=[json.loads(line)['event'] for line in (case/'audit/runtime/registry/events.jsonl').read_bytes().splitlines()]
attempt=next(e['attempt_id'] for e in reversed(events) if e['kind']=='pending' and e.get('external_id')=='39cafa1e9b11f91b27e396b66d033a6d')
listing=case/'synthetic-projects.json';listing.write_text(json.dumps({'success':True,'projects':[{'projectId':active}]}),encoding='utf-8')
commands=[]
def run(args):
    c=[sys.executable,'-B',*map(str,args)]
    r=subprocess.run(c,cwd=case,text=True,encoding='utf-8',capture_output=True,timeout=40,
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1'))
    d={'command':c,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr};commands.append(d);return d
pointer=case/'audit/engineering_current.json';journal=case/'audit/runtime/registry/events.jsonl'
before_pointer=pointer.read_bytes();before_journal=journal.read_bytes()
initial=run([Path(__file__).resolve(),'--inspect',case,attempt])
blocked=run([case/'tools/stage2.py','freeze','--plan-file','config/engineering_joint_pilot.json','--projects-file',listing])
assert initial['returncode']==0 and blocked['returncode']!=0 and pointer.read_bytes()==before_pointer
accepted=run([case/'tools/stage2.py','freeze','--plan-file','config/engineering.json','--projects-file',listing])
after_prepare=run([case/'tools/stage2.py','prepare','--attempt',attempt])
data={'source':str(source),'case':str(case),'original_pending_attempt':attempt,
 'original_context_accepts_attempt':initial['returncode']==0,'joint_freeze_refused':blocked['returncode']!=0,
 'legacy_freeze_returncode':accepted['returncode'],'pointer_changed':pointer.read_bytes()!=before_pointer,
 'prepare_old_attempt_returncode':after_prepare['returncode'],'prepare_error':after_prepare['stderr'],
 'ledger_unchanged':journal.read_bytes()==before_journal,'commands':commands,'actual_QC_calls':0}
output.mkdir(parents=True,exist_ok=True);(output/'result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(data,ensure_ascii=False,indent=2))
assert accepted['returncode']!=0 and pointer.read_bytes()==before_pointer,'Legacy freeze replaced unresolved project settlement context'
