"""Synthetic nbformat error grammar; not an observed QC failed-cell receipt."""
from copy import deepcopy
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import canonical_json, content_hash
from qresearch.engineering_tasks import EngineeringTaskError
import qresearch.engineering_receipts as receipts
import stage2 as cli
from test_engineering_receipts import context, envelope, report, research_tool
from test_wr17_engineering_recovery import SyntheticFixture

SECRET = "SYNTHETIC_PRIVATE_TRACEBACK_WITH_MARKET_VALUE_123.45"


def cell_error(**changes):
    node = {"output_type": "error", "ename": "ValueError", "evalue": SECRET,
            "traceback": ["Traceback: " + SECRET, "ValueError: " + SECRET]}
    node.update(changes)
    return node


def error_tool(native=None, *, index=2, is_error=False):
    tool = envelope("jupyter_execute_cell", {"projectId": 17, "index": index},
                    cell_error() if native is None else native)
    tool["result"]["isError"] = is_error
    return tool


def read_cell(payload, deployment, *, index=2, source=None):
    source = receipts.research_cell_source(payload, deployment) if source is None else source
    return envelope("jupyter_read_cell", {"projectId": 17, "index": index},
                    {"cellType": "code", "source": source.splitlines(keepends=True)})


def bind(payload, deployment, *, index=2):
    return receipts.research_dispatch_binding(payload, deployment, read_cell(payload, deployment, index=index))


class NativeResearchFailureTests(unittest.TestCase):
    def parse(self, *, payload=None, deployment=None, tool=None, binding=None):
        if payload is None:
            payload, deployment = context("research")
        if binding is None:
            binding = bind(payload, deployment)
        return receipts.research_execution_failure(payload, deployment,
            error_tool() if tool is None else tool, dispatch_binding=binding)

    def test_exact_synthetic_error_grammar_emits_only_bound_hashes_and_counts(self):
        payload, deployment = context("research")
        tool = error_tool()
        result = self.parse(payload=payload, deployment=deployment, tool=tool)
        self.assertEqual(set(result), {"submission", "completion"})
        self.assertEqual(set(result["completion"]), {"platform"})
        self.assertIs(result["submission"]["accepted"], True)
        platform = result["completion"]["platform"]
        self.assertEqual(platform["status"], "runtime_error")
        self.assertIs(platform["terminal"], True)
        self.assertEqual(platform["deployment"], deployment)
        self.assertEqual(platform["identity"]["external_id"], "qc-research:17:" + "1" * 32)
        self.assertEqual(platform["raw_receipt"]["response_sha256"], content_hash(tool["result"]))
        self.assertIs(platform["raw_receipt"]["native_research_error"], True)
        self.assertEqual(platform["raw_receipt"]["error_output_count"], 1)
        self.assertEqual(platform["raw_receipt"]["traceback_line_count"], 2)
        encoded = json.dumps(result)
        for value in (SECRET, "traceback\"", "evalue", "ValueError", "cell_source"):
            if value == "cell_source":
                self.assertNotIn('"cell_source":', encoded)
            else:
                self.assertNotIn(value, encoded)

    def test_registered_error_shapes_and_semantic_carriers(self):
        for native in (cell_error(), [cell_error()], {"status": "error", "outputs": [cell_error()]},
                       {"status": "error", "execution_count": 1, "cell_index": 2,
                        "outputs": [cell_error()], "metadata": {}}):
            for is_error in (False, True):
                with self.subTest(native=native, is_error=is_error):
                    tool = error_tool(native, is_error=is_error)
                    for shape in ("mirrored", "content", "structured"):
                        value = deepcopy(tool)
                        if shape == "content":
                            del value["result"]["structuredContent"]
                        elif shape == "structured":
                            del value["result"]["content"]
                        result = self.parse(tool=value)
                        self.assertEqual(result["completion"]["platform"]["status"], "runtime_error")

    def test_missing_dispatch_and_wrong_attempt_input_index_or_protocol_reject(self):
        payload, deployment = context("research")
        binding = bind(payload, deployment)
        variants = [None, {}, dict(binding, protocol="unknown"), dict(binding, cell_source_sha256="0" * 64)]
        for field in ("attempt_id", "plan_hash", "config_id", "source_manifest_hash", "deployment_hash"):
            value = deepcopy(binding)
            value["identity"][field] = "0" * (32 if field == "attempt_id" else 64)
            variants.append(value)
        for field in ("input_hash", "source_manifest_hash", "deployment_hash"):
            value = deepcopy(binding)
            value["deployment"][field] = "0" * 64
            variants.append(value)
        value = deepcopy(binding); value["arguments"]["index"] = 3; variants.append(value)
        for value in variants:
            with self.subTest(binding=value), self.assertRaises(receipts.ReceiptParseError):
                receipts.research_execution_failure(payload, deployment, error_tool(), dispatch_binding=value)

    def test_success_caught_exception_marker_stderr_rows_and_network_are_not_native_failure(self):
        payload, deployment = context("research")
        variants = [
            {"success": False, "errors": ["Request timed out", SECRET]},
            {"success": False, "errors": [SECRET]},
            {"status": "ok", "outputs": [cell_error()]},
            {"status": "pending", "outputs": [cell_error()]},
            {"status": "error", "outputs": [cell_error(), {"output_type": "stream", "name": "stdout", "text": SECRET}]},
            {"status": "error", "outputs": [cell_error(), {"output_type": "stream", "name": "stderr", "text": SECRET}]},
            {"status": "error", "outputs": [cell_error()], "rows": [1]},
            {"status": "error", "outputs": [cell_error(), cell_error()]},
            {"output_type": "stream", "name": "stdout", "text": json.dumps(cell_error())},
        ]
        variants.append(research_tool(payload)["result"]["structuredContent"])
        for native in variants:
            with self.subTest(native=native), self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool=error_tool(native))

    def test_error_shape_types_unknown_keys_and_bounds_are_closed(self):
        variants = [{"output_type": "stream"}, {"ename": ""}, {"ename": "bad name"},
            {"ename": SECRET * 20}, {"evalue": 1}, {"evalue": SECRET * 10000},
            {"traceback": []}, {"traceback": [""]}, {"traceback": "not-list"},
            {"traceback": [False]}, {"traceback": [SECRET] * 129}, {"rows": [1]},
            {"data": {"text/plain": SECRET}}]
        for change in variants:
            with self.subTest(change=change), self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool=error_tool(cell_error(**change)))
        self.assertEqual(self.parse(tool=error_tool(cell_error(evalue="")))["completion"]["platform"]["status"], "runtime_error")

    def test_tool_project_index_internal_index_and_stage_are_exact(self):
        for mutate in (lambda t: t.update(tool_name="mcp__quantconnect__jupyter_read_cell"),
                lambda t: t["arguments"].update(projectId=18),
                lambda t: t["arguments"].update(projectId=True),
                lambda t: t["arguments"].update(index=True),
                lambda t: t["arguments"].update(index=-1),
                lambda t: t["arguments"].update(extra=SECRET)):
            tool = error_tool(); mutate(tool)
            with self.subTest(mutate=mutate), self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool=tool)
        for value in (True, -1, 3):
            with self.subTest(value=value), self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool=error_tool({"status": "error", "cell_index": value, "outputs": [cell_error()]}))
        payload, deployment = context("lean")
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(payload=payload, deployment=deployment)

    def test_mcp_mirror_hidden_output_and_flag_type_reject_without_leaking(self):
        mutations = (lambda r: r["content"][0].update(text="network failure"),
            lambda r: r["content"].append({"type": "text", "text": SECRET}),
            lambda r: r.update(_meta={"rows": [SECRET]}), lambda r: r.update(extra=SECRET),
            lambda r: r["content"][0].update(annotations={"rows": [SECRET]}),
            lambda r: r.update(isError=1), lambda r: r.update(isError="true"))
        for mutate in mutations:
            tool = error_tool(); mutate(tool["result"])
            with self.subTest(mutate=mutate), self.assertRaises(receipts.ReceiptParseError) as caught:
                self.parse(tool=tool)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_actual_read_cell_must_equal_exact_canonical_source_before_binding(self):
        payload, deployment = context("research")
        value = bind(payload, deployment)
        self.assertEqual(value["identity"], payload["identity"])
        self.assertEqual(value["deployment"], deployment)
        self.assertEqual(value["arguments"], {"projectId": 17, "index": 2})
        self.assertNotIn("source", value)
        for change in ("\n", "# another cell\n", receipts.research_cell_source(payload, deployment).replace("run_research_task", "evil")):
            with self.subTest(change=change), self.assertRaises(receipts.ReceiptParseError):
                receipts.research_dispatch_binding(payload, deployment, read_cell(payload, deployment, source=change))
        for mutate in (lambda t: t.update(tool_name="mcp__quantconnect__jupyter_execute_cell"),
                lambda t: t["arguments"].update(projectId=18),
                lambda t: t["arguments"].update(index=True),
                lambda t: t["result"]["structuredContent"].update(outputs=[cell_error()]),
                lambda t: t["result"]["structuredContent"].update(cellType="markdown")):
            tool = read_cell(payload, deployment); mutate(tool)
            with self.subTest(mutate=mutate), self.assertRaises(receipts.ReceiptParseError):
                receipts.research_dispatch_binding(payload, deployment, tool)

    def test_canonical_cell_reads_original_input_once_and_emits_existing_success_marker(self):
        payload, deployment = context("research")
        raw = ("TASK_INPUT_JSON = " + repr(canonical_json(payload).decode()) + "\n").encode()
        deployment["input_hash"] = hashlib.sha256(raw).hexdigest()
        source = receipts.research_cell_source(payload, deployment)
        output = io.StringIO()
        import builtins
        original_import = builtins.__import__
        calls = []
        def controlled_import(name, *args, **kwargs):
            if name == "qresearch.engineering_data":
                return SimpleNamespace(run_research_task=lambda value: calls.append(value) or report(value))
            if name == "qresearch.artifacts":
                return SimpleNamespace(canonical_json=canonical_json)
            return original_import(name, *args, **kwargs)
        # The real cloud cell evicts stale shared modules. Restore this test
        # process's module registry afterward, and inject no market provider.
        with patch.dict(sys.modules), patch("builtins.__import__", side_effect=controlled_import), \
                patch("pathlib.Path.read_bytes", return_value=raw) as read, redirect_stdout(output):
            exec(compile(source, "synthetic-fixed-research-cell", "exec"), {})
        self.assertEqual(read.call_count, 1)
        self.assertEqual(calls, [payload])
        self.assertIn("_aqrp_sys.modules.pop", source)
        tool = envelope("jupyter_execute_cell", {"projectId": 17, "index": 2},
            {"output_type": "stream", "name": "stdout", "text": output.getvalue()})
        observed = receipts.research_observation(payload, deployment, tool)
        self.assertEqual(observed["completion"]["cloud_report"], report(payload)["cloud_report"])

    def test_changed_raw_input_is_rejected_before_any_cloud_worker_call(self):
        payload, deployment = context("research")
        source = receipts.research_cell_source(payload, deployment)
        with patch("pathlib.Path.read_bytes", return_value=b"arbitrary changed input"), \
                patch("qresearch.engineering_data.run_research_task") as run, self.assertRaisesRegex(ValueError, "input identity"):
            exec(compile(source, "synthetic-fixed-research-cell", "exec"), {})
        run.assert_not_called()

    def test_success_without_dispatch_remains_compatible_but_failure_needs_original_binding(self):
        payload, deployment = context("research")
        self.assertEqual(receipts.research_observation(payload, deployment, research_tool(payload))["completion"]["platform"]["status"], "completed")
        with self.assertRaises(receipts.ReceiptParseError):
            receipts.research_observation(payload, deployment, error_tool())
        failure = receipts.research_observation(payload, deployment, error_tool(), dispatch_binding=bind(payload, deployment))
        self.assertEqual(failure["completion"]["platform"]["status"], "runtime_error")

    def test_cli_dispatch_is_one_time_no_budget_change_and_failure_is_idempotent(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                before = fixture.registry.snapshot()
                source = fixture.command("research-cell", attempt=fixture.attempt)
                self.assertIs(source["execution_started"], False)
                read = read_cell(fixture.admission["payload"], fixture.admission["deployment"])
                dispatch = fixture.command("research-dispatch", attempt=fixture.attempt, tool=read)
                self.assertIs(dispatch["should_execute"], True)
                self.assertIs(fixture.command("research-dispatch", attempt=fixture.attempt, tool=read)["should_execute"], False)
                self.assertEqual(fixture.registry.snapshot(), before)
                failed = fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())
                self.assertEqual(failed["status"], "failed")
                after = fixture.registry.snapshot(); saved = dict(fixture.store._data)
                self.assertEqual(after["usage"], before["usage"])
                self.assertEqual(fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())["status"], "failed")
                self.assertEqual(fixture.registry.snapshot(), after)
                self.assertEqual(fixture.store._data, saved)
                self.assertNotIn(SECRET, str(fixture.store._data))
                with self.assertRaises(EngineeringTaskError):
                    fixture.bridge.claim("lean")

    def test_cli_without_dispatch_network_failure_and_changed_cell_do_not_write(self):
        for native in (cell_error(), {"success": False, "errors": ["Request timed out"]}):
            with SyntheticFixture(1) as fixture:
                before = fixture.registry.snapshot(); saved = dict(fixture.store._data)
                with self.assertRaises(receipts.ReceiptParseError):
                    fixture.command("research-result", attempt=fixture.attempt, tool=error_tool(native))
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)
        with SyntheticFixture(1) as fixture:
            read = read_cell(fixture.admission["payload"], fixture.admission["deployment"], source="print('foreign')\n")
            before = fixture.registry.snapshot(); saved = dict(fixture.store._data)
            with self.assertRaises(receipts.ReceiptParseError):
                fixture.command("research-dispatch", attempt=fixture.attempt, tool=read)
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)

    def test_cli_recovery_uses_original_binding_and_input_after_current_context_removed(self):
        with SyntheticFixture(2) as fixture:
            read = read_cell(fixture.admission["payload"], fixture.admission["deployment"])
            fixture.command("research-dispatch", attempt=fixture.attempt, tool=read)
            fixture.alter_current_context(pointer=False)
            self.assertEqual(fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())["status"], "failed")
            self.assertEqual(fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())["status"], "failed")

    def test_cli_changed_failure_cannot_overwrite_original_terminal(self):
        with SyntheticFixture(1) as fixture:
            read = read_cell(fixture.admission["payload"], fixture.admission["deployment"])
            fixture.command("research-dispatch", attempt=fixture.attempt, tool=read)
            fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())
            before = fixture.registry.snapshot(); saved = dict(fixture.store._data)
            with self.assertRaises(EngineeringTaskError):
                fixture.command("research-result", attempt=fixture.attempt, tool=error_tool(cell_error(evalue="different")))
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)

    def test_dispatch_cannot_backfill_an_accepted_or_ambiguous_execution(self):
        for status in ("pending", "ambiguous"):
            with self.subTest(status=status), SyntheticFixture(1) as fixture:
                if status == "pending":
                    parsed = receipts.research_observation(fixture.admission["payload"], fixture.admission["deployment"], fixture.research_observation())
                    fixture.bridge.record_submission(fixture.attempt, parsed["submission"])
                else:
                    fixture.registry.ambiguous(fixture.attempt, reason="Synthetic unknown dispatch")
                before = fixture.registry.snapshot(); saved = dict(fixture.store._data)
                with self.assertRaises(EngineeringTaskError):
                    fixture.command("research-dispatch", attempt=fixture.attempt,
                        tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"]))
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_concurrent_dispatch_has_only_one_execute_permission(self):
        with SyntheticFixture(1) as fixture:
            tool = read_cell(fixture.admission["payload"], fixture.admission["deployment"])
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [pool.submit(cli.research_dispatch, fixture.bridge, fixture.attempt, deepcopy(tool)) for _ in range(2)]
                results = [job.result() for job in jobs]
            self.assertEqual(sum(result["should_execute"] for result in results), 1)

    def test_boolean_alias_in_saved_dispatch_does_not_equal_integer_cell_index(self):
        payload, deployment = context("research")
        binding = bind(payload, deployment, index=1)
        binding["arguments"]["index"] = True
        with self.assertRaises(receipts.ReceiptParseError):
            receipts.research_execution_failure(payload, deployment, error_tool(index=1), dispatch_binding=binding)

    def test_legacy_started_input_cannot_backfill_dispatch_or_new_entry_protocol(self):
        with SyntheticFixture(1) as fixture:
            key = "engineering/research-entry-protocol/" + fixture.attempt + ".json"
            del fixture.store._data[key]
            before = fixture.registry.snapshot(); saved = dict(fixture.store._data)
            self.assertEqual(cli.prepare(fixture.bridge, fixture.attempt), fixture.admission)
            self.assertEqual(fixture.store._data, saved)
            with self.assertRaises(EngineeringTaskError):
                fixture.command("research-dispatch", attempt=fixture.attempt,
                    tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"]))
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)
            self.assertEqual(fixture.settle_research()["status"], "completed")

    def test_missing_original_entry_protocol_cannot_recover_a_bound_failure(self):
        with SyntheticFixture(1) as fixture:
            fixture.command("research-dispatch", attempt=fixture.attempt,
                tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"]))
            del fixture.store._data["engineering/research-entry-protocol/" + fixture.attempt + ".json"]
            before = fixture.registry.snapshot(); saved = dict(fixture.store._data)
            with self.assertRaises(EngineeringTaskError):
                fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)

    def test_prepare_protocol_write_fault_stays_blocked_and_never_backfills(self):
        with SyntheticFixture(1, prepare=False) as fixture:
            original = fixture.store.write_once
            def interrupted_protocol(key, data):
                if key.startswith("engineering/research-entry-protocol/"):
                    raise OSError("Synthetic admission marker write interrupted")
                return original(key, data)
            before = fixture.registry.snapshot()
            with patch.object(fixture.store, "write_once", side_effect=interrupted_protocol), self.assertRaises(OSError):
                cli.prepare(fixture.bridge, fixture.attempt)
            admission = cli.prepare(fixture.bridge, fixture.attempt)
            self.assertTrue(fixture.store.exists("engineering/admitted-inputs/" + fixture.attempt + ".json"))
            self.assertFalse(fixture.store.exists("engineering/research-entry-protocol/" + fixture.attempt + ".json"))
            with self.assertRaises(EngineeringTaskError):
                fixture.command("research-dispatch", attempt=fixture.attempt,
                    tool=read_cell(admission["payload"], admission["deployment"]))
            self.assertEqual(fixture.registry.snapshot(), before)

    def test_failure_settlement_recovers_after_original_evidence_write_fault(self):
        with SyntheticFixture(1) as fixture:
            fixture.command("research-dispatch", attempt=fixture.attempt,
                tool=read_cell(fixture.admission["payload"], fixture.admission["deployment"]))
            original = fixture.store.write_once
            injected = []
            def fail_first_submission(key, data):
                if "/submission/" in key and not injected:
                    injected.append(key)
                    raise OSError("Synthetic write interrupted")
                return original(key, data)
            before = fixture.registry.snapshot()
            with patch.object(fixture.store, "write_once", side_effect=fail_first_submission), self.assertRaises(OSError):
                fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertTrue(fixture.store.exists(fixture.bridge._submission_key(fixture.attempt)))
            self.assertEqual(fixture.command("research-result", attempt=fixture.attempt, tool=error_tool())["status"], "failed")
            self.assertEqual(fixture.registry.snapshot()["usage"], before["usage"])


if __name__ == "__main__":
    unittest.main()
