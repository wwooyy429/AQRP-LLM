import hashlib,json,shutil,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent;root=out/'legacy_adapted';root.mkdir(exist_ok=True);records=[]
tasks=[('legacy_adapted_scripts/native_boundaries.py','main'),('legacy_adapted_scripts/compat_scripts/completion_boundaries.py','compat_boundaries'),
    ('legacy_adapted_scripts/compat_scripts/failure_settlement.py','compat_failure'),('legacy_adapted_scripts/crash_boundaries.py','crash_addendum'),
    ('recovery_adapted_scripts/independent_recovery.py','recovery')]
for script,target in tasks:
    dest=root/target;dest.mkdir(exist_ok=True)
    if target=='recovery':shutil.copy2(out/'recovery_adapted_scripts/direct_freeze_entry.py',dest/'direct_freeze_entry.py')
    argv=[sys.executable,'-B',str(out/script),'--source',str(out.parent/'source'),'--out',str(dest)]
    r=subprocess.run(argv,cwd=out,capture_output=True)
    (dest/'first.stdout').write_bytes(r.stdout);(dest/'first.stderr').write_bytes(r.stderr)
    record={'script':script,'target':target,'argv':argv,'cwd':str(out),'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),
        'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()}
    (dest/'execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8');records.append(record)
    print(json.dumps(record),flush=True);print(r.stdout.decode('utf-8',errors='replace')[-800:],flush=True);print(r.stderr.decode('utf-8',errors='replace')[-2200:],flush=True)
(root/'executions.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
sys.exit(0 if all(row['exit_code']==0 for row in records) else 1)
