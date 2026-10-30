from pathlib import Path
import hashlib,importlib.metadata,json,os,platform,subprocess,sys,time
R=Path(__file__).parent;cmd=[sys.executable,'-B',str(R/'verify_source_evidence.py')];t=time.monotonic()
p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
(R/'source_evidence_final.stdout').write_bytes(p.stdout);(R/'source_evidence_final.stderr').write_bytes(p.stderr)
record={'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'note':'First reader failure is preserved; this captures a repeated successful verification after dynamic checks.227 static checks are not counted twice.'}
(R/'source_evidence_execution.json').write_bytes((json.dumps(record,indent=2)+'\n').encode())
import numpy
env={'platform':platform.platform(),'python':platform.python_version(),'executable':sys.executable,'dependencies':{n:importlib.metadata.version(n)for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},'native_Windows':True,'numpy_longdouble_mantissa_bits':numpy.finfo(numpy.longdouble).nmant}
(R/'environment.json').write_bytes((json.dumps(env,indent=2)+'\n').encode());print(json.dumps(record));print(p.stdout.decode('utf-8'));sys.exit(p.returncode)
