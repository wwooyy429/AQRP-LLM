from pathlib import Path
import hashlib,json,os,subprocess,time
R=Path(__file__).resolve().parent;G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo');W=R/'git_worktree';PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe';C='2f5591e28c0748ac42caeae7bbf3977141d031cb'
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',PYTHONUTF8='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
for key in ['GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES','PYTHONOPTIMIZE']:env.pop(key,None)
records=[]
def run(label,argv,cwd=R):
 t=time.monotonic();p=subprocess.run(list(map(str,argv)),cwd=cwd,env=env,capture_output=True)
 (R/(label+'.stdout')).write_bytes(p.stdout);(R/(label+'.stderr')).write_bytes(p.stderr)
 row={'label':label,'command':list(map(str,argv)),'cwd':str(cwd),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};records.append(row);(R/'root_execution_records.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8');print(json.dumps(row),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-1200:],flush=True);return p
assert not W.exists()
assert run('clone_private_git',['git','clone','--quiet','--no-hardlinks','--no-checkout','--local',G,W]).returncode==0
assert run('checkout_private_git',['git','-c','core.autocrlf=false','-c','core.eol=lf','checkout','--quiet','--detach',C],W).returncode==0
fixed=json.loads((R/'source_git_manifest.json').read_bytes())['candidate']['files']
assert {p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in W.rglob('*')if p.is_file()and'.git'not in p.relative_to(W).parts}==fixed
run('build_git_protection',[PY,'-B','audit/review_packages/deployment-eof-v2/build_git_protection.py','--repository','.', '--output','audit/review_packages/deployment-eof-v2/protected_git_baseline.json'],W)
run('developer_audit11',[PY,'-B','audit/review_packages/wr28/test_git_protection.py','-q'],W)
run('developer_end_to_end_full',[PY,'-B','audit/review_packages/wr28/verify_wr28_end_to_end.py','--commit',C,'--evidence-dir',R/'end_to_end','--full-verify'],W)
run('developer_verify_import',[PY,'-B','audit/reviews/20261028-4a42c18-eofv2/verify_import.py'],W)
after={p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in W.rglob('*')if p.is_file()and'.git'not in p.relative_to(W).parts}
assert after==fixed,'Private fixed checkout bytes changed'
(R/'private_checkout_guard.json').write_text(json.dumps({'fixed_commit':C,'all6379_raw_Git_files_unchanged':True,'checkout_mode':'core.autocrlf=false/core.eol=lf'},indent=2)+'\n',encoding='utf-8')
raise SystemExit(int(any(x['exit_code']for x in records)))
