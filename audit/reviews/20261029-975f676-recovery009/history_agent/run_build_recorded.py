from pathlib import Path
import subprocess,sys,json,hashlib,time
O=Path(__file__).resolve().parent
cmd=[sys.executable,'-B',str(O/'build_report.py')]
t=time.monotonic();p=subprocess.run(cmd,cwd=O,capture_output=True)
(O/'build_report.stdout').write_bytes(p.stdout);(O/'build_report.stderr').write_bytes(p.stderr)
row={'command':cmd,'cwd':str(O),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
(O/'build_report_execution.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
print(json.dumps(row),flush=True);print((p.stdout+p.stderr).decode('utf-8','replace')[-2000:],flush=True)
