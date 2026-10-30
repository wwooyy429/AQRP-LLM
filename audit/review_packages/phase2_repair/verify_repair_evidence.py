"""Read-only reconciliation of the bounded repair and its native failed receipt."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'cloud')]
from research import read_json, open_registry
from stage2 import bridge_for_attempt, admitted_input, _read_research_dispatch
from qresearch.engineering_receipts import research_observation
from qresearch.collection import _safe_source_diagnostic
from qresearch.artifacts import content_hash

BASELINE = '2069ef583526b8f2e7c7dfd1dda3c9fb175f6a98'
ATTEMPT = 'e17fd1ac2d3e433e909aef149c7afeec'

def verify():
    registry = open_registry()
    journal_path = ROOT / 'audit/runtime/registry/events.jsonl'
    before = journal_path.read_bytes()
    old = subprocess.check_output(['git', 'show', BASELINE + ':audit/runtime/registry/events.jsonl'], cwd=ROOT)
    assert len(old.splitlines()) == 28 and before.startswith(old)
    usage = registry.snapshot()['usage']
    assert {k: v['total'] for k, v in usage.items()} == {'configurations': 10, 'research': 13, 'lean': 1}
    round_record = registry.engineering_rounds_snapshot()['stage2-repair-round-003']
    assert round_record['status'] == 'closed'
    assert round_record['usage'] == {'configurations': 1, 'research': 1, 'lean': 0}
    bridge = bridge_for_attempt(ATTEMPT, registry=registry)
    original = admitted_input(bridge, ATTEMPT)
    payload, deployment = original['payload'], original['deployment']
    binding = _read_research_dispatch(bridge, payload, deployment, require_dispatch=True)
    path = ROOT / 'audit/tool_observations' / (ATTEMPT + '-research.json')
    packet = read_json(path)
    observed = research_observation(payload, deployment, packet, dispatch_binding=binding, dispatch_required=True)
    assert observed['completion']['platform']['status'] == 'runtime_error'
    assert bridge._record(ATTEMPT)['status'] == 'failed'
    native = {block['text'] for block in packet['result']['content']}
    assert len(native) == 1
    error = json.loads(next(iter(native)))
    diagnostic = _safe_source_diagnostic(json.loads(error['evalue'].split('; diagnostic=', 1)[1]))
    assert diagnostic is not None and diagnostic['stage'] == 'row_identity'
    assert diagnostic['rows_emitted'] == 5124 and diagnostic['response_kind'] == 'series'
    assert diagnostic['snapshot_kind'] == 'list' and diagnostic['response_rows'] == 1
    assert 'cloud_report' not in observed['completion']
    baseline_budget = json.loads(subprocess.check_output(['git', 'show', BASELINE + ':config/budget.json'], cwd=ROOT))
    current_budget = read_json(ROOT / 'config/budget.json')
    baseline_budget.pop('usage'); current_budget.pop('usage')
    assert baseline_budget == current_budget
    exposure = ROOT / 'audit/data_exposure.json'
    exposure_raw = exposure.read_bytes()
    exposure_git = subprocess.check_output(['git', 'show', BASELINE + ':audit/data_exposure.json'], cwd=ROOT)
    # Repository text policy permits CRLF checkout/LF Git presentation. Require
    # identical bytes after that declared normalization, not a false mutation.
    assert exposure_raw.replace(b'\r\n', b'\n') == exposure_git.replace(b'\r\n', b'\n')
    assert json.loads(exposure_raw) == json.loads(exposure_git)
    flags = read_json(ROOT / 'config/development.json')['execution']
    assert all(flags[key] is False for key in ('market_research_enabled', 'llm_runtime_enabled', 'final_test_enabled', 'live_trading_enabled'))
    assert before == journal_path.read_bytes()
    return {'schema_version': 1, 'kind': 'developer_read_only_repair_evidence_integrity',
        'baseline_commit': BASELINE, 'original_28_event_prefix_preserved': True,
        'current_event_count': len(before.splitlines()), 'journal_sha256': hashlib.sha256(before).hexdigest(),
        'global_usage': usage, 'budget_policy_and_allocations_unchanged': True,
        'data_exposure_unchanged_under_declared_LF_policy': True,
        'data_exposure_normalized_sha256': hashlib.sha256(exposure_raw.replace(b'\r\n', b'\n')).hexdigest(),
        'round': round_record,
        'attempt': {'id': ATTEMPT, 'identity': payload['identity'], 'frozen_deployment': deployment,
            'dispatch_binding_sha256': content_hash(binding), 'ledger_status': 'failed',
            'platform_status': 'runtime_error', 'diagnostic': diagnostic,
            'diagnostic_scope': 'one failing native fetch; not whole Research totals',
            'native_packet_sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
        'counts': {'new_configuration_charges': 1, 'new_Research_executions': 1, 'new_LEAN_submissions': 0,
            'failure_refunds': 0},
        'source_boundary_repair_has_real_nonempty_observation': True,
        'all_Research_checks_passed': False, 'new_LEAN_completed': False,
        'actual_SID_failure_subtype_proven': False, 'SID_rows_dropped_or_deduplicated': False,
        'normal_budget_use_authorized_in_this_receipt': False,
        'independent_GPT_Work_acceptance': False, 'financial_evidence': False, 'final_test_enabled': False}

if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
