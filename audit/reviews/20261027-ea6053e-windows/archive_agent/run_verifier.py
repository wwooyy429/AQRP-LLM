from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
python=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe')
script=R/'verify_archive_evidence.py'
cmd=[str(python),'-B',str(script)]
start=time.perf_counter()
p=subprocess.run(cmd,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8'),cwd=R)
(R/'corrected.stdout').write_bytes(p.stdout);(R/'corrected.stderr').write_bytes(p.stderr)
records=[{'label':'first','command':cmd,'exit_code':1,'script':'verify_archive_evidence_first.py','script_raw_sha256':sha((R/'verify_archive_evidence_first.py').read_bytes()),'stdout':'first.stdout','stdout_raw_sha256':sha((R/'first.stdout').read_bytes()),'stderr':'first.stderr','stderr_raw_sha256':sha((R/'first.stderr').read_bytes()),'reviewer_error':'Independent engineering-package classifier used nonexistent engineering_plan/collection_plan keys. Actual schema is engineering_task_schema_version + plan.scope. First 54 checks passed; engineering classifier assertion was reviewer error, not product finding. Original report_first.json preserved.'},
{'label':'corrected','command':cmd,'cwd':str(R),'exit_code':p.returncode,'elapsed_seconds':round(time.perf_counter()-start,3),'script_raw_sha256':sha(script.read_bytes()),'stdout':'corrected.stdout','stdout_raw_sha256':sha(p.stdout),'stderr':'corrected.stderr','stderr_raw_sha256':sha(p.stderr)}]
(R/'execution_records.json').write_bytes((json.dumps(records,ensure_ascii=False,indent=2)+'\n').encode())
sys.stdout.buffer.write(p.stdout);sys.stderr.buffer.write(p.stderr)
sys.exit(p.returncode)
