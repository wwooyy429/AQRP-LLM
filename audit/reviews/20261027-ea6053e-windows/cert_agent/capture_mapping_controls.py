from pathlib import Path
import hashlib,json,os,subprocess,time
O=Path(__file__).parent;cmd=[r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe','-B',str(O/'mapping_gap_controls.py')];t=time.perf_counter();r=subprocess.run(cmd,cwd=O,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),capture_output=True)
for name,raw in [('mapping_controls_first.stdout',r.stdout),('mapping_controls_first.stderr',r.stderr)]:(O/name).write_bytes(raw)
(O/'mapping_controls_execution.json').write_text(json.dumps({'command':cmd,'cwd':str(O),'exit_code':r.returncode,'seconds':time.perf_counter()-t,'stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest(),'actually_executed':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(r.stdout.decode('utf-8'));raise SystemExit(r.returncode)
