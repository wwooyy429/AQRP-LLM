"""Synthetic native-rejection boundaries, never QC execution or certification."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tools'), str(ROOT / 'tests')]
import qresearch.engineering_receipts as receipts
import stage2 as cli
from qresearch.artifacts import canonical_json, content_hash, FilesystemArtifactStore
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskError
from qresearch.registry import Registry
from test_engineering_receipts import envelope
from test_wr17_engineering_recovery import SyntheticFixture

SECRET = 'SENSITIVE_MARKET_TEXT_123.45'


@contextmanager
def lean_fixture(version=1):
    with SyntheticFixture(version) as fixture:
        fixture.settle_research()
        attempt = fixture.bridge.claim('lean').attempt_id
        admission = cli.prepare(fixture.bridge, attempt)
        yield fixture, attempt, admission


def rejected(errors=None, **extras):
    return envelope('create_backtest', {'projectId': 17, 'backtestName': SECRET},
                    dict({'success': False, 'errors': {'stub.py': ['1:2 ' + SECRET]} if errors is None else errors}, **extras))


class NativeBacktestRejectionTests(unittest.TestCase):
    def parser(self):
        parser = getattr(receipts, 'backtest_rejection', None)
        self.assertTrue(callable(parser), 'Missing fixed native create_backtest rejection parser')
        return parser

    def parse(self, admission, tool):
        return self.parser()(admission['payload'], admission['deployment'], tool)

    def test_documented_error_shapes_parse_as_candidates_without_copying_text(self):
        with lean_fixture() as (_, _, admission):
            for errors, eligible, count, files in (([SECRET, 'another error'], False, 2, 0),
                    ({'stub.py': ['1:2 ' + SECRET, '2:3 more']}, True, 2, 1),
                    ({'stub.py': ['unclassified native error']}, False, 1, 1)):
                with self.subTest(errors=errors):
                    tool = rejected(errors)
                    value = self.parse(admission, tool)
                    self.assertIs(value['accepted'], False)
                    self.assertEqual(value['status'], 'rejected')
                    self.assertNotIn('external_id', value)
                    raw = value['raw_receipt']
                    self.assertEqual(raw['response_sha256'], content_hash(tool['result']))
                    self.assertEqual(raw['arguments_sha256'], content_hash(tool['arguments']))
                    self.assertIs(raw['settlement_eligible'], eligible)
                    self.assertEqual((raw['error_count'], raw['error_file_count']), (count, files))
                    self.assertNotIn(SECRET, json.dumps(value))
                    self.assertNotIn('stub.py', json.dumps(value))

    def test_content_only_structured_only_mirrored_and_direct_native_shapes(self):
        with lean_fixture() as (_, _, admission):
            tool = rejected()
            forms = [tool, deepcopy(tool), deepcopy(tool), deepcopy(tool)]
            del forms[1]['result']['structuredContent']
            del forms[2]['result']['content']
            forms[3]['result'] = forms[3]['result']['structuredContent']
            for form in forms:
                self.assertTrue(self.parse(admission, form)['raw_receipt']['settlement_eligible'])

    def test_unknown_contradictory_or_incomplete_native_fields_are_rejected(self):
        with lean_fixture() as (_, _, admission):
            native_cases = [
                {'success': True, 'errors': ['failed']}, {'success': 0, 'errors': ['failed']},
                {'success': 'false', 'errors': ['failed']}, {'errors': ['failed']},
                {'success': False}, {'success': False, 'errors': []},
                {'success': False, 'errors': {}}, {'success': False, 'errors': ''},
                {'success': False, 'errors': ['']}, {'success': False, 'errors': [' ']},
                {'success': False, 'errors': [False]}, {'success': False, 'errors': {'stub.py': []}},
                {'success': False, 'errors': {'stub.py': [1]}}, {'success': False, 'errors': {'': ['1:2 bad']}},
                {'success': False, 'errors': ['bad'], 'backtestId': None},
                {'success': False, 'errors': ['bad'], 'backtestId': ''},
                {'success': False, 'errors': ['bad'], 'backtestId': 'already-accepted'},
                {'success': False, 'errors': ['bad'], 'compileId': 'unknown'},
                {'success': False, 'errors': ['bad'], 'status': 'timeout'},
                {'success': False, 'errors': ['bad'], 'rows': [[123.45]]},
                {'success': False, 'errors': ['bad'], 'warnings': [SECRET]},
            ]
            for native in native_cases:
                with self.subTest(native=native), self.assertRaises(receipts.ReceiptParseError):
                    self.parse(admission, envelope('create_backtest', {'projectId': 17}, native))

    def test_all_carriers_transport_and_tool_context_are_inspected(self):
        edits = [lambda t: t['result'].update(isError=True),
            lambda t: t['result'].update(isError=0),
            lambda t: t['result'].update(_meta={'timeout': True}),
            lambda t: t['result']['content'].append({'type': 'text', 'text': SECRET}),
            lambda t: t['result']['content'].append({'type': 'image', 'data': SECRET}),
            lambda t: t['result']['content'][0].update(text=json.dumps({'success': True})),
            lambda t: t.update(tool_name='mcp__quantconnect__create_compile'),
            lambda t: t['arguments'].update(projectId=18),
            lambda t: t['arguments'].update(projectId=True),
            lambda t: t['arguments'].update(backtestName=True),
            lambda t: t['arguments'].update(timeout=True)]
        with lean_fixture() as (_, _, admission):
            for index, edit in enumerate(edits):
                tool = rejected(); edit(tool)
                with self.subTest(index=index), self.assertRaises(receipts.ReceiptParseError):
                    self.parse(admission, tool)

    def test_only_bound_relative_source_diagnostics_are_settlement_eligible(self):
        with lean_fixture() as (_, _, admission):
            cases = [({'../stub.py': ['1:2 bad']}, False), ({'/stub.py': ['1:2 bad']}, False),
                ({'C:/stub.py': ['1:2 bad']}, False), ({'foreign.py': ['1:2 bad']}, False),
                ({'stub.py': ['0:2 bad']}, False), ({'stub.py': ['1:0 bad']}, False),
                ({'stub.py': ['1:2']}, False), ({'stub.py': ['1:2 bad\nextra']}, False),
                ({'stub.py': ['1:2 bad', 'timeout']}, False),
                ({'_engineering_task_input.py': ['1:2 bad']}, True),
                ({'stub.py': ['1:2 variable timeout is not defined']}, True)]
            for errors, eligible in cases:
                with self.subTest(errors=errors):
                    self.assertIs(self.parse(admission, rejected(errors))['raw_receipt']['settlement_eligible'], eligible)

    def test_compile_rejection_remains_distinct_from_a_backtest_submission(self):
        with lean_fixture() as (_, _, admission):
            with self.assertRaises(receipts.ReceiptParseError):
                receipts.backtest_submission(admission['payload'], admission['deployment'], rejected())

    def test_cli_recovers_v1_and_v2_original_attempt_without_current_pointer(self):
        self.parser()
        for version in (1, 2):
            with self.subTest(version=version), lean_fixture(version) as (fixture, attempt, admission):
                original_input = (fixture.root / admission['input_path']).read_bytes()
                fixture.alter_current_context(pointer=False)
                before = fixture.registry.snapshot()['usage']
                result = fixture.command('backtest-rejection', attempt=attempt, tool=rejected())
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['config_id'], fixture.bridge.config_id)
                self.assertIsNone(result['external_id'])
                self.assertEqual(fixture.registry.snapshot()['usage'], before)
                self.assertEqual(before['lean']['total'], 1)
                self.assertEqual((fixture.root / admission['input_path']).read_bytes(), original_input)
                self.assertNotIn(SECRET.encode(), b''.join(fixture.store._data.values()))

    def test_same_rejection_is_idempotent_and_different_evidence_is_not_replayed(self):
        self.parser()
        with lean_fixture() as (fixture, attempt, _):
            first = fixture.command('backtest-rejection', attempt=attempt, tool=rejected())
            before = deepcopy(fixture.registry.snapshot()); saved = dict(fixture.store._data)
            self.assertEqual(fixture.command('backtest-rejection', attempt=attempt, tool=rejected()), first)
            self.assertEqual(fixture.store._data, saved)
            with self.assertRaises((ValueError, EngineeringTaskError)):
                fixture.command('backtest-rejection', attempt=attempt, tool=rejected({'stub.py': ['3:4 different']}))
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)

    def test_ambiguous_without_accepted_identity_can_reconcile_only_definite_rejection(self):
        self.parser()
        with lean_fixture() as (fixture, attempt, _):
            fixture.registry.ambiguous(attempt, reason='Synthetic uncertain dispatch')
            usage = deepcopy(fixture.registry.snapshot()['usage'])
            result = fixture.command('backtest-rejection', attempt=attempt, tool=rejected())
            self.assertEqual(result['status'], 'failed')
            self.assertTrue(fixture.bridge._record(attempt)['reconciliation'])
            self.assertEqual(fixture.registry.snapshot()['usage'], usage)

    def test_unclassified_server_transport_and_timeout_errors_do_not_settle(self):
        self.parser()
        for errors in (['timeout'], ['unexpected server response'], ['internal error'], ['bad gateway'],
                       ['connection lost'], {'stub.py': ['no structured compile location']}):
            with self.subTest(errors=errors), lean_fixture() as (fixture, attempt, _):
                saved = dict(fixture.store._data); before = fixture.registry.snapshot()
                with self.assertRaises((ValueError, EngineeringTaskError)):
                    fixture.command('backtest-rejection', attempt=attempt, tool=rejected(errors))
                self.assertEqual(fixture.store._data, saved)
                self.assertEqual(fixture.registry.snapshot(), before)

    def test_pending_and_ambiguous_with_accepted_submission_cannot_be_overwritten(self):
        self.parser()
        for ambiguous in (False, True):
            with self.subTest(ambiguous=ambiguous), lean_fixture() as (fixture, attempt, admission):
                tool = envelope('create_backtest', {'projectId': 17}, {'success': True, 'backtestId': 'native-id'})
                if ambiguous:
                    fixture.registry.ambiguous(attempt, reason='Synthetic uncertain dispatch')
                fixture.command('backtest-submission', attempt=attempt, tool=tool)
                before = fixture.registry.snapshot(); saved = dict(fixture.store._data)
                with self.assertRaises((ValueError, EngineeringTaskError)):
                    fixture.command('backtest-rejection', attempt=attempt, tool=rejected())
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_external_id_pointer_and_final_failure_block_without_persisting_evidence(self):
        self.parser()
        for guard in ('external', 'pointer', 'failed'):
            with self.subTest(guard=guard), lean_fixture() as (fixture, attempt, _):
                if guard == 'external':
                    fixture.registry.pending(attempt, external_id='native-id')
                    fixture.registry.ambiguous(attempt, reason='Synthetic uncertain read')
                elif guard == 'pointer':
                    fixture.store.write_once(fixture.bridge._submission_key(attempt), b'{}')
                else:
                    fixture.registry.fail(attempt, 'different confirmed failure')
                saved = dict(fixture.store._data); before = fixture.registry.snapshot()
                with self.assertRaises((ValueError, EngineeringTaskError)):
                    fixture.command('backtest-rejection', attempt=attempt, tool=rejected())
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_malformed_or_foreign_input_is_rejected_before_rejection_write(self):
        self.parser()
        with lean_fixture() as (fixture, attempt, admission):
            path = fixture.root / admission['input_path']; path.write_bytes(b'tampered')
            saved = dict(fixture.store._data); before = fixture.registry.snapshot()
            with self.assertRaises(ValueError):
                fixture.command('backtest-rejection', attempt=attempt, tool=rejected())
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)

    def test_real_filesystem_path_uses_one_transaction_without_nested_registry_lock(self):
        self.parser()
        with lean_fixture() as (fixture, attempt, admission):
            filesystem = FilesystemArtifactStore(fixture.root / 'synthetic-store')
            for key, data in fixture.store._data.items():
                filesystem.write_once(key, data)
            registry = Registry(filesystem, fixture.registry.limits)
            with patch.object(cli, 'open_registry', return_value=registry):
                result = fixture.command('backtest-rejection', attempt=attempt, tool=rejected())
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(fixture.command('backtest-rejection', attempt=attempt, tool=rejected()), result)
            self.assertEqual(registry.snapshot()['usage']['lean']['total'], 1)

    def test_concurrent_acceptance_and_rejection_cannot_publish_conflicting_final_state(self):
        self.parser()
        for replay in range(12):
            with self.subTest(replay=replay), lean_fixture() as (fixture, attempt, admission):
                gate = threading.Barrier(2); results = []
                accepted = receipts.backtest_submission(admission['payload'], admission['deployment'],
                    envelope('create_backtest', {'projectId': 17}, {'success': True, 'backtestId': 'native-id'}))
                rejection = self.parse(admission, rejected())
                def call(method, receipt):
                    gate.wait()
                    try:
                        results.append(method(attempt, receipt).status)
                    except (ValueError, EngineeringTaskError):
                        results.append('rejected_conflict')
                threads = [threading.Thread(target=call, args=(fixture.bridge.record_submission, accepted)),
                           threading.Thread(target=call, args=(fixture.bridge.record_rejection, rejection))]
                for thread in threads: thread.start()
                for thread in threads: thread.join(5)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
                state = fixture.bridge._record(attempt)
                self.assertIn(state['status'], {'pending', 'failed'})
                self.assertEqual(results.count('rejected_conflict'), 1)
                self.assertEqual(fixture.store.exists(fixture.bridge._submission_key(attempt)), state['status'] == 'pending')
                self.assertEqual(fixture.registry.snapshot()['usage']['lean']['total'], 1)


if __name__ == '__main__':
    unittest.main()
