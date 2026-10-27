from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;D=R/'wr25_confirmation';D.mkdir()
names=['first_unmapped_classification_probe.py','cert_fixture.py']
bindings=[]
for name in names:
 p=R/'cert_agent'/name;q=D/name;shutil.copyfile(p,q)
 assert p.read_bytes()==q.read_bytes()
 bindings.append({'name':name,'sha256':hashlib.sha256(q.read_bytes()).hexdigest()})
cmd=[sys.executable,'-B',str(D/names[0])];t=time.monotonic()
p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1'))
(D/'stdout').write_bytes(p.stdout);(D/'stderr').write_bytes(p.stderr)
record={'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'script_bindings':bindings,'source_commit':'ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6','real_calls':0}
(D/'execution.json').write_bytes(json.dumps(record,indent=2).encode())
assert p.returncode==1,(p.stdout+p.stderr).decode(errors='replace')
d=json.loads((D/'first_unmapped_classification_result.json').read_bytes())
assert d['status']=='observations_passed' and all(d['checks'].values()) and d['all_certification_flags_false']
print(json.dumps({'exit_code':p.returncode,'status':d['status'],'checks':len(d['checks']),'counts':d['counts'],'all_certification_flags_false':d['all_certification_flags_false']}))
