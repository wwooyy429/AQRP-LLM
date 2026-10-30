from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parent;script=R/'minimal_wr27_root_manifest.py'
cmd=[sys.executable,'-B',str(script),'--source',str(R.parent/'source'),'--git-repository',r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo','--output',str(R/'wr27_first')];start=time.perf_counter()
p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'))
(R/'wr27_first.stdout').write_bytes(p.stdout);(R/'wr27_first.stderr').write_bytes(p.stderr);sha=lambda b:hashlib.sha256(b).hexdigest()
(R/'wr27_first_execution.json').write_bytes((json.dumps({'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_defect_exit':1,'seconds':round(time.perf_counter()-start,3),'script_raw_sha256':sha(script.read_bytes()),'stdout_raw_sha256':sha(p.stdout),'stderr_raw_sha256':sha(p.stderr)},ensure_ascii=False,indent=2)+'\n').encode())
sys.stdout.buffer.write(p.stdout);sys.stderr.buffer.write(p.stderr);sys.exit(p.returncode)
