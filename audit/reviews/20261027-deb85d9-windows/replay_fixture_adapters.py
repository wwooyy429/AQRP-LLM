from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-66ff72f-20261027/source')
W=R/'collection_historical_fixture';W.mkdir(exist_ok=False)
shutil.copytree(R/'source',W/'source')
# Keep all current source/config except the explicitly separate historical ledger/usage fixture.
runtime=W/'source/audit/runtime';archived=OLD/'audit/runtime'
for p in list(runtime.rglob('*')):
    if p.is_file()and not(archived/p.relative_to(runtime)).exists():p.unlink()
for p in archived.rglob('*'):
    if p.is_file():q=runtime/p.relative_to(archived);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
(W/'source/config/budget.json').write_bytes((OLD/'config/budget.json').read_bytes())
folder=W/'collection_recovery_replay';folder.mkdir()
original=R/'collection_recovery_replay/independent_recovery.py';shutil.copyfile(original,folder/original.name)
wrapper=R/'joint_worker_replay/replay_historical_budget.py'
wrapper.write_bytes(('''from pathlib import Path
import json,runpy
import independent_market_helper as h
h.BUDGET=json.loads(Path(r"'''+str(OLD/'config/budget.json')+'''").read_bytes())
runpy.run_path(str(Path(__file__).parent/'independent_joint_worker.py'),run_name='__main__')
''').encode())
commands=[('joint_worker_historical_budget',[wrapper,'--source',R/'source','--out',R/'joint_worker_replay/historical_budget_results']),
 ('collection_historical_ledger',[folder/original.name])]
records=[]
for name,args in commands:
    cmd=[sys.executable,'-B',*map(str,args)];start=time.monotonic()
    p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (R/(name+'.stdout')).write_bytes(p.stdout);(R/(name+'.stderr')).write_bytes(p.stderr)
    rec={'label':name,'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-start,
      'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),
      'fixture_note':'Current deb production and original assertion bytes; only isolated historical budget/ledger fixture differs. Authoritative17 events untouched.'}
    records.append(rec);(R/'fixture_adapter_execution.json').write_bytes(json.dumps(records,indent=2).encode());print(json.dumps(rec),flush=True)
assert original.read_bytes()==(folder/original.name).read_bytes()
original_files={p.relative_to(R/'source').as_posix():p.read_bytes()for p in(R/'source').rglob('*')if p.is_file()}
changed=[name for name,data in original_files.items()if(W/'source'/name).is_file()and(W/'source'/name).read_bytes()!=data]
(R/'fixture_adapter_description.json').write_bytes(json.dumps({'unchanged_test_bytes':True,'original_test_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'derived_source_changed_paths':changed,'changes_are_only_historical_budget_and_runtime':all(p=='config/budget.json'or p.startswith('audit/runtime/')for p in changed),'actual_source_directory_unchanged':True,'old_fixture_root':str(OLD)},indent=2).encode())
sys.exit(int(any(x['exit_code']for x in records)))
