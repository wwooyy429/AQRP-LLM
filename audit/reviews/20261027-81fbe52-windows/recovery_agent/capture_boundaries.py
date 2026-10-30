import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent;result_dir=out/'boundaries';result_dir.mkdir(exist_ok=True)
argv=[sys.executable,'-B',str(out/'completion_boundaries.py'),'--source',str(out.parent/'source'),'--out',str(result_dir)]
result=subprocess.run(argv,cwd=out,capture_output=True)
(result_dir/'first.stdout').write_bytes(result.stdout);(result_dir/'first.stderr').write_bytes(result.stderr)
record={'argv':argv,'cwd':str(out),'exit_code':result.returncode,'stdout_bytes':len(result.stdout),'stderr_bytes':len(result.stderr),
    'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr).hexdigest()}
(result_dir/'execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));print(result.stdout.decode('utf-8',errors='replace')[-18000:]);print(result.stderr.decode('utf-8',errors='replace')[-6000:])
sys.exit(result.returncode)
