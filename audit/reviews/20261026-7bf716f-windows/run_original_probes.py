from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
R=Path(__file__).parent;archive=R/'source/audit/reviews/20261026-fbe2454-windows'
baseline=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-fbe2454-20261026\source')
records=[]
for filename in ['minimal_missing_date.py','minimal_history_boundary.py']:
    shutil.copy2(archive/filename,R/filename)
    digest=hashlib.sha256((R/filename).read_bytes()).hexdigest()
    for label,source,commit in [('candidate',R/'source','7bf716f45fd6183951a492f0201012af717070f0'),('baseline',baseline,'fbe2454e6ea10aa59211c01f236c54bb251527be')]:
        command=[sys.executable,'-B',str(R/filename),str(source)]
        p=subprocess.run(command,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,encoding='utf-8')
        prefix=label+'_'+Path(filename).stem
        (R/(prefix+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(R/(prefix+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
        data=json.loads(p.stdout) if p.stdout.strip() else None
        if data is not None:(R/(prefix+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        records.append(dict(actual_source_commit=commit,script=filename,script_sha256=digest,original_unchanged=True,command=command,cwd=str(R),exit_code=p.returncode,
            literal_source_commit_in_original_script='fbe2454e6ea10aa59211c01f236c54bb251527be',real_SDK_executed=False,unit_methods=None))
        print(json.dumps({'source':label,'script':filename,'exit':p.returncode,'result':data}),flush=True)
(R/'original_probe_execution.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
