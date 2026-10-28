"""Read-only metadata reconciliation of gate verification; no provider IO."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
PACKAGE=Path(__file__).resolve().parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
report=json.loads((ROOT/'audit/stage2_gate_verification_20261028.json').read_bytes())
failure=json.loads((PACKAGE/'lean/delivered_failure_result.json').read_bytes())
sources=json.loads((PACKAGE/'cloud_sources_result.json').read_bytes())
assert report['verification_completed'] is True and report['all_acceptance_gates_passed'] is False
assert report['stage2_accepted'] is False and report['final_test_enabled'] is False
assert report['global_usage']==dict(configurations=12,research=15,lean=2)
raw=subprocess.check_output(['git','show','662ccd876b67ca0949f921a53c4c33df37cfbbf1:cloud/engineering_smoke.py'],cwd=ROOT)
assert sha(raw)==failure['worker_diagnostic']['expected_sha256']
assert sha(raw+b'\n')==failure['worker_diagnostic']['observed_sha256']
assert len(raw)==3561 and len(raw+b'\n')==3562
assert failure['exact_matching_candidate']=='append_one_LF_only'
assert len(sources['files'])==32 and all(x['equal'] for x in sources['files'])
assert failure['actual_seven_success_checks'] is None and failure['actual_orders'] is None
native=ROOT/'audit/tool_observations/37dc855045e14ca49c88fd9d75f40cf7-backtest-result.json'
logs=ROOT/'audit/tool_observations/37dc855045e14ca49c88fd9d75f40cf7-backtest-logs.json'
assert sha(native.read_bytes())==failure['native_packet_sha256']
assert sha(logs.read_bytes())==failure['native_logs_packet_sha256']
command=[sys.executable,'-B',str(ROOT/'audit/review_packages/normal004/verify_round_evidence.py'),
    '--lean-packet','37dc855045e14ca49c88fd9d75f40cf7='+str(native),
    '--lean-logs','37dc855045e14ca49c88fd9d75f40cf7='+str(logs)]
result=subprocess.run(command,cwd=ROOT,capture_output=True)
assert result.returncode==0,result.stderr.decode('utf-8',errors='replace')
proof=json.loads(result.stdout)
assert proof['round_status']=='closed' and proof['same_plan_LEAN_completed'] is False
assert proof['pending_or_unreconciled_attempts']==[]
journal=(ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
before=subprocess.check_output(['git','show','d23c0ab93ceba71529eb813e349c8dfdcbb5ea88:audit/runtime/registry/events.jsonl'],cwd=ROOT)
assert journal.startswith(before) and len(journal.splitlines())==48 and len(before.splitlines())==46
print(json.dumps(dict(verification='passed_evidence_reconciliation',LEAN_gate_passed=False,
    actual_terminal_reconciled=True,round_status='closed',project_sources_checked=32,
    first_worker_file_LF_candidate_exact=True,all_stage2_gates_passed=False,
    new_market_executions=0,financial_evidence=False,final_test_enabled=False)))
