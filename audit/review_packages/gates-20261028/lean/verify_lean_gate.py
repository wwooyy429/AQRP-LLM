from pathlib import Path
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
COMMIT='d23c0ab93ceba71529eb813e349c8dfdcbb5ea88'
ATTEMPT='37dc855045e14ca49c88fd9d75f40cf7'
BACKTEST='3e68866a46ca88ff16481c31b3c2c822'
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
from qresearch.artifacts import MemoryArtifactStore,content_hash
from qresearch.registry import Registry
from qresearch.engineering_receipts import backtest_submission
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge

def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(name,value):(OUT/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
tracked=[p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p]
protected={p:sha((ROOT/p).read_bytes()) for p in tracked if p.startswith(('cloud/','config/','tools/','tests/','audit/runtime/'))}
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==COMMIT
store=MemoryArtifactStore()
for name in tracked:
    if name.startswith('audit/runtime/'):
        store._data[name[len('audit/runtime/'):]]=(ROOT/name).read_bytes()
baseline=json.loads((ROOT/'audit/runtime/registry/baseline.json').read_bytes())
registry=Registry(store,baseline)
snapshot=registry.snapshot()
record=next(r for r in snapshot['attempts'] if r['attempt_id']==ATTEMPT)
assert record['status']=='pending' and record['external_id']==BACKTEST
assert {k:v['total'] for k,v in snapshot['usage'].items()}==dict(configurations=12,research=15,lean=2)
journal=(ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
assert len(journal.splitlines())==46
admitted=json.loads((ROOT/f'audit/runtime/engineering/admitted-inputs/{ATTEMPT}.json').read_bytes())
payload,deployment=admitted['payload'],admitted['deployment']
assert sha((ROOT/admitted['input_path']).read_bytes())==deployment['input_hash']
plan=EngineeringTaskPlan.from_dict(payload['plan'],discovered_project_ids=[payload['identity']['project_id']])
assert len(plan.to_dict()['required_checks']['research'])==13
assert len(plan.to_dict()['required_checks']['lean'])==7
native_packet=json.loads((ROOT/f'audit/tool_observations/{ATTEMPT}-submission.json').read_bytes())
parsed=backtest_submission(payload,deployment,native_packet)
assert parsed['external_id']==BACKTEST
bridge=EngineeringTaskBridge(registry,plan)
assert payload['research_resolution']==bridge._research_result()['cloud_report']['resolution']
saved=bridge._recorded_submission(payload)
assert saved['receipt_ref']['sha256']==content_hash(parsed)
private=OUT/'fixed-fixture'
assert not private.exists()
private.mkdir()
raw=subprocess.check_output(['git','archive','--format=zip',COMMIT,'cloud','audit/runtime'],cwd=ROOT)
(OUT/'fixed-fixture.zip').write_bytes(raw)
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    for item in archive.infolist():
        destination=(private/item.filename).resolve()
        assert destination.is_relative_to(private.resolve())
    archive.extractall(private)
suite=OUT/'full-capacity-suite'
suite.mkdir()
origin=ROOT/'audit/reviews/20261028-4520fd1-recheck/evidence/budget_recheck'
for name in ('frontier_support.py','process_settlement_worker.py','settlement_frontier_tests.py'):
    shutil.copyfile(origin/name,suite/name)
environment=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
    OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',AQRP_REVIEW_SOURCE=str(private))
commands=[('engineering_receipts',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_engineering_receipts.py','-q'],ROOT),
    ('native_runtime_failure',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_native_runtime_failure.py','-q'],ROOT),
    ('normal_round',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_normal_engineering_round.py','-q'],ROOT),
    ('full_capacity',[sys.executable,'-B',str(suite/'settlement_frontier_tests.py')],suite)]
runs=[]
for label,command,cwd in commands:
    started=time.monotonic()
    result=subprocess.run(command,cwd=cwd,env=environment,capture_output=True)
    (OUT/(label+'.stdout')).write_bytes(result.stdout)
    (OUT/(label+'.stderr')).write_bytes(result.stderr)
    text=(result.stdout+result.stderr).decode('utf-8')
    matches=re.findall(r'Ran (\d+) tests? in',text)
    runs.append(dict(label=label,command=command,cwd=str(cwd),exit_code=result.returncode,
        seconds=round(time.monotonic()-started,3),methods=int(matches[-1]) if matches else None,
        stdout_sha256=sha(result.stdout),stderr_sha256=sha(result.stderr)))
    print(json.dumps(runs[-1]),flush=True)
    if result.returncode:
        write('execution_failed.json',runs)
        raise SystemExit(result.returncode)
capacity=json.loads((suite/'first_results.json').read_bytes())
assert capacity['methods']==7 and capacity['failure_records']==capacity['error_records']==0
for name,digest in protected.items():assert sha((ROOT/name).read_bytes())==digest,name
evidence=dict(schema_version=1,kind='developer_readonly_original_LEAN_gate_verification',
    source_commit=COMMIT,runtime_source_commit='662ccd876b67ca0949f921a53c4c33df37cfbbf1',
    attempt_id=ATTEMPT,backtest_id=BACKTEST,identity=payload['identity'],deployment=deployment,
    existing_ledger_status=record['status'],authoritative_events=46,usage=snapshot['usage'],
    required_checks=plan.to_dict()['required_checks'],native_submission_verified=True,
    native_submission_packet_sha256=sha((ROOT/f'audit/tool_observations/{ATTEMPT}-submission.json').read_bytes()),
    original_input_hash_verified=True,Research_resolution_matches_original_payload=True,
    log_query='AQRP_ENGINEERING '+ATTEMPT,actual_terminal_obtained=False,actual_runtime_checks=None,
    actual_orders=None,LEAN_gate='insufficient_evidence_no_terminal',
    fixed_fixture_git_archive_sha256=sha(raw),runs=runs,capacity_named_scenarios=capacity['named_scenarios'],
    actual_full_capacity_processes=capacity['native_Windows_processes'],capacity_thread_workers=capacity['thread_workers'],
    protected_files_unchanged=len(protected),QC_calls=0,Research_calls=0,LEAN_submissions=0,
    true_ledger_writes=0,product_edits=0,independent_GPT_Work_acceptance=False,financial_evidence=False,final_test_enabled=False,
    limitations=['synthetic tests do not supply missing live terminal or original worker source',
        'native Total Orders is enforced only when present; actual zero-order claim requires delivered native counter or equivalent actual order evidence',
        'an explicit runtime-error terminal can settle failure only, without manufacturing seven results or zero orders',
        'native identity originates from trusted actual I/O context; hashes are not a remote signature'],
    execution_note='Copied immutable Git metadata/cloud fixture into private work area for all full-capacity synthetic settlement; original archived scripts and production data remain unchanged.')
write('result.json',evidence)
print(json.dumps(dict(verified=True,runs=[{k:r[k] for k in ('label','methods','exit_code')} for r in runs],
    capacity_named_scenarios=capacity['named_scenarios'],LEAN_gate=evidence['LEAN_gate'],protected_files_unchanged=len(protected))),flush=True)
