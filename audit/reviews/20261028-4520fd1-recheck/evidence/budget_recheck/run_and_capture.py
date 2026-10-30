from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parent;SOURCE=R.parent/'source'
def guard():return{p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in SOURCE.rglob('*')if p.is_file()}
before=guard();command=[sys.executable,'-B',str(R/'settlement_frontier_tests.py')];t=time.monotonic()
p=subprocess.run(command,cwd=R,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8'),capture_output=True)
(R/'first.stdout').write_bytes(p.stdout);(R/'first.stderr').write_bytes(p.stderr)
after=guard();assert before==after
d={'command':command,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'source_files':len(before),'source_all_raw_unchanged':True,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'test_script_sha256':hashlib.sha256((R/'settlement_frontier_tests.py').read_bytes()).hexdigest()}
(R/'execution.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(json.dumps(d));print(p.stdout.decode('utf-8'));print(p.stderr.decode('utf-8'));sys.exit(p.returncode)
