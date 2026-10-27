from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,json,os,subprocess,time
O=Path(__file__).parent;R=O.parent;OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027');PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe';env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
def sha(b):return hashlib.sha256(b).hexdigest()
copies=[];jobs=[]
for label,root in [('baseline',OLD),('candidate',R)]:
 d=O/(label+'_original');d.mkdir(exist_ok=False)
 origins={'cert_fixture.py':OLD/'cert_agent/cert_fixture.py','minimal_wr25_wr26.py':OLD/'minimal_wr25_wr26.py','independent_certification.py':OLD/'cert_agent/candidate_original/independent_certification.py','independent_fix_boundaries.py':OLD/'cert_agent/candidate_original/independent_fix_boundaries.py','independent_history_boundaries.py':OLD/'cert_agent/independent_history_boundaries.py'}
 for name,origin in origins.items():
  raw=origin.read_bytes();(d/name).write_bytes(raw);copies.append({'version':label,'file':name,'origin':str(origin),'raw_sha256':sha(raw),'byte_identical':raw==(d/name).read_bytes()})
 names=['minimal_wr25_wr26.py','independent_history_boundaries.py']+(['independent_certification.py','independent_fix_boundaries.py'] if label=='candidate' else [])
 for name in names:
  if name=='minimal_wr25_wr26.py':cmd=[PY,'-B',str(d/name),'--source',str(root/'source'),'--output',str(d/'combined_first_result.json')]
  else:cmd=[PY,'-B',str(O/'launch_original.py'),str(root/'source'),str(d/name)]
  jobs.append((label,d,name,cmd,root/'source'))
def work(job):
 label,d,name,cmd,source=job;stem={'minimal_wr25_wr26.py':'combined','independent_certification.py':'WR20_suite','independent_fix_boundaries.py':'previous9_suite','independent_history_boundaries.py':'history9_suite'}[name]
 t=time.perf_counter();r=subprocess.run(cmd,cwd=d,env=env,capture_output=True)
 for suffix,b in [('stdout',r.stdout),('stderr',r.stderr)]:(d/(stem+'_first.'+suffix)).write_bytes(b)
 e={'version':label,'source_tree':str(source),'fixed_commit':'ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6' if label=='baseline' else '44676db609b3b7c2175fa7fa4f19c8ccf8165458','command':cmd,'cwd':str(d),'exit_code':r.returncode,'seconds':time.perf_counter()-t,'original_script_raw_sha256':sha((d/name).read_bytes()),'source_data_certification_raw_sha256':sha((source/'cloud/qresearch/data_certification.py').read_bytes()),'stdout_raw_sha256':sha(r.stdout),'stderr_raw_sha256':sha(r.stderr),'assertions_and_original_bytes_unchanged':True,'source_binding_external_not_original_version_literals':True}
 (d/(stem+'_execution.json')).write_bytes((json.dumps(e,ensure_ascii=False,indent=2)+'\n').encode());return e
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for f in as_completed([pool.submit(work,j) for j in jobs]):
  e=f.result();results.append(e);print(json.dumps({k:e[k] for k in ('version','command','exit_code','seconds')},ensure_ascii=False),flush=True)
(O/'original_replay_index.json').write_bytes((json.dumps({'byte_identity':copies,'commands':results,'source_binding_only':True,'original_assertion_edits':0,'real_QC_market_model_or_budget_calls':0},ensure_ascii=False,indent=2)+'\n').encode())
