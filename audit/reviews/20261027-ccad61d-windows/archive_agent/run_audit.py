from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parent;script=R/'verify_source_archive.py';cmd=[sys.executable,'-B',str(script)]
start=time.perf_counter();p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'))
(R/'first.stdout').write_bytes(p.stdout);(R/'first.stderr').write_bytes(p.stderr);sha=lambda b:hashlib.sha256(b).hexdigest()
record={'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':round(time.perf_counter()-start,3),'script_raw_sha256':sha(script.read_bytes()),'stdout_raw_sha256':sha(p.stdout),'stderr_raw_sha256':sha(p.stderr),'independent_product_unit_methods':0}
(R/'first_execution.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode());sys.stdout.buffer.write(p.stdout);sys.stderr.buffer.write(p.stderr);sys.exit(p.returncode)
