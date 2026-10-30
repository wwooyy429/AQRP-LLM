from pathlib import Path
import hashlib,json,os,subprocess
O=Path(__file__).resolve().parent
cmd=[r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe','-B',str(O/'verify_metadata.py')]
r=subprocess.run(cmd,cwd=O,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
for stream,data in [('stdout',r.stdout),('stderr',r.stderr)]:(O/('corrected.'+stream+'.txt')).write_bytes(data)
record={'command':cmd,'cwd':str(O),'exit_code':r.returncode,'stdout':'corrected.stdout.txt','stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr':'corrected.stderr.txt','stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest()}
(O/'corrected_execution_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(r.stdout.decode('utf-8',errors='replace'));print(r.stderr.decode('utf-8',errors='replace'));raise SystemExit(r.returncode)
