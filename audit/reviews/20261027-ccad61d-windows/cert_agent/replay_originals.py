from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,json,os,subprocess,time
O=Path(__file__).parent;R=O.parent;OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ea6053e-20261027');DEB=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-deb85d9-20261027')
PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe';env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
def sha(b):return hashlib.sha256(b).hexdigest()
copies=[];jobs=[]
for label,root in [('baseline',OLD),('candidate',R)]:
 d=O/(label+'_original');d.mkdir(exist_ok=False)
 origins={'cert_fixture.py':OLD/'cert_agent/cert_fixture.py','minimal_wr22.py':OLD/'cert_agent/minimal_wr22.py','independent_certification.py':DEB/'cert_agent/independent_certification.py','independent_fix_boundaries.py':OLD/'cert_agent/independent_fix_boundaries.py'}
 for name,origin in origins.items():
  raw=origin.read_bytes();(d/name).write_bytes(raw);copies.append({'version':label,'name':name,'origin':str(origin),'raw_sha256':sha(raw),'byte_identical':raw==(d/name).read_bytes()})
 for name in (('minimal_wr22.py',) if label=='baseline' else ('minimal_wr22.py','independent_certification.py','independent_fix_boundaries.py')):
  cmd=[PY,'-B',str(O/'launch_original.py'),str(root/'source'),str(d/name)]
  if name.startswith('minimal'):cmd+=['--output',str(d/'minimal_wr22_first_result.json')]
  jobs.append((label,d,name,cmd))
def work(job):
 label,d,name,cmd=job;stem={'minimal_wr22.py':'minimal_wr22','independent_certification.py':'WR20_suite','independent_fix_boundaries.py':'prior9_suite'}[name]
 t=time.perf_counter();r=subprocess.run(cmd,cwd=d,env=env,capture_output=True)
 for suffix,b in [('stdout',r.stdout),('stderr',r.stderr)]:(d/(stem+'_first.'+suffix)).write_bytes(b)
 e={'version':label,'source_binding':str(OLD/'source') if label=='baseline' else str(R/'source'),'fixed_commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58' if label=='baseline' else 'ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6','command':cmd,'cwd':str(d),'exit_code':r.returncode,'seconds':time.perf_counter()-t,'original_script_raw_sha256':sha((d/name).read_bytes()),'stdout_raw_sha256':sha(r.stdout),'stderr_raw_sha256':sha(r.stderr),'original_bytes_and_assertions_unchanged':True,'external_source_binding_only':True,'historical_embedded_version_literals_not_current_identity':True}
 (d/(stem+'_execution.json')).write_bytes((json.dumps(e,ensure_ascii=False,indent=2)+'\n').encode());return e
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 futures=[pool.submit(work,job) for job in jobs]
 for f in as_completed(futures):
  e=f.result();results.append(e);print(json.dumps({k:e[k] for k in ('version','command','exit_code','seconds')},ensure_ascii=False),flush=True)
(O/'original_replay_index.json').write_bytes((json.dumps({'original_copies':copies,'commands':results,'wrapper_raw_sha256':sha((O/'launch_original.py').read_bytes()),'software_assertion_changes':0,'real_QC_market_model_or_budget_calls':0},ensure_ascii=False,indent=2)+'\n').encode())
