import os,json,hashlib,shutil,subprocess,time,sys
from pathlib import Path
R=Path(__file__).resolve().parent; OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ea6053e-20261027'); records=[]
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for label,source in [('baseline',OLD/'source'),('candidate',R.parent/'source')]:
    d=R/'original_mre'/label;d.mkdir(parents=True,exist_ok=True)
    for name in ('minimal_prepare_entry_crash.py','independent_recovery_support.py'):shutil.copy2(OLD/'dispatch_agent'/name,d/name)
    argv=[sys.executable,'-B',str(d/'minimal_prepare_entry_crash.py'),'--source',str(source),'--out',str(d/'results')]
    t=time.time();p=subprocess.run(argv,cwd=d,env=ENV,capture_output=True);(d/'first.stdout').write_bytes(p.stdout);(d/'first.stderr').write_bytes(p.stderr)
    row={'case':label,'source':str(source),'argv':argv,'exit_code':p.returncode,'elapsed_seconds':time.time()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'script_sha256':hashlib.sha256((d/'minimal_prepare_entry_crash.py').read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256((d/'independent_recovery_support.py').read_bytes()).hexdigest()}
    records.append(row);(d/'execution.json').write_bytes(json.dumps(row,indent=2).encode());(R/'original_mre_execution.json').write_bytes(json.dumps(records,indent=2).encode());print(json.dumps(row),flush=True)
