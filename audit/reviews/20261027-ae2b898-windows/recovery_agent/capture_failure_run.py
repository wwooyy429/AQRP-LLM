import hashlib,json,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
argv=[sys.executable,'-B',str(OUT/'failure_settlement.py'),'--source',str(OUT.parent/'source'),'--out',str(OUT)]
r=subprocess.run(argv,cwd=OUT,capture_output=True)
(OUT/'failure_settlement.stdout').write_bytes(r.stdout);(OUT/'failure_settlement.stderr').write_bytes(r.stderr)
record={'argv':argv,'cwd':str(OUT),'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),
    'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()}
(OUT/'failure_execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));print(r.stdout.decode('utf-8',errors='replace')[-10000:]);print(r.stderr.decode('utf-8',errors='replace')[-6000:])
sys.exit(r.returncode)
