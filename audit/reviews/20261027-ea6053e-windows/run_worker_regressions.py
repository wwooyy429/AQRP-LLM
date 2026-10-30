from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;O=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-deb85d9-20261027/entry_agent');D=R/'control_replay';D.mkdir(exist_ok=False)
names=['independent_worker_identity.py','independent_preflight_corrected.py','independent_cli_gates.py','independent_preflight_cli.py','quick_joint_probes.py']
bindings=[]
for name in names:
    shutil.copyfile(O/name,D/name);assert(O/name).read_bytes()==(D/name).read_bytes();bindings.append({'name':name,'sha256':hashlib.sha256((D/name).read_bytes()).hexdigest()})
(D/'script_bindings.json').write_bytes(json.dumps(bindings,indent=2).encode());records=[]
for name in names[:4]:
    cmd=[sys.executable,'-B',str(D/name)];t=time.monotonic();p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (D/(name+'.stdout')).write_bytes(p.stdout);(D/(name+'.stderr')).write_bytes(p.stderr)
    row={'script':name,'actual_commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','actual_source':str(R/'source'),'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'embedded_old_SHA_not_actual_source_identity':True}
    records.append(row);(D/'execution_records.json').write_bytes(json.dumps(records,indent=2).encode());print(json.dumps(row),flush=True)
sys.exit(int(any(r['exit_code']for r in records)))
