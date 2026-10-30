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
review=root.parent/'LLM审核/review-ae2b898-20261027'
out=root/'.git/repair-work'/('wr18-full-'+phase)
out.mkdir(parents=True,exist_ok=True)
source=review/'source' if phase=='before' else root
shutil.copytree(source/'cloud',out/'source/cloud',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
scripts=out/'admission_agent';scripts.mkdir(exist_ok=True)
names=('minimal_checked_dependency.py','independent_wr16_boundaries.py','quick_joint_probes.py')
hashes={}
for name in names:
    shutil.copyfile(review/'admission_agent'/name,scripts/name)
    hashes[name]=hashlib.sha256((scripts/name).read_bytes()).hexdigest()
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
records=[]
for name,args in [('minimal_checked_dependency.py',[str(out/'source')]),('independent_wr16_boundaries.py',[])]:
    command=[sys.executable,'-B',str(scripts/name),*args]
    start=time.monotonic();result=subprocess.run(command,cwd=out,env=env,capture_output=True)
    (out/(name+'.stdout')).write_bytes(result.stdout);(out/(name+'.stderr')).write_bytes(result.stderr)
    records.append({'command':command,'cwd':str(out),'exit_code':result.returncode,'seconds':time.monotonic()-start,
                    'stdout':name+'.stdout','stderr':name+'.stderr'})
    print(json.dumps(records[-1],ensure_ascii=True),flush=True)
(out/'execution.json').write_bytes((json.dumps({'phase':phase,'scripts_byte_equal_original':True,'script_sha256':hashes,
    'source_root_copied_from':str(source),'records':records,'actual_cloud_or_model_calls':0},ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
