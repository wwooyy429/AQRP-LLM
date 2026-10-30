"""Replay this review in a NEW directory; expected defects remain failures."""
import argparse, ast, difflib, json, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--out',type=Path,required=True)
    out=parser.parse_args().out.resolve(); out.mkdir(parents=True,exist_ok=False)
    shutil.copytree(ROOT/'source',out/'source')
    for folder in ['admission_agent','receipt_agent']:
        (out/folder).mkdir()
        for file in (ROOT/folder).glob('*.py'): shutil.copy2(file,out/folder/file.name)
    for name in ['minimal_cli_switch.py','minimal_parallel_carrier.py','replay_archived_script.py','replay_public_class.py']:
        shutil.copy2(ROOT/name,out/name)
    archived=out/'source/audit/reviews/20261026-7bf716f-windows/date_cache_agent'
    date_copy=out/'portable_date_cache'; date_copy.mkdir()
    for file in archived.glob('*.py'): shutil.copy2(file,date_copy/file.name)
    file=date_copy/'independent_date_cache.py'; before=file.read_text(encoding='utf-8')
    lines=before.splitlines(True); selected=[i for i,line in enumerate(lines) if line.startswith('OLD=Path(')]
    assert len(selected)==1
    lines[selected[0]]='OLD=Path('+repr(str(ROOT/'baselines/fbe2454/source'))+')\n'
    after=''.join(lines); file.write_text(after,encoding='utf-8')
    (out/'portable_date_path.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True))),encoding='utf-8')
    file=ROOT/'run_main_checks.py'; before=file.read_text(encoding='utf-8'); after=before.replace('import json,os,shutil,subprocess,time','import json,os,shutil,subprocess,time,sys')
    old=next(line for line in after.splitlines() if line.startswith('PY=Path(')); after=after.replace(old,'PY=Path(sys.executable)')
    after=after.replace("accepted/'date_cache_agent/independent_date_cache.py'","R/'portable_date_cache/independent_date_cache.py'")
    ast.parse(after); (out/'run_main_checks.py').write_text(after,encoding='utf-8')
    (out/'portable_runner.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True))),encoding='utf-8')
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'); records=[]
    def run(label,args,expected):
        command=[sys.executable,'-B',*[str(x) for x in args]]
        result=subprocess.run(command,cwd=out,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/(label+'.stdout.txt')).write_text(result.stdout,encoding='utf-8'); (out/(label+'.stderr.txt')).write_text(result.stderr,encoding='utf-8')
        records.append(dict(label=label,command=command,exit_code=result.returncode,expected_exit=expected))
        (out/'portable_commands.json').write_text(json.dumps(records,indent=2),encoding='utf-8'); print(label,result.returncode,flush=True)
    run('historical_and_repository',['run_main_checks.py'],0)
    main_records=json.loads((out/'runs/execution_records.json').read_text(encoding='utf-8'))
    run('admission',['admission_agent/independent_admission.py'],0)
    run('receipts',['receipt_agent/independent_receipts.py','--source','source','--out','receipt_agent'],1)
    run('parallel_full',['receipt_agent/minimal_parallel_output.py','--source','source','--out','parallel_full.json'],1)
    run('adapter_recovery',['receipt_agent/adapter_recovery.py','--source','source','--out','adapter_recovery.json'],0)
    for case in ['pointer','catalog']: run('CLI_'+case,['minimal_cli_switch.py','source',case],1)
    run('parallel_boundary',['minimal_parallel_carrier.py','source'],1)
    wrong=[x for x in records if x['exit_code']!=x['expected_exit']]+[x for x in main_records if x['exit_code']!=0]
    summary={'unexpected_exit_records':wrong,'review_result':'failed_WR11_WR12','note':'Reproducing expected failures does not mean software acceptance passed.'}
    (out/'portable_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8'); print(json.dumps(summary))
    return 2 if wrong else 0
if __name__=='__main__': raise SystemExit(main())
