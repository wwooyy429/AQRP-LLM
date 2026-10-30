from pathlib import Path
import subprocess, json, sys, os, hashlib, time, re, importlib.metadata, platform
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
PY=sys.executable
records=[]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
def write(name,value): (R/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def run(label,cmd,cwd):
    start=time.time()
    with (R/(label+'.stdout')).open('wb') as out,(R/(label+'.stderr')).open('wb') as err:
        p=subprocess.run(cmd,cwd=cwd,env=env,stdout=out,stderr=err)
    rec={'label':label,'command':list(map(str,cmd)),'cwd':str(cwd),'exit_code':p.returncode,'seconds':round(time.time()-start,3)}
    records.append(rec); write('root_execution_records.json',records)
    print(json.dumps(rec),flush=True)
    return p.returncode
write('environment.json',{'platform':platform.platform(),'python':sys.version,'executable':PY,'dependencies':{n:importlib.metadata.version(n) for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']}})
if run('build_first',[PY,'-B','tools/research.py','build'],R/'work_source')==0:
    run('build_second',[PY,'-B','tools/research.py','build'],R/'work_source')
run('repository_verify',[PY,'-B','tools/stages.py','verify'],R/'work_source')
report=json.loads((R/'work_source/audit/stage_verification.json').read_text(encoding='utf-8'))
write('repository_verification.json',report)
dest=R/'materials_checkout'
if dest.exists(): raise RuntimeError('Refuse overwrite checkout')
if run('clone_private',['git','clone','--no-checkout','--no-hardlinks',str(G),str(dest)],R)==0:
    run('checkout_materials',['git','-c','core.autocrlf=false','-c','core.eol=lf','checkout','--detach','a6a5a165d87c172535cdea6cf495e3c1a850e6e4'],dest)
    run('verify_materials',[PY,'-B','audit/review_packages/recovery009/verify_review.py'],dest)
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
guard={}
for label,item in maps.items():
    changed=[name for name,old in item['files'].items() if hashlib.sha256((R/label/name).read_bytes()).hexdigest()!=old['sha256']]
    guard[label]={'files':len(item['files']),'changed':changed}
work_changed=[name for name,old in maps['source']['files'].items() if hashlib.sha256((R/'work_source'/name).read_bytes()).hexdigest()!=old['sha256']]
guard['work_source']={'changed':work_changed,'note':'Only generated audit/stage_verification.json is expected to change.'}
write('root_guard.json',guard)
print('DONE',flush=True)
