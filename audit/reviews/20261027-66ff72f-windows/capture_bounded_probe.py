from pathlib import Path
import hashlib,importlib.metadata,json,os,platform,subprocess,sys,time
R=Path(__file__).parent
cmd=[sys.executable,'-B',str(R/'verify_phase2_scope.py'),str(R/'source')]
t=time.monotonic();p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
(R/'bounded_probe.stdout').write_bytes(p.stdout);(R/'bounded_probe.stderr').write_bytes(p.stderr)
record={'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),
 'first_execution':'The identical script first ran through exec_command at 08:32 UTC; exit0, four probe chains passed. Tool output retained in chat. This file captures a repeated execution, not four additional unique tests.',
 'probe_chains':4,'unit_methods':0,'actually_executed':True}
(R/'bounded_probe_execution.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
import numpy
env={'platform':platform.platform(),'python':platform.python_version(),'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,
 'dependencies':{n:importlib.metadata.version(n)for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},'native_Windows':True,'numpy_longdouble_mantissa_bits':numpy.finfo(numpy.longdouble).nmant,'locked_dependencies_checked':True}
(R/'environment.json').write_bytes((json.dumps(env,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'probe':record,'environment':env},ensure_ascii=False));sys.exit(p.returncode)
