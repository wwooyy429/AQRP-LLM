from pathlib import Path
import json,os,subprocess,sys
R=Path(__file__).parent;records=[]
jobs=[('full_chain',[str(R/'receipt_agent/nested_annotations_probe.py'),'--source',str(R/'source'),'--out',str(R/'root_nested_annotations.json')]),('extractor_boundary',[str(R/'minimal_nested_annotations.py'),str(R/'source')])]
for label,args in jobs:
    command=[sys.executable,'-B',*args];p=subprocess.run(command,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,encoding='utf-8')
    (R/('root_nested_'+label+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(R/('root_nested_'+label+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    records.append(dict(actually_executed=True,command=command,cwd=str(R),exit_code=p.returncode,source_commit='be9442603a31481a9a71e51ca794df77650c7411',unit_methods=None))
    print(label,p.returncode,p.stdout[-1500:])
(R/'root_nested_commands.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
assert all(r['exit_code']==1 for r in records)
