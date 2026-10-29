from pathlib import Path
import json,hashlib,subprocess,sys,time,os,difflib
O=Path(__file__).resolve().parent;W=O/'replay_context';S=W/'source'
original=W/'carriers_original/independent_carrier_boundaries_corrected.py'
old=original.read_text(encoding='utf-8')
before="BUDGET=json.loads((ROOT/'config/budget.json').read_text(encoding='utf-8'))"
after="BUDGET=json.loads((ROOT/'audit/runtime/registry/baseline.json').read_text(encoding='utf-8'))"
assert old.count(before)==1
new=old.replace(before,after)
folder=W/'carriers_baseline_adapter';folder.mkdir(exist_ok=False);target=folder/original.name;target.write_text(new,encoding='utf-8',newline='\n')
(O/'carrier_budget_adapter.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original',tofile='baseline_adapter')),encoding='utf-8')
cmd=[sys.executable,'-B',str(target),'--source',str(S),'--out',str(O/'carriers_baseline_adapter_results')]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',PYTHONPATH=str(W),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
t=time.monotonic();p=subprocess.run(cmd,cwd=W,capture_output=True,env=env)
(O/'carriers_baseline_adapter.stdout').write_bytes(p.stdout);(O/'carriers_baseline_adapter.stderr').write_bytes(p.stderr)
rec={'actually_executed':True,'command':cmd,'cwd':str(W),'exit_code':p.returncode,'seconds':time.monotonic()-t,'original_raw_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'adapted_raw_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'adaptation':'Only synthetic fresh Memory Registry baseline uses immutable registry/baseline instead of the current lifetime budget projection; current config16 cumulative exceeds active cycle13 capacity without replay. Original44 error records retained. No production changes or assertion changes.','financial_evidence':False}
(O/'carriers_baseline_adapter_execution.json').write_text(json.dumps(rec,indent=2),encoding='utf-8')
print(json.dumps({'exit_code':p.returncode,'seconds':rec['seconds']}));print((p.stdout+p.stderr).decode('utf-8','replace')[-1500:])
