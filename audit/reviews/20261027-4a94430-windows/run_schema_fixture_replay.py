"""Replay the unchanged prior annotation suite with its required OUT fixture."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
R=Path(__file__).parent;folder=R/'source/audit/reviews/20261027-dc49f0f-windows/receipt_agent'
script=folder/'independent_annotations_role_corrected.py';fixture=folder/'official_mcp_schema_2025-11-25.json'
expected='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7'
assert hashlib.sha256(fixture.read_bytes()).hexdigest()==expected
OUT=R/'runs/dc_annotations_with_fixture';OUT.mkdir(exist_ok=False);shutil.copy2(fixture,OUT/fixture.name)
command=[sys.executable,'-B',str(script),'--source',str(R/'source'),'--out',str(OUT)]
p=subprocess.run(command,cwd=R,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,encoding='utf-8')
(OUT/'process.stdout.txt').write_text(p.stdout,encoding='utf-8');(OUT/'process.stderr.txt').write_text(p.stderr,encoding='utf-8')
record=dict(actually_executed=True,reviewed_source_commit='4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7',command=command,cwd=str(R),exit_code=p.returncode,script_raw_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),script_changed=False,fixture_raw_sha256=expected,correction='Original suite reads schema from OUT, not script directory; copy same fixed raw fixture to a new output directory; first failure untouched')
(OUT/'command.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record));raise SystemExit(p.returncode)
