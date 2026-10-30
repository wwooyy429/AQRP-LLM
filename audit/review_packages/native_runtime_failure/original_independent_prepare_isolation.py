from pathlib import Path
import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
LABEL=sys.argv[1] if len(sys.argv)>1 else 'fixed81'
assert LABEL in {'fixed81','fixed81-final'}
FIXED=WORK/LABEL
COMMIT='81fbe5294055423e88ee5aeae48ca6223e7971da'
assert not FIXED.exists()
FIXED.mkdir()
raw=subprocess.check_output(['git','archive','--format=zip',COMMIT,'cloud','tools','config'],cwd=ROOT)
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    archive.extractall(FIXED)
def inventory(folder):
    return {p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file() and '.lock' not in p.name and '.locks' not in p.parts}
before=inventory(ROOT/'audit/runtime')
shutil.copytree(ROOT/'audit/runtime',FIXED/'audit/runtime')
shutil.copytree(ROOT/'audit/task_inputs',FIXED/'audit/task_inputs')
assert before==inventory(ROOT/'audit/runtime')==inventory(FIXED/'audit/runtime')
original=ROOT/'audit/tool_observations/bfd00f2611fd4496b9498d4597618a8e-terminal-runtime-error.json'
target=WORK/'native_original.json'
target.write_bytes(original.read_bytes())
report={'source_commit':COMMIT,'actual_runtime_files':len(before),'actual_runtime_raw_sha256':before,
    'native_original_raw_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
    'fixed_git_archive_used':True,'real_ledger_changed':False,'real_QC_calls':0}
(WORK/('isolation_manifest_final.json' if LABEL.endswith('-final') else 'isolation_manifest.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_commit':COMMIT,'actual_runtime_files':len(before),
    'native_original_raw_sha256':report['native_original_raw_sha256'],'real_ledger_changed':False}))
