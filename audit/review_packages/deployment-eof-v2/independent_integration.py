"""Independent synthetic integration boundaries; no cloud or ledger changes."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / 'cloud/qresearch').is_dir() and (path / 'config').is_dir())
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tools'), str(ROOT / 'tests')]
from qresearch.artifacts import content_hash, canonical_json, MemoryArtifactStore
from qresearch import deployment_sources as ds
from qresearch import engineering_data as data
from qresearch.deployment_observation import validate_deployment_observation, validate_observation_binding
from qresearch.engineering_receipts import backtest_rejection
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge, EngineeringTaskError
from qresearch.registry import Registry
from qresearch.collection_tasks import CollectionTaskPlan, CollectionTaskBridge
from qresearch.collection_execution import run_collection_task
import deployment_preflight
import stage2
from test_engineering_receipts import context, report
from test_collection_tasks import raw_plan as collection_raw_plan, CAT, Source


def envelope(name, args, result):
    return {'tool_name': 'mcp__quantconnect__' + name, 'arguments': args, 'result': result}


def payload_for(manifest):
    old, _ = context('lean')
    document = deepcopy(old['plan'])
    document['deployment_hash'] = content_hash(manifest)
    plan = EngineeringTaskPlan.from_dict(document, discovered_project_ids=[17])
    payload = deepcopy(old)
    payload['plan'] = plan.to_dict()
    payload['identity'].update(plan_hash=plan.hash, deployment_hash=content_hash(manifest),
                               config_id=content_hash({'engineering_task_schema_version': 1, 'plan': plan.to_dict()}))
    payload['report_key'] = 'engineering/receipts/reports/' + plan.hash + '/lean/' + '1' * 32 + '.json'
    payload['deployment_manifest'] = manifest
    deployment = {'source_manifest_hash': payload['identity']['source_manifest_hash'],
                  'deployment_hash': content_hash(manifest), 'input_hash': 'f' * 64}
    return payload, deployment


class IndependentIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = b'value = 211\n'
        self.manifest = ds.build_manifest({'sample.py': self.original})
        (self.root / 'sample.py').write_bytes(self.original)

    def test_worker_normalization_summary_is_bounded_and_manifest_bound(self):
        (self.root / 'sample.py').write_bytes(self.original + b'\n')
        observed = data.verify_deployment_observation(self.manifest, content_hash(self.manifest), source_root=self.root)
        self.assertEqual(observed['deployment_hash'], content_hash(self.manifest))
        self.assertEqual(observed['eof_normalized_file_count'], 1)
        self.assertEqual(observed['verified_file_count'], 1)
        self.assertFalse(observed['original_source_identity_match'])
        validate_observation_binding({'deployment_verification': observed}, self.manifest, content_hash(self.manifest))

    def test_strict_local_mode_rejects_extra_eof_and_retains_static_diagnostic(self):
        (self.root / 'sample.py').write_bytes(self.original + b'\n')
        with self.assertRaises(data.DeploymentVerificationError) as caught:
            data.verify_deployment(self.manifest, content_hash(self.manifest), source_root=self.root,
                                   require_source_bytes=True, worker_diagnostics=True)
        self.assertEqual(caught.exception.diagnostics['schema_version'], 1)
        self.assertNotIn('worker_observation', caught.exception.diagnostics)

    def test_v1_still_rejects_eof_with_controlled_schema2(self):
        legacy = {'sample.py': ds.source_sha256(self.original)}
        (self.root / 'sample.py').write_bytes(self.original + b'\n')
        with self.assertRaises(data.DeploymentVerificationError) as caught:
            data.verify_deployment(legacy, content_hash(legacy), source_root=self.root, worker_diagnostics=True)
        diagnostic = caught.exception.diagnostics
        self.assertEqual(diagnostic['schema_version'], 2)
        self.assertEqual(diagnostic['observed_sha256'], ds.source_sha256(self.original + b'\n'))
        self.assertEqual(diagnostic['worker_observation']['source_format']['normalized_trailing_lf_count'], 2)

    def test_v1_success_gains_no_new_summary(self):
        legacy = {'sample.py': ds.source_sha256(self.original)}
        self.assertIsNone(data.verify_deployment_observation(legacy, content_hash(legacy), source_root=self.root))

    def test_entire_manifest_validates_before_first_read(self):
        invalid = deepcopy(self.manifest)
        invalid['files']['../invalid.py'] = ds.source_record(b'x=1\n')
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('source read is premature')) as reader:
            with self.assertRaises(data.DeploymentVerificationError):
                data.verify_deployment(invalid, content_hash(invalid), source_root=self.root)
            self.assertEqual(reader.call_count, 0)

    def test_body_tamper_uses_static_redacted_v2_failure(self):
        (self.root / 'sample.py').write_bytes(b'value = 212  # SYNTHETIC_SECRET\n')
        with self.assertRaises(data.DeploymentVerificationError) as caught:
            data.verify_deployment(self.manifest, content_hash(self.manifest), source_root=self.root, worker_diagnostics=True)
        self.assertNotIn('SYNTHETIC_SECRET', str(caught.exception))
        self.assertNotIn('worker_observation', caught.exception.diagnostics)

    def test_summary_unknown_and_non_scalar_modes_fail_closed(self):
        summary = data.verify_deployment_observation(self.manifest, content_hash(self.manifest), source_root=self.root)
        for mode in ([], {}, None, True):
            with self.assertRaises(ValueError):
                validate_deployment_observation(dict(summary, verification_mode=mode))
        with self.assertRaises(ValueError):
            validate_deployment_observation(dict(summary, source='SYNTHETIC_SECRET'))

    def test_summary_count_and_mode_must_match_admitted_manifest(self):
        summary = data.verify_deployment_observation(self.manifest, content_hash(self.manifest), source_root=self.root)
        for changed in (dict(summary, declared_file_count=2, verified_file_count=2),
                        dict(summary, verification_mode='project_original_source')):
            with self.assertRaises(ValueError):
                validate_observation_binding({'deployment_verification': changed}, self.manifest, content_hash(self.manifest))
        with self.assertRaises(ValueError):
            validate_observation_binding({}, self.manifest, content_hash(self.manifest))

    def test_v1_cannot_claim_v2_summary(self):
        legacy = {'sample.py': ds.source_sha256(self.original)}
        summary = data.verify_deployment_observation(self.manifest, content_hash(self.manifest), source_root=self.root)
        with self.assertRaises(ValueError):
            validate_observation_binding({'deployment_verification': summary}, legacy, content_hash(legacy))

    def test_project_readback_remains_strict_for_v2(self):
        listing = envelope('list_projects', {}, {'success': True, 'projects': [{'projectId': 17, 'name': 'synthetic', 'language': 'Py'}]})
        def read(raw):
            return envelope('read_project', {'projectId': 17}, {'success': True, 'project': {
                'projectId': 17, 'name': 'synthetic', 'language': 'Py', 'files': [{'filePath': 'sample.py', 'content': raw.decode()}]}})
        valid = deployment_preflight.read_project_preflight(read(self.original), listing, self.manifest, content_hash(self.manifest), project_id=17)
        self.assertTrue(valid['preflight_passed'])
        changed = deployment_preflight.read_project_preflight(read(self.original+b'\n'), listing, self.manifest, content_hash(self.manifest), project_id=17)
        self.assertFalse(changed['preflight_passed'])
        self.assertFalse(changed['worker_source_verified'])

    def test_collection_generated_input_cannot_satisfy_engineering_input_hash(self):
        from hashlib import sha256
        marker = b'TASK_INPUT_JSON = "synthetic-only"\n'
        listing = envelope('list_projects', {}, {'success': True, 'projects': [{'projectId': 17, 'name': 'synthetic', 'language': 'Py'}]})
        project = envelope('read_project', {'projectId': 17}, {'success': True, 'project': {
            'projectId': 17, 'name': 'synthetic', 'language': 'Py', 'files': [
                {'filePath': 'sample.py', 'content': self.original.decode()},
                {'filePath': '_collection_task_input.py', 'content': marker.decode()}]}})
        observed = deployment_preflight.read_project_preflight(project, listing, self.manifest,
                    content_hash(self.manifest), project_id=17, input_sha256=sha256(marker).hexdigest())
        self.assertTrue(observed['source_reference_matches'])
        self.assertEqual(observed['ignored_generated_input_file_count'], 1)
        self.assertFalse(observed['input_binding_verified'])
        self.assertFalse(observed['preflight_passed'])
        self.assertNotIn('synthetic-only', json.dumps(observed))

    def test_v2_native_compile_rejection_uses_inner_paths(self):
        payload, deployment = payload_for(self.manifest)
        for name, expected in (('sample.py', True), ('foreign.py', False)):
            tool = envelope('create_backtest', {'projectId': 17}, {'success': False, 'errors': {name: ['1:2 SYNTHETIC_SECRET']}})
            parsed = backtest_rejection(payload, deployment, tool)
            self.assertIs(parsed['raw_receipt']['settlement_eligible'], expected)
            self.assertNotIn('SYNTHETIC_SECRET', json.dumps(parsed))

    def test_v2_local_preflight_does_not_accept_worker_tolerance(self):
        workspace = self.root / 'workspace'
        (workspace / 'cloud').mkdir(parents=True)
        (workspace / 'audit').mkdir()
        (workspace / 'cloud/sample.py').write_bytes(self.original+b'\n')
        (workspace / 'audit/deployment.json').write_text(json.dumps({'source_files': {'sample.py': ds.source_sha256(self.original)},
                                                                     'deployment_manifest': self.manifest}), encoding='utf-8')
        with patch.object(stage2, 'ROOT', workspace), self.assertRaises(ValueError):
            stage2.local_deployment_preflight()

    def test_engineering_bridge_requires_manifest_bound_success_summary(self):
        payload, _ = payload_for(self.manifest)
        plan = EngineeringTaskPlan.from_dict(payload['plan'], discovered_project_ids=[17])
        store = MemoryArtifactStore()
        registry = Registry(store, {name: {'total': 10, 'normal': 8, 'reserve': 2} for name in ('configurations', 'research', 'lean')})
        bridge = EngineeringTaskBridge(registry, plan)
        value = report(payload)['cloud_report']
        summary = data.verify_deployment_observation(self.manifest, content_hash(self.manifest), source_root=self.root)
        value['evidence']['deployment_verification'] = summary
        with self.assertRaises(EngineeringTaskError):
            bridge._cloud_report(value, payload)
        store.write_once('engineering/admitted-inputs/'+'1'*32+'.json', canonical_json({'payload': payload}))
        # LEAN's resolution still depends on an earlier Research result. Check
        # the source binding in Research mode to avoid manufacturing that result.
        research_payload = deepcopy(payload)
        research_payload['identity']['stage'] = 'research'
        research_value = report(research_payload)['cloud_report']
        research_value['evidence']['deployment_verification'] = summary
        bridge._cloud_report(research_value, research_payload)
        for modified in (dict(summary, declared_file_count=2, verified_file_count=2), None):
            changed = deepcopy(research_value)
            if modified is None:
                del changed['evidence']['deployment_verification']
            else:
                changed['evidence']['deployment_verification'] = modified
            with self.assertRaises(EngineeringTaskError):
                bridge._cloud_report(changed, research_payload)

    def test_collection_bridge_uses_collection_admission_namespace_and_rejects_false_counts(self):
        document = collection_raw_plan()
        document['deployment_hash'] = content_hash(self.manifest)
        plan = CollectionTaskPlan.from_dict(document, discovered_project_ids=[17], field_catalog=CAT)
        store = MemoryArtifactStore()
        registry = Registry(store, {name: {'total': 10, 'normal': 8, 'reserve': 2} for name in ('configurations', 'research', 'lean')})
        bridge = CollectionTaskBridge(registry, plan)
        bridge.register()
        attempt = bridge.claim()
        payload = dict(bridge.payload(attempt), deployment_manifest=self.manifest)
        wrapper = run_collection_task(payload, field_catalog=CAT, store=MemoryArtifactStore(),
                                      source=Source(), synthetic=True, source_root=self.root)
        value = wrapper['cloud_report']
        with self.assertRaises(EngineeringTaskError):
            bridge._cloud_report(value, payload)
        store.write_once('collection/admitted-inputs/'+attempt.attempt_id+'.json', canonical_json({'payload': payload}))
        bridge._cloud_report(value, payload)
        for missing in (False, True):
            changed = deepcopy(value)
            if missing:
                del changed['evidence']['deployment_verification']
            else:
                changed['evidence']['deployment_verification'].update(declared_file_count=2, verified_file_count=2)
            with self.assertRaises(EngineeringTaskError):
                bridge._cloud_report(changed, payload)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentIntegration))
    summary = {'kind': 'independent_synthetic_deployment_integration_boundaries', 'test_count': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'successful': result.wasSuccessful(),
               'cloud_calls': 0, 'provider_calls': 0, 'financial_evidence': False}
    Path(__file__).with_name('integration_result.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
