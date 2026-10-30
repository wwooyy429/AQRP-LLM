from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-81fbe52-20261027')
OUT=R/'metadata_replay';OUT.mkdir(exist_ok=False)
script=OUT/'original_minimal_wr19.py';shutil.copyfile(OLD/'minimal_wr19.py',script)
assert script.read_bytes()==(OLD/'minimal_wr19.py').read_bytes()
records=[]
for label,args,expected in [
 ('original_baseline',[script,OLD/'source'],1),
 ('original_candidate',[script,R/'source'],0),
 ('developer_verifier',[R/'source/audit/review_packages/wr19/verify_archived_comparison.py',R/'source'],0)]:
 cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic()
 p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8'))
 (OUT/(label+'.stdout.txt')).write_bytes(p.stdout);(OUT/(label+'.stderr.txt')).write_bytes(p.stderr)
 record={'label':label,'reviewed_source_commit':'84414ab49c39e25cb50ece1c1debeefa3993c874','baseline_commit':'81fbe5294055423e88ee5aeae48ca6223e7971da',
  'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_exit_code':expected,'seconds':time.monotonic()-t,
  'script_sha256':hashlib.sha256(Path(args[0]).read_bytes()).hexdigest(),'software_unit_methods':0,
  'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
 records.append(record);(OUT/'execution_records.json').write_bytes(json.dumps(records,indent=2).encode())
 print(json.dumps(record),flush=True);print(p.stdout.decode('utf-8')[-1200:],flush=True)
 assert p.returncode==expected
assert json.loads((OUT/'original_candidate.stdout.txt').read_text(encoding='utf-8'))['computed']==13
