"""Reproduce 4a review in a NEW directory; WR15 remains nonblocking."""
import argparse,ast,difflib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    out=parser.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=False);shutil.copytree(ROOT/'source',out/'source')
    for folder in ['receipt_agent','recovery_agent']:
        (out/folder).mkdir()
        for file in (ROOT/folder).glob('*.py'):shutil.copy2(file,out/folder/file.name)
    shutil.copy2(ROOT/'receipt_agent/official_mcp_schema_2025-11-25.json',out/'receipt_agent/official_mcp_schema_2025-11-25.json')
    for name in ['minimal_cli_switch.py','minimal_parallel_carrier.py','minimal_nested_annotations.py','minimal_fractional_clock.py','minimal_manifest_hash.py','replay_archived_script.py','replay_public_class.py']:
        shutil.copy2(ROOT/name,out/name)
    source=out/'source';date_copy=out/'portable_date_cache';date_copy.mkdir()
    for file in (source/'audit/reviews/20261026-7bf716f-windows/date_cache_agent').glob('*.py'):shutil.copy2(file,date_copy/file.name)
    file=date_copy/'independent_date_cache.py';before=file.read_text(encoding='utf-8');lines=before.splitlines(True)
    selected=[i for i,line in enumerate(lines) if line.startswith('OLD=Path(')];assert len(selected)==1
    lines[selected[0]]='OLD=Path('+repr(str(ROOT/'baselines/fbe2454/source'))+')\n';after=''.join(lines);file.write_text(after,encoding='utf-8')
    (out/'portable_date_path.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True))),encoding='utf-8')
    before=(ROOT/'run_main_checks.py').read_text(encoding='utf-8');after=before.replace('import json,os,shutil,subprocess,time','import json,os,shutil,subprocess,time,sys')
    old=next(line for line in after.splitlines() if line.startswith('PY=Path('));after=after.replace(old,'PY=Path(sys.executable)')
    after=after.replace("accepted/'date_cache_agent/independent_date_cache.py'","R/'portable_date_cache/independent_date_cache.py'")
    target='run("dc_annotations_role_corrected",'
    binding='schema_out=RUN/"dc_annotations_role_corrected";schema_out.mkdir(exist_ok=False)\nshutil.copy2(dc/"receipt_agent/official_mcp_schema_2025-11-25.json",schema_out/"official_mcp_schema_2025-11-25.json")\n'
    assert after.count(target)==1;after=after.replace(target,binding+target)
    ast.parse(after);(out/'run_main_checks.py').write_text(after,encoding='utf-8')
    (out/'portable_runner.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True))),encoding='utf-8')
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');records=[]
    def run(label,args,expected):
        command=[sys.executable,'-B',*[str(x) for x in args]];p=subprocess.run(command,cwd=out,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/(label+'.stdout.txt')).write_text(p.stdout,encoding='utf-8');(out/(label+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
        records.append(dict(label=label,command=command,exit_code=p.returncode,expected_exit=expected));(out/'portable_commands.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(label,p.returncode,flush=True)
    run('historical_and_repository',['run_main_checks.py'],0);old_records=json.loads((out/'runs/execution_records.json').read_text(encoding='utf-8'))
    run('new_fractional_boundaries',['receipt_agent/independent_fraction_boundaries.py','--source',source,'--out',out/'receipt_agent'],0)
    run('recovery_replay',['recovery_agent/independent_recovery.py'],0)
    run('new_parser_recovery',['recovery_agent/new_parser_recovery.py'],0)
    run('WR14_current',['minimal_fractional_clock.py',source],0)
    run('WR14_old',['minimal_fractional_clock.py',ROOT/'baselines/dc49f0f/source'],1)
    run('WR13_current',['minimal_nested_annotations.py',source],0)
    run('WR11_current',['minimal_parallel_carrier.py',source],0)
    for case in ['pointer','catalog']:run('WR12_'+case,['minimal_cli_switch.py',source,case],0)
    probe=source/'audit/reviews/20261027-dc49f0f-windows/receipt_agent/fractional_clock_probe.py'
    for label,src,expected in [('current',source,0),('old',ROOT/'baselines/dc49f0f/source',1)]:
        run('WR14_full_'+label,[probe,'--source',src,'--out',out/('full_'+label)],expected)
    run('WR15_nonblocking_raw_hash',['minimal_manifest_hash.py',source],1)
    wrong=[x for x in records if x['exit_code']!=x['expected_exit']]+[x for x in old_records if x['exit_code']!=0]
    summary={'unexpected_exit_records':wrong,'WR14':'passed_after_fix','nonblocking':['WR-15'],'whole_system':'not_accepted'}
    (out/'portable_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary));return 2 if wrong else 0
if __name__=='__main__':raise SystemExit(main())
