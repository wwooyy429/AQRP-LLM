import hashlib,json,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
argv=[sys.executable,'-B',str(OUT/'independent_recovery.py'),'--source',str(OUT.parent/'source'),'--out',str(OUT)]
r=subprocess.run(argv,cwd=OUT,capture_output=True)
(OUT/'first_run.stdout').write_bytes(r.stdout);(OUT/'first_run.stderr').write_bytes(r.stderr)
record={'argv':argv,'cwd':str(OUT),'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),
    'stderr_sha256':hashlib.sha256(r.stderr).hexdigest(),'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr)}
(OUT/'first_execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));print(r.stdout.decode('utf-8',errors='replace')[-16000:]);print(r.stderr.decode('utf-8',errors='replace')[-4000:])
sys.exit(r.returncode)
