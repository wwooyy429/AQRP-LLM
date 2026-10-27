from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).parent;O=R/'wr20_confirmation';O.mkdir(exist_ok=False)
cmd=[sys.executable,'-B',str(R/'cert_agent/minimal_wr20.py'),'--output',str(O/'result.json')]
t=time.monotonic();p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
(O/'stdout').write_bytes(p.stdout);(O/'stderr').write_bytes(p.stderr)
record={'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_defect_exit':1,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'script_sha256':hashlib.sha256((R/'cert_agent/minimal_wr20.py').read_bytes()).hexdigest(),'fresh_memory_stores':True,'provider_calls':0,'actually_executed':True}
(O/'execution.json').write_bytes(json.dumps(record,indent=2).encode());print(json.dumps(record));print(p.stdout.decode('utf-8'));print(p.stderr.decode('utf-8'))
sys.exit(0 if p.returncode==1 else 1)
