from pathlib import Path
import subprocess, json, sys, os, hashlib, time, platform, importlib.metadata
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
PY=sys.executable; records=[]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
def write(name,obj):(R/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def run(label,cmd,cwd):
    start=time.time()
    with (R/(label+'.stdout')).open('wb') as out,(R/(label+'.stderr')).open('wb') as err:
        p=subprocess.run(cmd,cwd=cwd,env=env,stdout=out,stderr=err)
    row={'label':label,'command':list(map(str,cmd)),'cwd':str(cwd),'exit_code':p.returncode,'seconds':round(time.time()-start,3)}
    records.append(row);write('root_execution_records.json',records);print(json.dumps(row),flush=True)
    return p.returncode
write('environment.json',{'platform':platform.platform(),'python':sys.version,'executable':PY,'dependencies':{n:importlib.metadata.version(n) for n in ('numpy','pandas','python-dateutil','pytz','six','tzdata')}})
run('build_first',[PY,'-B','tools/research.py','build'],R/'work_source')
run('build_second',[PY,'-B','tools/research.py','build'],R/'work_source')
run('repository_verify',[PY,'-B','tools/stages.py','verify'],R/'work_source')
write('repository_verification.json',json.loads((R/'work_source/audit/stage_verification.json').read_text(encoding='utf-8')))
run('host_specific_19',[PY,'-B','-m','unittest','discover','-s','tests','-p','test_followup_host.py','-q'],R/'work_source')
dest=R/'materials_checkout'
assert not dest.exists(),dest
if run('clone_private',['git','clone','--no-checkout','--no-hardlinks',str(G),str(dest)],R)==0:
    run('checkout_materials',['git','-c','core.autocrlf=false','-c','core.eol=lf','checkout','--detach','fe088461e84586d7feb73f20be54a22d09706942'],dest)
    run('verify_materials',[PY,'-B','audit/review_packages/host010/verify_review.py'],dest)
    run('verify_scope_7',[PY,'-B','audit/review_packages/host010/verify_review.py','--self-test'],dest)
maps=json.loads((R/'source_git_manifest.json').read_text())
guard={}
for label,item in maps.items():guard[label]={'files':len(item['files']),'changed':[n for n,v in item['files'].items() if hashlib.sha256((R/label/n).read_bytes()).hexdigest()!=v['sha256']]}
guard['work_source']={'changed':[n for n,v in maps['source']['files'].items() if hashlib.sha256((R/'work_source'/n).read_bytes()).hexdigest()!=v['sha256']]}
write('root_guard.json',guard)
print('DONE',flush=True)
