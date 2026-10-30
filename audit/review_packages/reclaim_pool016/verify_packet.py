"""Verify this fixed offline retention packet; no provider or cloud execution."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def main():
    manifest = json.loads((HERE / 'packet_manifest.json').read_bytes())
    for row in manifest['files']:
        path = ROOT / row['path']
        require(path.is_file() and sha256(path.read_bytes()).hexdigest() == row['sha256'], row['path'])
    protection = json.loads((HERE / 'protection.json').read_bytes())
    exclude = protection['allowed_current_metadata_updates']
    def entries(ref):
        rows = []
        for raw in subprocess.check_output(['git', 'ls-tree', '-r', '-z', ref], cwd=ROOT).split(b'\0'):
            if raw:
                meta, name = raw.split(b'\t', 1)
                rows.append([name.decode('utf-8'), meta.split()[2].decode()])
        return rows
    originals = [r for r in entries(protection['base_commit']) if r[0] not in exclude]
    require(len(originals) == protection['old_raw_Git_blob_identities_protected'], 'Original count')
    require(sha256(json.dumps(originals, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        == protection['old_raw_tree_fingerprint_sha256'], 'Original Git tree fingerprint')
    current = dict(entries('HEAD'))
    for name, oid in originals:
        require(current.get(name) == oid, 'Historical Git blob changed: ' + name)
    registry = (ROOT / 'audit/runtime/registry/events.jsonl').read_bytes()
    budget_raw = (ROOT / 'config/budget.json').read_bytes()
    require(sha256(registry).hexdigest() == protection['registry_sha256'], 'Registry raw changed')
    require(sha256(budget_raw).hexdigest() == protection['budget_sha256'], 'Budget raw changed')
    budget = json.loads(budget_raw)
    require(budget['usage']['research_execution_attempts'] == 19 and budget['usage']['lean_submission_attempts'] == 4,
        'Budget usage')
    require(budget['configuration_cycle']['usage']['total'] == 5, 'Configuration cycle')
    dev = json.loads((ROOT / 'config/development.json').read_bytes())
    require(all(dev['execution'][k] is False for k in ['market_research_enabled', 'llm_runtime_enabled',
        'final_test_enabled', 'live_trading_enabled']), 'Execution gate')
    exp = (ROOT / 'audit/experiments.jsonl').read_bytes()
    prefix = exp[:protection['previous_experiment_bytes']]
    require(sha256(prefix).hexdigest() == protection['previous_experiment_sha256'], 'Historical experiment prefix')
    extra = [json.loads(x) for x in exp[len(prefix):].splitlines() if x]
    require(len(extra) == 1 and extra[0]['experiment_id'] == 'STAGE2-RECLAIM-POOL-RETENTION-016', 'Single audit append')
    a = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(HERE / 'analyze_pool.py')], cwd=ROOT, capture_output=True)
    require(a.returncode == 0, a.stderr.decode('utf-8', 'replace'))
    actual = json.loads(a.stdout)
    require(actual == json.loads((HERE / 'assessment.json').read_bytes()), 'Recomputed assessment')
    t = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(HERE / 'test_assessment.py')], cwd=ROOT, capture_output=True)
    require(t.returncode == 0, t.stderr.decode('utf-8', 'replace'))
    require('Ran 25 tests' in t.stderr.decode('utf-8'), 'Test count')
    report = json.loads((ROOT / 'audit/stage2_reclaim_pool016_report.json').read_bytes())
    require(report['proposed_deletion_keys'] == [] and report['stage2_accepted'] is False
        and report['final_test_enabled'] is False and report['Object_Store_payload_reads'] == 0, 'Disposition boundaries')
    print(json.dumps({'packet_files_verified': len(manifest['files']),
        'historical_raw_Git_blob_IDs_preserved': len(originals), 'candidate_objects': 16,
        'candidate_physical_bytes': 2772902, 'proposed_deletions': 0, 'confirmed_reclaimable_bytes': 0,
        'boundary_tests_actual_passed': 25, 'new_Research_executions': 0, 'new_LEAN_submissions': 0,
        'Research_used': 19, 'LEAN_used': 4, 'Registry_events': 86, 'stage2_accepted': False,
        'final_test_enabled': False, 'independent_acceptance': False}, sort_keys=True))

if __name__ == '__main__':
    main()
