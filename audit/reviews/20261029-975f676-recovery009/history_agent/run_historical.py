from pathlib import Path
import subprocess, sys, json, shutil, hashlib, os, time
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
S=O.parent/'source'
W=O/'replay_context'
W.mkdir(exist_ok=False)
shutil.copytree(S,W/'source')
specs=[
 ('numeric_time','audit/reviews/20261026-fe4374c-windows/numeric_agent/numeric_time_review.py',[]),
 ('pearson','audit/reviews/20261026-7b0dcce-windows/numeric_agent/exact_pearson_review.py',[]),
 ('ic_summary','audit/reviews/20261026-d0b9c98-windows/numeric_agent/exact_ic_summary_review.py',[]),
 ('certification','audit/reviews/20261027-44676db-windows/cert_agent/candidate_original/independent_certification.py',[]),
 ('carriers_original','audit/reviews/20261026-be94426-windows/receipt_agent/independent_carrier_boundaries_corrected.py',['--source',str(W/'source'),'--out',str(O/'carriers_original_results')]),
 ('wr25_wr26','audit/reviews/20261027-44676db-windows/cert_agent/candidate_original/minimal_wr25_wr26.py',['--source',str(W/'source'),'--output',str(O/'wr25_wr26_results.json')])
]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(W))
(W/'sitecustomize.py').write_text('import socket\ndef deny(*a,**k): raise AssertionError("Independent audit forbids network")\nsocket.socket.connect=deny\nsocket.create_connection=deny\n',encoding='utf-8')
records=[]
for label,original,args in specs:
    folder=W/label;folder.mkdir()
    dest=folder/Path(original).name
    shutil.copyfile(S/original,dest)
    if label=='certification':
        shutil.copyfile(S/'audit/reviews/20261027-44676db-windows/cert_agent/cert_fixture.py',folder/'cert_fixture.py')
    before=hashlib.sha256(dest.read_bytes()).hexdigest()
    cmd=[sys.executable,'-B',str(dest),*args]
    t=time.monotonic();p=subprocess.run(cmd,cwd=W,capture_output=True,env=env)
    (O/(label+'.stdout')).write_bytes(p.stdout);(O/(label+'.stderr')).write_bytes(p.stderr)
    rec={'label':label,'reviewed_source_commit':'975f676d62b561689909744f9e7236290e3f5fcb','historical_script_path':original,'script_raw_sha256':before,'script_changed':False,'command':cmd,'cwd':str(W),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()}
    records.append(rec);(O/'historical_execution.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps({'label':label,'exit_code':p.returncode,'seconds':rec['seconds']}),flush=True)
    print((p.stdout+p.stderr).decode('utf-8','replace')[-1000:],flush=True)
print('Historical replays completed; failures retained for interpretation.',flush=True)
