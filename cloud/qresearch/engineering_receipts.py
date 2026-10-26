"""Fixed parsers for trusted native QC tool observations, never LLM approvals.

The dispatcher supplies the actual tool name, arguments and returned envelope.
This is an operational trust boundary, not a signature or proof of remote
provenance. No parser performs I/O, polls a backtest or consumes budget. Native
financial panels are hashed transiently and discarded; only whitelisted task
metadata and the cloud's bounded engineering report may enter the ledger.
"""
import base64
from decimal import Decimal, InvalidOperation
import json
import math
import re

from .artifacts import canonical_json, content_hash, validate_key
from .engineering_data import _identity_shape, _safe_evidence
from .engineering_tasks import EngineeringTaskPlan


class ReceiptParseError(ValueError):
    """The observation does not prove the expected fixed engineering transition."""


_PREFIX = "AQRP_ENGINEERING_JSON "
_CHUNK = re.compile(r"AQRP_ENGINEERING ([0-9a-f]{32}) ([0-9]{1,3})/([0-9]{1,3}) ([A-Za-z0-9+/=]{1,500})$")
_IDENTITY_KINDS = {"research": "logical_research_execution_receipt", "lean": "quantconnect_backtest_id"}
_REPORT_KEYS = {"schema_version", "identity", "status", "terminal", "checks", "statistics", "resolution",
    "market_values_exported", "economic_factor_tested", "final_data_accessed", "full_US200_coverage_certified",
    "actual_availability_verified", "evidence"}
_STATS = {"research": {"record_count", "history_calls_first", "history_calls_second", "expected_formation_count"},
    "lean": {"data_event_count", "slice_count", "orders_submitted", "runtime_error_count", "dividend_event_count",
             "split_event_count", "delisting_event_count", "mapping_event_count"}}
_CHECKS = {"source_snapshot_matches", "raw_data_received", "second_prefetch_no_history", "same_partition_ids",
    "cache_only_consumer", "read_only_write_rejected", "final_request_rejected", "coverage_observed_complete",
    "development_only", "symbol_registry_resolved", "complete_expected_bars", "no_orders", "corporate_action_received"}


def _fail(message):
    raise ReceiptParseError(message)


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("Duplicate JSON keys are ambiguous")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: _fail("Non-finite JSON is prohibited"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ReceiptParseError("Malformed native JSON observation") from exc


def _context(payload, deployment, stage):
    try:
        encoded = canonical_json(payload)
        payload = _json(encoded)
        identity = payload["identity"]
        _identity_shape(identity)
        plan = EngineeringTaskPlan.from_dict(payload["plan"], discovered_project_ids=(identity["project_id"],))
        document = plan.to_dict()
        if (identity["stage"] != stage or identity["plan_hash"] != plan.hash
                or identity["config_id"] != content_hash({"engineering_task_schema_version": 1, "plan": document})
                or identity["data_request_hash"] != plan.request_hash
                or any(identity[key] != document[key] for key in ("project_id", "source_manifest_hash", "deployment_hash"))):
            _fail("Payload does not identify its exact registered engineering plan")
        key = document["report_namespace"] + "/reports/" + plan.hash + "/" + stage + "/" + identity["attempt_id"] + ".json"
        if payload.get("report_key") != key or payload.get("external_identity_kind") != _IDENTITY_KINDS[stage]:
            _fail("Payload report destination or identity kind changed")
        if (not isinstance(deployment, dict) or set(deployment) != {"source_manifest_hash", "deployment_hash", "input_hash"}
                or any(not _hash(value) for value in deployment.values())
                or any(deployment[key] != identity[key] for key in ("source_manifest_hash", "deployment_hash"))):
            _fail("Observed deployment/input binding differs from this task")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ReceiptParseError):
            raise
        raise ReceiptParseError("Invalid fixed engineering context") from exc
    return payload, _json(canonical_json(deployment))


def _native(result):
    if not isinstance(result, dict):
        _fail("Actual MCP result must be a JSON object")
    if "isError" in result and result["isError"] is not False:
        _fail("Native tool error is not a completion")
    if "structuredContent" in result and result["structuredContent"] is not None:
        return result["structuredContent"]
    if "content" in result:
        blocks = result["content"]
        if not isinstance(blocks, list) or not blocks:
            _fail("Native content is missing")
        texts = []
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "text" or not isinstance(block.get("text"), str):
                _fail("Only text native observations are permitted")
            texts.append(block["text"])
        if len(texts) == 1:
            text = texts[0]
            return _json(text) if text.lstrip().startswith(("{", "[")) else text
        return texts
    return result


def _tool(envelope, tool_name, payload, *, external_id=None):
    if not isinstance(envelope, dict) or set(envelope) != {"tool_name", "arguments", "result"} or envelope["tool_name"] != tool_name:
        _fail("Wrong native tool observation")
    args = envelope["arguments"]
    if not isinstance(args, dict) or type(args.get("projectId")) is not int or args["projectId"] != payload["identity"]["project_id"]:
        _fail("Native tool project does not match the admitted task")
    allowed = {"projectId"}
    if tool_name.endswith("jupyter_execute_cell"):
        allowed.add("index")
        if type(args.get("index")) is not int or args["index"] < 0:
            _fail("An explicit Research cell index is required")
    elif tool_name.endswith("create_backtest"):
        allowed.add("backtestName")
    else:
        allowed.add("backtestId")
        if not isinstance(external_id, str) or not external_id.strip() or args.get("backtestId") != external_id:
            _fail("An explicit matching native backtest identity is required")
        if tool_name.endswith("search_backtest_logs"):
            allowed |= {"query", "page"}
            if args.get("query") != "AQRP_ENGINEERING " + payload["identity"]["attempt_id"]:
                _fail("Log query is not bound to this engineering attempt")
            if "page" in args and (type(args["page"]) is not int or args["page"] < 1):
                _fail("Native log pages start at one")
    if set(args) - allowed:
        _fail("Unknown native argument overrides are prohibited")
    try:
        raw = {"tool_name": tool_name, "arguments": _json(canonical_json(args)),
               "response_sha256": content_hash(envelope["result"])}
        return _native(envelope["result"]), raw
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ReceiptParseError):
            raise
        raise ReceiptParseError("Native observation is not canonical JSON metadata") from exc


def _ref(reference):
    if not isinstance(reference, dict) or set(reference) != {"key", "sha256"} or not _hash(reference["sha256"]):
        _fail("Malformed cloud metadata reference")
    try:
        validate_key(reference["key"])
    except (TypeError, ValueError) as exc:
        raise ReceiptParseError("Invalid cloud metadata key") from exc


def _report(wrapper, payload):
    if not isinstance(wrapper, dict) or set(wrapper) != {"cloud_report", "report_ref"}:
        _fail("Only an engineering cloud report and its immutable reference may leave the cloud")
    report, reference = wrapper["cloud_report"], wrapper["report_ref"]
    required = _REPORT_KEYS - {"evidence", "resolution"}
    if (not isinstance(report, dict) or not required <= set(report) or set(report) - _REPORT_KEYS
            or type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["identity"] != payload["identity"] or report["terminal"] is not True
            or not isinstance(report["status"], str) or report["status"] not in {"completed", "failed"}):
        _fail("Cloud report shape, identity or terminal status is invalid")
    for flag in ("market_values_exported", "economic_factor_tested", "final_data_accessed",
                 "full_US200_coverage_certified", "actual_availability_verified"):
        if report[flag] is not False:
            _fail("Engineering limitations must remain explicit")
    checks, statistics = report["checks"], report["statistics"]
    stage = payload["identity"]["stage"]
    expected_checks = set(payload["plan"]["required_checks"][stage])
    if (not isinstance(checks, dict) or not expected_checks <= set(checks)
            or set(checks) - (_CHECKS | expected_checks) or any(type(x) is not bool for x in checks.values())
            or report["status"] != ("completed" if all(checks.values()) else "failed")):
        _fail("Only fixed observed boolean engineering checks are permitted")
    if (not isinstance(statistics, dict) or set(statistics) - _STATS[stage]
            or any(type(x) is not int or x < 0 for x in statistics.values())):
        _fail("Only whitelisted nonnegative engineering counts are permitted")
    resolution = report.get("resolution")
    if payload["plan"]["request_mode"] == "symbol_resolution" or resolution is not None:
        keys = {"resolved_request_hash", "resolved_registry_hash", "resolution_artifact_hash", "tickers",
                "ticker_count", "permanent_sid_count", "method", "resolved_registry_ref", "resolved_request_ref"}
        if (not isinstance(resolution, dict) or set(resolution) != keys or resolution["tickers"] != ["AAPL", "MSFT"]
                or type(resolution["ticker_count"]) is not int or resolution["ticker_count"] != 2
                or type(resolution["permanent_sid_count"]) is not int or resolution["permanent_sid_count"] != 2
                or resolution["method"] != "QuantBook.add_equity/as-of fixed fixture"
                or any(not _hash(resolution[name]) for name in ("resolved_request_hash", "resolved_registry_hash", "resolution_artifact_hash"))):
            _fail("Unknown SID resolution metadata")
        refs = {key: resolution[key] for key in ("resolved_registry_ref", "resolved_request_ref")}
        for ref in refs.values():
            _ref(ref)
        if (content_hash(refs) != resolution["resolution_artifact_hash"]
                or refs["resolved_registry_ref"]["sha256"] != resolution["resolved_registry_hash"]
                or refs["resolved_request_ref"]["sha256"] != resolution["resolved_request_hash"]):
            _fail("Resolution references disagree with their observed hashes")
    try:
        _safe_evidence(report.get("evidence", {}))
    except (ValueError, TypeError) as exc:
        raise ReceiptParseError("Unrecognized or row-level cloud evidence is prohibited") from exc
    _ref(reference)
    if reference["key"] != payload["report_key"] or reference["sha256"] != content_hash(report):
        _fail("Cloud report content or destination differs from this attempt")
    return wrapper


def _decode(encoded, payload):
    if not isinstance(encoded, str) or not encoded or len(encoded) > 64000:
        _fail("Engineering marker payload exceeds its bounded metadata size")
    try:
        decoded = base64.b64decode(encoded, validate=True)
        if base64.b64encode(decoded).decode("ascii") != encoded:
            _fail("Engineering marker base64 is not canonical")
        wrapper = _json(decoded.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ReceiptParseError("Malformed engineering marker encoding") from exc
    return _report(wrapper, payload)


def _research_stdout(native):
    lines = []
    wrappers = {"outputs", "output", "cells", "results", "result", "content"}
    metadata = {"execution_count", "status", "success", "execution_state", "cell_index", "index", "metadata"}
    def visit(node):
        if isinstance(node, str):
            if node.lstrip().startswith(("{", "[")):
                visit(_json(node))
            else:
                lines.extend(node.splitlines())
            return
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            _fail("Unknown Research output or row array is prohibited")
        if "output_type" in node or node.get("name") == "stdout":
            if (node.get("output_type", "stream") != "stream" or node.get("name") != "stdout"
                    or set(node) - {"output_type", "name", "text"}):
                _fail("Research errors, stderr and displayed values are prohibited")
            text = node.get("text")
            if isinstance(text, list) and all(isinstance(x, str) for x in text):
                text = "".join(text)
            if not isinstance(text, str):
                _fail("Research stdout must contain text only")
            lines.extend(text.splitlines())
            return
        if node.get("type") == "text" and set(node) <= {"type", "text", "annotations"}:
            visit(node.get("text"))
            return
        if set(node) - wrappers - metadata:
            _fail("Unknown Research output metadata is prohibited")
        for key, value in node.items():
            if key in wrappers:
                visit(value)
            elif key == "metadata" and value not in ({}, None):
                _fail("Unregistered Research output metadata is prohibited")
            elif key == "success" and value is not True:
                _fail("Research native execution was not successful")
            elif key in {"status", "execution_state"} and (not isinstance(value, str) or value not in {"ok", "completed", "success", "idle"}):
                _fail("Research execution is not completed")
            elif key in {"execution_count", "cell_index", "index"} and value is not None and (type(value) is not int or value < 0):
                _fail("Invalid Research execution metadata")
    visit(native)
    nonempty = [line for line in lines if line.strip()]
    if len(nonempty) != 1 or not nonempty[0].startswith(_PREFIX):
        _fail("Exactly one engineering stdout marker and no other printed values are required")
    return nonempty[0][len(_PREFIX):]


def _platform(payload, deployment, external_id, raw, status="completed"):
    return {"identity": dict(payload["identity"], external_id=external_id), "status": status,
            "terminal": True, "deployment": deployment, "raw_receipt": raw}


def research_observation(payload, deployment, tool_envelope):
    """Parse one completed cell's marker into separate acknowledgement/result."""
    payload, deployment = _context(payload, deployment, "research")
    native, raw = _tool(tool_envelope, "mcp__quantconnect__jupyter_execute_cell", payload)
    wrapper = _decode(_research_stdout(native), payload)
    external = "qc-research:" + str(payload["identity"]["project_id"]) + ":" + payload["identity"]["attempt_id"]
    raw.update(marker_count=1, stdout_only=True)
    submission = {"identity": payload["identity"], "identity_kind": payload["external_identity_kind"],
        "external_id": external, "accepted": True, "status": "acknowledged", "deployment": deployment, "raw_receipt": raw}
    completion = {"platform": _platform(payload, deployment, external, raw), **wrapper}
    return {"submission": submission, "completion": completion}


def backtest_submission(payload, deployment, tool_envelope):
    """Compilation alone, rejections and missing IDs are not submissions."""
    payload, deployment = _context(payload, deployment, "lean")
    native, raw = _tool(tool_envelope, "mcp__quantconnect__create_backtest", payload)
    if (not isinstance(native, dict) or native.get("success") is not True or native.get("errors")
            or not isinstance(native.get("backtestId"), str) or not native["backtestId"].strip()):
        _fail("A successful native backtest submission with its actual backtestId is required")
    external = native["backtestId"]
    raw.update(success=True, backtestId=external)
    return {"identity": payload["identity"], "identity_kind": payload["external_identity_kind"],
        "external_id": external, "accepted": True, "status": "submitted", "deployment": deployment, "raw_receipt": raw}


def _logs(payload, external_id, envelopes):
    if not isinstance(envelopes, (list, tuple)) or not envelopes:
        _fail("Delivered successful backtests need their actual engineering log observations")
    chunks, declared, receipts, pages, total_pages = {}, None, [], set(), None
    for envelope in envelopes:
        native, raw = _tool(envelope, "mcp__quantconnect__search_backtest_logs", payload, external_id=external_id)
        if (not isinstance(native, dict) or native.get("success") is not True or native.get("errors")
                or set(native) - {"success", "errors", "logs", "totalPages"}
                or not isinstance(native.get("logs"), list) or any(not isinstance(line, str) for line in native["logs"])):
            _fail("Native engineering logs were not read successfully")
        page = envelope["arguments"].get("page", 1)
        if page in pages:
            _fail("Duplicate native log pages are ambiguous")
        pages.add(page)
        if "totalPages" in native:
            count = native["totalPages"]
            if type(count) is not int or not 1 <= count <= 128 or (total_pages is not None and count != total_pages):
                _fail("Native log pagination is inconsistent or unbounded")
            total_pages = count
        receipts.append(raw)
        for line in native["logs"]:
            match = _CHUNK.search(line)
            if match is None or line.count("AQRP_ENGINEERING") != 1 or match[1] != payload["identity"]["attempt_id"]:
                _fail("Unknown or foreign engineering log line")
            index, count, chunk = int(match[2]), int(match[3]), match[4]
            if (str(index) != match[2] or str(count) != match[3] or not 1 <= count <= 128 or not 0 <= index < count or len(chunk) > 500
                    or (index < count - 1 and len(chunk) != 500) or index in chunks
                    or (declared is not None and declared != count)):
                _fail("Engineering log chunks are missing, duplicated or inconsistent")
            declared = count
            chunks[index] = chunk
    if (declared is None or set(chunks) != set(range(declared))
            or (total_pages is not None and pages != set(range(1, total_pages + 1)))):
        _fail("Engineering report log chunks are incomplete")
    return _decode("".join(chunks[index] for index in range(declared)), payload), receipts


def backtest_observation(payload, deployment, external_id, tool_envelope, log_envelopes):
    """Parse only after automatic completion delivery; never perform polling."""
    payload, deployment = _context(payload, deployment, "lean")
    native, raw = _tool(tool_envelope, "mcp__quantconnect__read_backtest", payload, external_id=external_id)
    if not isinstance(native, dict) or native.get("success") is not True or native.get("errors"):
        _fail("Actual completed-backtest read did not succeed")
    backtest = native.get("backtest")
    if (not isinstance(backtest, dict) or backtest.get("backtestId") != external_id
            or type(backtest.get("projectId")) is not int or backtest["projectId"] != payload["identity"]["project_id"]
            or type(backtest.get("completed")) is not bool or type(backtest.get("hasInitializeError", False)) is not bool):
        _fail("Native backtest identity or terminal metadata is invalid")
    progress, status = backtest.get("progress"), backtest.get("status")
    if not isinstance(status, str):
        _fail("Native backtest status is invalid")
    if isinstance(progress, bool) or not isinstance(progress, (int, float)) or not math.isfinite(progress) or not 0 <= progress <= 1:
        _fail("Native backtest progress is invalid")
    for name in ("error", "stacktrace"):
        if backtest.get(name) is not None and not isinstance(backtest[name], str):
            _fail("Native error metadata has an invalid type")
    stats = backtest.get("statistics", {})
    if not isinstance(stats, dict):
        _fail("Native statistics metadata is invalid")
    if "Total Orders" in stats:
        value = stats["Total Orders"]
        try:
            count = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ReceiptParseError("Native total order count is invalid") from exc
        if isinstance(value, bool) or not count.is_finite() or count != 0:
            _fail("Engineering backtests must have zero actual orders")
        raw["orders"] = 0
    error_present = bool(backtest.get("error") or backtest.get("stacktrace") or backtest.get("hasInitializeError"))
    failed = status == "Runtime Error" or (backtest["completed"] and error_present)
    if not failed and (status != "Completed." or backtest["completed"] is not True or progress != 1 or error_present):
        _fail("Queued, running or unknown native states are not terminal completions")
    if failed and status not in {"Runtime Error", "Completed."}:
        _fail("A nonterminal error flag is not a delivered terminal failure")
    raw.update(success=True, backtestId=external_id, completed=backtest["completed"], status=status,
               progress=progress, initialize_error=backtest.get("hasInitializeError", False), error_present=error_present)
    platform = _platform(payload, deployment, external_id, raw, status="failed" if failed else "completed")
    if failed:
        return {"platform": platform}
    wrapper, log_receipts = _logs(payload, external_id, log_envelopes)
    raw["log_receipts"] = log_receipts
    return {"platform": platform, **wrapper}
