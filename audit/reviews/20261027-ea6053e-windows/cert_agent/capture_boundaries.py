from pathlib import Path
import hashlib,json,os,subprocess,time
O=Path(__file__).parent;PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe';env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for name,stem,extra in [('minimal_wr22.py','minimal_wr22',['--output',str(O/'minimal_wr22_first_result.json')]),('independent_fix_boundaries.py','boundaries',[])]:
 cmd=[PY,'-B',str(O/name)]+extra;t=time.perf_counter();r=subprocess.run(cmd,cwd=O,env=env,capture_output=True)
 for suffix,b in [('stdout',r.stdout),('stderr',r.stderr)]:(O/(stem+'_first.'+suffix)).write_bytes(b)
 execution={'command':cmd,'cwd':str(O),'exit_code':r.returncode,'seconds':time.perf_counter()-t,'stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest(),'script_raw_sha256':hashlib.sha256((O/name).read_bytes()).hexdigest(),'actually_executed':True,'synthetic_memory_only':True}
 (O/(stem+'_execution.json')).write_text(json.dumps(execution,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'script':name,'exit':r.returncode,'seconds':execution['seconds']}),flush=True)
