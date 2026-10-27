"""Capture exact stdout/stderr bytes without overwriting the first audit run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
destination=OUT/'captured_run'
destination.mkdir(exist_ok=False)
argv=[sys.executable,'-B',str(OUT/'independent_joint_worker.py'),'--source',str(OUT.parent/'source'),'--out',str(destination)]
completed=subprocess.run(argv,cwd=str(OUT),capture_output=True)
stdout=destination/'stdout.txt';stderr=destination/'stderr.txt'
stdout.write_bytes(completed.stdout);stderr.write_bytes(completed.stderr)
summary=json.loads((destination/'first_run_summary.json').read_text(encoding='utf-8'))
record={'purpose':'One explicit repeated capture run; same 9/81 inputs, not 81 additional unique cases. Original first_run files remain untouched.',
    'argv':argv,'cwd':str(OUT),'exit_code':completed.returncode,
    'stdout':{'path':str(stdout),'bytes':len(completed.stdout),'sha256':hashlib.sha256(completed.stdout).hexdigest()},
    'stderr':{'path':str(stderr),'bytes':len(completed.stderr),'sha256':hashlib.sha256(completed.stderr).hexdigest()},
    'methods':summary['methods'],'subcases':summary['subcases'],'failures':summary['failure_records'],'errors':summary['error_records'],
    'skipped':summary['skipped'],'actual_component_invocations':summary['actual_component_invocations']}
(OUT/'captured_execution.json').write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
sys.exit(completed.returncode)
