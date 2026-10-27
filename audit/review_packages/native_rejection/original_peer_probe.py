"""Independent development-side synthetic boundaries; no QC or real ledger."""
from contextlib import contextmanager
from copy import deepcopy
import json
import multiprocessing
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tools'), str(ROOT / 'tests')]
import stage2 as cli
import qresearch.engineering_receipts as parsers
from qresearch.artifacts import canonical_json, content_hash, FilesystemArtifactStore
from qresearch.engineering_tasks import EngineeringTaskError, EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import Registry
from test_engineering_receipts import envelope
from test_wr17_engineering_recovery import SyntheticFixture


@contextmanager
def fixture(version=1):
    with SyntheticFixture(version) as f:
        f.settle_research()
        aid = f.bridge.claim('lean').attempt_id
        admitted = cli.prepare(f.bridge, aid)
        yield f, aid, admitted


def native(errors=None):
    return envelope('create_backtest', {'projectId': 17, 'backtestName': 'peer-rejection'},
        {'success': False, 'errors': errors if errors is not None else {'stub.py': ['2:3 peer compiler diagnostic']}})


def parse(admitted, obs=None):
    method = getattr(parsers, 'backtest_rejection', None)
    if not callable(method):
        raise unittest.SkipTest('Implementation not available yet')
    return method(admitted['payload'], admitted['deployment'], obs or native())


def accepted(admitted):
    return parsers.backtest_submission(admitted['payload'], admitted['deployment'],
        envelope('create_backtest', {'projectId': 17}, {'success': True, 'backtestId': 'peer-native-id'}))


def race_worker(store_path, limits, plan, aid, receipt, accept, gate, result):
    try:
        store = FilesystemArtifactStore(store_path)
        registry = Registry(store, limits)
        bridge = EngineeringTaskBridge(registry, EngineeringTaskPlan.from_dict(plan, discovered_project_ids=[17]))
        gate.wait(10)
        method = bridge.record_submission if accept else bridge.record_rejection
        value = method(aid, receipt)
        result.put({'status':value.status,'error':None})
    except Exception as exc:
        result.put({'status':None,'error':type(exc).__name__})


class IndependentRejectionBoundaries(unittest.TestCase):
    def assert_ineligible(self, admitted, obs):
        try:
            result = parse(admitted, obs)
        except parsers.ReceiptParseError:
            return
        self.assertIs(result['raw_receipt']['settlement_eligible'], False)

    def test_manifest_injection_does_not_authorize_a_foreign_diagnostic(self):
        with fixture() as (_, _, admitted):
            bad = deepcopy(admitted)
            bad['payload']['deployment_manifest']['foreign.py'] = 'e' * 64
            self.assert_ineligible(bad, native({'foreign.py': ['2:3 compiler text']}))

    def test_bad_manifest_hash_types_and_path_grammar_are_not_evidence(self):
        edits = [lambda d: d.pop('deployment_manifest'),
            lambda d: d['deployment_manifest'].update({'stub.py': True}),
            lambda d: d['deployment_manifest'].update({'../stub.py': 'b' * 64}),
            lambda d: d.update(deployment_manifest=['stub.py'])]
        with fixture() as (_, _, admitted):
            for index, edit in enumerate(edits):
                with self.subTest(index=index):
                    bad = deepcopy(admitted); edit(bad['payload'])
                    self.assert_ineligible(bad, native())

    def test_bridge_independently_rejects_a_different_generated_input_hash(self):
        for version in (1, 2):
            with self.subTest(version=version), fixture(version) as (f, aid, admitted):
                receipt = parse(admitted)
                receipt['deployment']['input_hash'] = '0' * 64
                saved = dict(f.store._data); before = f.registry.snapshot()
                with self.assertRaises((EngineeringTaskError, ValueError)):
                    f.bridge.record_rejection(aid, receipt)
                self.assertEqual(f.store._data, saved)
                self.assertEqual(f.registry.snapshot(), before)

    def test_generic_native_errors_are_candidates_and_cannot_release_the_slot(self):
        for errors in (['unexpected server response'], {'stub.py': ['server response missing']},
                       {'unfrozen.py': ['2:3 compiler text']}):
            with self.subTest(errors=errors), fixture() as (f, aid, admitted):
                receipt = parse(admitted, native(errors))
                self.assertIs(receipt['raw_receipt']['settlement_eligible'], False)
                before = f.registry.snapshot(); saved = dict(f.store._data)
                with self.assertRaises((EngineeringTaskError, ValueError)):
                    f.bridge.record_rejection(aid, receipt)
                self.assertEqual(f.registry.snapshot(), before)
                self.assertEqual(f.store._data, saved)

    def test_accepted_pointer_crash_cannot_be_reclassified_as_rejection(self):
        with fixture() as (f, aid, admitted):
            receipt = accepted(admitted)
            original = f.bridge._save
            def crash(*args, **kwargs):
                if len(args) > 1 and args[1] == 'submission':
                    raise OSError('synthetic complete receipt persistence failure')
                return original(*args, **kwargs)
            with patch.object(f.bridge, '_save', side_effect=crash):
                with self.assertRaises(OSError):
                    f.bridge.record_submission(aid, receipt)
            self.assertTrue(f.store.exists(f.bridge._submission_key(aid)))
            before = f.registry.snapshot(); saved = dict(f.store._data)
            with self.assertRaises((EngineeringTaskError, ValueError)):
                f.bridge.record_rejection(aid, parse(admitted))
            self.assertEqual(f.registry.snapshot(), before)
            self.assertEqual(f.store._data, saved)
            self.assertEqual(f.bridge.record_submission(aid, receipt).status, 'pending')
            self.assertEqual(f.registry.snapshot()['usage']['lean']['total'], 1)

    def test_rejection_evidence_then_event_crash_repairs_once(self):
        with fixture() as (f, aid, admitted):
            receipt = parse(admitted)
            original = f.registry._append
            def crash(event):
                if event['kind'] == 'failed':
                    raise OSError('synthetic failure event persistence error')
                return original(event)
            with patch.object(f.registry, '_append', side_effect=crash):
                with self.assertRaises(OSError):
                    f.bridge.record_rejection(aid, receipt)
            self.assertEqual(f.bridge._record(aid)['status'], 'started')
            self.assertEqual(f.bridge.record_rejection(aid, receipt).status, 'failed')
            saved = dict(f.store._data); before = f.registry.snapshot()
            self.assertEqual(f.bridge.record_rejection(aid, receipt).status, 'failed')
            self.assertEqual(f.store._data, saved)
            self.assertEqual(f.registry.snapshot(), before)
            self.assertEqual(before['usage']['lean']['total'], 1)

    def test_conflicting_raw_mcp_mirror_is_not_a_rejection(self):
        with fixture() as (_, _, admitted):
            obs = native()
            obs['result']['content'][0]['text'] = json.dumps({'success': False,
                'errors': {'stub.py': ['2:3 DIFFERENT native result']}})
            with self.assertRaises(parsers.ReceiptParseError):
                parse(admitted, obs)

    def test_ambiguous_id_and_rejected_policy_bits_do_not_finalize(self):
        with fixture() as (f, aid, admitted):
            receipt = parse(admitted)
            f.registry.pending(aid, external_id='peer-native-id')
            f.registry.ambiguous(aid, reason='synthetic remote read unknown')
            before = f.registry.snapshot(); saved = dict(f.store._data)
            with self.assertRaises((EngineeringTaskError, ValueError)):
                f.bridge.record_rejection(aid, receipt)
            self.assertEqual(f.registry.snapshot(), before)
            self.assertEqual(f.store._data, saved)

    def test_legacy_admission_is_not_retroactively_given_new_protocol(self):
        with fixture() as (f, aid, admitted):
            marker='engineering/submission-protocol/'+aid+'.json'
            self.assertTrue(f.store.exists(marker))
            del f.store._data[marker]
            # Simulate the old accepted-original-before-pointer crash window.
            f.bridge._save(aid,'submission',accepted(admitted))
            before=f.registry.snapshot(); saved=dict(f.store._data)
            self.assertEqual(cli.prepare(f.bridge,aid),admitted)
            self.assertFalse(f.store.exists(marker))
            with self.assertRaises((EngineeringTaskError,ValueError,FileNotFoundError)):
                f.bridge.record_rejection(aid,parse(admitted))
            self.assertEqual(f.registry.snapshot(),before)
            self.assertEqual(f.store._data,saved)
            # Old successful acknowledgement recovery is still available.
            self.assertEqual(f.bridge.record_submission(aid,accepted(admitted)).status,'pending')

    def test_protocol_metadata_must_match_canonical_bound_original(self):
        edits=[lambda x:x.update(schema_version=True),lambda x:x.update(schema_version=2),
            lambda x:x.update(protocol='legacy'),lambda x:x['deployment'].update(input_hash='0'*64),
            lambda x:x['identity'].update(attempt_id='9'*32),lambda x:x.update(extra=True)]
        with fixture() as (f,aid,admitted):
            marker='engineering/submission-protocol/'+aid+'.json'
            self.assertTrue(f.store.exists(marker))
            original=f.store.read_bytes(marker)
            for index,edit in enumerate(edits):
                with self.subTest(index=index):
                    value=json.loads(original);edit(value);f.store._data[marker]=canonical_json(value)
                    before=f.registry.snapshot();saved=dict(f.store._data)
                    with self.assertRaises((EngineeringTaskError,ValueError)):
                        f.bridge.record_rejection(aid,parse(admitted))
                    self.assertEqual(f.registry.snapshot(),before)
                    self.assertEqual(f.store._data,saved)
            f.store._data[marker]=original

    def test_same_failed_rejection_requires_intact_original_receipt_bytes(self):
        for mutation in ('missing','changed'):
            with self.subTest(mutation=mutation),fixture() as (f,aid,admitted):
                receipt=parse(admitted)
                self.assertEqual(f.bridge.record_rejection(aid,receipt).status,'failed')
                ref=f.bridge._record(aid)['error']['receipt_ref']['key']
                if mutation=='missing':del f.store._data[ref]
                else:f.store._data[ref]=b'{}'
                before=f.registry.snapshot();saved=dict(f.store._data)
                with self.assertRaises((EngineeringTaskError,ValueError,FileNotFoundError)):
                    f.bridge.record_rejection(aid,receipt)
                self.assertEqual(f.registry.snapshot(),before)
                self.assertEqual(f.store._data,saved)

    def test_filesystem_two_process_acceptance_rejection_are_serialized(self):
        with fixture() as (f,aid,admitted):
            path=f.root/'peer-process-store';store=FilesystemArtifactStore(path)
            for key,data in f.store._data.items():store.write_once(key,data)
            context=multiprocessing.get_context('spawn')
            gate=context.Barrier(2);out=context.Queue()
            args=(str(path),f.registry.limits,f.plan.to_dict(),aid)
            workers=[context.Process(target=race_worker,args=(*args,accepted(admitted),True,gate,out)),
                context.Process(target=race_worker,args=(*args,parse(admitted),False,gate,out))]
            for worker in workers:worker.start()
            for worker in workers:worker.join(15)
            for worker in workers:
                if worker.is_alive():worker.terminate();worker.join();self.fail('Registry lock did not complete across processes')
                self.assertEqual(worker.exitcode,0)
            results=[out.get(timeout=3),out.get(timeout=3)]
            self.assertEqual(sum(x['status'] is not None for x in results),1,results)
            self.assertEqual([x['error'] for x in results if x['error'] is not None],['EngineeringTaskError'])
            registry=Registry(store,f.registry.limits)
            record=next(x for x in registry.snapshot()['attempts'] if x['attempt_id']==aid)
            self.assertIn(record['status'],{'pending','failed'})
            self.assertEqual(store.exists(f.bridge._submission_key(aid)),record['status']=='pending')
            self.assertEqual(registry.snapshot()['usage']['lean']['total'],1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
