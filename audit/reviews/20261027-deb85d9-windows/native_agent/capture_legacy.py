import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent;records=[]
for name,target in [('native_boundaries.py','main'),('compat_scripts/completion_boundaries.py','compat_boundaries'),
                    ('compat_scripts/failure_settlement.py','compat_failure'),('crash_boundaries.py','crash_addendum')]:
    dest=out/target;dest.mkdir(exist_ok=True)
    argv=[sys.executable,'-B',str(out/'legacy_scripts'/name),'--source',str(out.parent/'source'),'--out',str(dest)]
    result=subprocess.run(argv,cwd=out,capture_output=True)
    (dest/'first.stdout').write_bytes(result.stdout);(dest/'first.stderr').write_bytes(result.stderr)
    record={'argv':argv,'cwd':str(out),'exit_code':result.returncode,'stdout_bytes':len(result.stdout),'stderr_bytes':len(result.stderr),
        'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr).hexdigest()}
    (dest/'execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8');records.append(record)
    print(json.dumps(record),flush=True);print(result.stdout.decode('utf-8',errors='replace')[-1400:],flush=True);print(result.stderr.decode('utf-8',errors='replace')[-2500:],flush=True)
(out/'legacy_execution.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
sys.exit(0 if all(item['exit_code']==0 for item in records) else 1)
