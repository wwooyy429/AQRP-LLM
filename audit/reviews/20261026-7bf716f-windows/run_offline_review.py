"""Replay fixed 7bf software review offline in a new output directory."""
from pathlib import Path
import argparse,difflib,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);src=out/'source';shutil.copytree(ROOT/'source',src)
    base=ROOT/'baselines/fbe2454/source'
    for folder in ['date_cache_agent','interval_agent']:
        (out/folder).mkdir()
        for p in (ROOT/folder).glob('*.py'):shutil.copy2(p,out/folder/p.name)
    # Bind the independent test's old-source path in a separate output copy.
    # Child legacy-writer processes read this same copy; no assertion changes.
    path=out/'date_cache_agent/independent_date_cache.py';before=path.read_text(encoding='utf-8')
    lines=before.splitlines(True);matches=[i for i,line in enumerate(lines) if line.startswith('OLD=Path(')]
    if len(matches)!=1:raise ValueError('Unexpected reviewer baseline-path declaration')
    lines[matches[0]]='OLD=Path('+repr(str(base.resolve()))+')\n';after=''.join(lines);path.write_text(after,encoding='utf-8')
    (out/'portable_baseline_path.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='original-reviewer-script',tofile='portable-path-copy')),encoding='utf-8')
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');records=[]
    def run(label,args,cwd=out):
        cmd=[sys.executable,'-B',*[str(v) for v in args]];p=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/(label+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(out/(label+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
        records.append(dict(label=label,command=cmd,cwd=str(cwd),exit_code=p.returncode));(out/'execution_records.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(label,p.returncode,flush=True)
    run('repository_verify',['tools/stages.py','verify'],src)
    for suite in ['compatibility','pearson']:
        run('archived_'+suite,[src/'docs/review/wr08/replay.py','--source-dir',src,'--output-dir',out/('archived_'+suite),'--suite',suite])
    for suite in ['numeric','atomic']:
        run('archived_'+suite,[src/'docs/review/wr07/replay.py','--source-dir',src,'--output-dir',out/('archived_'+suite),'--suite',suite])
    run('adapted_56',[src/'docs/review/wr04-wr06/replay.py','--source-dir',src,'--output-dir',out/'adapted_56','--mode','adapted'])
    d0=src/'audit/reviews/20261026-d0b9c98-windows'
    for label,file,cls in [('d0_summary','numeric_agent/exact_ic_summary_review.py','SummaryTests'),('d0_compatibility','compat_agent/public_compatibility.py','Compatibility')]:
        run(label,[ROOT/'replay_public_class.py','--source',src,'--script',d0/file,'--class-name',cls,'--output',out/label])
    archive=src/'audit/reviews/20261026-fbe2454-windows'
    for label,file in [('source','source_agent/independent_source_review.py'),('boundary','source_agent/secondary_source_review_counted.py'),('collection','collection_agent/independent_collection.py')]:
        run('fbe_'+label,[ROOT/'replay_archived_script.py','--source',src,'--script',archive/file,'--output',out/('fbe_'+label)])
    for label,file in [('source','source_agent/independent_source_review.py'),('boundary','source_agent/secondary_source_review_counted.py')]:
        run('baseline_'+label,[ROOT/'replay_archived_script.py','--source',base,'--script',archive/file,'--output',out/('baseline_'+label)])
    run('new_dates',[out/'date_cache_agent/independent_date_cache.py'])
    run('new_intervals',[out/'interval_agent/independent_intervals.py','--source',src,'--label','candidate','--out',out/'interval_agent'])
    for filename in ['minimal_missing_date.py','minimal_history_boundary.py']:
        run('current_'+filename,[ROOT/filename,src]);run('baseline_'+filename,[ROOT/filename,base])
    bad=[r for r in records if r['exit_code']!=(1 if r['label'].startswith('baseline_') else 0)]
    print(json.dumps({'unexpected_exit_records':bad,'repair_software_scope':'passed_after_fix','whole_system':'not_accepted'}));return 2 if bad else 0
if __name__=='__main__':raise SystemExit(main())
