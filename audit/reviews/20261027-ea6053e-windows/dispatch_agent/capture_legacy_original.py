import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent;destroot=out/'legacy_original';destroot.mkdir(exist_ok=True);records=[]
for name,target in [('legacy_scripts/native_boundaries.py','main'),('legacy_scripts/compat_scripts/completion_boundaries.py','compat_boundaries'),
    ('legacy_scripts/compat_scripts/failure_settlement.py','compat_failure'),('legacy_scripts/crash_boundaries.py','crash_addendum'),
    ('research_failure_original.py','research')]:
    dest=destroot/target;dest.mkdir(exist_ok=True)
    argv=[sys.executable,'-B',str(out/name),'--source',str(out.parent/'source'),'--out',str(dest)]
    r=subprocess.run(argv,cwd=out,capture_output=True)
    (dest/'first.stdout').write_bytes(r.stdout);(dest/'first.stderr').write_bytes(r.stderr)
    row={'script':name,'target':target,'argv':argv,'cwd':str(out),'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),
        'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()}
    (dest/'execution.json').write_text(json.dumps(row,indent=2),encoding='utf-8');records.append(row)
    print(json.dumps(row),flush=True);print(r.stdout.decode('utf-8',errors='replace')[-900:],flush=True);print(r.stderr.decode('utf-8',errors='replace')[-1800:],flush=True)
(destroot/'executions.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
# Preserve observations; nonzero children are expected to be diagnosed, not hidden.
sys.exit(0)
