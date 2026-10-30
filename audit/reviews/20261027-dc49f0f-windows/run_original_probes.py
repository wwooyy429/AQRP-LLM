"""Run unchanged public reproducers against fixed dc49 and be944 sources."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).parent;OUT=R/'original_probes';OUT.mkdir(exist_ok=False)
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
jobs=[('candidate',R/'source','dc49f0f3037918f3ce4413665c59b164a8d6e2b7','minimal_nested_annotations.py',[],0),
      ('baseline',R.parent/'aqrp-review-be94426-20261026/source','be9442603a31481a9a71e51ca794df77650c7411','minimal_nested_annotations.py',[],1)]
jobs += [('candidate',R/'source','dc49f0f3037918f3ce4413665c59b164a8d6e2b7',script,args,0) for script,args in [('minimal_parallel_carrier.py',[]),('minimal_cli_switch.py',['pointer']),('minimal_cli_switch.py',['catalog'])]]
records=[]
for label,source,sha,script,extra,expected in jobs:
    name=label+'_'+Path(script).stem+('_'+extra[0] if extra else '')
    command=[sys.executable,'-B',str(R/script),str(source),*extra]
    start=time.monotonic();p=subprocess.run(command,cwd=R,env=env,capture_output=True,text=True,encoding='utf-8')
    (OUT/(name+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(OUT/(name+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    records.append(dict(label=name,command=command,cwd=str(R),actual_source_commit=sha,script_sha256=hashlib.sha256((R/script).read_bytes()).hexdigest(),script_changed=False,exit_code=p.returncode,expected_exit_code=expected,seconds=time.monotonic()-start,unit_methods=None))
    (OUT/'execution_records.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(json.dumps(records[-1]),flush=True)
unexpected=[x for x in records if x['exit_code']!=x['expected_exit_code']]
print(json.dumps({'unexpected_exit_records':unexpected}));raise SystemExit(2 if unexpected else 0)
