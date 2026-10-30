from pathlib import Path
import json
import os
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[2]
phase = sys.argv[1]
target = root / '.git/repair-work' / ('wr16-' + phase)
target.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
original = root.parent / 'LLM审核/review-8f7236e-20261027/admission_agent/minimal_joint_registry.py'
commands = [('original_mre', [sys.executable, '-B', str(original), str(root)]),
            ('new_tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_wr16_registry_admission.py', '-v'])]
records=[]
for name, command in commands:
    start=time.monotonic()
    result=subprocess.run(command, cwd=root, env=env, capture_output=True)
    (target/(name+'.stdout')).write_bytes(result.stdout)
    (target/(name+'.stderr')).write_bytes(result.stderr)
    records.append({'name':name,'command':command,'cwd':str(root),'exit_code':result.returncode,'seconds':time.monotonic()-start})
    print(json.dumps(records[-1]), flush=True)
(target/'commands.json').write_text(json.dumps({'phase':phase,'synthetic_only':True,'records':records},indent=2)+'\n',encoding='utf-8')
