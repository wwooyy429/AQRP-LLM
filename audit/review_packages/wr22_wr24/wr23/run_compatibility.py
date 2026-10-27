from pathlib import Path
import json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
modules=['test_wr23_prepare_protocol','test_wr21_research_dispatch','test_wr17_engineering_recovery','test_native_research_failure',
         'test_research_error_representations','test_engineering_receipts','test_native_runtime_failure','test_native_backtest_rejection']
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONPATH=str(ROOT/'tests'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
cmd=[sys.executable,'-B','-m','unittest','-v',*modules]
start=time.monotonic();r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
(OUT/'compatibility.stdout').write_bytes(r.stdout);(OUT/'compatibility.stderr').write_bytes(r.stderr)
record={'command':cmd,'exit_code':r.returncode,'elapsed_seconds':round(time.monotonic()-start,3),
        'modules':modules,'new_QC_calls':0,'new_authoritative_budget_writes':0,'independent_acceptance':False}
(OUT/'compatibility_execution.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record));sys.exit(r.returncode)
