from pathlib import Path
import hashlib,json,os,subprocess
OUT=Path(__file__).resolve().parent
cmd=[r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe','-B',str(OUT/'supplemental_checks.py')]
r=subprocess.run(cmd,cwd=OUT,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
for stream,data in [('stdout',r.stdout),('stderr',r.stderr)]:(OUT/('supplement_first.'+stream+'.txt')).write_bytes(data)
log=json.loads((OUT/'command_log.json').read_text(encoding='utf-8-sig'))
log.append({'label':'supplement_first','command':cmd,'cwd':str(OUT),'exit_code':r.returncode,'stdout':'supplement_first.stdout.txt','stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr':'supplement_first.stderr.txt','stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest()})
(OUT/'command_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(r.stdout.decode('utf-8',errors='replace'));print(r.stderr.decode('utf-8',errors='replace'));raise SystemExit(r.returncode)
