"""Observed native-error shape, with synthetic diagnostics and no provider I/O."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tools'), str(ROOT / 'tests')]
import qresearch.engineering_receipts as receipts
import stage2 as cli
from qresearch.artifacts import content_hash
from qresearch.engineering_tasks import EngineeringTaskError
from test_engineering_receipts import context, envelope, completed_tool, log_tools, report
from test_wr17_engineering_recovery import SyntheticFixture

MARKER = 'The backtest ended with a runtime error.'
SECRET = 'SYNTHETIC_PRIVATE_DIAGNOSTIC_123.45'
EXTERNAL = 'native-backtest-id'


def native_failure(errors=None):
    native = {'success': False, 'errors': [MARKER, 'During initialize: ' + SECRET, 'Traceback: ' + SECRET] if errors is None else errors}
    tool = envelope('read_backtest', {'projectId': 17, 'backtestId': EXTERNAL}, native)
    tool['result']['isError'] = True
    return tool


class NativeRuntimeFailureTests(unittest.TestCase):
    def parse(self, payload=None, deployment=None, tool=None, external=EXTERNAL):
        if payload is None:
            payload, deployment = context('lean')
        method = getattr(receipts, 'backtest_runtime_failure', None)
        self.assertTrue(callable(method), 'Missing fixed native terminal runtime-error parser')
        return method(payload, deployment, external, native_failure() if tool is None else tool)

    def test_exact_observed_shape_yields_only_bounded_failure_metadata(self):
        tool = native_failure()
        result = self.parse(tool=tool)
        self.assertEqual(set(result), {'platform'})
        platform = result['platform']
        self.assertEqual(platform['status'], 'runtime_error')
        self.assertIs(platform['terminal'], True)
        self.assertEqual(platform['identity']['external_id'], EXTERNAL)
        raw = platform['raw_receipt']
        self.assertIs(raw['success'], False)
        self.assertIs(raw['native_runtime_error'], True)
        self.assertEqual(raw['diagnostic_count'], 2)
        self.assertEqual(raw['response_sha256'], content_hash(tool['result']))
        self.assertEqual(raw['arguments'], tool['arguments'])
        self.assertEqual(set(raw), {'tool_name', 'arguments', 'response_sha256', 'success', 'native_runtime_error', 'diagnostic_count'})
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn('backtest', result)
        self.assertNotIn('orders_count', raw)
        self.assertNotIn('completed', raw)

    def test_backtest_observation_routes_native_terminal_error_without_logs(self):
        payload, deployment = context('lean')
        expected = self.parse(payload, deployment)
        self.assertEqual(receipts.backtest_observation(payload, deployment, EXTERNAL, native_failure(), []), expected)

    def test_content_only_structured_only_and_semantically_equal_mirrors(self):
        for shape in ('content', 'structured', 'mirrored'):
            with self.subTest(shape=shape):
                tool = native_failure()
                if shape == 'content':
                    del tool['result']['structuredContent']
                elif shape == 'structured':
                    del tool['result']['content']
                else:
                    native = tool['result']['structuredContent']
                    tool['result']['content'][0]['text'] = json.dumps(native, indent=4)
                self.assertEqual(self.parse(tool=tool)['platform']['status'], 'runtime_error')

    def test_transport_timeout_and_missing_terminal_marker_are_not_failures(self):
        variants = ([MARKER], ['Request timed out', SECRET], ['Network unavailable', SECRET],
            ['Internal server error', SECRET], ['The backtest is still in progress.', SECRET],
            [' ' + MARKER, SECRET], [MARKER + ' unknown', SECRET], ['', SECRET])
        for errors in variants:
            with self.subTest(errors=errors):
                with self.assertRaises(receipts.ReceiptParseError):
                    self.parse(tool=native_failure(errors))

    def test_errors_are_nonempty_strings_with_at_least_one_actual_diagnostic(self):
        variants = (None, {}, '', [], [MARKER, ''], [MARKER, ' \n\t'], [MARKER, MARKER],
            [MARKER, MARKER, SECRET], [MARKER, False],
            [MARKER, ['rows']], [MARKER, {'rows': [1]}], [MARKER, 1], [MARKER, None])
        for errors in variants:
            with self.subTest(errors=errors):
                tool = native_failure()
                native = tool['result']['structuredContent']
                native['errors'] = errors
                tool['result']['content'][0]['text'] = json.dumps(native)
                with self.assertRaises(receipts.ReceiptParseError):
                    self.parse(tool=tool)

    def test_exact_failure_boolean_and_only_registered_native_fields(self):
        for update in ({'success': True}, {'success': 0}, {'success': 'false'},
                {'backtest': {}}, {'backtestId': EXTERNAL}, {'status': 'Runtime Error'},
                {'statistics': {'Total Orders': '0'}}, {'rows': [[1, 2]]}):
            with self.subTest(update=update):
                tool = native_failure()
                native = tool['result']['structuredContent']
                native.update(update)
                tool['result']['content'][0]['text'] = json.dumps(native)
                with self.assertRaises(receipts.ReceiptParseError):
                    self.parse(tool=tool)

    def test_explicit_mcp_error_flag_is_required_and_cannot_be_truthy_alias(self):
        for value in (None, False, 0, 1, 'true'):
            with self.subTest(value=value):
                tool = native_failure()
                if value is None:
                    del tool['result']['isError']
                else:
                    tool['result']['isError'] = value
                with self.assertRaises(receipts.ReceiptParseError):
                    self.parse(tool=tool)

    def test_mirror_conflicts_extra_text_and_unregistered_envelope_metadata_reject(self):
        for mutation in (
                lambda r: r['content'][0].update(text='network error'),
                lambda r: r['content'].append({'type': 'text', 'text': SECRET}),
                lambda r: r.update(_meta={'rows': [1]}),
                lambda r: r.update(extra_output=SECRET),
                lambda r: r['content'].append({'type': 'image', 'data': SECRET}),
                lambda r: r['content'][0].update(annotations={'rows': [1]})):
            tool = native_failure()
            mutation(tool['result'])
            with self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool=tool)

    def test_registered_annotations_do_not_expand_failure_or_time_certification(self):
        tool = native_failure()
        tool['result']['content'][0]['annotations'] = {'audience': ['assistant'], 'priority': 0.5,
            'lastModified': '2026-10-27T06:00:00.1234Z'}
        result = self.parse(tool=tool)
        self.assertNotIn('lastModified', json.dumps(result))
        self.assertEqual(result['platform']['status'], 'runtime_error')

    def test_tool_project_external_id_and_stage_are_exactly_bound(self):
        variants = (
            lambda t: t.update(tool_name='mcp__quantconnect__create_backtest'),
            lambda t: t['arguments'].update(projectId=18),
            lambda t: t['arguments'].update(projectId=True),
            lambda t: t['arguments'].update(backtestId='another-native-id'),
            lambda t: t['arguments'].pop('backtestId'),
            lambda t: t['arguments'].update(extra=SECRET))
        for mutation in variants:
            tool = native_failure()
            mutation(tool)
            with self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool=tool)
        payload, deployment = context('research')
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(payload, deployment)
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(external='wrong-expected-id')

    def test_payload_and_deployment_shape_validation_remains_mandatory(self):
        payload, deployment = context('lean')
        for field in ('source_manifest_hash', 'deployment_hash', 'input_hash'):
            bad = dict(deployment, **{field: 'not-a-hash'})
            with self.subTest(field=field), self.assertRaises(receipts.ReceiptParseError):
                self.parse(payload, bad)
        changed = deepcopy(payload)
        changed['identity']['plan_hash'] = 'f' * 64
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(changed, deployment)

    def test_existing_success_and_success_flag_runtime_failure_paths_are_unchanged(self):
        payload, deployment = context('lean')
        success = receipts.backtest_observation(payload, deployment, EXTERNAL, completed_tool(), log_tools(payload))
        self.assertEqual(success['platform']['status'], 'completed')
        self.assertEqual(success['cloud_report'], report(payload)['cloud_report'])
        failed = receipts.backtest_observation(payload, deployment, EXTERNAL,
            completed_tool(status='Runtime Error', completed=False, progress=0, error=SECRET), [])
        self.assertEqual(failed['platform']['status'], 'failed')
        tool = completed_tool()
        tool['result']['isError'] = True
        with self.assertRaises(receipts.ReceiptParseError):
            receipts.backtest_observation(payload, deployment, EXTERNAL, tool, [])

    def test_default_native_and_other_parser_error_denies_remain_closed(self):
        with self.assertRaises(receipts.ReceiptParseError):
            receipts._native(native_failure()['result'])
        payload, deployment = context('lean')
        for parser in (receipts.backtest_submission, receipts.backtest_rejection):
            with self.assertRaises(receipts.ReceiptParseError):
                parser(payload, deployment, native_failure())

    def test_original_accepted_binding_settles_failed_once_without_refund(self):
        with SyntheticFixture(1) as fixture:
            fixture.settle_research()
            attempt = fixture.bridge.claim('lean').attempt_id
            admission = cli.prepare(fixture.bridge, attempt)
            accepted = envelope('create_backtest', {'projectId': 17}, {'success': True, 'backtestId': EXTERNAL})
            fixture.bridge.record_submission(attempt,
                receipts.backtest_submission(admission['payload'], admission['deployment'], accepted))
            before = fixture.registry.snapshot()
            observed = self.parse(admission['payload'], admission['deployment'])
            failed = fixture.bridge.consume_completion(attempt, completion_source=lambda _: observed)
            self.assertEqual(failed.status, 'failed')
            after = fixture.registry.snapshot()
            self.assertEqual(before['usage'], after['usage'])
            self.assertEqual(fixture.bridge.consume_completion(attempt, completion_source=lambda _: observed).status, 'failed')
            self.assertEqual(fixture.registry.snapshot(), after)
            self.assertNotIn(SECRET, ''.join(value.decode('utf-8') for value in fixture.store._data.values()))

    def test_valid_but_different_input_hash_is_rejected_by_original_bridge_binding(self):
        with SyntheticFixture(1) as fixture:
            fixture.settle_research()
            attempt = fixture.bridge.claim('lean').attempt_id
            admission = cli.prepare(fixture.bridge, attempt)
            accepted = envelope('create_backtest', {'projectId': 17}, {'success': True, 'backtestId': EXTERNAL})
            fixture.bridge.record_submission(attempt,
                receipts.backtest_submission(admission['payload'], admission['deployment'], accepted))
            deployment = dict(admission['deployment'], input_hash='f' * 64)
            observed = self.parse(admission['payload'], deployment)
            before = fixture.registry.snapshot()
            with self.assertRaises(EngineeringTaskError):
                fixture.bridge.consume_completion(attempt, completion_source=lambda _: observed)
            self.assertEqual(fixture.registry.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
