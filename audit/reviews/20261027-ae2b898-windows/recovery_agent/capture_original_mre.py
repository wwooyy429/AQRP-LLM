import hashlib,json,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
script=OUT/'original_minimal_pending_freeze.py'
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-8f7236e-20261027\admission_agent\minimal_pending_freeze.py')
assert script.read_bytes()==old.read_bytes()
argv=[sys.executable,'-B',str(script),str(OUT.parent/'source'),str(OUT/'original_mre')]
r=subprocess.run(argv,cwd=OUT,capture_output=True)
(OUT/'original_mre.stdout').write_bytes(r.stdout);(OUT/'original_mre.stderr').write_bytes(r.stderr)
value={'argv':argv,'cwd':str(OUT),'exit_code':r.returncode,'script_raw_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
    'byte_identical_to_original':True,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),
    'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()}
(OUT/'original_mre_execution.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
print(json.dumps(value));print(r.stdout.decode('utf-8',errors='replace')[-3500:]);print(r.stderr.decode('utf-8',errors='replace')[-3500:])
sys.exit(r.returncode)
