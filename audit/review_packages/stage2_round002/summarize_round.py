"""Recompute this closed engineering round from native receipts; no provider I/O."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'cloud')]
from research import open_registry, read_json, write_changed
from stage2 import bridge_for_attempt, admitted_input, _read_research_dispatch
from qresearch.engineering_receipts import research_observation
from qresearch.artifacts import content_hash

ATTEMPTS = (
    ('4de020ffad5a4e82a26c5374f7715685', '0d54bf94b72c5038913f63a2f40f2a3b17da0c3e'),
    ('d45af7fcfdc849c888694aaa6dd7c0ae', '0656cb758c412ecedb5fa3af180407b720677d6e'),
)

def main():
    registry = open_registry()
    rounds = registry.engineering_rounds_snapshot()
    grant = rounds['stage2-cloud-round-002']
    assert grant['status'] == 'closed' and grant['usage'] == {'configurations': 2, 'research': 2, 'lean': 0}
    before = (ROOT / 'audit/runtime/registry/events.jsonl').read_bytes()
    result = []
    for attempt, commit in ATTEMPTS:
        bridge = bridge_for_attempt(attempt, registry=registry)
        admission = admitted_input(bridge, attempt)
        payload, deployment = admission['payload'], admission['deployment']
        dispatch = _read_research_dispatch(bridge, payload, deployment, require_dispatch=True)
        path = ROOT / 'audit/tool_observations' / (attempt + '-research.json')
        packet = read_json(path)
        observed = research_observation(payload, deployment, packet, dispatch_binding=dispatch, dispatch_required=True)
        completion = observed['completion']
        report = completion.get('cloud_report')
        state = bridge._record(attempt)
        assert state['status'] == 'failed'
        result.append({
            'attempt_id': attempt, 'source_commit': commit, 'identity': payload['identity'],
            'frozen_input_sha256': deployment['input_hash'], 'dispatch_binding_sha256': content_hash(dispatch),
            'tool_observation': {'path': path.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
            'receipt_native_status': completion['platform']['status'],
            'ledger_terminal_status': state['status'],
            'engineering_status': report['status'] if report else None,
            'checks': report['checks'] if report else None,
            'statistics': report['statistics'] if report else None,
            'evidence': report['evidence'] if report else None,
            'cloud_report_ref': completion.get('report_ref'),
            'financial_evidence': False,
        })
    assert result[1]['checks']['collection_nonempty'] is False
    assert result[1]['evidence']['collection_probe']['empty_windows'] == 40
    assert result[1]['evidence']['collection_probe']['record_count'] == 0
    report = {
        'schema_version': 1, 'kind': 'closed_bounded_stage2_engineering_round',
        'round_id': 'stage2-cloud-round-002', 'scope': 'engineering_only',
        'status': 'stopped_at_preregistered_configuration_and_Research_cap',
        'stage2_acceptance': 'pending_real_joint_success_independent_review_and_data_certification',
        'global_limits': registry.limits, 'global_usage': registry.snapshot()['usage'], 'round': grant,
        'turn_start_usage': {'configurations': 7, 'research': 10, 'lean': 1},
        'new_charges': {'configurations': 2, 'research': 2, 'lean': 0},
        'failed_debits_refunded': False, 'unused_LEAN_reservation_released': True,
        'LEAN_not_submitted_reason': 'No same-parent Research satisfied all frozen checks.',
        'attempts': result,
        'observed_outcome': {
            'first': 'Native CollectionError at response_contract for an observed zero-row DataFrame.',
            'repair': 'Narrow empty sentinel handling reached a complete native report; engineering checks still failed.',
            'second': 'All 40 collection windows empty; no historical-universe rows; empty source cause remains unknown.',
            'price_cache': 'Both prefetch counters were zero in the second run; fixed two-symbol raw cache/calendar checks passed.',
        },
        'remaining_gates': [
            'nonempty real historical-universe source, with source/config/entitlement evidence',
            'qualifying same-parent Research followed by a completed verified LEAN receiver',
            'new round-control and empty-response code independently reviewed on an exact commit',
            'old failed worker-specific source mismatch explanation remains unproven',
            'complete historical US200, permanent-SID/classification/corporate-action evidence',
            'financial values, publication/vintage and actual historical delivery/ingestion evidence',
        ],
        'source_review': {'last_independently_accepted_software_commit': '44676db609b3b7c2175fa7fa4f19c8ccf8165458',
            'new_runtime_implementation_commit': ATTEMPTS[1][1], 'new_independent_acceptance': False,
            'developer_repair_test_methods': 703, 'developer_test_source_manifest_hash': read_json(ROOT / 'audit/stage2_round002_repair_verification.json')['source_hash']},
        'financial_evidence': False, 'IC': None, 'returns': None, 'costs': None, 'risk_metrics': None,
        'market_research_enabled': False, 'llm_runtime_enabled': False, 'final_test_enabled': False,
        'live_trading_enabled': False, 'extra_spend_usd': 0,
        'prior_2024_2025_exposure_preserved': True, 'year2026_independence': 'not_certified',
        'reproduction': {'program': Path(__file__).resolve().relative_to(ROOT).as_posix(),
            'program_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'market_provider_calls': 0, 'Research_executions': 0, 'LEAN_submissions': 0},
    }
    assert before == (ROOT / 'audit/runtime/registry/events.jsonl').read_bytes()
    target = ROOT / 'audit/stage2_round002_report.json'
    write_changed(target, json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': target.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'new_charges': report['new_charges'], 'stage2_accepted': False, 'final_test_enabled': False}))

if __name__ == '__main__':
    main()
