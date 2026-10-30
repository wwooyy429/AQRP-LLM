from pathlib import Path
import json,sys,shutil,subprocess,hashlib,time,os
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent;R=OUT.parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029\host_api_agent')
CONTEXT=OUT/'replay_context'; E=CONTEXT/'host_api_agent';S=CONTEXT/'source'
assert not CONTEXT.exists(),'Refuse overwrite replay context'
E.mkdir(parents=True)
shutil.copytree(R/'source',S)
records=[]
for name,label in [('independent_host_api.py','original_API_main'),('supplement_host_api.py','original_API_supplement')]:
    raw=(OLD/name).read_bytes();(E/name).write_bytes(raw)
    command=[sys.executable,'-B',str(E/name)]
    start=time.time()
    with (OUT/(label+'.stdout')).open('wb') as out,(OUT/(label+'.stderr')).open('wb') as err:
        completed=subprocess.run(command,cwd=E,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=out,stderr=err)
    records.append({'label':label,'command':command,'cwd':str(E),'exit_code':completed.returncode,'seconds':round(time.time()-start,3),'original_script_sha256':hashlib.sha256(raw).hexdigest(),'script_bytes_changed':False,'actually_imported_source':str(S),'actual_source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','embedded_old_source_SHA_is_only_historical_label':True})
    (OUT/'execution_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(records[-1]),flush=True)
for name in ('corrected_results.json','supplement_results.json'):
    shutil.copyfile(E/name,OUT/name)
print('REPLAYS DONE',flush=True)
