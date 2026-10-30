from pathlib import Path
import json, os, shutil, subprocess, time, hashlib
R = Path(__file__).parent
SRC = R / 'source'
RUN = R / 'runs'
RUN.mkdir(exist_ok=True)
PY = Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe')
env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
env['AQRP_REVIEW_HISTORICAL_RUNTIME'] = str(R/'legacy_pending_runtime')
records = []

def run(label, args, cwd=R):
    command = [str(PY), '-B', *map(str, args)]
    start = time.monotonic()
    p = subprocess.run(command, cwd=cwd, env=env, capture_output=True)
    (RUN / (label + '.stdout.txt')).write_bytes(p.stdout)
    (RUN / (label + '.stderr.txt')).write_bytes(p.stderr)
    rec = dict(label=label, command=command, cwd=str(cwd), exit_code=p.returncode, seconds=time.monotonic()-start,
               stdout_sha256=hashlib.sha256(p.stdout).hexdigest(), stderr_sha256=hashlib.sha256(p.stderr).hexdigest())
    records.append(rec)
    (RUN / 'execution_records.json').write_bytes(json.dumps(records, indent=2).encode())
    print(json.dumps(rec), flush=True)
    print((p.stdout+p.stderr).decode('utf-8', errors='replace')[-650:], flush=True)

work = RUN / 'repository_source'
shutil.copytree(SRC, work)
run('repository_verify', ['tools/stages.py', 'verify'], work)
for suite in ['compatibility', 'pearson']:
    run('archived_'+suite, [SRC/'docs/review/wr08/replay.py', '--source-dir', SRC, '--output-dir', RUN/('archived_'+suite), '--suite', suite])
for suite in ['numeric', 'atomic']:
    run('archived_'+suite, [SRC/'docs/review/wr07/replay.py', '--source-dir', SRC, '--output-dir', RUN/('archived_'+suite), '--suite', suite])
run('previous_adapted_56', [SRC/'docs/review/wr04-wr06/replay.py', '--source-dir', SRC, '--output-dir', RUN/'previous_adapted_56', '--mode', 'adapted'])
archive = SRC/'audit/reviews/20261026-d0b9c98-windows'
for label, folder, script, cls in [('d0_summary','numeric_agent','exact_ic_summary_review.py','SummaryTests'), ('d0_compatibility','compat_agent','public_compatibility.py','Compatibility')]:
    run(label, [R/'replay_public_class.py', '--source', SRC, '--script', archive/folder/script, '--class-name', cls, '--output', RUN/label])
archive = SRC/'audit/reviews/20261026-fbe2454-windows'
for label, path in [('fbe_source','source_agent/independent_source_review.py'), ('fbe_boundary','source_agent/secondary_source_review_counted.py'), ('fbe_collection','collection_agent/independent_collection.py')]:
    run(label, [R/'replay_archived_script.py', '--source', SRC, '--script', archive/path, '--output', RUN/label])
archive = SRC/'audit/reviews/20261026-7bf716f-windows'
run('7bf_dates', [R/'replay_archived_script.py', '--source', SRC, '--script', archive/'date_cache_agent/independent_date_cache.py', '--output', RUN/'7bf_dates'])
run('7bf_intervals', [archive/'interval_agent/independent_intervals.py', '--source', SRC, '--label', 'candidate', '--out', RUN/'7bf_intervals'])
archive = SRC/'audit/reviews/20261026-e513c66-windows'
run('e513_admission', [R/'replay_archived_script.py', '--source', SRC, '--script', R/'legacy_adapter/admission_agent/independent_admission.py', '--output', RUN/'e513_admission'])
run('e513_receipts', [archive/'portable_replay/receipt_agent/independent_receipts.py', '--source', SRC, '--out', RUN/'e513_receipts'])
archive = SRC/'audit/reviews/20261026-be94426-windows'
run('be_carriers_corrected', [archive/'receipt_agent/independent_carrier_boundaries_corrected.py', '--source', SRC, '--out', RUN/'be_carriers_corrected'])
schema = next((SRC/'audit/reviews').rglob('official_mcp_schema_2025-11-25.json'))
assert hashlib.sha256(schema.read_bytes()).hexdigest() == '268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7'
out = RUN/'dc_annotations_role_corrected'
out.mkdir(exist_ok=True)
shutil.copyfile(schema, out/schema.name)
archive = SRC/'audit/reviews/20261027-dc49f0f-windows'
run('dc_annotations_role_corrected', [archive/'receipt_agent/independent_annotations_role_corrected.py', '--source', SRC, '--out', out])
raise SystemExit(int(any(x['exit_code'] != 0 for x in records)))
