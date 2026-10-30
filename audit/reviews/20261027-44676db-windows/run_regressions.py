from pathlib import Path
import concurrent.futures,hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;O=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-deb85d9-20261027');H=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-66ff72f-20261027/source')
copies={'collection_recovery_replay':['independent_recovery.py'],'fraction_replay':['independent_fractional_harness.py','independent_fraction_boundaries.py'],'joint_worker_replay':['independent_joint_worker.py','independent_market_helper.py'],'admission_agent':['independent_wr16_boundaries.py','independent_wr18_contract_corrected.py','quick_joint_probes.py'],'recovery_agent':['independent_recovery.py','independent_recovery_support.py','direct_freeze_entry.py']}
bindings=[]
for folder,names in copies.items():
    dest=R/folder;dest.mkdir(exist_ok=False)
    for name in names:
        source=O/folder/name;target=dest/name;shutil.copyfile(source,target);assert source.read_bytes()==target.read_bytes()
        bindings.append({'original':str(source),'copy':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
(R/'regression_script_bindings.json').write_bytes(json.dumps(bindings,indent=2).encode())
W=R/'historical_fixture';W.mkdir()
S=R/'source'
for item in S.iterdir():
    target=W/'source'/item.name
    if item.is_dir():
        if item.name=='audit':shutil.copytree(item,target,ignore=lambda folder,names:['runtime']if Path(folder)==S/'audit'else[])
        else:shutil.copytree(item,target)
    else:target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(item,target)
shutil.copytree(H/'audit/runtime',W/'source/audit/runtime');shutil.copyfile(H/'config/budget.json',W/'source/config/budget.json')
f=W/'collection_recovery_replay';f.mkdir();shutil.copyfile(R/'collection_recovery_replay/independent_recovery.py',f/'independent_recovery.py')
wrapper=R/'joint_worker_replay/historical_budget.py';wrapper.write_bytes(('from pathlib import Path\nimport json,runpy\nimport independent_market_helper as h\nh.BUDGET=json.loads(Path(r"'+str(H/'config/budget.json')+'").read_bytes())\nrunpy.run_path(str(Path(__file__).parent/"independent_joint_worker.py"),run_name="__main__")\n').encode())
out=R/'fraction_replay/results';out.mkdir();schema=next((S/'audit/reviews').rglob('official_mcp_schema_2025-11-25.json'));assert hashlib.sha256(schema.read_bytes()).hexdigest()=='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7';shutil.copyfile(schema,out/schema.name);shutil.copyfile(R/'fraction_replay/independent_fractional_harness.py',out/'independent_fractional_harness.py')
out2=R/'recovery_agent/results_original';out2.mkdir();shutil.copyfile(R/'recovery_agent/direct_freeze_entry.py',out2/'direct_freeze_entry.py')
commands=[('collection_recovery',[f/'independent_recovery.py']),('joint_worker',[wrapper,'--source',S,'--out',R/'joint_worker_replay/results']),('fraction',[R/'fraction_replay/independent_fraction_boundaries.py','--source',S,'--out',out])]
def run(spec):
    label,args=spec;cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic()
    p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (R/(label+'.stdout')).write_bytes(p.stdout);(R/(label+'.stderr')).write_bytes(p.stderr)
    record={'label':label,'actual_commit':'44676db609b3b7c2175fa7fa4f19c8ccf8165458','command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};print(json.dumps(record),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-600:],flush=True);return record
records=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
    for record in pool.map(run,commands):records.append(record);(R/'regression_execution_records.json').write_bytes(json.dumps(records,indent=2).encode())
for spec in [('wr16',[R/'admission_agent/independent_wr16_boundaries.py']),('wr18',[R/'admission_agent/independent_wr18_contract_corrected.py'])]:records.append(run(spec));(R/'regression_execution_records.json').write_bytes(json.dumps(records,indent=2).encode())
old={p.relative_to(S).as_posix():p.read_bytes()for p in S.rglob('*')if p.is_file()};new={p.relative_to(W/'source').as_posix():p.read_bytes()for p in(W/'source').rglob('*')if p.is_file()};changed=[p for p in set(old)|set(new)if old.get(p)!=new.get(p)]
assert all(p=='config/budget.json'or p.startswith('audit/runtime/')for p in changed)
(R/'historical_fixture_description.json').write_bytes(json.dumps({'current_production_bytes_preserved':True,'original_assertions_unchanged':True,'only_changed_paths':sorted(changed),'reason':'Previously recognized historical13-event and9-Research budget fixtures; actual17-event authority remains stopped and unchanged.'},indent=2).encode())
sys.exit(int(any(x['exit_code']for x in records)))
