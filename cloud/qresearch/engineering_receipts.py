"""Fixed parsers for trusted native QC tool observations, never LLM approvals.

The dispatcher supplies the actual tool name, arguments and returned envelope.
This is an operational trust boundary, not a signature or proof of remote
provenance. No parser performs I/O, polls a backtest or consumes budget. Native
financial panels are hashed transiently and discarded; only whitelisted task
metadata and the cloud's bounded engineering report may enter the ledger.
"""
import base64
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re

from .artifacts import canonical_json, content_hash, validate_key
from .engineering_data import _identity_shape, _safe_evidence
from .engineering_tasks import EngineeringTaskPlan, validate_joint_report


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


def _annotations(value):
    """Registered MCP content hints only; never uninspected output containers.

    These hints do not establish market/publication/availability timestamps.
    Accept the common ISO date and second-precision datetime spellings used by
    the adapter, including fractions, UTC/offset and naive local hint clocks.
    """
    if value is None:
        return
    if not isinstance(value, dict) or set(value) - {"audience", "priority", "lastModified"}:
        _fail("Unknown text annotations cannot carry side data")
    if "audience" in value:
        audience = value["audience"]
        if (not isinstance(audience, list)
                or any(not isinstance(role, str) or role not in {"user", "assistant"} for role in audience)):
            _fail("Annotation audience must contain registered roles only")
    if "priority" in value:
        priority = value["priority"]
        try:
            valid = type(priority) in {int, float} and math.isfinite(priority) and 0 <= priority <= 1
        except OverflowError:
            valid = False
        if not valid:
            _fail("Annotation priority must be a finite number between zero and one")
    if "lastModified" in value:
        stamp = value["lastModified"]
        if (not isinstance(stamp, str) or re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[Tt ](?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:[.,][0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])?)?", stamp) is None):
            _fail("Annotation lastModified must be a registered ISO clock string")
        try:
            # The grammar already checks time, offset and fractional digits.
            # Validate only the calendar here: Python 3.10's fromisoformat
            # rejects legal 1/2/4/5-digit fractions. No fraction conversion is
            # needed for a content hint, and the original string stays intact.
            datetime(int(stamp[:4]), int(stamp[5:7]), int(stamp[8:10]))
        except ValueError:
            _fail("Annotation lastModified is not a valid calendar clock")


def _text_node(node):
    """One validator for outer carriers and every nested Research text node."""
    if (not isinstance(node, dict) or node.get("type") != "text"
            or not isinstance(node.get("text"), str) or set(node) - {"type", "text", "annotations"}):
        _fail("Only registered text observations are permitted")
    _annotations(node.get("annotations"))
    return node["text"]


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


def _native(result, *, allow_tool_error=False):
    if not isinstance(result, dict):
        _fail("Actual MCP result must be a JSON object")
    if ("isError" in result and result["isError"] is not False
            and not (allow_tool_error is True and result["isError"] is True)):
        _fail("Native tool error is not a completion")
    wrapped = "structuredContent" in result or "content" in result
    if not wrapped:
        return result
    # Every present output carrier must be inspected. Taking a preferred one
    # would hide displayed rows, stderr or an execution error in its mirror.
    if (set(result) - {"isError", "structuredContent", "content", "_meta"}
            or result.get("_meta") not in (None, {})):
        _fail("Unknown native envelope metadata cannot hide additional output")
    structured = result.get("structuredContent")
    carriers = [] if structured is None else [structured]
    if "content" in result:
        blocks = result["content"]
        if not isinstance(blocks, list) or (not blocks and structured is None):
            _fail("Native content is missing")
        texts = []
        for block in blocks:
            texts.append(_text_node(block))
        if len(texts) == 1:
            text = texts[0]
            carriers.append(_json(text) if text.lstrip().startswith(("{", "[")) else text)
        elif texts:
            carriers.append(texts)
    if not carriers:
        _fail("Native observation is missing")
    # Canonical JSON ignores object-key ordering/formatting but preserves typed
    # values, output order, status and errors. Multiple mirrored representations
    # are one observation only when their full decoded semantics agree.
    try:
        first = canonical_json(carriers[0])
        if any(canonical_json(carrier) != first for carrier in carriers[1:]):
            _fail("Native output carriers disagree or contain additional output")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ReceiptParseError):
            raise
        raise ReceiptParseError("Native observations are not supported JSON values") from None
    return carriers[0]


def _tool(envelope, tool_name, payload, *, external_id=None, allow_tool_error=False):
    if not isinstance(envelope, dict) or set(envelope) != {"tool_name", "arguments", "result"} or envelope["tool_name"] != tool_name:
        _fail("Wrong native tool observation")
    args = envelope["arguments"]
    if not isinstance(args, dict) or type(args.get("projectId")) is not int or args["projectId"] != payload["identity"]["project_id"]:
        _fail("Native tool project does not match the admitted task")
    allowed = {"projectId"}
    if tool_name.endswith(("jupyter_execute_cell", "jupyter_read_cell")):
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
        return _native(envelope["result"], allow_tool_error=allow_tool_error), raw
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
        validate_joint_report(report, payload["plan"])
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
        if node.get("type") == "text":
            visit(_text_node(node))
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


def research_cell_source(payload, deployment):
    """Canonical no-catch cell, bound to one admitted raw input and identity.

    The input is read once and parsed as an inert literal; it is never imported
    as executable Python. No exception is caught into a successful output. A
    failed cell must instead deliver its actual native error observation.
    """
    payload, deployment = _context(payload, deployment, "research")
    return (
        "import ast as _aqrp_ast\n"
        "import base64 as _aqrp_base64\n"
        "import hashlib as _aqrp_hashlib\n"
        "import json as _aqrp_json\n"
        "from pathlib import Path as _aqrp_Path\n"
        "import sys as _aqrp_sys\n"
        "import importlib as _aqrp_importlib\n"
        "import importlib.util as _aqrp_import_util\n"
        "for _aqrp_name in list(_aqrp_sys.modules):\n"
        "    if _aqrp_name == 'qresearch' or _aqrp_name.startswith('qresearch.'):\n"
        "        _aqrp_sys.modules.pop(_aqrp_name, None)\n"
        "_aqrp_importlib.invalidate_caches()\n"
        "_aqrp_spec = _aqrp_import_util.find_spec('qresearch')\n"
        "_aqrp_locations = list(_aqrp_spec.submodule_search_locations or ()) if _aqrp_spec is not None else []\n"
        "if len(_aqrp_locations) != 1 or not isinstance(_aqrp_locations[0], str) or not _aqrp_locations[0]:\n"
        "    raise ValueError('Frozen Research implementation root is unavailable or ambiguous')\n"
        "if not _aqrp_Path(_aqrp_locations[0]).is_absolute():\n"
        "    raise ValueError('Frozen Research implementation root is unavailable or ambiguous')\n"
        "_aqrp_root = _aqrp_Path(_aqrp_locations[0]).resolve().parent\n"
        "_aqrp_input = (_aqrp_root / '_engineering_task_input.py').read_bytes()\n"
        "if _aqrp_hashlib.sha256(_aqrp_input).hexdigest() != " + repr(deployment["input_hash"]) + ":\n"
        "    raise ValueError('Frozen Research input identity differs')\n"
        "_aqrp_tree = _aqrp_ast.parse(_aqrp_input.decode('utf-8-sig'))\n"
        "if (len(_aqrp_tree.body) != 1 or not isinstance(_aqrp_tree.body[0], _aqrp_ast.Assign)\n"
        "        or len(_aqrp_tree.body[0].targets) != 1\n"
        "        or not isinstance(_aqrp_tree.body[0].targets[0], _aqrp_ast.Name)\n"
        "        or _aqrp_tree.body[0].targets[0].id != 'TASK_INPUT_JSON'\n"
        "        or not isinstance(_aqrp_tree.body[0].value, _aqrp_ast.Constant)\n"
        "        or not isinstance(_aqrp_tree.body[0].value.value, str)):\n"
        "    raise ValueError('Frozen Research input must be one inert JSON assignment')\n"
        "_aqrp_payload = _aqrp_json.loads(_aqrp_tree.body[0].value.value)\n"
        "if not isinstance(_aqrp_payload, dict) or _aqrp_payload.get('identity') != " + repr(payload["identity"]) + ":\n"
        "    raise ValueError('Frozen Research input identity differs')\n"
        "from qresearch.engineering_data import run_research_task as _aqrp_run\n"
        "from qresearch.artifacts import canonical_json as _aqrp_canonical\n"
        "_aqrp_result = _aqrp_run(_aqrp_payload)\n"
        "print('AQRP_ENGINEERING_JSON ' + _aqrp_base64.b64encode(_aqrp_canonical(_aqrp_result)).decode('ascii'))\n"
    )


def research_dispatch_binding(payload, deployment, read_cell_envelope):
    """Observe the canonical source before dispatch; no I/O or admission here.

    The controller must save this result once, before executing the cell. It
    does not turn arbitrary local JSON into proof of native tool provenance.
    Only the documented read-cell source shape is supported; output fields or
    unknown cell metadata are not silently discarded.
    """
    payload, deployment = _context(payload, deployment, "research")
    native, raw = _tool(read_cell_envelope, "mcp__quantconnect__jupyter_read_cell", payload)
    if (not isinstance(native, dict) or set(native) != {"cellType", "source"}
            or native["cellType"] != "code" or not isinstance(native["source"], list)
            or any(not isinstance(line, str) for line in native["source"])):
        _fail("An actual code-cell source read without outputs is required")
    source = research_cell_source(payload, deployment)
    if "".join(native["source"]) != source:
        _fail("Read Research cell source differs from the fixed admitted entry")
    return {"schema_version": 1, "protocol": "native_research_error_v1",
        "identity": payload["identity"], "deployment": deployment,
        "arguments": raw["arguments"],
        "cell_source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "cell_read_response_sha256": raw["response_sha256"]}


def research_entry_protocol(payload, deployment):
    """Pin new-entry semantics during first admission, never on old recovery."""
    payload, deployment = _context(payload, deployment, "research")
    return {"schema_version": 1, "protocol": "fixed_research_entry_before_dispatch_v1",
        "identity": payload["identity"], "deployment": deployment,
        "cell_source_sha256": hashlib.sha256(research_cell_source(payload, deployment).encode("utf-8")).hexdigest()}


def _research_binding(binding, payload, deployment, arguments):
    required = {"schema_version", "protocol", "identity", "deployment", "arguments",
                "cell_source_sha256", "cell_read_response_sha256"}
    if not isinstance(binding, dict) or set(binding) != required:
        _fail("Original pre-dispatch Research source/input binding is required")
    try:
        same = (canonical_json(binding["identity"]) == canonical_json(payload["identity"])
                and canonical_json(binding["deployment"]) == canonical_json(deployment)
                and canonical_json(binding["arguments"]) == canonical_json(arguments))
    except (TypeError, ValueError):
        _fail("Original pre-dispatch Research source/input binding is invalid")
    if (not same
            or type(binding["schema_version"]) is not int or binding["schema_version"] != 1
            or binding["protocol"] != "native_research_error_v1"
            or not _hash(binding["cell_read_response_sha256"])
            or binding["cell_source_sha256"] != hashlib.sha256(
                research_cell_source(payload, deployment).encode("utf-8")).hexdigest()):
        _fail("Original pre-dispatch Research source/input binding is required")
    if (not isinstance(arguments, dict) or set(arguments) != {"projectId", "index"}
            or type(arguments["projectId"]) is not int or arguments["projectId"] != payload["identity"]["project_id"]
            or type(arguments["index"]) is not int or arguments["index"] < 0):
        _fail("Research dispatch arguments must identify the original project and cell")


def _research_error(native, index):
    """A deliberately narrow nbformat error grammar, not generic tool failure.

    The direct/list node mirrors the existing execute-cell stream shape. An
    explicit one-cell error wrapper is supported for adapters returning cell
    metadata. A delivered CollectionError has been observed in the direct-node
    form; other registered forms retain their synthetic compatibility scope.
    """
    node = native
    if isinstance(node, dict) and "outputs" in node:
        allowed = {"status", "outputs", "execution_count", "cell_index", "metadata"}
        if (set(node) - allowed or node.get("status") != "error"
                or node.get("metadata") not in (None, {})):
            _fail("Only an explicit completed native cell error is registered")
        if "execution_count" in node and (type(node["execution_count"]) is not int or node["execution_count"] < 1):
            _fail("A native failed execution count must be positive")
        if "cell_index" in node and (type(node["cell_index"]) is not int or node["cell_index"] != index):
            _fail("Native failed-cell index differs from the original dispatch")
        node = node["outputs"]
    if isinstance(node, list):
        if len(node) != 1:
            _fail("Exactly one native error output and no side output is required")
        node = node[0]
    if (not isinstance(node, dict) or set(node) != {"output_type", "ename", "evalue", "traceback"}
            or node["output_type"] != "error" or not isinstance(node["ename"], str)
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,127}", node["ename"]) is None
            or not isinstance(node["evalue"], str) or len(node["evalue"]) > 65536
            or not isinstance(node["traceback"], list) or not 1 <= len(node["traceback"]) <= 128
            or any(not isinstance(line, str) or len(line) > 65536 for line in node["traceback"])
            or not any(line.strip() for line in node["traceback"])
            or sum(map(len, node["traceback"])) > 262144):
        _fail("A bounded native nbformat error output is required")
    return len(node["traceback"])


def _research_execution_native(tool_envelope, payload):
    """Narrowly compare the observed duplicate Research-error text carriers.

    The actual connector delivered one failed execution as exactly two top-level
    text representations of the same direct nbformat error. Every text is a
    complete error JSON object, with identical typed semantics and annotations.
    An actual JSON array of errors, nested wrappers, printed values or arbitrary
    duplicate success outputs are not this transport representation.

    Per-carrier single-text projections are validation views ONLY: _tool and
    _native still inspect every retained outer field/annotation and any original
    structured mirror. No projected envelope is archived or claimed as native.
    The returned response hash is always of the COMPLETE UNCHANGED result.
    Global _native and all other callers' default carrier rules stay unchanged.
    """
    result = tool_envelope.get("result") if isinstance(tool_envelope, dict) else None
    blocks = result.get("content") if isinstance(result, dict) else None
    if not isinstance(blocks, list) or len(blocks) != 2:
        native, raw = _tool(tool_envelope, "mcp__quantconnect__jupyter_execute_cell", payload, allow_tool_error=True)
        return native, raw, None
    first, annotations, raw, native = None, None, None, None
    for block in blocks:
        parsed = _json(_text_node(block))
        if not isinstance(parsed, dict) or parsed.get("output_type") != "error":
            _fail("Duplicate Research text carriers must each be a direct native error JSON object")
        projection = dict(result, content=[block])
        native, raw = _tool(dict(tool_envelope, result=projection),
            "mcp__quantconnect__jupyter_execute_cell", payload, allow_tool_error=True)
        _research_error(native, raw["arguments"]["index"])
        typed = canonical_json(parsed)
        hints = canonical_json(block.get("annotations"))
        if first is None:
            first, annotations = typed, hints
        elif typed != first or hints != annotations:
            _fail("Duplicate Research error representations disagree")
    raw["response_sha256"] = content_hash(result)
    count = len(blocks) + (1 if result.get("structuredContent") is not None else 0)
    return native, raw, count


def research_execution_failure(payload, deployment, tool_envelope, *, dispatch_binding):
    """One definite failed cell, bound to its immutable pre-dispatch source.

    isError/false success alone cannot establish execution or terminal state.
    Timeout, network failures, caught errors and printed error dictionaries are
    rejected. Exceptions are inspected transiently; only hashes/counts persist.
    """
    payload, deployment = _context(payload, deployment, "research")
    native, raw, representations = _research_execution_native(tool_envelope, payload)
    _research_binding(dispatch_binding, payload, deployment, raw["arguments"])
    count = _research_error(native, raw["arguments"]["index"])
    external = "qc-research:" + str(payload["identity"]["project_id"]) + ":" + payload["identity"]["attempt_id"]
    raw.update(native_research_error=True, error_output_count=1, traceback_line_count=count,
        dispatch_binding_sha256=content_hash(dispatch_binding))
    if representations is not None:
        raw["native_error_representation_count"] = representations
    submission = {"identity": payload["identity"], "identity_kind": payload["external_identity_kind"],
        "external_id": external, "accepted": True, "status": "submitted", "deployment": deployment, "raw_receipt": raw}
    return {"submission": submission,
        "completion": {"platform": _platform(payload, deployment, external, raw, status="runtime_error")}}


def research_observation(payload, deployment, tool_envelope, *, dispatch_binding=None):
    """Parse completed success, or a separately bound registered cell error.

    Legacy successful markers still bind their own identity without a new
    dispatch record. Legacy failures without that prior record stay unresolved.
    """
    if dispatch_binding is not None:
        # Both grammars remain closed: a success-shaped cell must satisfy the
        # original marker parser; every other shape must satisfy strict error.
        payload, deployment = _context(payload, deployment, "research")
        native, raw, _ = _research_execution_native(tool_envelope, payload)
        _research_binding(dispatch_binding, payload, deployment, raw["arguments"])
        try:
            _research_error(native, raw["arguments"]["index"])
        except ReceiptParseError:
            pass
        else:
            return research_execution_failure(payload, deployment, tool_envelope, dispatch_binding=dispatch_binding)
    payload, deployment = _context(payload, deployment, "research")
    native, raw = _tool(tool_envelope, "mcp__quantconnect__jupyter_execute_cell", payload)
    wrapper = _decode(_research_stdout(native), payload)
    external = "qc-research:" + str(payload["identity"]["project_id"]) + ":" + payload["identity"]["attempt_id"]
    raw.update(marker_count=1, stdout_only=True)
    submission = {"identity": payload["identity"], "identity_kind": payload["external_identity_kind"],
        "external_id": external, "accepted": True, "status": "submitted", "deployment": deployment, "raw_receipt": raw}
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


def backtest_rejection(payload, deployment, tool_envelope):
    """Parse a native error candidate; only bound compile diagnostics settle.

    A generic error string may describe a lost response after creation. Typed
    success=False alone cannot establish that no worker exists. The fixed
    dispatcher may settle only the tool's file/line/column compile-error form;
    all other well-shaped errors remain ineligible candidates. This operational
    tool trust boundary is not a remote signature or actual-platform acceptance.
    Error text, file names and supplied backtest names are never persisted.
    """
    payload, deployment = _context(payload, deployment, "lean")
    native, observed = _tool(tool_envelope, "mcp__quantconnect__create_backtest", payload)
    if (not isinstance(native, dict) or set(native) - {"success", "errors", "warnings"}
            or native.get("success") is not False):
        _fail("An explicit native rejection without a backtest identity is required")
    arguments = tool_envelope["arguments"]
    if "backtestName" in arguments and (not isinstance(arguments["backtestName"], str)
            or not arguments["backtestName"].strip() or len(arguments["backtestName"]) > 256
            or any(character in arguments["backtestName"] for character in "\r\n")):
        _fail("Native backtest name is not bounded submission metadata")

    def messages(values):
        return (isinstance(values, list) and bool(values)
                and all(isinstance(value, str) and bool(value.strip()) for value in values))

    errors = native.get("errors")
    if messages(errors):
        error_format, error_count, file_count, eligible = "list", len(errors), 0, False
    elif (isinstance(errors, dict) and bool(errors)
            and all(isinstance(name, str) and bool(name.strip()) and messages(values)
                    for name, values in errors.items())):
        error_format, error_count, file_count = "file_map", sum(map(len, errors.values())), len(errors)
        manifest = payload.get("deployment_manifest")
        known = set(manifest) if isinstance(manifest, dict) else set()
        # The generated input is pinned separately by deployment.input_hash.
        known.add("_engineering_task_input.py")
        eligible = isinstance(manifest, dict) and bool(manifest) and content_hash(manifest) == deployment["deployment_hash"]
        for name, digest in (manifest.items() if isinstance(manifest, dict) else ()):
            try:
                validate_key(name)
            except (TypeError, ValueError):
                eligible = False
            if not isinstance(name, str) or not name.endswith(".py") or not _hash(digest):
                eligible = False
        for name, values in errors.items():
            try:
                validate_key(name)
            except (TypeError, ValueError):
                eligible = False
            if name not in known or not name.endswith(".py") or any(
                    re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]* [^\r\n]+", value) is None
                    or not value.partition(" ")[2].strip() for value in values):
                eligible = False
    else:
        _fail("Native rejection errors must be a nonempty string list or file map")
    warnings = native.get("warnings", {})
    if (not isinstance(warnings, dict)
            or any(not isinstance(name, str) or not name.strip() or not messages(values)
                   for name, values in warnings.items())):
        _fail("Native warning metadata is not the documented file map")
    raw = {"tool_name": observed["tool_name"], "response_sha256": observed["response_sha256"],
        "arguments_sha256": content_hash(arguments), "success": False, "rejected": True,
        "error_format": error_format, "error_count": error_count, "error_file_count": file_count,
        "warning_count": sum(map(len, warnings.values())), "settlement_eligible": eligible}
    return {"identity": payload["identity"], "identity_kind": payload["external_identity_kind"],
        "accepted": False, "status": "rejected", "deployment": deployment, "raw_receipt": raw}


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


def backtest_runtime_failure(payload, deployment, external_id, tool_envelope):
    """Recognize the native connector's explicit delivered runtime-error form.

    This tool form has no returned backtest object. Its identity comes from the
    trusted dispatcher's exact read arguments and is checked against the
    original accepted submission by the Bridge. The fixed terminal marker is
    distinct from transport errors; isError or success=False alone proves no
    terminal state. Diagnostic text is inspected transiently and never stored.
    """
    payload, deployment = _context(payload, deployment, "lean")
    native, raw = _tool(tool_envelope, "mcp__quantconnect__read_backtest", payload,
                        external_id=external_id, allow_tool_error=True)
    if (not isinstance(tool_envelope["result"], dict)
            or tool_envelope["result"].get("isError") is not True
            or not isinstance(native, dict) or set(native) != {"success", "errors"}
            or native["success"] is not False):
        _fail("An explicit native completed-runtime-error envelope is required")
    errors = native["errors"]
    if (not isinstance(errors, list) or len(errors) < 2
            or errors[0] != "The backtest ended with a runtime error."
            or any(not isinstance(value, str) or not value.strip()
                   or value.strip() == errors[0] for value in errors[1:])):
        _fail("A native runtime terminal marker and nonempty diagnostics are required")
    raw.update(success=False, native_runtime_error=True, diagnostic_count=len(errors) - 1)
    return {"platform": _platform(payload, deployment, external_id, raw, status="runtime_error")}


def backtest_observation(payload, deployment, external_id, tool_envelope, log_envelopes):
    """Parse only after automatic completion delivery; never perform polling."""
    if (isinstance(tool_envelope, dict) and isinstance(tool_envelope.get("result"), dict)
            and tool_envelope["result"].get("isError") is True):
        return backtest_runtime_failure(payload, deployment, external_id, tool_envelope)
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
        raw["orders_count"] = 0
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
    # Persist the fixed observations' digest/count, not an array that could be
    # mistaken for row payloads by the bridge's metadata residency boundary.
    raw["log_receipt_count"] = len(log_receipts)
    raw["log_receipts_sha256"] = content_hash(log_receipts)
    return {"platform": platform, **wrapper}
