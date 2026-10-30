"""Resolve the archived byte-identical script reference, then replay it."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
R=Path(__file__).parent;archive=R/'source/audit/reviews/20261026-e513c66-windows'
manifest=json.loads((archive/'archive_manifest.json').read_text(encoding='utf-8'))
ref=next(x for x in manifest['reused_existing_evidence'] if x['origin_relative_path']=='receipt_agent/independent_receipts.py')
script=R/'source'/ref['existing_repository_path'];assert hashlib.sha256(script.read_bytes()).hexdigest()==ref['raw_sha256']
assert script.read_bytes()==(R.parent/'aqrp-review-e513c66-20261026/receipt_agent/independent_receipts.py').read_bytes()
out=R/'runs/e513_receipts_resolved'
command=[sys.executable,'-B',str(script),'--source',str(R/'source'),'--out',str(out)]
result=subprocess.run(command,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,encoding='utf-8')
(R/'runs/e513_receipts_resolved.stdout.txt').write_text(result.stdout,encoding='utf-8');(R/'runs/e513_receipts_resolved.stderr.txt').write_text(result.stderr,encoding='utf-8')
record={'actually_executed':True,'command':command,'cwd':str(R),'exit_code':result.returncode,'script_sha256':ref['raw_sha256'],'script_changed':False,'correction':'Resolve the documented deduplicated original script, no input or assertion change','previous_attempt_exit':2,'previous_attempt_methods':0}
(R/'runs/e513_receipts_resolved.command.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record));print(result.stdout[-1000:]);print(result.stderr[-500:]);raise SystemExit(result.returncode)
