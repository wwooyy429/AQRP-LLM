from pathlib import Path
import subprocess,os,sys,json,time,hashlib
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent;R=D.parent
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029\source')
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
records=[]
def run(label,args,expected):
    start=time.monotonic();p=subprocess.run([sys.executable,'-B',*args],cwd=D,env=env,capture_output=True)
    (D/(label+'.stdout')).write_bytes(p.stdout);(D/(label+'.stderr')).write_bytes(p.stderr)
    rec={'label':label,'command':[sys.executable,'-B',*args],'cwd':str(D),'expected_program_exit':expected,'actual_exit':p.returncode,'seconds':round(time.monotonic()-start,3),'stdout':label+'.stdout','stderr':label+'.stderr'}
    records.append(rec);(D/'replay_execution.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(rec),flush=True)
    return p
run('original_stdio15',[str(D/'independent_stdio.py')],0)
run('original_supplement4',[str(D/'supplement_stdio.py')],0)
run('original_minimum_new',[str(D/'minimal_cli_factory_repro.py'),str(R/'source')],0)
run('original_minimum_old',[str(D/'minimal_cli_factory_repro.py'),str(old)],1)
for name in ('independent_stdio.py','supplement_stdio.py','minimal_cli_factory_repro.py'):
    original=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029\stdio_agent')/name
    assert original.read_bytes()==(D/name).read_bytes(),name
print('REPLAY_DONE',flush=True)
