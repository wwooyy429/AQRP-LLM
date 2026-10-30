from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).parent;G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
C='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58';B='deb85d9f27441b275ab8b108f0232ecd2707a1e8';P='6a1edbf07fa8fc6cf774084094f4beacc28ff60b'
commands=[('baseline_merge_base',['merge-base',B,C]),('PR_base_merge_base',['merge-base',P,C]),
 ('PR_complete_name_status',['diff','--name-status',P,C]),('current_complete_name_status',['diff','--name-status',B,C]),
 ('PR_complete_patch',['diff','--binary',P,C])]
records=[]
for name,args in commands:
    cmd=['git','-C',str(G),*args];p=subprocess.run(cmd,capture_output=True)
    (R/(name+'.stdout')).write_bytes(p.stdout);(R/(name+'.stderr')).write_bytes(p.stderr)
    assert p.returncode==0,name
    if name=='baseline_merge_base':assert p.stdout.decode().strip()==B
    if name=='PR_base_merge_base':assert p.stdout.decode().strip()==P
    records.append({'name':name,'command':cmd,'exit_code':p.returncode,'stdout_bytes':len(p.stdout),'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()})
(R/'git_context.json').write_bytes((json.dumps(records,indent=2)+'\n').encode())
print(json.dumps([{'name':x['name'],'stdout_bytes':x['stdout_bytes'],'exit_code':x['exit_code']}for x in records]))
