from pathlib import Path
import subprocess,json,sys,time,os
OUT=Path(__file__).resolve().parent
command=[sys.executable,'-B',str(OUT/'independent_append_recovery.py')]
start=time.time()
with (OUT/'append_recovery.stdout').open('wb') as out,(OUT/'append_recovery.stderr').open('wb') as err:
    completed=subprocess.run(command,cwd=OUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=out,stderr=err)
record={'command':command,'cwd':str(OUT),'exit_code':completed.returncode,'seconds':round(time.time()-start,3),'stdout':'append_recovery.stdout','stderr':'append_recovery.stderr','source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','first_execution_preserved':'append_recovery_first_script.py / append_recovery_first_results.json / append_recovery_first.stderr','reviewer_correction':'Path.open(ab) CRT retains errno13 but winerrorNone; separately verify direct native CreateFileW returns32. Only reviewer OS expectation corrected.'}
(OUT/'fault_execution.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record));print((OUT/'append_recovery.stderr').read_text(encoding='utf-8',errors='replace'))
raise SystemExit(completed.returncode)
