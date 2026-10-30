"""Capture all command output bytes without text transcode."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
OUT=Path(__file__).resolve().parent
PYTHON=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
records=[]
for label,script in [('evidence_first','verify_evidence.py'),('build_preview_first','build_and_preview.py')]:
    cmd=[PYTHON,'-B',str(OUT/script)]
    result=subprocess.run(cmd,cwd=OUT,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
    stdout=OUT/(label+'.stdout.txt');stderr=OUT/(label+'.stderr.txt')
    stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
    records.append({'label':label,'command':cmd,'cwd':str(OUT),'exit_code':result.returncode,'stdout':stdout.name,'stdout_raw_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr':stderr.name,'stderr_raw_sha256':hashlib.sha256(result.stderr).hexdigest()})
    (OUT/'command_log.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(label,'exit',result.returncode)
    print(result.stdout.decode('utf-8',errors='replace'))
    if result.returncode:print(result.stderr.decode('utf-8',errors='replace'))
raise SystemExit(0 if all(r['exit_code']==0 for r in records) else 1)
