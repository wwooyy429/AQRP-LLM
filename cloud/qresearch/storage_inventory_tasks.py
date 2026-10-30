"""Explicit, precharged Object Store inventory task and native receipt boundary.

This Research-only diagnostic uses one separately pinned standard-library worker.
It neither deploys the production research library nor writes cloud objects. The
trusted dispatcher supplies actual tools; hashes bind observations, not issuers.
"""
import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import re
import zlib

from .artifacts import canonical_json, content_hash
from .engineering_receipts import (_tool, _json, _research_error,
    _research_execution_native, ReceiptParseError, _text_node)


WORKER_PATH = "qresearch/storage_inventory.py"
MARKER = "AQRP_OBJECT_STORE_INVENTORY_V1 "
PREFIX = "object-store-inventory/"
WIRE_LIMIT = 131072
_HASH = re.compile(r"[0-9a-f]{64}")


def _hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


def _error(message):
    raise ValueError(message) from None


def _bounded_envelope(envelope):
    """Bound raw carriers before recursive JSON/native compatibility parsing."""
    pending=[(envelope,0)];nodes=0;text_bytes=0
    while pending:
        value,depth=pending.pop();nodes+=1
        if depth>64 or nodes>10000:
            raise ReceiptParseError("Inventory native envelope exceeds structural bounds")
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                raise ReceiptParseError("Inventory native object keys must be text")
            pending.extend((item,depth+1) for item in value.values())
        elif type(value) is list:
            pending.extend((item,depth+1) for item in value)
        elif type(value) is str:
            try:text_bytes+=len(value.encode('utf-8'))
            except UnicodeError:raise ReceiptParseError("Invalid native UTF8 text") from None
            if text_bytes>2097152:raise ReceiptParseError("Inventory native text exceeds bound")
        elif value is not None and type(value) not in {bool,int,float}:
            raise ReceiptParseError("Unknown native output type")
        elif type(value) is int and value.bit_length()>128:
            raise ReceiptParseError("Inventory native integer exceeds bound")


@dataclass(frozen=True, init=False)
class InventoryTaskPlan:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use from_dict with actual project discovery")

    @classmethod
    def from_dict(cls, raw, *, discovered_project_ids):
        fields = {"schema_version", "task_kind", "scope", "plan_id", "project_id",
            "source_manifest_hash", "worker_sha256", "inventory_policy", "max_retries",
            "final_test_enabled", "orders_enabled", "market_history_enabled"}
        if type(raw) is not dict or set(raw) != fields:
            _error("A complete fixed inventory task is required")
        value = _json(canonical_json(raw))
        ids = tuple(discovered_project_ids)
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["task_kind"] != "object_store_inventory" or value["scope"] != "engineering"
                or type(value["project_id"]) is not int or value["project_id"] <= 0
                or any(type(i) is not int or i <= 0 for i in ids) or value["project_id"] not in ids
                or type(value["max_retries"]) is not int or value["max_retries"] != 0
                or any(value[k] is not False for k in ("final_test_enabled", "orders_enabled", "market_history_enabled"))):
            _error("Inventory is discovered-project Research only, with zero retries and closed gates")
        if (type(value["plan_id"]) is not str
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value["plan_id"]) is None
                or not _hash(value["source_manifest_hash"]) or not _hash(value["worker_sha256"])
                or value["source_manifest_hash"] != value["worker_sha256"]):
            _error("One canonical LF worker source identity is required")
        from .storage_inventory import validate_policy
        value["inventory_policy"] = validate_policy(value["inventory_policy"])
        if len(canonical_json(value)) > 32768:
            _error("Inventory task input exceeds its bounded metadata size")
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json(value))
        return result

    def to_dict(self):
        return _json(self._encoded)

    @property
    def hash(self):
        return sha256(self._encoded).hexdigest()


def context(payload):
    if type(payload) is not dict or set(payload) != {"schema_version", "plan", "identity"} or type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        _error("An original typed inventory payload is required")
    identity = payload["identity"]
    names = {"project_id", "attempt_id", "config_id", "plan_hash", "stage", "worker_sha256"}
    if (type(identity) is not dict or set(identity) != names or identity["stage"] != "research"
            or type(identity["attempt_id"]) is not str or re.fullmatch(r"[0-9a-f]{32}", identity["attempt_id"]) is None
            or not all(_hash(identity[k]) for k in ("config_id", "plan_hash", "worker_sha256"))):
        _error("Inventory task identity is invalid")
    plan = InventoryTaskPlan.from_dict(payload["plan"], discovered_project_ids=(identity["project_id"],))
    value = plan.to_dict()
    if (identity["project_id"] != value["project_id"] or identity["worker_sha256"] != value["worker_sha256"]
            or identity["plan_hash"] != plan.hash
            or identity["config_id"] != content_hash({"engineering_task_schema_version": 1, "plan": value})):
        _error("Inventory identity does not match the frozen configuration")
    return plan


class InventoryTaskBridge:
    def __init__(self, registry, plan):
        if type(plan) is not InventoryTaskPlan:
            raise TypeError("A validated InventoryTaskPlan is required")
        self.registry, self.store, self.plan = registry, registry.store, plan
        self.package = {"engineering_task_schema_version": 1, "plan": plan.to_dict()}
        self.config_id = content_hash(self.package)

    def register(self, *, allocation="normal"):
        if allocation != "normal":
            _error("Inventory uses its explicit bounded normal-allocation grant")
        return self.registry.register_config(self.package, allocation)

    def claim(self, *, allocation="normal"):
        if allocation != "normal":
            _error("Inventory uses its explicit bounded normal-allocation grant")
        return self.registry.begin_attempt(self.config_id, "research", allocation,
            operation_key="object-store-inventory:" + self.plan.hash + ":research")

    def _record(self, attempt):
        identity = getattr(attempt, "attempt_id", attempt)
        records = [r for r in self.registry.snapshot()["attempts"] if r["attempt_id"] == identity]
        if (len(records) != 1 or records[0]["config_id"] != self.config_id or records[0]["stage"] != "research"
                or records[0]["operation_key"] != "object-store-inventory:" + self.plan.hash + ":research"):
            _error("Unknown original inventory attempt")
        return records[0]

    def payload(self, attempt):
        record = self._record(attempt)
        return {"schema_version": 1, "plan": self.plan.to_dict(), "identity": {
            "project_id": self.plan.to_dict()["project_id"], "attempt_id": record["attempt_id"],
            "config_id": self.config_id, "plan_hash": self.plan.hash, "stage": "research",
            "worker_sha256": self.plan.to_dict()["worker_sha256"]}}

    def read_result(self, attempt):
        self._record(attempt)
        return self.registry.read_result(attempt)


def _canonical(store, key, expected=None):
    raw = store.read_bytes(key)
    value = _json(raw)
    if canonical_json(value) != raw or expected is not None and sha256(raw).hexdigest() != expected:
        _error("Original immutable inventory metadata changed")
    return value


def prepare_input(bridge, attempt):
    record = bridge._record(attempt)
    key = PREFIX + "admissions/" + record["attempt_id"] + ".json"
    if bridge.store.exists(key):
        return admitted_input(bridge, record["attempt_id"])
    if record["status"] != "started" or record.get("external_id") is not None:
        _error("Only an undispatched charged inventory attempt may prepare input")
    payload = bridge.payload(record["attempt_id"])
    source = cell_source(payload)
    admission = {"schema_version": 1, "payload": payload,
        "cell_source_sha256": sha256(source.encode()).hexdigest()}
    with bridge.store.locked(bridge.registry.LOCK):
        current = bridge.registry._replay()["attempts"][record["attempt_id"]]
        if current["status"] != "started" or current.get("external_id") is not None:
            _error("Accepted inventory attempts cannot prepare fresh input")
        bridge.store.write_once(key, canonical_json(admission))
    return admission


def admitted_input(bridge, attempt):
    record = bridge._record(attempt)
    value = _canonical(bridge.store, PREFIX + "admissions/" + record["attempt_id"] + ".json")
    if (type(value) is not dict or set(value) != {"schema_version", "payload", "cell_source_sha256"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["payload"] != bridge.payload(record["attempt_id"])
            or value["cell_source_sha256"] != sha256(cell_source(value["payload"]).encode()).hexdigest()):
        _error("Original inventory admission is required")
    return value


def cell_source(payload):
    context(payload)
    # The only executed repository source is verified before exec. Finding a
    # package root does not import the possibly older project research library.
    text = ("import base64 as _b64, hashlib as _hash, json as _json, zlib as _zlib, importlib.util as _iu, types as _types, sys as _sys\n"
        "from pathlib import Path as _Path\n"
        "_spec = _iu.find_spec('qresearch')\n"
        "_locations = list(_spec.submodule_search_locations or ()) if _spec is not None else []\n"
        "if len(_locations) != 1 or not _Path(_locations[0]).is_absolute():\n"
        "    raise ValueError('Inventory worker root is unavailable or ambiguous')\n"
        "_path = _Path(_locations[0]).resolve() / 'storage_inventory.py'\n"
        "_worker_raw = _path.read_bytes()\n"
        "if _hash.sha256(_worker_raw).hexdigest() != " + repr(payload["identity"]["worker_sha256"]) + ":\n"
        "    raise ValueError('Frozen inventory worker differs')\n"
        "_worker = _types.ModuleType('aqrp_object_store_inventory_worker')\n"
        "_worker.__file__ = str(_path)\n"
        "_sys.modules[_worker.__name__] = _worker\n"
        "exec(compile(_worker_raw, str(_path), 'exec'), _worker.__dict__)\n"
        "_payload = _json.loads(" + repr(canonical_json(payload).decode()) + ")\n"
        "from QuantConnect.Research import QuantBook as _QuantBook\n"
        "_qb = _QuantBook()\n"
        "_result = _worker.run_inventory(_qb.object_store, _payload['plan']['inventory_policy'], _payload['identity'])\n"
        "_result = _worker.validate_report(_result, _payload['plan']['inventory_policy'], _payload['identity'])\n"
        "_wire = _b64.b64encode(_zlib.compress(_json.dumps(_result, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8'), 9)).decode('ascii')\n"
        "if len(_wire) > " + str(WIRE_LIMIT) + ":\n"
        "    raise ValueError('Inventory metadata output exceeds bound')\n"
        "print(" + repr(MARKER) + " + _wire)\n")
    if len(text) > 60800:
        _error("Inventory cell exceeds the observed platform source bound")
    return text


def reserve_dispatch(bridge, attempt, read_cell_envelope):
    admission = admitted_input(bridge, attempt)
    payload = admission["payload"]
    _bounded_envelope(read_cell_envelope)
    try:
        native, raw = _tool(read_cell_envelope, "mcp__quantconnect__jupyter_read_cell", payload)
    except RecursionError:
        raise ReceiptParseError("Inventory native JSON exceeds structural bound") from None
    if (type(native) is not dict or set(native) != {"cellType", "source"} or native["cellType"] != "code"
            or type(native["source"]) is not list or any(type(line) is not str for line in native["source"])
            or "".join(native["source"]) != cell_source(payload)):
        _error("Actual read-cell source differs from the frozen inventory task")
    binding = {"schema_version": 1, "protocol": "object_store_inventory_native_v1", "identity": payload["identity"],
        "arguments": raw["arguments"], "cell_source_sha256": admission["cell_source_sha256"],
        "cell_read_response_sha256": raw["response_sha256"]}
    key = PREFIX + "dispatch/" + payload["identity"]["attempt_id"] + ".json"
    with bridge.store.locked(bridge.registry.LOCK):
        if bridge.store.exists(key):
            if _canonical(bridge.store, key) != binding:
                _error("An inventory dispatch cannot acquire another source or cell")
            return {"should_execute": False, "arguments": binding["arguments"], "binding_sha256": content_hash(binding)}
        record = bridge.registry._replay()["attempts"][payload["identity"]["attempt_id"]]
        if record["status"] != "started" or record.get("external_id") is not None:
            _error("Only a charged undispatched inventory attempt may reserve dispatch")
        bridge.store.write_once(key, canonical_json(binding))
    return {"should_execute": True, "arguments": binding["arguments"], "binding_sha256": content_hash(binding)}


def _stdout(native, index):
    lines = []
    wrappers = {"outputs", "output", "cells", "results", "result", "content"}
    metadata = {"execution_count", "status", "success", "execution_state", "cell_index", "index", "metadata"}
    def visit(node):
        if type(node) is str:
            if node.lstrip().startswith(("{", "[")):
                visit(_json(node))
            else:
                lines.extend(node.splitlines())
            return
        if type(node) is list:
            for item in node: visit(item)
            return
        if type(node) is not dict:
            raise ReceiptParseError("Unknown inventory output is prohibited")
        if "output_type" in node or node.get("name") == "stdout":
            if (node.get("output_type", "stream") != "stream" or node.get("name") != "stdout"
                    or set(node) - {"output_type", "name", "text"}):
                raise ReceiptParseError("Displayed values or stderr are prohibited")
            text = node.get("text")
            if type(text) is list and all(type(item) is str for item in text): text = "".join(text)
            if type(text) is not str: raise ReceiptParseError("Inventory stdout must be text")
            lines.extend(text.splitlines()); return
        if node.get("type") == "text":
            visit(_text_node(node)); return
        if set(node) - wrappers - metadata: raise ReceiptParseError("Unknown inventory output metadata")
        for key,value in node.items():
            if key in wrappers: visit(value)
            elif key == "metadata" and value not in ({}, None): raise ReceiptParseError("Unknown native metadata")
            elif key == "success" and value is not True: raise ReceiptParseError("Execution was not successful")
            elif key in {"status", "execution_state"} and value not in {"ok", "completed", "success", "idle"}: raise ReceiptParseError("Execution is not terminal")
            elif key in {"execution_count", "cell_index", "index"} and value is not None and (type(value) is not int or value < 0): raise ReceiptParseError("Invalid native counter")
            elif key in {"cell_index", "index"} and value is not None and value != index: raise ReceiptParseError("Foreign native cell")
    visit(native)
    values = [line for line in lines if line.strip()]
    if len(values) != 1 or not values[0].startswith(MARKER): raise ReceiptParseError("One inventory marker and no other stdout required")
    return values[0][len(MARKER):]


def stdout_marker(report, payload):
    plan = context(payload)
    from .storage_inventory import validate_report
    clean = validate_report(report, plan.to_dict()["inventory_policy"], payload["identity"])
    raw = canonical_json(clean)
    encoded = base64.b64encode(zlib.compress(raw, 9)).decode("ascii")
    if len(encoded) > WIRE_LIMIT: raise ReceiptParseError("Inventory wire size exceeded")
    return MARKER + encoded


def _decode(encoded, payload):
    plan = context(payload)
    if type(encoded) is not str or not 1 <= len(encoded) <= WIRE_LIMIT:
        raise ReceiptParseError("Inventory wire is missing or exceeds bound")
    try:
        compressed = base64.b64decode(encoded, validate=True)
        limit = plan.to_dict()["inventory_policy"]["max_report_bytes"]
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, limit + 1)
        if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data or len(raw) > limit:
            raise ReceiptParseError("Inventory compressed output is incomplete, concatenated or oversized")
        report = _json(raw)
        from .storage_inventory import validate_report
        return validate_report(report, plan.to_dict()["inventory_policy"], payload["identity"])
    except (ValueError, TypeError, zlib.error, RecursionError) as exc:
        raise ReceiptParseError("Invalid bounded inventory metadata") from exc


def _binding(store, payload):
    identity = payload["identity"]
    binding = _canonical(store, PREFIX + "dispatch/" + identity["attempt_id"] + ".json")
    fields = {"schema_version", "protocol", "identity", "arguments", "cell_source_sha256", "cell_read_response_sha256"}
    if (type(binding) is not dict or set(binding) != fields or type(binding["schema_version"]) is not int or binding["schema_version"] != 1
            or binding["protocol"] != "object_store_inventory_native_v1" or binding["identity"] != identity
            or binding["cell_source_sha256"] != sha256(cell_source(payload).encode()).hexdigest()
            or not _hash(binding["cell_read_response_sha256"]) or type(binding["arguments"]) is not dict
            or set(binding["arguments"]) != {"projectId", "index"}
            or type(binding["arguments"]["projectId"]) is not int or binding["arguments"]["projectId"] != identity["project_id"]
            or type(binding["arguments"]["index"]) is not int or binding["arguments"]["index"] < 0):
        _error("Original inventory source/cell dispatch is required")
    return binding


def _native_error_lines(native, index):
    """One strict nbformat error leaf across registered Research wrappers.

    All wrapper fields are checked. Validation may unwrap carriers, but the
    proof always hashes the complete unchanged native result. Error text is
    transient and only its bounded line count is retained.
    """
    counts=[]
    wrappers={"outputs","output","cells","results","result","content"}
    metadata={"execution_count","status","success","execution_state","cell_index","index","metadata"}
    def visit(node):
        if type(node) is str:
            if not node.lstrip().startswith(("{","[")):
                raise ReceiptParseError("Unstructured error text is not a native cell terminal")
            visit(_json(node));return
        if type(node) is list:
            for item in node:visit(item)
            return
        if type(node) is not dict:
            raise ReceiptParseError("Unknown native error output")
        if node.get("output_type")=="error":
            counts.append(_research_error(node,index));return
        if node.get("type")=="text":
            visit(_text_node(node));return
        if set(node)-wrappers-metadata:
            raise ReceiptParseError("Native cell error contains unregistered output")
        for key,value in node.items():
            if key in wrappers:visit(value)
            elif key=="metadata" and value not in ({},None):raise ReceiptParseError("Unknown native error metadata")
            elif key=="success" and value is not False:raise ReceiptParseError("Native error success flag is contradictory")
            elif key=="status" and value!="error":raise ReceiptParseError("Native error status is contradictory")
            elif key=="execution_state" and value not in {"error","idle"}:raise ReceiptParseError("Native error is not terminal")
            elif key=="execution_count" and (type(value) is not int or value<1):raise ReceiptParseError("Invalid native error count")
            elif key in {"cell_index","index"} and (type(value) is not int or value!=index):raise ReceiptParseError("Foreign native error cell")
    visit(native)
    if len(counts)!=1:raise ReceiptParseError("Exactly one native error output is required")
    return counts[0]


def native_observation(payload, binding, envelope):
    context(payload)
    _bounded_envelope(envelope)
    try:
        native, raw, _ = _research_execution_native(envelope, payload)
    except RecursionError:
        raise ReceiptParseError("Inventory native JSON exceeds structural bound") from None
    if raw["arguments"] != binding["arguments"]:
        raise ReceiptParseError("Native inventory cell differs from dispatch")
    try:
        lines = _native_error_lines(native, raw["arguments"]["index"])
    except (ReceiptParseError,RecursionError):
        if envelope["result"].get("isError") is True:
            raise ReceiptParseError("Native tool error is not a verified single-cell error terminal") from None
        lines = None
    if lines is not None:
        report = None
        error = {"native_error_output_count": 1, "traceback_line_count": lines}
        status = "failed"
    else:
        report = _decode(_stdout(native, raw["arguments"]["index"]), payload)
        error = None
        status = report["status"]
    observation = {"identity": payload["identity"], "status": status, "report": report, "error_summary": error}
    return {"schema_version": 1, "protocol": "fixed_object_store_inventory_native_v1",
        "binding_sha256": content_hash(binding), "native_result_sha256": raw["response_sha256"],
        "native_arguments": raw["arguments"], "observation": observation,
        "observation_sha256": content_hash(observation)}


def _proof(store, payload):
    context(payload)
    proof = _canonical(store, PREFIX + "native-receipts/" + payload["identity"]["attempt_id"] + ".json")
    fields = {"schema_version", "protocol", "binding_sha256", "native_result_sha256", "native_arguments", "observation", "observation_sha256"}
    binding = _binding(store, payload)
    if (type(proof) is not dict or set(proof) != fields or type(proof["schema_version"]) is not int or proof["schema_version"] != 1
            or proof["protocol"] != "fixed_object_store_inventory_native_v1"
            or proof["binding_sha256"] != content_hash(binding) or not _hash(proof["native_result_sha256"])
            or proof["native_arguments"] != binding["arguments"]):
        _error("Original fixed-parser inventory native proof is required")
    observation = proof["observation"]
    if (type(observation) is not dict or set(observation) != {"identity", "status", "report", "error_summary"}
            or observation["identity"] != payload["identity"] or observation["status"] not in {"completed", "failed"}
            or content_hash(observation) != proof["observation_sha256"]):
        _error("Inventory parsed observation changed")
    if observation["report"] is not None:
        from .storage_inventory import validate_report
        validate_report(observation["report"], payload["plan"]["inventory_policy"], payload["identity"])
        if observation["status"] != observation["report"]["status"] or observation["error_summary"] is not None:
            _error("Inventory report status differs from native observation")
    else:
        error = observation["error_summary"]
        if (observation["status"] != "failed" or type(error) is not dict
                or set(error) != {"native_error_output_count", "traceback_line_count"}
                or type(error["native_error_output_count"]) is not int or error["native_error_output_count"] != 1
                or type(error["traceback_line_count"]) is not int or not 1 <= error["traceback_line_count"] <= 128):
            _error("Inventory native error proof must contain only fixed counts")
    return proof


def _proof_ref(proof, attempt):
    return {"key": PREFIX + "native-receipts/" + attempt + ".json", "sha256": content_hash(proof)}


def _result(payload, proof):
    return {"schema_version": 1, "kind": "object_store_inventory_native_result", "identity": payload["identity"],
        "status": proof["observation"]["status"], "report": proof["observation"]["report"],
        "native_proof_ref": _proof_ref(proof, payload["identity"]["attempt_id"]),
        "financial_evidence": False, "final_test_enabled": False}


def validate_registry_transition(store, package, record, kind, *, fields=None, result=None):
    """Pure guard under Registry.LOCK; no replay, network or nested Registry call."""
    attempt = record["attempt_id"]
    admission = _canonical(store, PREFIX + "admissions/" + attempt + ".json")
    if (type(admission) is not dict or set(admission) != {"schema_version", "payload", "cell_source_sha256"}
            or type(admission["schema_version"]) is not int or admission["schema_version"] != 1):
        _error("Original inventory admission is required for lifecycle transitions")
    payload = admission["payload"]
    plan = context(payload)
    identity = payload["identity"]
    if (payload["plan"] != package["plan"] or identity["attempt_id"] != attempt or identity["config_id"] != record["config_id"]
            or record["stage"] != "research" or record["operation_key"] != "object-store-inventory:" + plan.hash + ":research"
            or admission["cell_source_sha256"] != sha256(cell_source(payload).encode()).hexdigest()):
        _error("Inventory transition belongs to another frozen admission")
    proof = _proof(store, payload)
    external = "qc-inventory:" + str(identity["project_id"]) + ":" + attempt
    fields = fields or {}
    common = {"kind", "attempt_id", "recorded_at"}
    allowed = {"pending": {"external_id", "details"},
               "completed": {"external_id", "result_sha256"},
               "failed": {"error", "reconciliation"}}
    if kind not in allowed or set(fields) - common - allowed[kind]:
        _error("Inventory lifecycle fields cannot carry unregistered side data")
    ref = _proof_ref(proof, attempt)
    if kind == "pending":
        if fields.get("external_id") != external or fields.get("details") != {"identity": identity, "native_proof_ref": ref}:
            _error("Inventory pending state requires its original native proof")
    elif kind == "completed":
        if proof["observation"]["status"] != "completed" or result != _result(payload, proof):
            _error("Inventory completion requires its exact successful native metadata")
        if fields.get("external_id") != external:
            _error("Inventory completion external identity changed")
    elif kind == "failed":
        expected = {"failure_code": "inventory_native_cell_error" if proof["observation"]["report"] is None else "inventory_observation_failed", "native_proof_ref": ref}
        if proof["observation"]["status"] != "failed" or fields.get("error") != expected:
            _error("Inventory failure requires its exact fixed-parser native metadata")
    else:
        _error("Unknown inventory lifecycle transition")


def settle_result(bridge, attempt, envelope):
    admission = admitted_input(bridge, attempt)
    payload = admission["payload"]
    binding = _binding(bridge.store, payload)
    proof = native_observation(payload, binding, envelope)
    key = PREFIX + "native-receipts/" + payload["identity"]["attempt_id"] + ".json"
    with bridge.store.locked(bridge.registry.LOCK):
        if bridge.store.exists(key) and _canonical(bridge.store, key) != proof:
            _error("A settled inventory observation cannot be replaced by another native result")
        bridge.store.write_once(key, canonical_json(proof))
    record = bridge._record(attempt)
    if record["status"] in {"completed", "failed"}:
        _proof(bridge.store, payload)
        if record["status"] != proof["observation"]["status"]:
            _error("Inventory attempt has another terminal state")
        return bridge.registry._attempt(record)
    external = "qc-inventory:" + str(payload["identity"]["project_id"]) + ":" + record["attempt_id"]
    ref = _proof_ref(proof, record["attempt_id"])
    if record["status"] == "started":
        bridge.registry.pending(record["attempt_id"], external_id=external, details={"identity": payload["identity"], "native_proof_ref": ref})
    if proof["observation"]["status"] == "completed":
        return bridge.registry.complete(record["attempt_id"], _result(payload, proof), external_id=external)
    error = {"failure_code": "inventory_native_cell_error" if proof["observation"]["report"] is None else "inventory_observation_failed", "native_proof_ref": ref}
    return bridge.registry.fail(record["attempt_id"], error,
        reconciliation=content_hash(proof) if record["status"] == "ambiguous" else None)
