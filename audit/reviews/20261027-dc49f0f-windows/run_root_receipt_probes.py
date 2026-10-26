from pathlib import Path
import json,os,subprocess,sys
R=Path(__file__).parent;OUT=R/'root_receipt_probes';OUT.mkdir(exist_ok=False);records=[]
jobs=[('WR13_five_cases',[str(R/'receipt_agent/adapted_nested_annotations_probe.py'),'--source',str(R/'source'),'--out',str(OUT/'adapted_WR13.json')],0),
      ('WR14_full_chain',[str(R/'receipt_agent/fractional_clock_probe.py'),'--source',str(R/'source'),'--out',str(OUT)],1),
      ('WR14_boundary',[str(R/'minimal_fractional_clock.py'),str(R/'source')],1)]
for label,args,expected in jobs:
    command=[sys.executable,'-B',*args];p=subprocess.run(command,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,encoding='utf-8')
    (OUT/(label+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(OUT/(label+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    records.append(dict(actually_executed=True,label=label,command=command,cwd=str(R),exit_code=p.returncode,expected_exit=expected,reviewed_source_commit='dc49f0f3037918f3ce4413665c59b164a8d6e2b7',unit_methods=None))
    (OUT/'command_log.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(label,p.returncode,p.stdout[-250:],flush=True)
assert all(r['exit_code']==r['expected_exit'] for r in records)
