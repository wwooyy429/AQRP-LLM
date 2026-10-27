from pathlib import Path
import hashlib,json,os,subprocess
O=Path(__file__).resolve().parent;cmd=[r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe','-B',str(O/'independent_certification.py')]
r=subprocess.run(cmd,cwd=O,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),capture_output=True)
for n,b in [('suite_first.stdout',r.stdout),('suite_first.stderr',r.stderr)]:(O/n).write_bytes(b)
(O/'suite_execution.json').write_text(json.dumps({'command':cmd,'cwd':str(O),'exit_code':r.returncode,'stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest()},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(r.stdout.decode('utf-8',errors='replace'));print(r.stderr.decode('utf-8',errors='replace'));raise SystemExit(r.returncode)
