from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-4a94430-20261027')
REC=R/'recovery_replay';REC.mkdir(exist_ok=True)
FRAC=R/'fraction_replay';FRAC.mkdir(exist_ok=True)
for folder,name in [(REC,'recovery_agent/independent_recovery.py'),(FRAC,'receipt_agent/independent_fractional_harness.py'),(FRAC,'receipt_agent/independent_fraction_boundaries.py')]:
    data=(OLD/name).read_bytes();target=folder/Path(name).name
    if target.exists():assert target.read_bytes()==data
    else:target.write_bytes(data)
commands=[('recovery', [REC/'independent_recovery.py']),('fraction',[FRAC/'independent_fraction_boundaries.py','--source',R/'source','--out',FRAC/'results'])]
records=[]
for label,args in commands:
    cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic()
    p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    (R/(label+'_replay.stdout.txt')).write_bytes(p.stdout);(R/(label+'_replay.stderr.txt')).write_bytes(p.stderr)
    row={'label':label,'reviewed_source_commit':'8f7236ecbafcb514f07a6af4150a5afdbc1fd474','source_directory':str(R/'source'),'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'script_sha256':hashlib.sha256(Path(args[0]).read_bytes()).hexdigest()}
    records.append(row);(R/'additional_regression_records.json').write_bytes(json.dumps(records,indent=2).encode())
    print(json.dumps(row),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-1000:],flush=True)
raise SystemExit(int(any(r['exit_code'] for r in records)))
