import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent;dest=out/'prepare_crash_first';dest.mkdir(exist_ok=True)
argv=[sys.executable,'-B',str(out/'minimal_prepare_entry_crash.py'),'--source',str(out.parent/'source'),'--out',str(dest)]
r=subprocess.run(argv,cwd=out,capture_output=True)
(dest/'first.stdout').write_bytes(r.stdout);(dest/'first.stderr').write_bytes(r.stderr)
record={'argv':argv,'cwd':str(out),'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),
 'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()}
(dest/'execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));print(r.stdout.decode('utf-8',errors='replace')[-12000:]);print(r.stderr.decode('utf-8',errors='replace')[-2500:])
sys.exit(r.returncode)
