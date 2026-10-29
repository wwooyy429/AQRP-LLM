from pathlib import Path
from hashlib import sha256
import base64, json, shutil, sys, subprocess, time, os
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
A=Path(__file__).resolve().parent
S=R/'source';M=R/'materials'
OLD=M/'audit/reviews/20261029-975f676-recovery009'
CONTEXT=A/'replay_context'
assert not CONTEXT.exists()
CONTEXT.mkdir();shutil.copytree(S,CONTEXT/'source')
scripts={
 'windows_lock':('windows_lock_agent/independent_windows_lock.py','windows_lock_agent/first_results.json'),
 'notifications':('notification_agent/independent_notifications.py','notification_agent/corrected_results.json'),
 'notification_supplement':('notification_agent/supplement_notifications.py','notification_agent/supplement_results.json'),
 'cycles_rounds':('windows_lock_agent/supplement/independent_cycles_rounds.py','windows_lock_agent/supplement/first_results.json')}
manifest=json.loads((OLD/'archive_manifest.json').read_text())
records=[]
for name,(relative,resultfile) in scripts.items():
    rec=manifest['original_artifacts'][relative]
    data=base64.b64decode((OLD/rec['raw_base64_path']).read_bytes()) if 'raw_base64_path' in rec else (OLD/rec['readable_path']).read_bytes()
    assert sha256(data).hexdigest()==rec['original_sha256']
    path=CONTEXT/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    # supplement imports the original notification module copied above.
    start=time.monotonic()
    cmd=[sys.executable,'-B',str(path)]
    with (A/(name+'.stdout')).open('wb') as out,(A/(name+'.stderr')).open('wb') as err:
        p=subprocess.run(cmd,cwd=CONTEXT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=out,stderr=err)
    record={'name':name,'command':cmd,'cwd':str(CONTEXT),'script_original_sha256':sha256(data).hexdigest(),'script_changed':False,'exit_code':p.returncode,'seconds':round(time.monotonic()-start,3),'result':resultfile}
    if (CONTEXT/resultfile).exists():
        result=json.loads((CONTEXT/resultfile).read_text(encoding='utf-8'))
        record['output_result']=result
        shutil.copyfile(CONTEXT/resultfile,A/(name+'_result.json'))
    records.append(record)
    (A/'replay_execution.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='output_result'}),flush=True)
print('DONE',flush=True)
