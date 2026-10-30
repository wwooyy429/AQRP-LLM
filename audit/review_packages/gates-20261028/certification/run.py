from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
tracked=[p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p]
protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tracked}
env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
    OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1')
cases=[('capabilities',['tools/data_certification.py','capabilities'],0),
    ('certification_tests',['-m','unittest','discover','-s','tests','-p','test_data_certification.py','-v'],0),
    ('ingestion_tests',['-m','unittest','discover','-s','tests','-p','test_ingestion.py','-v'],0),
    ('empty_financial_probe',[str(OUT/'probe.py')],0),
    ('empty_plan_cli',['tools/data_certification.py','validate-plan','--plan-file',str(OUT/'synthetic_empty_financial_plan.json')],0),
    ('dispatch_cli_absent',['tools/data_certification.py','dispatch'],2)]
runs=[]
for label,args,expected in cases:
    start=time.monotonic()
    p=subprocess.run([sys.executable,'-X','utf8','-B',*args],cwd=ROOT,env=env,capture_output=True)
    (OUT/(label+'.stdout')).write_bytes(p.stdout);(OUT/(label+'.stderr')).write_bytes(p.stderr)
    record={'label':label,'command':['python','-X','utf8','-B',*args],'exit_code':p.returncode,
        'expected_exit_code':expected,'seconds':round(time.monotonic()-start,3),
        'stdout':label+'.stdout','stderr':label+'.stderr'}
    runs.append(record);print(json.dumps(record),flush=True)
    if p.returncode!=expected:raise SystemExit('Unexpected exit: '+label)
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items())
proof={'schema_version':1,'kind':'developer_readonly_gate_verification_synthetic_only',
    'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    'runs':runs,'all_expected_exits':True,'protected_tracked_files_unchanged':len(protected),
    'QC_calls':0,'Research_executions':0,'LEAN_submissions':0,'model_calls':0,
    'budget_changed':False,'product_source_changes':False,'final_test_enabled':False,
    'financial_evidence':False,'independent_acceptance':False}
(OUT/'execution.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':True,'runs':len(runs),'tracked_files_unchanged':len(protected)}),flush=True)
