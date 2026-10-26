"""Run the unchanged published WR11/12 reproducers on new and old sources."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).parent;OUT=R/'original_probes';OUT.mkdir(exist_ok=False)
old=R.parent/'aqrp-review-e513c66-20261026/source'
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
records=[]
for label,source,sha in [('candidate',R/'source','be9442603a31481a9a71e51ca794df77650c7411'),('baseline',old,'e513c66e5965133fbe83fb0ab987eae853f96260')]:
    for script,extra in [('minimal_parallel_carrier.py',[]),('minimal_cli_switch.py',['pointer']),('minimal_cli_switch.py',['catalog'])]:
        name=label+'_'+Path(script).stem+('_'+extra[0] if extra else '')
        command=[sys.executable,'-B',str(R/script),str(source),*extra]
        start=time.monotonic();result=subprocess.run(command,cwd=R,env=env,capture_output=True,text=True,encoding='utf-8')
        (OUT/(name+'.stdout.txt')).write_text(result.stdout,encoding='utf-8');(OUT/(name+'.stderr.txt')).write_text(result.stderr,encoding='utf-8')
        record=dict(label=name,command=command,cwd=str(R),actual_source_commit=sha,script_sha256=hashlib.sha256((R/script).read_bytes()).hexdigest(),script_changed=False,exit_code=result.returncode,expected_exit_code=0 if label=='candidate' else 1,seconds=time.monotonic()-start,unit_methods=None)
        records.append(record);(OUT/'execution_records.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(json.dumps(record),flush=True)
unexpected=[x for x in records if x['exit_code']!=x['expected_exit_code']]
print(json.dumps({'unexpected_exit_records':unexpected}));raise SystemExit(2 if unexpected else 0)
