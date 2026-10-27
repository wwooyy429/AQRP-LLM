from pathlib import Path
import json
import os
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[2]
out=root/'.git/repair-work/wr18-compat';out.mkdir(exist_ok=True)
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
names=('test_engineering_tasks.py','test_engineering_receipts.py','test_collection_tasks.py',
       'test_collection_task_cli.py','test_wr16_registry_admission.py','test_wr17_engineering_recovery.py')
records=[]
for name in names:
    command=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p',name,'-v']
    start=time.monotonic();result=subprocess.run(command,cwd=root,env=env,capture_output=True)
    (out/(name+'.stdout')).write_bytes(result.stdout);(out/(name+'.stderr')).write_bytes(result.stderr)
    records.append({'name':name,'command':command,'cwd':str(root),'exit_code':result.returncode,
                    'seconds':time.monotonic()-start,'stdout':name+'.stdout','stderr':name+'.stderr'})
    print(json.dumps(records[-1],ensure_ascii=True),flush=True)
(out/'execution.json').write_bytes((json.dumps({'purpose':'developer_compatibility_replay_after_shared_completion_contract',
    'records':records,'actual_cloud_or_model_calls':0},ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
raise SystemExit(0 if all(r['exit_code']==0 for r in records) else 1)
