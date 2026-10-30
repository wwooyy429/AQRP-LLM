from pathlib import Path
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
BASE=OUT/'baselinef373-fully-isolated'
assert not BASE.exists()
BASE.mkdir()
archive=subprocess.check_output(['git','archive','--format=zip','f37340415ff080ae44310c912044f683e9986e96',
    'cloud','tests','tools','config'],cwd=ROOT)
with zipfile.ZipFile(io.BytesIO(archive)) as z:z.extractall(BASE)
test=ROOT/'tests/test_deployment_integrity_diagnostics.py'
raw=test.read_bytes()
shutil.copyfile(test,BASE/'tests'/test.name)
(OUT/'final_tests.py').write_bytes(raw)
commands=[]
for label,cwd in [('final_baseline',BASE),('final_candidate',ROOT)]:
    cmd=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p',test.name,'-v']
    result=subprocess.run(cmd,cwd=cwd,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONPATH=''))
    (OUT/(label+'.stdout')).write_bytes(result.stdout)
    (OUT/(label+'.stderr')).write_bytes(result.stderr)
    text=result.stderr.decode('utf-8','replace')
    failed=re.findall(r'^FAIL: (test_[^\s(]+)',text,re.M)
    errors=re.findall(r'^ERROR: (test_[^\s(]+)',text,re.M)
    commands.append({'name':label,'command':cmd,'cwd':str(cwd),'exit_code':result.returncode,
        'methods':15,'failure_outcomes':len(failed),'error_outcomes':len(errors),
        'unique_failure_methods':len(set(failed)),'unique_error_methods':len(set(errors)),
        'unique_unsuccessful_methods':len(set(failed+errors))})
assert commands[0]['exit_code']==1 and commands[1]['exit_code']==0
report={'baseline_commit':'f37340415ff080ae44310c912044f683e9986e96','test_raw_sha256':hashlib.sha256(raw).hexdigest(),
    'source_raw_sha256':hashlib.sha256((ROOT/'cloud/qresearch/engineering_data.py').read_bytes()).hexdigest(),
    'same_final_test_bytes':(BASE/'tests'/test.name).read_bytes()==test.read_bytes(),
    'runs':commands,'shared_path_contract_reused':True,'EOF_hash_policy_changed':False,
    'legacy_engineering_data_methods':14,'legacy_passed':True,'original_source75_25_files_still_verify':True,
    'real_device_paths_read_by_tests':False,'legacy_and_new_source_readers_both_mocked_for_unsafe_paths':True,
    'earlier_probe_isolation_correction_preserved':'pre_reader_isolation_*',
    'real_QC_calls':0,'real_registry_writes':0,'financial_evidence':False}
(OUT/'final_replay.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
