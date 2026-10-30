"""Preserve corrected static check and WR19 raw MRE output; no build rerun."""
from pathlib import Path
import hashlib,json,os,subprocess
OUT=Path(__file__).resolve().parent;R=OUT.parent
PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
log=json.loads((OUT/'command_log.json').read_text(encoding='utf-8-sig'))
for label,argv in [('evidence_corrected',[PY,'-B',str(OUT/'verify_evidence.py')]),('WR19_first',[PY,'-B',str(OUT/'minimal_wr19.py'),str(R/'source'),r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo'])]:
 result=subprocess.run(argv,cwd=OUT,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
 for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]:(OUT/(label+'.'+stream+'.txt')).write_bytes(data)
 log.append({'label':label,'command':argv,'cwd':str(OUT),'exit_code':result.returncode,'stdout':label+'.stdout.txt','stdout_raw_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr':label+'.stderr.txt','stderr_raw_sha256':hashlib.sha256(result.stderr).hexdigest()})
 (OUT/'command_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(label,'exit',result.returncode)
 if result.stderr:print(result.stderr.decode('utf-8',errors='replace')[:2500])
e=json.loads((OUT/'evidence_verification.json').read_text(encoding='utf-8'))
print(json.dumps({k:e[k] for k in ('check_count','passed_checks','failed_checks','unit_test_methods_executed','discrepancies')},ensure_ascii=False,indent=2))
print((OUT/'WR19_first.stdout.txt').read_text(encoding='utf-8-sig'))
