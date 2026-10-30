"""Read-only native-failure, original identity and append-only settlement checks."""
from pathlib import Path
from hashlib import sha256
import base64
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
PACKET = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from research import open_registry
from stage2 import bridge_for_attempt, admitted_input
from stages import source_manifest
from qresearch.artifacts import canonical_json, content_hash, decode_events
from qresearch.engineering_receipts import backtest_observation


def main():
    def load(name):
        return json.loads((PACKET / name).read_bytes())
    before, settled = load('before.json'), load('settlement.json')
    original = base64.b64decode((PACKET / 'native_terminal.json.raw.base64').read_bytes(), validate=False)
    assert sha256(original).hexdigest() == load('native_original_index.json')['decoded_sha256']
    native = json.loads(original)
    assert native['arguments'] == {'projectId': 38436695, 'backtestId': '6347a33efc37e761f486f982e804dbac'}
    assert native['result']['isError'] is True
    assert content_hash(native['result']) == settled['native_response_sha256']
    journal = (ROOT / 'audit/runtime/registry/events.jsonl').read_bytes()
    prefix = b''.join(journal.splitlines(keepends=True)[:78])
    assert sha256(prefix).hexdigest() == before['registry_sha256']
    assert sha256(journal).hexdigest() == settled['final_journal_sha256']
    events = decode_events(journal)
    assert len(events) == 80
    assert [row['event']['kind'] for row in events[-2:]] == ['failed', 'engineering_round_closed']
    attempt = settled['attempt_id']
    assert events[-2]['event']['attempt_id'] == attempt
    assert events[-1]['event']['round_id'] == settled['round_id']
    registry = open_registry()
    bridge = bridge_for_attempt(attempt, registry=registry)
    admission = admitted_input(bridge, attempt)
    parsed = backtest_observation(admission['payload'], admission['deployment'], settled['backtest_id'], native, [])
    assert parsed == load('parsed_native_terminal.json')
    assert parsed['platform']['status'] == 'runtime_error'
    completion = events[-2]['event']['error']['evidence_ref']
    assert content_hash(parsed) == completion['sha256']
    assert json.loads(registry.store.read_bytes(completion['key'])) == parsed
    assert bridge._record(attempt)['status'] == 'failed'
    assert registry.engineering_rounds_snapshot()[settled['round_id']]['status'] == 'closed'
    assert registry.snapshot()['usage'] == before['usage'] == settled['usage']
    assert registry.configuration_cycle_snapshot() == before['configuration_cycle']
    source = source_manifest()
    assert source['source_hash'] == '397c9cfe2130a0c36d7c8b8bd7cd0051a93c1556562dc03a9575139ba54c099c'
    assert len(source['source_files']) == 232
    assert journal == (ROOT / 'audit/runtime/registry/events.jsonl').read_bytes()
    result = {'native_failure_reparsed': True, 'same_attempt_failed': True, 'round009_closed': True,
        'registry_events': 80, 'original78_prefix_preserved': True, 'source_files_unchanged': 232,
        'quota_changes': 0, 'cloud_calls': 0, 'zero_order_evidence': None,
        'software_suite_rerun': False, 'independent_acceptance': False,
        'stage2_accepted': False, 'financial_evidence': False, 'final_test_enabled': False}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
