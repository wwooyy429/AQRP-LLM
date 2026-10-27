from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
REVIEW=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ea6053e-20261027/cert_agent')
WORK=HERE/'independent_current'
WORK.mkdir(exist_ok=False)
SOURCE=WORK/'source'
for name in ('cloud','tools','config'):
    shutil.copytree(ROOT/name,SOURCE/name,ignore=shutil.ignore_patterns('__pycache__'))
(SOURCE/'audit').mkdir()
shutil.copyfile(ROOT/'audit/stage_verification.json',SOURCE/'audit/stage_verification.json')
launcher=WORK/'launch.py'
launcher.write_text('''from pathlib import Path
import runpy,sys,subprocess
source=Path(sys.argv[1]);script=Path(sys.argv[2])
sys.path[:0]=[str(source/'cloud'),str(script.parent)]
original=subprocess.run
def adapted(cmd,*args,**kwargs):
    cmd=list(cmd)
    if str(cmd[0]).lower().endswith('python.exe'):cmd[0]=sys.executable
    return original(cmd,*args,**kwargs)
subprocess.run=adapted
sys.argv=[str(script)]
runpy.run_path(str(script),run_name='__main__')
''',encoding='utf-8')
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
reports=[]
for label,original in [('old13',REVIEW/'candidate_original/independent_certification.py'),('new9',REVIEW/'independent_fix_boundaries.py')]:
    output=WORK/label
    output.mkdir()
    script=output/original.name
    fixture=output/'cert_fixture.py'
    shutil.copyfile(original,script)
    shutil.copyfile(REVIEW/'cert_fixture.py',fixture)
    cmd=[sys.executable,'-B',str(launcher),str(SOURCE),str(script)]
    start=time.monotonic();result=subprocess.run(cmd,cwd=ROOT,capture_output=True,env=env)
    (HERE/(label+'.stdout')).write_bytes(result.stdout)
    (HERE/(label+'.stderr')).write_bytes(result.stderr)
    report_name='first_results.json' if label=='old13' else 'boundaries_first_results.json'
    results=json.loads((output/report_name).read_text(encoding='utf-8-sig'))
    shutil.copyfile(output/report_name,HERE/(label+'_results.json'))
    actual_production=SOURCE/'cloud/qresearch/data_certification.py'
    assert actual_production.read_bytes()==(ROOT/'cloud/qresearch/data_certification.py').read_bytes()
    report={'label':label,'command':cmd,'exit_code':result.returncode,'elapsed_seconds':round(time.monotonic()-start,3),
      'original_script_raw_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
      'copied_script_byte_identical':original.read_bytes()==script.read_bytes(),
      'copied_fixture_byte_identical':(REVIEW/'cert_fixture.py').read_bytes()==fixture.read_bytes(),
      'production_raw_sha256':hashlib.sha256(actual_production.read_bytes()).hexdigest(),
      'method_count':results['methods'],'failed_methods':results['failed_methods'],'error_methods':results['error_methods'],
      'scenario_checks':results['scenario_checks'],'source_unchanged':results['source_unchanged'],
      'adaptations':['Fresh current cloud/tools/config and source-hash metadata snapshot, isolated outputs',
                     'Original scripts/expectations unchanged; original interpreter alias redirected to current locked venv'],
      'embedded_old_fixed_commit_labels_are_historical':True,'new_cloud_calls':0,'independent_acceptance':False}
    (HERE/(label+'_execution.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    reports.append(report)
    print(json.dumps(report),flush=True)
(HERE/'original_suites_summary.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
sys.exit(0 if all(r['exit_code']==0 for r in reports) else 1)
