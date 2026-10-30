from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ae2b898-20261027')
folders={n:R/n for n in ['collection_recovery_replay','fraction_replay','joint_worker_replay','original_probes','original_quick_full']}
for p in folders.values():p.mkdir(exist_ok=False)
copies=[('collection_recovery_replay/independent_recovery.py','collection_recovery_replay/independent_recovery.py'),
 ('fraction_replay/independent_fractional_harness.py','fraction_replay/independent_fractional_harness.py'),
 ('fraction_replay/independent_fraction_boundaries.py','fraction_replay/independent_fraction_boundaries.py'),
 ('joint_worker_replay/independent_joint_worker.py','joint_worker_replay/independent_joint_worker.py'),
 ('joint_worker_replay/independent_market_helper.py','joint_worker_replay/independent_market_helper.py'),
 ('root_confirmation/minimal_checked_dependency.py','original_probes/minimal_checked_dependency.py'),
 ('minimal_wr18.py','original_probes/minimal_wr18.py'),
 ('original_quick_full/quick_joint_probes.py','original_quick_full/quick_joint_probes.py')]
bindings=[]
for a,b in copies:
    source=OLD/a;target=R/b;shutil.copyfile(source,target);assert source.read_bytes()==target.read_bytes()
    bindings.append({'original':str(source),'copy':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
(R/'original_script_bindings.json').write_bytes(json.dumps(bindings,indent=2).encode())
out=R/'fraction_replay/results';out.mkdir()
schema=next((R/'source/audit/reviews').rglob('official_mcp_schema_2025-11-25.json'))
assert hashlib.sha256(schema.read_bytes()).hexdigest()=='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7'
shutil.copyfile(schema,out/schema.name);shutil.copyfile(R/'fraction_replay/independent_fractional_harness.py',out/'independent_fractional_harness.py')
commands=[
 ('full_WR18_baseline',[R/'original_probes/minimal_checked_dependency.py',OLD/'source'],1),
 ('full_WR18_candidate',[R/'original_probes/minimal_checked_dependency.py',R/'source'],0),
 ('short_WR18_original',[R/'original_probes/minimal_wr18.py',R/'source'],1),
 ('original_quick',[R/'original_quick_full/quick_joint_probes.py'],0),
 ('joint_worker',[R/'joint_worker_replay/independent_joint_worker.py','--source',R/'source','--out',R/'joint_worker_replay/results'],0),
 ('fraction',[R/'fraction_replay/independent_fraction_boundaries.py','--source',R/'source','--out',out],0),
 ('collection_recovery',[R/'collection_recovery_replay/independent_recovery.py'],0)]
records=[]
for label,args,expected in commands:
    cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic()
    p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (R/(label+'.stdout.txt')).write_bytes(p.stdout);(R/(label+'.stderr.txt')).write_bytes(p.stderr)
    record={'label':label,'reviewed_source_commit':'81fbe5294055423e88ee5aeae48ca6223e7971da',
      'actual_source_directory':str(OLD/'source' if label.endswith('baseline') else R/'source'),
      'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_exit_code':expected,'seconds':time.monotonic()-t,
      'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
    records.append(record);(R/'original_regression_records.json').write_bytes(json.dumps(records,indent=2).encode())
    print(json.dumps(record),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-700:],flush=True)
raise SystemExit(int(any(x['exit_code']!=x['expected_exit_code']for x in records)))
