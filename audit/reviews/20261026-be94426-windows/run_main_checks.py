from pathlib import Path
import json,os,shutil,subprocess,time
R=Path(__file__).parent;SRC=R/'source';RUN=R/'runs';RUN.mkdir(exist_ok=True)
PY=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe')
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
records=[]
def run(label,args,cwd=R):
    command=[str(PY),'-B',*[str(a) for a in args]];start=time.monotonic();p=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8')
    (RUN/(label+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(RUN/(label+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    rec=dict(label=label,command=command,cwd=str(cwd),exit_code=p.returncode,seconds=time.monotonic()-start);records.append(rec)
    (RUN/'execution_records.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(json.dumps(rec),flush=True);print((p.stdout+p.stderr)[-750:],flush=True)
work=RUN/'repository_source';shutil.copytree(SRC,work)
run('repository_verify',['tools/stages.py','verify'],work)
for suite in ['compatibility','pearson']:
    run('archived_'+suite,[SRC/'docs/review/wr08/replay.py','--source-dir',SRC,'--output-dir',RUN/('archived_'+suite),'--suite',suite])
for suite in ['numeric','atomic']:
    run('archived_'+suite,[SRC/'docs/review/wr07/replay.py','--source-dir',SRC,'--output-dir',RUN/('archived_'+suite),'--suite',suite])
run('previous_adapted_56',[SRC/'docs/review/wr04-wr06/replay.py','--source-dir',SRC,'--output-dir',RUN/'previous_adapted_56','--mode','adapted'])
archive=SRC/'audit/reviews/20261026-d0b9c98-windows'
for label,folder,script,cls in [('d0_summary','numeric_agent','exact_ic_summary_review.py','SummaryTests'),('d0_compatibility','compat_agent','public_compatibility.py','Compatibility')]:
    run(label,[R/'replay_public_class.py','--source',SRC,'--script',archive/folder/script,'--class-name',cls,'--output',RUN/label])
failed_archive=SRC/'audit/reviews/20261026-fbe2454-windows'
for label,path in [('fbe_source','source_agent/independent_source_review.py'),('fbe_boundary','source_agent/secondary_source_review_counted.py'),('fbe_collection','collection_agent/independent_collection.py')]:
    run(label,[R/'replay_archived_script.py','--source',SRC,'--script',failed_archive/path,'--output',RUN/label])
accepted=SRC/'audit/reviews/20261026-7bf716f-windows'
run('7bf_dates',[R/'replay_archived_script.py','--source',SRC,'--script',accepted/'date_cache_agent/independent_date_cache.py','--output',RUN/'7bf_dates'])
run('7bf_intervals',[accepted/'interval_agent/independent_intervals.py','--source',SRC,'--label','candidate','--out',RUN/'7bf_intervals'])

prior=SRC/"audit/reviews/20261026-e513c66-windows"
run("e513_admission",[R/"replay_archived_script.py","--source",SRC,"--script",prior/"admission_agent/independent_admission.py","--output",RUN/"e513_admission"])
run("e513_receipts",[prior/"receipt_agent/independent_receipts.py","--source",SRC,"--out",RUN/"e513_receipts"])
