"""Replay this fixed-source audit in a new output folder; known defects fail."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    src=out/'source';shutil.copytree(ROOT/'source',src)
    for folder in ['collection_agent','source_agent']:
        (out/folder).mkdir()
        for p in (ROOT/folder).glob('*.py'):shutil.copy2(p,out/folder/p.name)
    shutil.copy2(ROOT/'replay_public_class.py',out/'replay_public_class.py')
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    records=[]
    def run(label,argv,cwd=out):
        cmd=[sys.executable,'-B',*[str(a) for a in argv]];p=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/(label+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(out/(label+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
        records.append(dict(label=label,command=cmd,cwd=str(cwd),exit_code=p.returncode));(out/'execution_records.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(label,p.returncode,flush=True)
    run('repository_verify',['tools/stages.py','verify'],src)
    for suite in ['compatibility','pearson']:
        run('archived_'+suite,[src/'docs/review/wr08/replay.py','--source-dir',src,'--output-dir',out/('archived_'+suite),'--suite',suite])
    for suite in ['numeric','atomic']:
        run('archived_'+suite,[src/'docs/review/wr07/replay.py','--source-dir',src,'--output-dir',out/('archived_'+suite),'--suite',suite])
    run('adapted_56',[src/'docs/review/wr04-wr06/replay.py','--source-dir',src,'--output-dir',out/'adapted_56','--mode','adapted'])
    archived=src/'audit/reviews/20261026-d0b9c98-windows'
    for label,path,cls in [('d0_summary','numeric_agent/exact_ic_summary_review.py','SummaryTests'),('d0_compatibility','compat_agent/public_compatibility.py','Compatibility')]:
        run(label,[out/'replay_public_class.py','--source',src,'--script',archived/path,'--class-name',cls,'--output',out/label])
    run('collection_independent',[out/'collection_agent/independent_collection.py'])
    run('source_independent',[out/'source_agent/independent_source_review.py'])
    run('source_boundary',[out/'source_agent/secondary_source_review_counted.py'])
    run('WR09_minimal',[ROOT/'minimal_missing_date.py',src])
    run('WR10_minimal',[ROOT/'minimal_history_boundary.py',src])
    failing={'source_independent','source_boundary','WR09_minimal','WR10_minimal'}
    bad=[r for r in records if r['exit_code']!=(1 if r['label'] in failing else 0)]
    print(json.dumps({'known_open_findings':['WR-09','WR-10'],'unexpected_exit_records':bad,'software_acceptance':'failed'}))
    return 2 if bad else 1
if __name__=='__main__':raise SystemExit(main())
