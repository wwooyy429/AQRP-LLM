from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;S=R/'source';W=R/'build_source';shutil.copytree(S,W)
def hashes():return{p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in W.rglob('*')if p.is_file()}
before=hashes();cmd=[sys.executable,'-B','tools/research.py','build'];t=time.monotonic()
p=subprocess.run(cmd,cwd=W,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'))
(R/'build.stdout').write_bytes(p.stdout);(R/'build.stderr').write_bytes(p.stderr)
after=hashes();record={'command':cmd,'cwd':str(W),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'source_commit':'44676db609b3b7c2175fa7fa4f19c8ccf8165458','all_copy_bytes_unchanged':before==after,'changed_paths':sorted(k for k in set(before)|set(after)if before.get(k)!=after.get(k))}
(R/'build_execution.json').write_bytes((json.dumps(record,indent=2)+'\n').encode());print(json.dumps(record));print(p.stdout.decode());assert p.returncode==0 and before==after
