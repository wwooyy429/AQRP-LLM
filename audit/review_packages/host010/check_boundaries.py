"""Offline developer-support boundary checks; all stores are synthetic.

No market/QC/Research/LEAN/external calls; no production store is opened.
This is not independent stage acceptance or financial evidence.
"""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tools'), str(ROOT / 'tests')]
import followup_host as fh
import research
from qresearch.artifacts import FilesystemArtifactStore, canonical_json, decode_events
from qresearch.engineering_receipts import backtest_observation
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController
from test_task_followup import fixture, history, POLICY, DEADLINE
from test_engineering_tasks import submission

LIMITS = {kind: {'total': 10, 'normal': 8, 'reserve': 2} for kind in ('configurations', 'research', 'lean')}
EVIDENCE = Path(__file__).resolve().parent


def make_host(controller, attempt, **kwargs):
    authority = kwargs.pop('authority', fh.TransportAuthority('synthetic-boundary', frozenset({attempt}), frozenset({attempt})))
    return fh.FollowupHost(controller, enabled=True, authority=authority, clock=lambda: DEADLINE, **kwargs)


def response(request, result):
    return {key: deepcopy(request[key]) for key in ('attempt_id', 'correlation_id', 'tool_name', 'arguments')} | {'command': 'response', 'result': result}


def projects():
    return {'success': True, 'projects': [{'projectId': 17, 'name': 'SYNTHETIC', 'language': 'Py'}], 'page': 1, 'nextPage': None, 'totalPages': 1}


def reach_history():
    store, registry, bridge, attempt, controller = fixture()
    host = make_host(controller, attempt)
    discovery = host.prepare(attempt)
    assert discovery['tool_name'] == fh.PROJECTS
    assert host.accept_response(response(discovery, projects()))['action'] == 'projects_observed'
    request = host.prepare(attempt)
    assert request['tool_name'] == fh.HISTORY
    return store, registry, bridge, attempt, controller, host, request


def process_prepare(root, attempt):
    store = FilesystemArtifactStore(root, data_classification='synthetic')
    registry = Registry(store, LIMITS)
    controller = TaskFollowupController(registry, POLICY)
    return make_host(controller, attempt).prepare(attempt)


class HostBoundaryTests(unittest.TestCase):
    def test_default_gate_does_not_open_or_import_factory(self):
        out = io.StringIO()
        attempt = '1' * 32
        with patch.object(research, 'open_registry', side_effect=AssertionError('production registry accessed')), patch.object(fh.importlib, 'import_module', side_effect=AssertionError('factory imported')):
            fh.main(['serve', '--host-factory', 'must_not_load:factory'], input_stream=io.StringIO(json.dumps({'command': 'wake', 'attempt_id': attempt}) + '\n'), output_stream=out)
        self.assertEqual(json.loads(out.getvalue())['action'], 'dispatch_disabled')

    def test_discovery_reservation_survives_restart_and_original_response(self):
        store, registry, bridge, attempt, controller = fixture()
        before = registry.snapshot()['usage']
        host = make_host(controller, attempt)
        first = host.prepare(attempt)
        self.assertEqual(first['arguments'], {'page': 1})
        self.assertEqual(make_host(controller, attempt).prepare(attempt)['action'], 'attention_required')
        self.assertEqual(make_host(controller, attempt).accept_response(response(first, projects()))['action'], 'projects_observed')
        second = make_host(controller, attempt).prepare(attempt)
        self.assertEqual(second['tool_name'], fh.HISTORY)
        self.assertEqual(second['arguments'], {'projectId': 17, 'page': 1})
        self.assertEqual(make_host(controller, attempt).prepare(attempt)['action'], 'attention_required')
        requests = [e['event'] for e in decode_events(store.read_bytes(host._stream(attempt))) if e['event']['kind'] == 'reserved']
        self.assertEqual([r['tool_name'] for r in requests], [fh.PROJECTS, fh.HISTORY])
        self.assertEqual(registry.snapshot()['usage'], before)

    def test_exact_binding_rejects_wrong_tool_arguments_and_correlation(self):
        changes = [lambda m: m.update(correlation_id='0' * 32), lambda m: m.update(tool_name=fh.READ), lambda m: m['arguments'].update(page=True), lambda m: m['arguments'].update(extra='INJECTED_RAW_SENTINEL')]
        for change in changes:
            with self.subTest(change=change):
                store, registry, bridge, attempt, controller = fixture()
                host = make_host(controller, attempt)
                request = host.prepare(attempt)
                bad = response(request, projects())
                change(bad)
                answer = host.accept_response(bad)
                self.assertEqual(answer['failure_code'], 'response_binding_rejected')
                self.assertEqual(host.prepare(attempt)['action'], 'attention_required')
                self.assertNotIn(b'INJECTED_RAW_SENTINEL', store.read_bytes(host._stream(attempt)))

    def test_directory_terminal_and_input_booleans_cannot_grant_read(self):
        store, registry, bridge, attempt, controller, host, request = reach_history()
        host.accept_response(response(request, history()['result']))
        state = host.prepare(attempt)
        self.assertEqual(state['failure_code'], 'completed_read_not_authorized')
        events = [e['event'] for e in decode_events(store.read_bytes(controller._stream(attempt)))]
        self.assertNotIn('completed_read_reserved', [e['kind'] for e in events])
        for field in ('allow_read', 'should_execute', 'enabled', 'read_grants'):
            with self.assertRaises(ValueError):
                host.command({'command': 'wake', 'attempt_id': attempt, field: True})
        self.assertEqual(host.prepare(attempt)['action'], 'attention_required')

    def test_late_original_native_parser_settles_despite_host_attention(self):
        store, registry, bridge, attempt, controller, host, request = reach_history()
        original_usage = registry.snapshot()['usage']
        host.accept_response(response(request, history()['result']))
        self.assertEqual(host.prepare(attempt)['failure_code'], 'completed_read_not_authorized')
        payload = bridge.payload(attempt)
        deployment = submission(payload)['deployment']
        native = {'tool_name': fh.READ, 'arguments': {'projectId': 17, 'backtestId': 'actual-synthetic-backtest-id'}, 'result': {'isError': True, 'structuredContent': {'success': False, 'errors': ['The backtest ended with a runtime error.', 'SYNTHETIC late runtime terminal receipt']}}}
        parsed = backtest_observation(payload, deployment, 'actual-synthetic-backtest-id', native, [])
        terminal = bridge.consume_completion(attempt, completion_source=lambda _: parsed)
        self.assertEqual(terminal.status, 'failed')
        self.assertEqual(controller.sync(attempt)['action'], 'finished')
        self.assertEqual(host.prepare(attempt)['action'], 'finished')
        self.assertEqual(registry.snapshot()['usage'], original_usage)
        self.assertNotIn(b'SYNTHETIC late runtime terminal receipt', store.read_bytes(registry.JOURNAL))

    def test_malformed_and_ascii_overlimit_lines_have_no_store_writes(self):
        store, registry, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        before = dict(store._data)
        lines = ['{"command":"wake","command":"status","attempt_id":"' + attempt + '"}\n', '{"bad":NaN}\n', '{bad}\n', json.dumps({'command': 'wake', 'attempt_id': attempt}), 'A' * (fh.MAX_LINE + 1) + '\n']
        for line in lines:
            with self.subTest(length=len(line)):
                out = io.StringIO()
                fh.serve(host, io.StringIO(line), out)
                self.assertEqual(json.loads(out.getvalue())['action'], 'attention_required')
                self.assertEqual(store._data, before)

    def test_utf8_byte_limit_rejects_oversized_unicode_response(self):
        store, registry, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        request = host.prepare(attempt)
        before = dict(store._data)
        # Valid request binding; invalid native field is intentionally enormous.
        # Character count stays below MAX_LINE, while UTF-8 bytes exceed it.
        message = response(request, projects() | {'extra': '\u754c' * (fh.MAX_LINE // 2)})
        line = json.dumps(message, ensure_ascii=False) + '\n'
        self.assertLess(len(line), fh.MAX_LINE)
        self.assertGreater(len(line.encode('utf-8')), fh.MAX_LINE)
        out = io.StringIO()
        fh.serve(host, io.StringIO(line), out)
        self.assertEqual({k: len(v) for k, v in store._data.items()}, {k: len(v) for k, v in before.items()}, 'oversized UTF-8 response reached the durable ledger')

    def test_host_status_exposes_unknown_project_discovery(self):
        store, registry, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        self.assertEqual(host.prepare(attempt)['tool_name'], fh.PROJECTS)
        result = host.command({'command': 'status', 'attempt_id': attempt})
        self.assertEqual(result['action'], 'attention_required')
        self.assertEqual(result['failure_code'], 'reserved_response_unknown')

    def test_direct_api_rejects_byte_oversize_before_persistence(self):
        store, registry, bridge, attempt, controller = fixture()
        host = make_host(controller, attempt)
        request = host.prepare(attempt)
        before = dict(store._data)
        huge = response(request, projects() | {'extra': 'Z' * fh.MAX_LINE})
        try:
            host.accept_response(huge)
        except ValueError:
            pass
        self.assertEqual({k: len(v) for k, v in store._data.items()}, {k: len(v) for k, v in before.items()}, 'oversized API response reached persistence')

    def test_multiprocess_unique_discovery_output(self):
        memory, registry, bridge, attempt, controller = fixture()
        destination = EVIDENCE / ('synthetic-multiprocess-' + attempt)
        store = FilesystemArtifactStore(destination, data_classification='synthetic')
        for key, data in memory._data.items():
            store.write_once(key, data)
        with ProcessPoolExecutor(max_workers=4) as pool:
            answers = list(pool.map(process_prepare, [str(destination)] * 8, [attempt] * 8))
        self.assertEqual(sum(answer['type'] == 'tool_request' for answer in answers), 1)
        request = next(answer for answer in answers if answer['type'] == 'tool_request')
        self.assertEqual(request['tool_name'], fh.PROJECTS)
        events = [e['event'] for e in decode_events(store.read_bytes(fh.FollowupHost._stream(attempt)))]
        self.assertEqual(sum(event['kind'] == 'reserved' for event in events), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
