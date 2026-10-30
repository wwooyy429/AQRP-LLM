import os,json,hashlib,shutil,subprocess,time,sys
from pathlib import Path
R=Path(__file__).resolve().parent; OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ea6053e-20261027\dispatch_agent'); S=R.parent/'source'
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
records=[]
def execute(script,out,source=S):
    out.mkdir(parents=True,exist_ok=True);argv=[sys.executable,'-B',str(script),'--source',str(source),'--out',str(out)]
    t=time.time();p=subprocess.run(argv,cwd=R,env=ENV,capture_output=True)
    (out/'first.stdout').write_bytes(p.stdout);(out/'first.stderr').write_bytes(p.stderr)
    row={'script':str(script.relative_to(R)),'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'source':str(source),'argv':argv,'exit_code':p.returncode,'elapsed_seconds':time.time()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
    (out/'execution.json').write_bytes(json.dumps(row,indent=2).encode());records.append(row);(R/'execution_records.json').write_bytes(json.dumps(records,indent=2).encode());print(json.dumps(row),flush=True)
for name in ('legacy_adapted_scripts','recovery_adapted_scripts'):
    shutil.copytree(OLD/name,R/name)
shutil.copy2(OLD/'legacy_adapted_scripts/independent_recovery_support.py',R/'independent_recovery_support.py')
shutil.copy2(OLD/'research_failure_original.py',R/'research_failure_original.py')
for src,dest in [('legacy_adapted_scripts/native_boundaries.py','legacy/main'),('legacy_adapted_scripts/compat_scripts/completion_boundaries.py','legacy/compat'),('legacy_adapted_scripts/compat_scripts/failure_settlement.py','legacy/failure'),('legacy_adapted_scripts/crash_boundaries.py','legacy/crash'),('recovery_adapted_scripts/independent_recovery.py','legacy/recovery'),('research_failure_original.py','research_failure')]:
    target=R/dest
    if dest=='legacy/recovery':
        target.mkdir(parents=True,exist_ok=True);shutil.copy2(R/'recovery_adapted_scripts/direct_freeze_entry.py',target/'direct_freeze_entry.py')
    # Native Research suite pins index0 itself; it requires original helper's unbound setup.
    if src=='research_failure_original.py':shutil.copy2(OLD/'independent_recovery_support.py',R/'independent_recovery_support.py')
    execute(R/src,target)
print(json.dumps({'all_exit_zero':all(x['exit_code']==0 for x in records),'count':len(records)}))
