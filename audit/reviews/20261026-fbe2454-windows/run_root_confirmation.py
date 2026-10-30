from pathlib import Path
import json,os,subprocess,sys
R=Path(__file__).parent
command=[sys.executable,'-B',str(R/'minimal_missing_date.py'),str(R/'source')]
p=subprocess.run(command,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf-8')
(R/'root_missing_date.stdout.txt').write_text(p.stdout,encoding='utf-8')
(R/'root_missing_date.stderr.txt').write_text(p.stderr,encoding='utf-8')
(R/'root_missing_date_result.json').write_text(json.dumps(json.loads(p.stdout),indent=2),encoding='utf-8')
record={'actually_executed':True,'source_commit':'fbe2454e6ea10aa59211c01f236c54bb251527be','command':command,'cwd':str(R),'exit_code':p.returncode,
        'kind':'Repeated unchanged public pipeline reproduction for saved stdout/stderr; initial tool run also exited1','test_methods':None,'real_SDK_executed':False,'market_calls':0}
(R/'root_execution_records.json').write_text(json.dumps([record],indent=2),encoding='utf-8')
print(json.dumps(record))
