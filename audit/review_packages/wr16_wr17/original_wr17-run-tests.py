from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
root=Path(__file__).resolve().parents[2]
phase=sys.argv[1]
target=root
if phase=='baseline':
    target=root/'.git/repair-work/wr17-baseline-source'
    if target.exists():raise RuntimeError('Baseline output already exists')
    old=root.parent/'LLM审核/review-8f7236e-20261027/source'
    for name in ('cloud','tools','config','tests'):
        shutil.copytree(old/name,target/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(root/'tests/test_wr17_engineering_recovery.py',target/'tests/test_wr17_engineering_recovery.py')
out=root/'.git/repair-work'/('wr17-tests-'+phase)
out.mkdir(parents=True,exist_ok=True)
command=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_wr17_engineering_recovery.py','-v']
start=time.monotonic()
result=subprocess.run(command,cwd=target,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8'),capture_output=True)
(out/'stdout').write_bytes(result.stdout);(out/'stderr').write_bytes(result.stderr)
record={'phase':phase,'command':command,'cwd':str(target),'exit_code':result.returncode,'seconds':time.monotonic()-start,
        'test_raw_sha256':hashlib.sha256((target/'tests/test_wr17_engineering_recovery.py').read_bytes()).hexdigest(),
        'production_stage2_raw_sha256':hashlib.sha256((target/'tools/stage2.py').read_bytes()).hexdigest(),
        'real_cloud_or_model_calls':0}
(out/'execution_record.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps(record,ensure_ascii=True))
print(result.stderr.decode('utf-8')[-5000:])
