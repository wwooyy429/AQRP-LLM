from pathlib import Path
import hashlib,json,os,subprocess,time
O=Path(__file__).parent;R=O.parent;PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe';env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
jobs=[('minimal_wr25', [PY,'-B',str(O/'minimal_wr25.py'),'--output',str(O/'minimal_wr25_first_result.json')]),('future_current',[PY,'-B',str(O/'first_future_current_probe.py')])]
old_script=O/'baseline_original/first_unmapped_classification_probe.py';old_script.write_bytes((O/'first_unmapped_classification_probe.py').read_bytes());jobs.append(('unmapped_old_ea',[PY,'-B',str(O/'launch_original.py'),r'C:\Users\11638\.codex\tmp\aqrp-review-ea6053e-20261027\source',str(old_script)]))
for stem,cmd in jobs:
 t=time.perf_counter();r=subprocess.run(cmd,cwd=O,env=env,capture_output=True)
 for suffix,b in [('stdout',r.stdout),('stderr',r.stderr)]:(O/(stem+'_first.'+suffix)).write_bytes(b)
 e={'command':cmd,'cwd':str(O),'exit_code':r.returncode,'seconds':time.perf_counter()-t,'stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest(),'actually_executed':True,'new_market_QC_model_or_authoritative_budget_calls':0,'old_embedded_fixed_commit_is_literal_not_source_binding':stem=='unmapped_old_ea'}
 (O/(stem+'_execution.json')).write_bytes((json.dumps(e,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'stem':stem,'exit':r.returncode,'seconds':e['seconds']}),flush=True)
