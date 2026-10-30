import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time

root = Path(__file__).resolve().parents[2]
review = root.parent / 'LLM审核' / 'review-dc49f0f-20261027'
phase = sys.argv[1]
out = root / '.git' / 'repair-work' / ('wr14-original-' + phase)
out.mkdir(parents=True, exist_ok=True)
(out/'annotations').mkdir(exist_ok=True)
shutil.copyfile(review/'receipt_agent'/'official_mcp_schema_2025-11-25.json', out/'annotations'/'official_mcp_schema_2025-11-25.json')
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
suites = [('minimal', review / 'minimal_fractional_clock.py', [str(root)]),
          ('fractional', review / 'receipt_agent' / 'fractional_clock_probe.py', ['--source', str(root), '--out', str(out / 'fractional')]),
          ('annotations', review / 'receipt_agent' / 'independent_annotations_role_corrected.py', ['--source', str(root), '--out', str(out / 'annotations')])]
records = []
for name, script, args in suites:
    command = [sys.executable, '-B', str(script), *args]
    start = time.monotonic()
    result = subprocess.run(command, cwd=root, env=env, capture_output=True)
    (out / (name + '.stdout')).write_bytes(result.stdout)
    (out / (name + '.stderr')).write_bytes(result.stderr)
    record = dict(suite=name, command=command, cwd=str(root), exit_code=result.returncode, elapsed_seconds=time.monotonic()-start,
                  script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(), stdout=name+'.stdout', stderr=name+'.stderr')
    records.append(record)
    print(json.dumps(record, ensure_ascii=True), flush=True)
record = dict(phase=phase, source_commit_before_repair='dc49f0f3037918f3ce4413665c59b164a8d6e2b7',
              parser_normalized_sha256=hashlib.sha256((root/'cloud/qresearch/engineering_receipts.py').read_text(encoding='utf-8-sig').encode()).hexdigest(),
              scripts_unchanged=True, synthetic_only=True, real_calls=0, records=records)
(out/'execution_records.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
