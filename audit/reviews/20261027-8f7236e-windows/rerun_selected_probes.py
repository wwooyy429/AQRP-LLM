from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;OUT=R/'root_confirmation_complete';OUT.mkdir(exist_ok=False)
records=[]
def run(label,args,expected):
    cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic()
    p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (OUT/(label+'.stdout.txt')).write_bytes(p.stdout);(OUT/(label+'.stderr.txt')).write_bytes(p.stderr)
    row={'label':label,'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_product_counterexample_exit':expected,'seconds':time.monotonic()-t}
    records.append(row);(OUT/'execution_records.json').write_bytes(json.dumps(records,indent=2).encode())
    print(json.dumps(row),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-1400:],flush=True)
    assert p.returncode==expected
schema=next((R/'source/audit/reviews').rglob('official_mcp_schema_2025-11-25.json'))
assert hashlib.sha256(schema.read_bytes()).hexdigest()=='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7'
frac=R/'fraction_replay/complete_fixture_results';frac.mkdir(exist_ok=False);shutil.copyfile(schema,frac/schema.name)
helper=R/'fraction_replay/independent_fractional_harness.py'
assert hashlib.sha256(helper.read_bytes()).hexdigest()=='d6f469e02b6e8129af4ecdaf679e7d877dee5959edc13f3f68a991777a19cf25'
shutil.copyfile(helper,frac/helper.name)
run('fraction_fixture_corrected',[R/'fraction_replay/independent_fraction_boundaries.py','--source',R/'source','--out',frac],0)
run('wr16_minimal',[R/'admission_agent/minimal_joint_registry.py',R/'source'],1)
run('wr17_minimal',[R/'admission_agent/minimal_pending_freeze.py',R/'source',OUT/'wr17_case'],1)
