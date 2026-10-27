import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(__file__).resolve().parent;records=[]
for kind in ('baseline','candidate'):
    workspace=out/('mre_'+kind);script=workspace/'agent/minimal_new_success_without_dispatch.py'
    argv=[sys.executable,'-B',str(script)];r=subprocess.run(argv,cwd=workspace,capture_output=True)
    (workspace/'first.stdout').write_bytes(r.stdout);(workspace/'first.stderr').write_bytes(r.stderr)
    record={'kind':kind,'argv':argv,'cwd':str(workspace),'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),
        'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest(),
        'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest()}
    raw=workspace/'agent/new_success_without_dispatch_first.json'
    if raw.exists():
        result=json.loads(raw.read_text(encoding='utf-8').removesuffix('\\n'))
        record['actual_CLI_processes']=result['actual_entry_CLI_processes']
        record['unbound_CLI_exit']=result['unbound_CLI_exit_code'];record['unbound_result']=result['unbound_result']
        (workspace/'strict_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (workspace/'execution.json').write_text(json.dumps(record,indent=2),encoding='utf-8');records.append(record)
    print(json.dumps(record),flush=True);print(r.stderr.decode('utf-8',errors='replace')[-3000:],flush=True)
(out/'original_mre_execution.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
sys.exit(0 if [row['exit_code'] for row in records]==[1,0] else 1)
