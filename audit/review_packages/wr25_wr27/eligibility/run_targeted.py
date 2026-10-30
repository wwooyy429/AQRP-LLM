from pathlib import Path
import hashlib
import io
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
names = [
    'test_unmapped_current_types_with_missing_liquidity_remain_unknown',
    'test_expired_mapping_or_exclusion_without_current_coverage_is_unknown',
    'test_future_current_coverage_cannot_preemptively_exclude_historical_sid',
    'test_current_coverage_knowledge_equality_and_one_microsecond_delay',
    'test_explicit_current_exclusions_do_not_need_unrelated_unknown_fields',
    'test_future_only_master_does_not_leak_a_sid_into_historical_obligations',
    'test_known_liquidity_sid_without_any_master_coverage_is_unknown_even_below_cutoff',
    'test_closed_classification_semantics_never_infer_excluded_from_unknown',
]
cmd = [sys.executable, '-B', '-m', 'unittest', '-v', *['test_data_certification.DataCertificationTests.' + name for name in names]]
start = time.monotonic()
r = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT/'tests')+os.pathsep+str(ROOT/'cloud'),
    PYTHONIOENCODING='utf-8', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'), capture_output=True)
label = sys.argv[1]
(OUT / (label + '.stdout')).write_bytes(r.stdout)
(OUT / (label + '.stderr')).write_bytes(r.stderr)
record = {'command':cmd,'exit_code':r.returncode,'methods':len(names),'seconds':round(time.monotonic()-start,3),
    'production_raw_sha256':hashlib.sha256((ROOT/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),
    'synthetic_only':True,'provider_calls':0,'independent_acceptance':False}
(OUT / (label+'_execution.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
if r.returncode:print(r.stderr.decode('utf-8'))
sys.exit(r.returncode)
