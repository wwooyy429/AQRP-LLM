from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
R=Path(__file__).resolve().parent;S=R/'source';W=R/'verification_source'
PY=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe')
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
shutil.copytree(S,W)
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
records=[]
def run(label,args,extra_env=None):
 e=dict(env);e.update(extra_env or {});argv=[str(PY),'-B',*args];t=time.monotonic()
 p=subprocess.run(argv,cwd=W,env=e,capture_output=True)
 (R/(label+'.stdout')).write_bytes(p.stdout);(R/(label+'.stderr')).write_bytes(p.stderr)
 rec=dict(label=label,command=argv,cwd=str(W),exit_code=p.returncode,seconds=time.monotonic()-t,stdout_sha256=hashlib.sha256(p.stdout).hexdigest(),stderr_sha256=hashlib.sha256(p.stderr).hexdigest(),environment_override=extra_env or {})
 records.append(rec);(R/'root_execution_records.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(rec),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-700:],flush=True)
 return p
run('repository_verify',['tools/stages.py','verify'])
shutil.copyfile(W/'audit/stage_verification.json',R/'repository_verification.json')
for n in ['test_independent_normal_gate.py','test_independent_occurrences.py']:
 run(n,['audit/review_packages/normal004/'+n])
run('developer_round_checker',['audit/review_packages/normal004/verify_round_evidence.py'],dict(GIT_DIR=str(G/'.git'),GIT_WORK_TREE=str(W)))
run('build',['tools/research.py','build'])
raise SystemExit(int(any(x['exit_code']for x in records)))
