from pathlib import Path
import concurrent.futures,hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-81fbe52-20261027')
copies={
 'collection_recovery_replay':['independent_recovery.py'],
 'fraction_replay':['independent_fractional_harness.py','independent_fraction_boundaries.py'],
 'joint_worker_replay':['independent_joint_worker.py','independent_market_helper.py'],
 'original_quick_full':['quick_joint_probes.py'],
 'admission_agent':['independent_wr16_boundaries.py','independent_wr18_contract_corrected.py','quick_joint_probes.py'],
 'recovery_agent':['independent_recovery.py','independent_recovery_support.py','direct_freeze_entry.py']}
bindings=[]
for folder,names in copies.items():
    target=R/folder;target.mkdir(exist_ok=False)
    for name in names:
        source=OLD/folder/name;dest=target/name;shutil.copyfile(source,dest)
        assert source.read_bytes()==dest.read_bytes()
        bindings.append({'source':str(source),'copy':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
(R/'additional_script_bindings.json').write_bytes(json.dumps(bindings,indent=2).encode())
out=R/'fraction_replay/results';out.mkdir()
schema=next((R/'source/audit/reviews').rglob('official_mcp_schema_2025-11-25.json'))
assert hashlib.sha256(schema.read_bytes()).hexdigest()=='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7'
shutil.copyfile(schema,out/schema.name)
shutil.copyfile(R/'fraction_replay/independent_fractional_harness.py',out/'independent_fractional_harness.py')
commands=[
 ('collection_recovery',[R/'collection_recovery_replay/independent_recovery.py']),
 ('engineering_recovery',[R/'recovery_agent/independent_recovery.py','--source',R/'source','--out',R/'recovery_agent/results']),
 ('original_quick',[R/'original_quick_full/quick_joint_probes.py']),
 ('joint_worker',[R/'joint_worker_replay/independent_joint_worker.py','--source',R/'source','--out',R/'joint_worker_replay/results']),
 ('fraction',[R/'fraction_replay/independent_fraction_boundaries.py','--source',R/'source','--out',out]),
 ('wr16_boundaries',[R/'admission_agent/independent_wr16_boundaries.py']),
 ('wr18_contract',[R/'admission_agent/independent_wr18_contract_corrected.py'])]
def run(spec):
    label,args=spec;cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic()
    p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (R/(label+'.stdout.txt')).write_bytes(p.stdout);(R/(label+'.stderr.txt')).write_bytes(p.stderr)
    rec={'label':label,'reviewed_source_commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','actual_source_directory':str(R/'source'),'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
    print(json.dumps(rec),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-650:],flush=True)
    return rec
records=[]
# Filesystem recovery copies are isolated; the two admission modules run sequentially because one imports the other.
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as ex:
    for rec in ex.map(run,commands[:5]):
        records.append(rec);(R/'additional_regression_records.json').write_bytes(json.dumps(records,indent=2).encode())
for spec in commands[5:]:
    records.append(run(spec));(R/'additional_regression_records.json').write_bytes(json.dumps(records,indent=2).encode())
sys.exit(int(any(x['exit_code'] for x in records)))
