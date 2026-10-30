"""Native-shaped synthetic QC observations; no platform calls or market values."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.engineering_receipts import (ReceiptParseError, research_observation,
    backtest_submission, backtest_observation)
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import Registry


def context(stage):
    document = {"schema_version": 1, "plan_id": "independent-receipt-fixture", "scope": "engineering",
        "project_id": 17, "source_manifest_hash": "a" * 64, "deployment_hash": "b" * 64,
        "request_mode": "symbol_resolution", "request_template": {"dataset": "US Equities", "fields": ["close", "volume"],
            "start": "2018-01-01T00:00:00-05:00", "end": "2019-01-01T00:00:00-05:00",
            "data_version": "synthetic-only", "universe_hash": "c" * 64, "normalization": "raw", "timezone": "America/New_York"},
        "symbol_resolution": {"tickers": ["AAPL", "MSFT"], "as_of": "2019-01-01T00:00:00-05:00",
            "method": "QuantBook.add_equity/as-of fixed fixture"},
        "observation_window": {"start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2018-01-10T00:00:00-05:00"},
        "required_checks": {"research": ["raw_data_received", "second_prefetch_no_history"], "lean": ["raw_data_received", "no_orders"]},
        "max_retries": {"research": 0, "lean": 0}, "report_namespace": "engineering/receipts",
        "orders_enabled": False, "financial_metrics_enabled": False, "economic_factor": None, "economic_model": None}
    plan = EngineeringTaskPlan.from_dict(document, discovered_project_ids=[17])
    identity = {"plan_hash": plan.hash, "config_id": content_hash({"engineering_task_schema_version": 1, "plan": plan.to_dict()}),
        "attempt_id": "1" * 32, "stage": stage, "project_id": 17,
        "source_manifest_hash": "a" * 64, "deployment_hash": "b" * 64, "data_request_hash": plan.request_hash}
    payload = {"plan": plan.to_dict(), "identity": identity,
        "report_key": "engineering/receipts/reports/" + plan.hash + "/" + stage + "/" + "1" * 32 + ".json",
        "external_identity_kind": "logical_research_execution_receipt" if stage == "research" else "quantconnect_backtest_id"}
    return payload, {"source_manifest_hash": "a" * 64, "deployment_hash": "b" * 64, "input_hash": "f" * 64}


def report(payload):
    references = {"resolved_registry_ref": {"key": "synthetic/registry.json", "sha256": "d" * 64},
                  "resolved_request_ref": {"key": "synthetic/request.json", "sha256": "e" * 64}}
    resolution = dict(references, resolved_registry_hash="d" * 64, resolved_request_hash="e" * 64,
        resolution_artifact_hash=content_hash(references), tickers=["AAPL", "MSFT"], ticker_count=2, permanent_sid_count=2,
        method="QuantBook.add_equity/as-of fixed fixture")
    stage = payload["identity"]["stage"]
    value = {"schema_version": 1, "identity": deepcopy(payload["identity"]), "status": "completed", "terminal": True,
        "checks": {name: True for name in payload["plan"]["required_checks"][stage]},
        "statistics": {"record_count": 42, "history_calls_first": 1, "history_calls_second": 0, "expected_formation_count": 4}
            if stage == "research" else {"data_event_count": 8, "slice_count": 4, "orders_submitted": 0, "runtime_error_count": 0},
        "resolution": resolution, "market_values_exported": False, "economic_factor_tested": False,
        "final_data_accessed": False, "full_US200_coverage_certified": False, "actual_availability_verified": False,
        "evidence": {"lean_engine_version": "2.5.0.0", "vendor_revision_known": False,
            "runtime_environment": {"python": "3.11.0", "pandas": "2.3.3", "numpy": "1.26.4", "lean": "2.5.0.0"}}}
    return {"cloud_report": value, "report_ref": {"key": payload["report_key"], "sha256": content_hash(value)}}


def envelope(name, arguments, native, structured=True):
    result = {"content": [{"type": "text", "text": json.dumps(native)}]}
    if structured:
        result["structuredContent"] = native
    return {"tool_name": "mcp__quantconnect__" + name, "arguments": arguments, "result": result}


def research_tool(payload, wrapper=None):
    encoded = base64.b64encode(canonical_json(wrapper or report(payload))).decode()
    native = {"status": "ok", "execution_count": 1, "outputs": [{"output_type": "stream", "name": "stdout",
        "text": "AQRP_ENGINEERING_JSON " + encoded + "\n"}]}
    return envelope("jupyter_execute_cell", {"projectId": 17, "index": 0}, native)


def completed_tool(**changes):
    native = {"success": True, "backtest": {"projectId": 17, "backtestId": "native-backtest-id", "completed": True,
        "status": "Completed.", "progress": 1, "hasInitializeError": False, "error": None,
        "statistics": {"Total Orders": "0", "Net Profit": "SENSITIVE_FINANCIAL_SENTINEL"},
        "runtimeStatistics": {"Equity": "SENSITIVE_FINANCIAL_SENTINEL"}, "charts": ["Equity"]}}
    native["backtest"].update(changes)
    return envelope("read_backtest", {"projectId": 17, "backtestId": "native-backtest-id"}, native)


def log_tools(payload, wrapper=None, pages=1):
    encoded = base64.b64encode(canonical_json(wrapper or report(payload))).decode()
    chunks = [encoded[index:index + 500] for index in range(0, len(encoded), 500)]
    lines = ["2018-01-10 00:00:00 AQRP_ENGINEERING " + payload["identity"]["attempt_id"] + " "
             + str(index) + "/" + str(len(chunks)) + " " + chunk for index, chunk in enumerate(chunks)]
    grouped = [lines[index::pages] for index in range(pages)]
    return [envelope("search_backtest_logs", {"projectId": 17, "backtestId": "native-backtest-id",
        "query": "AQRP_ENGINEERING " + payload["identity"]["attempt_id"], "page": index + 1},
        {"success": True, "logs": group, "totalPages": pages}) for index, group in enumerate(grouped)]


class EngineeringReceiptTests(unittest.TestCase):
    def test_research_stdout_proves_separate_submission_and_completion(self):
        payload, deployment = context("research")
        tool = research_tool(payload)
        parsed = research_observation(payload, deployment, tool)
        self.assertTrue(parsed["submission"]["accepted"])
        self.assertEqual(parsed["submission"]["status"], "submitted")
        self.assertEqual(parsed["submission"]["external_id"], "qc-research:17:" + "1" * 32)
        self.assertEqual(parsed["completion"]["cloud_report"], report(payload)["cloud_report"])
        self.assertEqual(parsed["submission"]["raw_receipt"]["response_sha256"], content_hash(tool["result"]))
        self.assertNotIn("outputs", json.dumps(parsed["submission"]))
        # Content-only native JSON and mirrored MCP channels have the same behavior.
        del tool["result"]["structuredContent"]
        self.assertEqual(research_observation(payload, deployment, tool)["completion"], parsed["completion"] | {
            "platform": parsed["completion"]["platform"] | {"raw_receipt": parsed["completion"]["platform"]["raw_receipt"] |
                {"response_sha256": content_hash(tool["result"])}}})

    def test_research_rejects_errors_displays_extra_lines_and_duplicate_markers(self):
        payload, deployment = context("research")
        for mutation in (lambda native: native["outputs"].append(deepcopy(native["outputs"][0])),
                lambda native: native["outputs"].append({"output_type": "error", "ename": "ValueError", "traceback": []}),
                lambda native: native["outputs"].append({"output_type": "stream", "name": "stderr", "text": "failure"}),
                lambda native: native["outputs"].append({"output_type": "display_data", "data": {"text/plain": [[1, 2]]}}),
                lambda native: native["outputs"].append({"output_type": "stream", "name": "stdout", "text": "unknown metadata\n"}),
                lambda native: native.update(rows=[[1, 2]])):
            tool = research_tool(payload)
            mutation(tool["result"]["structuredContent"])
            with self.assertRaises(ReceiptParseError):
                research_observation(payload, deployment, tool)
        tool = research_tool(payload)
        tool["result"]["isError"] = True
        with self.assertRaises(ReceiptParseError):
            research_observation(payload, deployment, tool)

    def test_report_unknown_fields_arrays_identity_and_reference_are_rejected(self):
        payload, deployment = context("research")
        for mutation in (lambda wrapper: wrapper["cloud_report"].update(rows=[[1]]),
                lambda wrapper: wrapper["cloud_report"]["statistics"].update(net_return=0),
                lambda wrapper: wrapper["cloud_report"]["statistics"].update(record_count=[1]),
                lambda wrapper: wrapper["cloud_report"]["identity"].update(attempt_id="2" * 32),
                lambda wrapper: wrapper["cloud_report"]["evidence"].update(values=[1]),
                lambda wrapper: wrapper.update(values=[[1]])):
            wrapper = report(payload)
            mutation(wrapper)
            wrapper["report_ref"]["sha256"] = content_hash(wrapper["cloud_report"])
            with self.assertRaises(ReceiptParseError):
                research_observation(payload, deployment, research_tool(payload, wrapper))
        wrapper = report(payload)
        wrapper["report_ref"]["key"] = "foreign/report.json"
        with self.assertRaises(ReceiptParseError):
            research_observation(payload, deployment, research_tool(payload, wrapper))

    def test_failed_cloud_check_is_preserved_without_fabricated_platform_failure(self):
        payload, deployment = context("research")
        wrapper = report(payload)
        wrapper["cloud_report"]["checks"]["raw_data_received"] = False
        wrapper["cloud_report"]["status"] = "failed"
        wrapper["report_ref"]["sha256"] = content_hash(wrapper["cloud_report"])
        completion = research_observation(payload, deployment, research_tool(payload, wrapper))["completion"]
        self.assertEqual(completion["platform"]["status"], "completed")
        self.assertEqual(completion["cloud_report"]["status"], "failed")

    def test_integrity_hash_encoding_and_duplicate_JSON_keys_are_rejected(self):
        payload, deployment = context("research")
        wrapper = report(payload)
        wrapper["report_ref"]["sha256"] = "0" * 64
        with self.assertRaises(ReceiptParseError):
            research_observation(payload, deployment, research_tool(payload, wrapper))
        for text in ("AQRP_ENGINEERING_JSON @@@", "AQRP_ENGINEERING_JSON " + base64.b64encode(
                     b'{"cloud_report":{},"cloud_report":{},"report_ref":{}}').decode()):
            tool = research_tool(payload)
            tool["result"]["structuredContent"]["outputs"][0]["text"] = text
            with self.assertRaises(ReceiptParseError):
                research_observation(payload, deployment, tool)

    def test_tool_arguments_attempt_plan_and_deployment_must_match(self):
        payload, deployment = context("research")
        for mutation in (lambda tool: tool.update(tool_name="mcp__quantconnect__create_compile"),
                lambda tool: tool["arguments"].update(projectId=99),
                lambda tool: tool["arguments"].update(index=True),
                lambda tool: tool["arguments"].update(override="not allowed")):
            tool = research_tool(payload)
            mutation(tool)
            with self.assertRaises(ReceiptParseError):
                research_observation(payload, deployment, tool)
        for key in ("deployment_hash", "source_manifest_hash", "input_hash"):
            changed = dict(deployment, **{key: "wrong"})
            with self.assertRaises(ReceiptParseError):
                research_observation(payload, changed, research_tool(payload))

    def test_backtest_submission_needs_actual_id_and_is_not_compile_completion(self):
        payload, deployment = context("lean")
        tool = envelope("create_backtest", {"projectId": 17}, {"success": True, "backtestId": "native-backtest-id"})
        receipt = backtest_submission(payload, deployment, tool)
        self.assertEqual(receipt["raw_receipt"]["backtestId"], "native-backtest-id")
        self.assertEqual(receipt["status"], "submitted")
        for native in ({"success": True, "compileId": "compiled-only"}, {"success": False, "errors": ["rejected"]},
                       {"success": True, "backtestId": ""}):
            with self.assertRaises(ReceiptParseError):
                backtest_submission(payload, deployment, envelope("create_backtest", {"projectId": 17}, native))

    def test_completed_backtest_and_paginated_logs_only_export_metadata(self):
        payload, deployment = context("lean")
        tool = completed_tool()
        completion = backtest_observation(payload, deployment, "native-backtest-id", tool, log_tools(payload, pages=2))
        self.assertEqual(completion["platform"]["status"], "completed")
        self.assertEqual(completion["platform"]["raw_receipt"]["orders_count"], 0)
        self.assertEqual(completion["platform"]["raw_receipt"]["log_receipt_count"], 2)
        self.assertNotIn("log_receipts", completion["platform"]["raw_receipt"])
        self.assertEqual(completion["platform"]["raw_receipt"]["response_sha256"], content_hash(tool["result"]))
        self.assertNotIn("SENSITIVE_FINANCIAL_SENTINEL", json.dumps(completion))
        self.assertNotIn("runtimeStatistics", json.dumps(completion))
        self.assertNotIn("Net Profit", json.dumps(completion))
        self.assertEqual(completion["cloud_report"], report(payload)["cloud_report"])

    def test_real_parser_receipts_complete_research_then_LEAN_through_persistent_bridge(self):
        # This is an integration fixture, not a parallel handwritten receipt
        # schema: every receipt consumed below is emitted by the real parsers.
        base, research_deployment = context("research")
        plan = EngineeringTaskPlan.from_dict(base["plan"], discovered_project_ids=[17])
        store = MemoryArtifactStore()
        limits = {name: {"total": 5, "normal": 4, "reserve": 1}
                  for name in ("configurations", "research", "lean")}
        registry = Registry(store, limits)
        bridge = EngineeringTaskBridge(registry, plan)
        bridge.register()

        research_attempt = bridge.claim("research")
        self.assertTrue(research_attempt.should_execute)
        research_payload = bridge.payload(research_attempt)
        actual_cell_envelope = research_tool(research_payload)
        research = research_observation(research_payload, research_deployment, actual_cell_envelope)
        submitted = bridge.record_submission(research_attempt, research["submission"])
        self.assertEqual(submitted.status, "pending")
        finished = bridge.consume_completion(submitted,
            completion_source=lambda _: deepcopy(research["completion"]))
        self.assertEqual(finished.status, "completed")

        lean_attempt = bridge.claim("lean")
        self.assertTrue(lean_attempt.should_execute)
        lean_payload = bridge.payload(lean_attempt)
        self.assertEqual(lean_payload["research_resolution"], research["completion"]["cloud_report"]["resolution"])
        lean_deployment = dict(research_deployment, input_hash="0" * 64)
        create_envelope = envelope("create_backtest", {"projectId": 17, "backtestName": "Synthetic Integration"},
            {"success": True, "backtestId": "native-backtest-id"})
        lean_submission = backtest_submission(lean_payload, lean_deployment, create_envelope)
        lean_pending = bridge.record_submission(lean_attempt, lean_submission)
        self.assertEqual(lean_pending.status, "pending")
        delivered = backtest_observation(lean_payload, lean_deployment, lean_pending.external_id,
            completed_tool(), log_tools(lean_payload, pages=2))
        lean_finished = bridge.consume_completion(lean_pending,
            completion_source=lambda _: deepcopy(delivered))
        self.assertEqual(lean_finished.status, "completed")
        self.assertFalse(bridge.read_result(lean_finished)["financial_evidence"])
        self.assertNotIn("SENSITIVE_FINANCIAL_SENTINEL", str(store._data))
        self.assertEqual({name: registry.snapshot()["usage"][name]["total"]
            for name in ("configurations", "research", "lean")},
            {"configurations": 1, "research": 1, "lean": 1})

        restarted = EngineeringTaskBridge(Registry(store, limits), plan)
        repeated = restarted.claim("lean")
        self.assertFalse(repeated.should_execute)
        self.assertEqual(repeated.attempt_id, lean_finished.attempt_id)
        self.assertEqual(restarted.read_result(repeated)["cloud_report"], delivered["cloud_report"])
        self.assertEqual(restarted.registry.snapshot()["usage"]["lean"]["total"], 1)

    def test_running_unknown_partial_and_ordered_backtests_are_rejected(self):
        payload, deployment = context("lean")
        for changes in ({"completed": False, "status": "In Progress...", "progress": .5},
                {"status": "In Queue..."}, {"progress": .99}, {"completed": False}, {"progress": True},
                {"backtestId": "foreign"}, {"projectId": 18}, {"statistics": {"Total Orders": "1"}}):
            with self.subTest(changes=changes), self.assertRaises(ReceiptParseError):
                backtest_observation(payload, deployment, "native-backtest-id", completed_tool(**changes), log_tools(payload))

    def test_explicit_native_runtime_or_initialize_failure_needs_no_cloud_report(self):
        payload, deployment = context("lean")
        for changes in ({"completed": False, "status": "Runtime Error", "progress": .2, "error": "private failure detail"},
                        {"hasInitializeError": True, "error": "private failure detail"}):
            completion = backtest_observation(payload, deployment, "native-backtest-id", completed_tool(**changes), [])
            self.assertEqual(completion["platform"]["status"], "failed")
            self.assertNotIn("cloud_report", completion)
            self.assertNotIn("private failure detail", json.dumps(completion))

    def test_logs_require_complete_unique_attempt_bound_chunks_and_pages(self):
        payload, deployment = context("lean")
        for mutation in (lambda tools: tools[0]["arguments"].update(query="AQRP_ENGINEERING"),
                lambda tools: tools[0]["arguments"].update(backtestId="foreign"),
                lambda tools: tools[0]["result"]["structuredContent"]["logs"].pop(),
                lambda tools: tools[0]["result"]["structuredContent"]["logs"].append(tools[0]["result"]["structuredContent"]["logs"][0]),
                lambda tools: tools[0]["result"]["structuredContent"].update(totalPages=2),
                lambda tools: tools[0]["result"]["structuredContent"]["logs"].append("AQRP_ENGINEERING " + "2" * 32 + " 0/1 e30="),
                lambda tools: tools[0]["result"]["structuredContent"]["logs"].append("AQRP_ENGINEERING " + "1" * 32 + " 0/129 e30=")):
            tools = log_tools(payload)
            mutation(tools)
            with self.assertRaises(ReceiptParseError):
                backtest_observation(payload, deployment, "native-backtest-id", completed_tool(), tools)


if __name__ == "__main__":
    unittest.main()
