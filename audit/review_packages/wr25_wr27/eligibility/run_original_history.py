from pathlib import Path
import hashlib
import importlib.util
import json
import os
import runpy
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
WORK = OUT / 'independent_history'
SOURCE = WORK / 'source'
ORIGINAL = Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ccad61d-20261027/cert_agent')
if '--child' in sys.argv:
    sys.path.insert(0, str(SOURCE / 'cloud'))
    spec = importlib.util.spec_from_file_location('cert_fixture', WORK / 'cert_fixture.py')
    fixture = importlib.util.module_from_spec(spec)
    sys.modules['cert_fixture'] = fixture
    spec.loader.exec_module(fixture)
    fixture.SOURCE = SOURCE
    runpy.run_path(str(WORK / 'independent_history_boundaries.py'), run_name='__main__')
else:
    WORK.mkdir(exist_ok=True)
    (SOURCE / 'audit').mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'cloud', SOURCE / 'cloud', ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    shutil.copyfile(ROOT / 'audit/stage_verification.json', SOURCE / 'audit/stage_verification.json')
    original_hashes = {}
    for name in ('cert_fixture.py', 'independent_history_boundaries.py'):
        shutil.copyfile(ORIGINAL / name, WORK / name)
        original_hashes[name] = hashlib.sha256((WORK / name).read_bytes()).hexdigest()
        assert (WORK / name).read_bytes() == (ORIGINAL / name).read_bytes()
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--child']
    start = time.monotonic()
    r = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONIOENCODING='utf-8',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'), capture_output=True)
    (OUT / 'original_history.stdout').write_bytes(r.stdout)
    (OUT / 'original_history.stderr').write_bytes(r.stderr)
    report = json.loads((WORK / 'history_first_results.json').read_bytes()) if (WORK / 'history_first_results.json').exists() else None
    for name in ('history_first_results.json', 'history_first_unittest.txt'):
        if (WORK / name).exists():shutil.copyfile(WORK / name, OUT / ('original_' + name))
    record = {'command':command,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3),
        'original_scripts_unchanged':True,'original_script_raw_sha256':original_hashes,
        'fixture_adaptations':['SOURCE bound to a fresh projection of current cloud Python and original verification metadata required by this fixture',
            'Current cloud library hashes copied byte-for-byte; no expectations or original scripts edited',
            'Original fixed_commit literal is retained as historical script label, not current source identity',
            'No full-repository or concurrent real-source rglob for unchanged-source assertion'],
        'production_raw_sha256':hashlib.sha256((ROOT/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),
        'methods':report['methods'] if report else None,'scenario_checks':report['scenario_checks'] if report else None,
        'passed_methods':report['passed_methods'] if report else None,'failed_methods':report['failed_methods'] if report else None,
        'error_methods':report['error_methods'] if report else None,
        'source_unchanged_in_isolated_projection':report['source_unchanged'] if report else None,
        'network_attempts':report['network_attempts'] if report else None,'independent_acceptance':False}
    (OUT/'original_history_execution.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record))
    if r.returncode:print(r.stderr.decode('utf-8'))
    sys.exit(r.returncode)
