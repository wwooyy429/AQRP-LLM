from pathlib import Path
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
PYTHON=ROOT/'.git/repair-work/venv/Scripts/python.exe'
BASE='f37340415ff080ae44310c912044f683e9986e96'
test_raw=(ROOT/'tests/test_deployment_preflight.py').read_bytes()
(OUT/'final_tests.py').write_bytes(test_raw)
def run(name,cwd,modules):
    argv=[str(PYTHON),'-B','-m','unittest']+modules+['-v']
    result=subprocess.run(argv,cwd=cwd,capture_output=True,env={**os.environ,'PYTHONIOENCODING':'utf-8'},check=False)
    (OUT/(name+'.stdout')).write_bytes(result.stdout)
    (OUT/(name+'.stderr')).write_bytes(result.stderr)
    stderr=result.stderr.decode('utf-8','replace')
    match=re.search(r'Ran (\d+) tests?',stderr)
    record={'command':argv,'working_copy':name,'exit_code':result.returncode,'test_methods':int(match.group(1)) if match else None,
        'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr).hexdigest(),
        'dedicated_test_sha256':hashlib.sha256(test_raw).hexdigest(),'synthetic_only':True,'provider_calls':0,'real_budget_operations':0}
    (OUT/(name+'_execution.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return record
dedicated=run('candidate_final',ROOT,['discover','-s','tests','-p','test_deployment_preflight.py'])
compat=run('compatibility_final',ROOT,['tests.test_wr17_engineering_recovery','tests.test_phase2_joint_boundaries',
    'tests.test_native_runtime_failure','tests.test_native_backtest_rejection','tests.test_stage2_cli'])
archive=subprocess.run(['git','archive','--format=zip',BASE,'cloud','tools','tests','config'],cwd=ROOT,capture_output=True,check=True).stdout
base_root=OUT/'baseline_f373404_final_tests'
base_root.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(archive)) as bundle:bundle.extractall(base_root)
(base_root/'tests/test_deployment_preflight.py').write_bytes(test_raw)
before=run('baseline_same_final_tests',base_root,['discover','-s','tests','-p','test_deployment_preflight.py'])
sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('tools/stage2.py','tools/deployment_preflight.py',
    'tests/test_deployment_preflight.py','tests/test_wr17_engineering_recovery.py','tests/test_phase2_joint_boundaries.py')}
summary={'baseline_commit':BASE,'same_final_dedicated_tests':True,'baseline':before,'candidate':dedicated,'compatibility':compat,
    'source_raw_sha256':sources,'actual_provider_calls':0,'actual_research_executions':0,'actual_lean_submissions':0,
    'actual_budget_or_pointer_or_old_admission_changes':False,
    'fixture_changes':'Two existing fixture modules now create actual synthetic cloud/stub.py matching a real hash; original assertions and quota limits unchanged.',
    'v1_scope':'Strict local implementation manifest/set and frozen plan.deployment_hash; no new mutable full source_manifest recheck.',
    'v2_scope':'Strict implementation contract plus existing stable execution source/catalog identities retained.',
    'historical_worker_root_cause_proven':False,'worker_source_verified':False,'cloud_inventory_certified':False}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
