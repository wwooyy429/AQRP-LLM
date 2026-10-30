from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parents[2]
out=root/'.git/repair-work/wr16-quick-replay'
out.mkdir(parents=True,exist_ok=True)
source=out/'source'
for folder in ('cloud','tools','config','templates'):
    shutil.copytree(root/folder,source/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree(root/'audit/runtime',source/'audit/runtime',dirs_exist_ok=True)
for path in ('audit/engineering_current.json','audit/deployment.json'):
    target=source/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/path,target)
script=root.parent/'LLM审核/review-8f7236e-20261027/admission_agent/quick_joint_probes.py'
target=out/'admission_agent/quick_joint_probes.py'
target.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(script,target)
assert script.read_bytes()==target.read_bytes()
command=[sys.executable,'-B',str(target)]
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
result=subprocess.run(command,cwd=root,env=env,capture_output=True)
(out/'run.stdout').write_bytes(result.stdout)
(out/'run.stderr').write_bytes(result.stderr)
record={'command':command,'exit_code':result.returncode,'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
        'script_unchanged':True,'source_scope':'Current cloud/tools/config/templates plus copied authoritative metadata, no original ledger mutation',
        'historical_literals_in_script_are_not_current_source_identity':True,'actual_cloud_or_model_calls':0,
        'registry_normalized_sha256':hashlib.sha256((source/'cloud/qresearch/registry.py').read_text(encoding='utf-8-sig').encode()).hexdigest()}
(out/'execution.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
