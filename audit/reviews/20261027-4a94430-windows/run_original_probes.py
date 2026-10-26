"""Unchanged published reproducers and the same 14-case worker probe."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).parent;OUT=R/'original_probes';OUT.mkdir(exist_ok=False)
SHA='4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7';BASE='dc49f0f3037918f3ce4413665c59b164a8d6e2b7'
source=R/'source';old=R.parent/'aqrp-review-dc49f0f-20261027/source'
script=source/'audit/reviews/20261027-dc49f0f-windows/receipt_agent/fractional_clock_probe.py'
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
jobs=[('WR14_current',SHA,['minimal_fractional_clock.py',source],0),('WR14_old',BASE,['minimal_fractional_clock.py',old],1),
 ('WR11_current',SHA,['minimal_parallel_carrier.py',source],0),('WR13_current',SHA,['minimal_nested_annotations.py',source],0),
 *[('WR12_'+x,SHA,['minimal_cli_switch.py',source,x],0) for x in ['pointer','catalog']],
 ('WR14_full_current',SHA,[script,'--source',source,'--out',OUT/'current_full'],0),
 ('WR14_full_old',BASE,[script,'--source',old,'--out',OUT/'old_full'],1)]
records=[]
for label,sha,args,expected in jobs:
    command=[sys.executable,'-B',*[str(x) for x in args]];start=time.monotonic()
    p=subprocess.run(command,cwd=R,env=env,capture_output=True,text=True,encoding='utf-8')
    (OUT/(label+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(OUT/(label+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    path=Path(args[0]);path=R/path if not path.is_absolute() else path
    records.append(dict(label=label,command=command,cwd=str(R),actual_source_commit=sha,script_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),script_changed=False,exit_code=p.returncode,expected_exit=expected,seconds=time.monotonic()-start,unit_methods=None))
    (OUT/'command_log.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(label,p.returncode,flush=True)
bindings=[]
for label,folder,sha in [('current','current_full',SHA),('old','old_full',BASE)]:
    files=list((OUT/folder).glob('*fractional_clock.json'));assert len(files)==1
    d=json.loads(files[0].read_text(encoding='utf-8'));bindings.append(dict(actual_source_commit=sha,output=str(files[0]),historical_child_label_not_source_identity=d['label'],source_root=d['source_root'],receipt_source_sha256=d['receipt_source_sha256'],script_sha256=d['script_sha256'],helper_sha256=d['helper_sha256'],variants=d['variants'],actually_completed=d['actually_completed'],incorrect_rejections=d['incorrect_rejections']))
(OUT/'full_chain_bindings.json').write_text(json.dumps(bindings,indent=2),encoding='utf-8')
unexpected=[x for x in records if x['exit_code']!=x['expected_exit']]
print(json.dumps({'unexpected_exit_records':unexpected,'full_chain_bindings':bindings}));raise SystemExit(2 if unexpected else 0)
