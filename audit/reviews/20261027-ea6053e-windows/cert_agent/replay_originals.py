from pathlib import Path
import hashlib,json,os,subprocess,time
O=Path(__file__).resolve().parent;R=O.parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-deb85d9-20261027')
PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
def sha(b):return hashlib.sha256(b).hexdigest()
commands=[];copies=[]
for label,root in [('baseline',OLD),('candidate',R)]:
 d=O/(label+'_original');d.mkdir(exist_ok=False)
 for name in ('cert_fixture.py','minimal_wr20.py','independent_certification.py'):
  raw=(OLD/'cert_agent'/name).read_bytes();(d/name).write_bytes(raw)
  copies.append({'version':label,'file':name,'raw_sha256':sha(raw),'byte_identical':raw==(d/name).read_bytes()})
 for name in ('minimal_wr20.py','independent_certification.py'):
  cmd=[PY,'-B',str(O/'launch_original.py'),str(root/'source'),str(d/name)]
  if name=='minimal_wr20.py':cmd+=['--output',str(d/'minimal_first_result.json')]
  t=time.perf_counter();r=subprocess.run(cmd,cwd=d,env=env,capture_output=True)
  stem='minimal' if name.startswith('minimal') else 'suite'
  (d/(stem+'_first.stdout')).write_bytes(r.stdout);(d/(stem+'_first.stderr')).write_bytes(r.stderr)
  execution={'version':label,'bound_fixed_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8' if label=='baseline' else 'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','command':cmd,'cwd':str(d),'exit_code':r.returncode,'seconds':time.perf_counter()-t,'script_raw_sha256':sha((d/name).read_bytes()),'stdout_raw_sha256':sha(r.stdout),'stderr_raw_sha256':sha(r.stderr),'historical_embedded_fixed_commit_is_original_deb_string':True,'explicit_source_binding_only':True,'assertions_and_original_scripts_unchanged':True}
  (d/(stem+'_execution.json')).write_text(json.dumps(execution,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');commands.append(execution)
  print(json.dumps({'version':label,'script':name,'exit':r.returncode,'seconds':execution['seconds']},ensure_ascii=False),flush=True)
(O/'original_replay_index.json').write_text(json.dumps({'original_bytes':copies,'commands':commands,'wrapper_raw_sha256':sha((O/'launch_original.py').read_bytes()),'source_binding_not_test_or_assertion_adaptation':True,'new_QC_market_model_or_authoritative_budget_calls':0},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
