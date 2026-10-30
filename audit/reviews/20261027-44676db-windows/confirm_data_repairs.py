from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;O=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027');D=R/'root_repair_confirmation';D.mkdir()
p=O/'minimal_wr25_wr26.py';q=R/p.name;shutil.copyfile(p,q);assert p.read_bytes()==q.read_bytes()
cmd=[sys.executable,'-B',str(q),'--source',str(R/'source'),'--output',str(D/'result.json')];t=time.monotonic()
r=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
(D/'stdout').write_bytes(r.stdout);(D/'stderr').write_bytes(r.stderr)
record=dict(command=cmd,cwd=str(R),exit_code=r.returncode,seconds=time.monotonic()-t,script_sha256=hashlib.sha256(q.read_bytes()).hexdigest(),stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest(),source_commit='44676db609b3b7c2175fa7fa4f19c8ccf8165458')
(D/'execution.json').write_bytes((json.dumps(record,indent=2)+'\n').encode());print(json.dumps(record));print(r.stdout.decode());assert r.returncode==0,r.stderr.decode()
