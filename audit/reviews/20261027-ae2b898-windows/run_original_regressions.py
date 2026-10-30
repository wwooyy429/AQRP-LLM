from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-8f7236e-20261027')
REC=R/'collection_recovery_replay';REC.mkdir(exist_ok=False)
FRAC=R/'fraction_replay';FRAC.mkdir(exist_ok=False)
WORK=R/'joint_worker_replay';WORK.mkdir(exist_ok=False)
PROBE=R/'original_probes';PROBE.mkdir(exist_ok=False)
copies=[(OLD/'recovery_replay/independent_recovery.py',REC/'independent_recovery.py'),
        (OLD/'fraction_replay/independent_fractional_harness.py',FRAC/'independent_fractional_harness.py'),
        (OLD/'fraction_replay/independent_fraction_boundaries.py',FRAC/'independent_fraction_boundaries.py'),
        (OLD/'joint_worker_agent/independent_joint_worker.py',WORK/'independent_joint_worker.py'),
        (OLD/'joint_worker_agent/independent_market_helper.py',WORK/'independent_market_helper.py'),
        (OLD/'admission_agent/minimal_joint_registry.py',PROBE/'minimal_joint_registry.py'),
        (OLD/'admission_agent/minimal_pending_freeze.py',PROBE/'minimal_pending_freeze.py'),
        (OLD/'minimal_boundaries.py',PROBE/'minimal_boundaries.py')]
hashes=[]
for source,target in copies:
    shutil.copyfile(source,target);assert target.read_bytes()==source.read_bytes()
    hashes.append({'source':str(source),'copied':str(target),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
(R/'original_replay_script_bindings.json').write_bytes(json.dumps(hashes,indent=2).encode())
out=FRAC/'results';out.mkdir()
schema=next((R/'source/audit/reviews').rglob('official_mcp_schema_2025-11-25.json'))
assert hashlib.sha256(schema.read_bytes()).hexdigest()=='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7'
shutil.copyfile(schema,out/schema.name);shutil.copyfile(FRAC/'independent_fractional_harness.py',out/'independent_fractional_harness.py')
commands=[
 ('full_mre_registry_baseline',[PROBE/'minimal_joint_registry.py',OLD/'source'],1),
 ('full_mre_registry_candidate',[PROBE/'minimal_joint_registry.py',R/'source'],0),
 ('full_mre_freeze_baseline',[PROBE/'minimal_pending_freeze.py',OLD/'source',PROBE/'baseline_freeze'],1),
 ('full_mre_freeze_candidate',[PROBE/'minimal_pending_freeze.py',R/'source',PROBE/'candidate_freeze'],0),
 ('original_inline_registry',[PROBE/'minimal_boundaries.py',R/'source','registry'],1),
 ('original_inline_freeze',[PROBE/'minimal_boundaries.py',R/'source','freeze'],0),
 ('joint_worker',[WORK/'independent_joint_worker.py','--source',R/'source','--out',WORK/'results'],0),
 ('fraction',[FRAC/'independent_fraction_boundaries.py','--source',R/'source','--out',out],0),
 ('collection_recovery',[REC/'independent_recovery.py'],0)]
records=[]
for label,args,expected in commands:
    cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic()
    p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (R/(label+'.stdout.txt')).write_bytes(p.stdout);(R/(label+'.stderr.txt')).write_bytes(p.stderr)
    row={'label':label,'reviewed_source_commit':'ae2b8985f3799c246e90341370f86d80483f63ed','source_directory':str(OLD/'source' if label.endswith('baseline') else R/'source'),
         'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_exit_code':expected,'seconds':time.monotonic()-t,
         'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
    records.append(row);(R/'original_regression_records.json').write_bytes(json.dumps(records,indent=2).encode())
    print(json.dumps(row),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-1000:],flush=True)
raise SystemExit(int(any(x['exit_code']!=x['expected_exit_code'] for x in records)))
