from pathlib import Path
import hashlib,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
names=[n for n in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if n]
protected={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names
    if n.startswith(('cloud/','config/','tools/','tests/','audit/runtime/'))}
env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
    OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
started=time.monotonic()
process=subprocess.run([sys.executable,'-B','tools/stages.py','verify'],cwd=ROOT,env=env,capture_output=True)
(OUT/'full_verify.stdout').write_bytes(process.stdout);(OUT/'full_verify.stderr').write_bytes(process.stderr)
report=json.loads((ROOT/'audit/stage_verification.json').read_bytes())
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in protected.items())
evidence=dict(schema_version=1,kind='developer_full_offline_gate_verification',command='python -B tools/stages.py verify',
    exit_code=process.returncode,elapsed_seconds=round(time.monotonic()-started,3),source_hash=report['source_hash'],
    test_output=report['test_output'],protected_sources_and_runtime_unchanged=True,
    QC_calls=0,Research_executions=0,LEAN_submissions=0,independent_acceptance=False,financial_evidence=False,final_test_enabled=False)
(OUT/'full_offline_verification.json').write_bytes((json.dumps(evidence,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(dict(exit_code=process.returncode,source_hash=report['source_hash'],test_tail=report['test_output'][-200:])),flush=True)
raise SystemExit(process.returncode)
