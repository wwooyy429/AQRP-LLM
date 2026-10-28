"""Auxiliary developer-side review; synthetic only and read-only real recovery.

This is not GPT Work independent acceptance or a QuantConnect execution.
The actual failed-attempt identity is used only to verify immutable recovery.
"""
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / 'cloud/qresearch').is_dir() and (path / 'config').is_dir())
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tools'), str(Path(__file__).parent)]
from qresearch.artifacts import content_hash
from qresearch.deployment_sources import parse_manifest
from independent_boundaries import IndependentIdentityBoundaries
from independent_integration import IndependentIntegration
import stage2


def source_snapshot():
    return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for directory, suffix in (('cloud', '.py'), ('tools', '.py'), ('config', '.json'))
            for path in sorted((ROOT / directory).rglob('*' + suffix)) if '__pycache__' not in path.parts}


def protected_snapshot():
    names = ('config/budget.json', 'audit/runtime/registry/baseline.json', 'audit/runtime/registry/events.jsonl',
             'audit/engineering_current.json')
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names if (ROOT / name).exists()}


if __name__ == '__main__':
    before, protected_before = source_snapshot(), protected_snapshot()
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(IndependentIdentityBoundaries),
                               unittest.defaultTestLoader.loadTestsFromTestCase(IndependentIntegration)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    bridge = stage2.bridge_for_attempt('37dc855045e14ca49c88fd9d75f40cf7')
    admission = stage2.admitted_input(bridge, '37dc855045e14ca49c88fd9d75f40cf7')
    record = bridge._record('37dc855045e14ca49c88fd9d75f40cf7')
    recovery = {'attempt_id': record['attempt_id'], 'status': record['status'],
                'manifest_schema_version': parse_manifest(admission['payload']['deployment_manifest'])[0],
                'original_admission_recovered': True}
    after, protected_after = source_snapshot(), protected_snapshot()
    summary = {'kind': 'auxiliary_developer_side_deployment_review', 'test_count': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors),
               'synthetic_tests_passed': result.wasSuccessful(), 'source_snapshot_stable': before == after,
               'source_snapshot_sha256': content_hash(before), 'source_file_count': len(before),
               'protected_metadata_unchanged': protected_before == protected_after,
               'protected_metadata_sha256': protected_before, 'actual_failed_attempt_recovery': recovery,
               'cloud_calls': 0, 'provider_calls': 0, 'budget_debits': 0,
               'gpt_work_acceptance': False, 'phase_2_acceptance': False, 'financial_evidence': False}
    summary['successful'] = (result.wasSuccessful() and before == after and protected_before == protected_after
                             and recovery['status'] == 'failed' and recovery['manifest_schema_version'] == 1)
    output = Path(__file__).with_name('independent_review_result.json')
    output.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, sort_keys=True))
    raise SystemExit(0 if summary['successful'] else 1)
