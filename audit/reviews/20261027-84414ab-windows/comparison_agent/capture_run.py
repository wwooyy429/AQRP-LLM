import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent
argv=[sys.executable,'-B',str(out/'comparison_checks.py'),'--source',str(out.parent/'source'),
    '--baseline','C:\\Users\\11638\\.codex\\tmp\\aqrp-review-81fbe52-20261027\\source']
r=subprocess.run(argv,cwd=out,capture_output=True)
(out/'first.stdout').write_bytes(r.stdout);(out/'first.stderr').write_bytes(r.stderr)
record={'argv':argv,'cwd':str(out),'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),
    'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()}
(out/'execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));print(r.stdout.decode('utf-8',errors='replace')[-14000:]);print(r.stderr.decode('utf-8',errors='replace')[-5000:])
sys.exit(r.returncode)
