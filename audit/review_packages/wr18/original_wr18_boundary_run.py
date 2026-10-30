from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[2]
phase=sys.argv[1]
out=root/'.git/repair-work'/('wr18-boundary-'+phase)
out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
tests=root/'tests/test_wr18_completion_dependency.py'
shutil.copyfile(tests,out/'test_input.py')
for filename in ('registry.py','engineering_tasks.py'):
    shutil.copyfile(root/'cloud/qresearch'/filename,out/('source_'+filename))
commands=[('original_mre',[sys.executable,'-B',str(root.parent/'LLM审核/review-ae2b898-20261027/minimal_wr18.py'),str(root)]),
          ('new_tests',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_wr18_completion_dependency.py','-v'])]
records=[]
for label,command in commands:
    start=time.monotonic()
    result=subprocess.run(command,cwd=root,env=env,capture_output=True)
    (out/(label+'.stdout')).write_bytes(result.stdout)
    (out/(label+'.stderr')).write_bytes(result.stderr)
    records.append({'name':label,'command':command,'cwd':str(root),'exit_code':result.returncode,'seconds':time.monotonic()-start,
                    'stdout':label+'.stdout','stderr':label+'.stderr'})
    print(json.dumps(records[-1],ensure_ascii=True),flush=True)
summary={'phase':phase,'synthetic_only':True,'actual_cloud_or_model_calls':0,
         'test_sha256':hashlib.sha256(tests.read_bytes()).hexdigest(),'records':records}
(out/'commands.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
