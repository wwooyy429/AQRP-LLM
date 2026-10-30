from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,json,os,subprocess,time
O=Path(__file__).parent;PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe';env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
jobs=[('minimal_wr26',[PY,'-B',str(O/'minimal_wr26.py'),'--output',str(O/'minimal_wr26_first_result.json')]),('history',[PY,'-B',str(O/'independent_history_boundaries.py')])]
def work(job):
 stem,cmd=job;t=time.perf_counter();r=subprocess.run(cmd,cwd=O,env=env,capture_output=True)
 for suffix,b in [('stdout',r.stdout),('stderr',r.stderr)]:(O/(stem+'_first.'+suffix)).write_bytes(b)
 e={'command':cmd,'cwd':str(O),'exit_code':r.returncode,'seconds':time.perf_counter()-t,'stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest(),'actually_executed':True,'new_market_QC_model_or_authoritative_budget_calls':0}
 (O/(stem+'_execution.json')).write_bytes((json.dumps(e,ensure_ascii=False,indent=2)+'\n').encode());return {'stem':stem,'exit_code':r.returncode,'seconds':e['seconds']}
with ThreadPoolExecutor(max_workers=2) as pool:
 for f in as_completed([pool.submit(work,j) for j in jobs]):print(json.dumps(f.result()),flush=True)
