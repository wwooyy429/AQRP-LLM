from pathlib import Path
import json,os,subprocess,sys
R=Path(__file__).parent;cmd=[sys.executable,'-B',str(R/'minimal_history_boundary.py'),str(R/'source')]
p=subprocess.run(cmd,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf-8')
(R/'root_boundary.stdout.txt').write_text(p.stdout,encoding='utf-8');(R/'root_boundary.stderr.txt').write_text(p.stderr,encoding='utf-8')
(R/'root_boundary_result.json').write_text(json.dumps(json.loads(p.stdout),indent=2),encoding='utf-8')
rec={'actually_executed':True,'source_commit':'fbe2454e6ea10aa59211c01f236c54bb251527be','command':cmd,'cwd':str(R),'exit_code':p.returncode,
     'kind':'SDK-contract-shaped synthetic reproduction, not real SDK','test_methods':None,'market_calls':0}
(R/'root_boundary_execution.json').write_text(json.dumps(rec,indent=2),encoding='utf-8');print(json.dumps(rec));print(p.stdout)
