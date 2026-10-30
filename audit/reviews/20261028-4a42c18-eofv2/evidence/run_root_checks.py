from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
R=Path(__file__).resolve().parent;S=R/'source';W=R/'verification_source';PY=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe');G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
shutil.copytree(S,W)
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');records=[]
def run(label,args,extra=None):
 e=dict(env);e.update(extra or {});argv=[str(PY),'-B',*map(str,args)];t=time.monotonic();p=subprocess.run(argv,cwd=W,env=e,capture_output=True)
 (R/(label+'.stdout')).write_bytes(p.stdout);(R/(label+'.stderr')).write_bytes(p.stderr)
 row={'label':label,'command':argv,'cwd':str(W),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'extra_environment':extra or {}}
 records.append(row);(R/'root_execution_records.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8');print(json.dumps(row),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-900:],flush=True)
 return p
before={p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in W.rglob('*')if p.is_file()}
run('build',['tools/research.py','build'])
after={p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in W.rglob('*')if p.is_file()};assert before==after,'Build changed fixed candidate'
(R/'build_byte_identity.json').write_text(json.dumps({'all_fixed_files':len(before),'all_raw_bytes_unchanged':True},indent=2)+'\n',encoding='utf-8')
run('repository_verify',['tools/stages.py','verify']);shutil.copyfile(W/'audit/stage_verification.json',R/'repository_verification.json')
run('developer_auxiliary35',['audit/review_packages/deployment-eof-v2/run_independent_review.py']);shutil.copyfile(W/'audit/review_packages/deployment-eof-v2/independent_review_result.json',R/'developer_auxiliary_result.json')
run('developer_candidate_checker',['audit/review_packages/deployment-eof-v2/verify_candidate.py'],{'GIT_DIR':str(G/'.git'),'GIT_WORK_TREE':str(W)})
for suite in ['compatibility','pearson']:
 run('legacy_'+suite,[S/'docs/review/wr08/replay.py','--source-dir',S,'--output-dir',R/('legacy_'+suite),'--suite',suite])
for suite in ['numeric','atomic']:
 run('legacy_'+suite,[S/'docs/review/wr07/replay.py','--source-dir',S,'--output-dir',R/('legacy_'+suite),'--suite',suite])
run('legacy_adapted56',[S/'docs/review/wr04-wr06/replay.py','--source-dir',S,'--output-dir',R/'legacy_adapted56','--mode','adapted'])
raise SystemExit(int(any(r['exit_code']for r in records)))
