from pathlib import Path
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[3]
package=Path(__file__).resolve().parent
baseline=package/'baseline268f-final'
assert not baseline.exists(), 'Preserve previous baseline replay attempts'
baseline.mkdir()
raw=subprocess.check_output(['git','archive','--format=zip','268f420e9d066e7e7859566a65c0ce65523bec82',
    'cloud','config','tests','tools'],cwd=root)
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    archive.extractall(baseline)
test=root/'tests/test_native_backtest_rejection.py'
original=test.read_bytes()
(baseline/'tests'/test.name).write_bytes(original)
(package/'final_tests.py').write_bytes(original)
env=dict(os.environ,PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
runs=[]
for name,cwd in [('final_baseline',baseline),('final_candidate',root)]:
    command=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p',test.name,'-v']
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True)
    (package/(name+'.stdout')).write_bytes(result.stdout)
    (package/(name+'.stderr')).write_bytes(result.stderr)
    text=result.stderr.decode('utf-8','replace')
    count=re.search(r'Ran (\d+) tests',text)
    failures=re.search(r'failures=(\d+)',text)
    errors=re.search(r'errors=(\d+)',text)
    runs.append({'name':name,'command':command,'cwd':str(cwd),'exit_code':result.returncode,
        'methods':int(count[1]) if count else None,'failed_assertions':int(failures[1]) if failures else 0,
        'error_methods':int(errors[1]) if errors else 0})
assert test.read_bytes()==original
assert (baseline/'tests'/test.name).read_bytes()==original
record={'baseline_commit':'268f420e9d066e7e7859566a65c0ce65523bec82',
    'test_sha256':hashlib.sha256(original).hexdigest(),'same_final_test_bytes':True,'runs':runs,
    'scope':'Synthetic software only; baseline includes the new test file as a test overlay, no QC or market access'}
(package/'final_replay.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps(record,ensure_ascii=False))
assert runs[0]['exit_code']!=0 and runs[1]['exit_code']==0
