from pathlib import Path
import difflib,json,os,subprocess,sys
R=Path(__file__).parent;records=[]
for case in ['pointer','catalog']:
    cmd=[sys.executable,'-B',str(R/'root_cli_reconciliation.py'),case]
    p=subprocess.run(cmd,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,encoding='utf-8')
    (R/'cli_agent'/(case+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(R/'cli_agent'/(case+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    rec={'actually_executed':True,'command':cmd,'cwd':str(R),'exit_code':p.returncode,'real_SDK_executed':False,'unit_methods':None}
    records.append(rec);print(json.dumps(rec));print(p.stdout);print(p.stderr[-800:])
(R/'cli_agent/command_log.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
old=(R/'cli_agent/root_cli_reconciliation_first.py').read_text(encoding='utf-8');new=(R/'root_cli_reconciliation.py').read_text(encoding='utf-8')
(R/'cli_agent/harness_measurement_correction.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='first',tofile='corrected')),encoding='utf-8')
