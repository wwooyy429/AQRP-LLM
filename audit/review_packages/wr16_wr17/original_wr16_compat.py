from pathlib import Path
import io
import json
import os
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[2]
out=root/'.git/repair-work/wr16-compat'
out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
records=[]
for name in ('test_collection_admission.py','test_persistence.py','test_engineering_tasks.py','test_phase2_joint_plan.py','test_phase2_joint_boundaries.py'):
    command=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p',name,'-q']
    start=time.monotonic(); result=subprocess.run(command,cwd=root,env=env,capture_output=True)
    (out/(name+'.stdout')).write_bytes(result.stdout)
    (out/(name+'.stderr')).write_bytes(result.stderr)
    records.append({'command':command,'exit_code':result.returncode,'seconds':time.monotonic()-start})
    print(json.dumps(records[-1]),flush=True)
(out/'commands.json').write_text(json.dumps({'kind':'developer_unchanged_compatibility_suites','synthetic_only':True,'records':records},indent=2)+'\n',encoding='utf-8')
