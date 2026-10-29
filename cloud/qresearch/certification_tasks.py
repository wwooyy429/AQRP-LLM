"""Precharged, reference-only certification diagnostics on the shared Registry.

The kernel tests declared QC-resident evidence; it cannot authenticate historical
vendor provenance, platform billing or grant Research/financial approval. A
successful worker may correctly report insufficient data evidence. No imports
perform I/O, no function polls a task or calls a market-data provider.
"""
import base64
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import json
import re

from .artifacts import canonical_json, content_hash, validate_key
from .data_certification import (DataCertificationPlan, audit_data_certification,
    _COUNTS, _CHECKS, _FALSE_FLAGS, _GAPS, _REPORT_KEYS)
from .deployment_observation import validate_observation_binding
from .deployment_sources import parse_manifest
from .engineering_data import verify_deployment_observation
from .engineering_receipts import (_tool, _json, _research_stdout,
    _research_error, _research_execution_native, ReceiptParseError)
from .engineering_tasks import EngineeringTaskBridge, EngineeringTaskError, _safe_identity
from .ingestion import HistoricalBatchIngestor
from .contracts import aware


FLAGS = {"market_values_exported", "economic_factor_tested", "final_data_accessed",
         "full_US200_coverage_certified", "actual_availability_verified"}
CHECKS = {"diagnostic_completed", "source_identity_matches", "cloud_rows_not_exported", "development_only"}
REFS = {"liquidity", "financial", "membership", "prices", "security_master", "corporate_actions"}
_HASH = re.compile(r"[0-9a-f]{64}")
_BINDING = "certification/research-dispatch/"
_ADMISSION = "certification/admitted-inputs/"


def _fail(message):
    raise EngineeringTaskError(message) from None


def _hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


def _refs(value):
    if type(value) is not dict or set(value) != REFS:
        _fail("All six explicit certification reference lists are required")
    copied, seen = {}, set()
    for kind, items in value.items():
        if type(items) is not list or len(items) > 10000:
            _fail("Certification reference lists must be bounded")
        result = []
        for ref in items:
            prefix = "ingestion/v1/batches/" if kind in {"liquidity", "financial"} else "data-certification/v1/inputs/"
            if (type(ref) is not dict or set(ref) != {"key", "sha256"} or not _hash(ref["sha256"])
                    or ref["key"] != prefix + ref["sha256"] + ".json" or ref["key"] in seen):
                _fail("Certification inputs require unique exact content-addressed references")
            seen.add(ref["key"])
            result.append(dict(ref))
        copied[kind] = sorted(result, key=lambda ref: ref["key"])
    if len(seen) > 128:
        _fail("Partition certification tasks before exceeding128 immutable inputs")
    return copied


@dataclass(frozen=True, init=False)
class CertificationTaskPlan:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use from_dict with trusted project discovery and financial catalog")

    @classmethod
    def from_dict(cls, raw, *, discovered_project_ids, financial_catalog):
        fields = {"schema_version", "task_kind", "scope", "plan_id", "project_id", "source_manifest_hash",
                  "deployment_hash", "certification_plan", "input_refs", "source_binding", "store_prefix",
                  "report_namespace", "max_retries", "capacity"}
        if type(raw) is not dict or set(raw) != fields:
            _fail("A complete explicit certification task is required")
        try:
            value = json.loads(canonical_json(raw))
        except (ValueError, TypeError, UnicodeError):
            _fail("Certification tasks require finite JSON metadata")
        ids = tuple(discovered_project_ids)
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["task_kind"] != "data_certification" or value["scope"] != "engineering"
                or type(value["project_id"]) is not int or value["project_id"] <= 0
                or any(type(item) is not int or item <= 0 for item in ids) or value["project_id"] not in ids
                or type(value["max_retries"]) is not int or value["max_retries"] != 0):
            _fail("Use discovered projects, engineering scope and zero automatic retries")
        if (type(value["plan_id"]) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value["plan_id"]) is None
                or not all(_hash(value[name]) for name in ("source_manifest_hash", "deployment_hash"))):
            _fail("Explicit task and source/deployment identities are required")
        for name in ("store_prefix", "report_namespace"):
            if type(value[name]) is not str or len(value[name]) > 120:
                _fail("Bounded explicit artifact namespaces are required")
            validate_key(value[name])
        capacity = value["capacity"]
        bounds = {"required_bytes": (196608, 8388608), "required_files": (3, 64),
                  "reserve_bytes": (8192, 8388608), "reserve_files": (2, 64)}
        if (type(capacity) is not dict or set(capacity) != set(bounds)
                or any(type(capacity[key]) is not int or not lower <= capacity[key] <= upper
                       for key, (lower, upper) in bounds.items())):
            _fail("Freeze bounded capacity for three metadata writes and explicit reserve")
        plan = DataCertificationPlan.from_dict(value["certification_plan"])
        data = plan.to_dict()
        if (data["source_manifest_hash"] != value["source_manifest_hash"] or type(financial_catalog) is not dict
                or any(path not in financial_catalog or financial_catalog[path] != spec
                       for path, spec in data["financial_catalog"].items())):
            _fail("Certification may select only trusted financial fields with their frozen semantics")
        value["certification_plan"] = data
        value["input_refs"] = _refs(value["input_refs"])
        binding = value["source_binding"]
        if binding is not None:
            if (type(binding) is not dict or set(binding) != {"source", "data_version", "origin", "synthetic", "financial_catalog"}
                    or type(binding["synthetic"]) is not bool or binding["data_version"] != data["data_version"]
                    or binding["financial_catalog"] != data["financial_catalog"]):
                _fail("The original ingestion source binding must match this certification plan")
            if (type(binding["source"]) is not str
                    or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,159}", binding["source"]) is None
                    or binding["origin"] not in {"historical_all_market", "historical_declared_fixture"}):
                _fail("A bounded original ingestion source and historical origin are required")
            # The shared ingestor's namespace is the canonical source-binding
            # hash. Metadata validation neither opens a store nor invents one.
            if content_hash(binding) != data["ingestion_namespace"]:
                _fail("Ingestion namespace differs from its source binding")
        elif value["input_refs"]["liquidity"] or value["input_refs"]["financial"]:
            _fail("Source references require their original ingestion binding")
        if len(canonical_json(value)) > 32768:
            _fail("Partition certification task metadata before exceeding its input bound")
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json(value))
        return result

    def to_dict(self):
        return json.loads(self._encoded)

    @property
    def hash(self):
        return sha256(self._encoded).hexdigest()

    @property
    def certification_plan(self):
        return DataCertificationPlan.from_dict(self.to_dict()["certification_plan"])

    @property
    def request_hash(self):
        value = self.to_dict()
        return content_hash({name: value[name] for name in ("certification_plan", "input_refs", "source_binding", "store_prefix")})


def context(payload):
    required = {"plan", "identity", "report_key", "external_identity_kind"}
    if type(payload) is not dict or not required <= set(payload) or set(payload) - required - {"deployment_manifest"}:
        _fail("Only a complete frozen certification task input is permitted")
    identity = payload["identity"]
    _safe_identity(identity)
    raw = payload["plan"]
    frozen_catalog = raw.get("certification_plan", {}).get("financial_catalog") if type(raw) is dict else None
    plan = CertificationTaskPlan.from_dict(raw, discovered_project_ids=(identity["project_id"],), financial_catalog=frozen_catalog)
    value = plan.to_dict()
    expected = {"plan_hash": plan.hash, "config_id": content_hash({"engineering_task_schema_version": 1, "plan": value}),
                "stage": "research", "project_id": value["project_id"], "source_manifest_hash": value["source_manifest_hash"],
                "deployment_hash": value["deployment_hash"], "data_request_hash": plan.request_hash}
    key = value["report_namespace"] + "/reports/" + plan.hash + "/research/" + identity["attempt_id"] + ".json"
    if (any(identity[name] != wanted for name, wanted in expected.items()) or payload["report_key"] != key
            or payload["external_identity_kind"] != "logical_research_execution_receipt"):
        _fail("Certification identity, input references or report destination changed")
    return plan


def _observation(report, plan):
    """Closed metadata grammar, not independent authentication of data claims."""
    value = plan.certification_plan.to_dict()
    if (type(report) is not dict or set(report) != _REPORT_KEYS | {"report_ref"}
            or type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["kind"] != "data_certification_observed_scope" or report["plan_hash"] != plan.certification_plan.hash
            or any(report[name] is not False for name in _FALSE_FLAGS) or type(report["synthetic"]) is not bool
            or report["source_manifest_hash"] != value["source_manifest_hash"]
            or report["ingestion_namespace"] != value["ingestion_namespace"]
            or report["data_version_hash"] != content_hash(value["data_version"])
            or report["financial_catalog_hash"] != content_hash(value["financial_catalog"])
            or report["scope_start"] != value["start"] or report["scope_end_exclusive"] != value["end_exclusive"]
            or report["warmup_start"] != value["warmup_start"] or type(report["universe_size"]) is not int or report["universe_size"] != 200
            or type(report["liquidity_lookback_sessions"]) is not int or report["liquidity_lookback_sessions"] != 20):
        _fail("Only the frozen certification kernel observation may leave cloud")
    checks, counts = report["checks"], report["counts"]
    if (type(checks) is not dict or set(checks) != _CHECKS or any(type(flag) is not bool for flag in checks.values())
            or type(counts) is not dict or set(counts) != set(_COUNTS)
            or any(type(count) is not int or not 0 <= count <= 10**12 for count in counts.values())
            or report["status"] != ("observations_passed" if all(checks.values()) else "insufficient_evidence")
            or report["gap_codes"] != sorted(list(_GAPS) + ["observed_" + name + "_failed" for name, flag in checks.items() if not flag])
            or not _hash(report["calendar_hash"]) or not _hash(report["ranked_membership_hash"])
            or _refs(report["evidence_refs"]) != plan.to_dict()["input_refs"]):
        _fail("Certification counts, references, checks or insufficiency status changed")
    binding = plan.to_dict()["source_binding"]
    if binding is not None and report["synthetic"] is not binding["synthetic"]:
        _fail("Synthetic classification differs from the frozen source")
    if (counts["expected_member_cells"] != 200 * counts["formation_count"]
            or counts["observed_member_cells"] > counts["expected_member_cells"]
            or counts["price_observed_cells"] > counts["expected_member_cells"]
            or counts["price_missing_cells"] != counts["expected_member_cells"] - counts["price_observed_cells"]
            or counts["financial_available_cells"] > counts["financial_expected_cells"]
            or counts["financial_missing_cells"] != counts["financial_expected_cells"] - counts["financial_available_cells"]):
        _fail("Certification aggregate counts are inconsistent")
    for name, prefix in (("context_ref", "data-certification/v1/contexts/"), ("report_ref", "data-certification/v1/reports/")):
        ref = report[name]
        if type(ref) is not dict or set(ref) != {"key", "sha256"} or not _hash(ref["sha256"]) or ref["key"] != prefix + ref["sha256"] + ".json":
            _fail("Certification report/context reference is not content addressed")
    original = {name: item for name, item in report.items() if name != "report_ref"}
    if report["report_ref"]["sha256"] != content_hash(original):
        _fail("Certification kernel report digest changed")
    return report


def validate_report(report, plan, identity):
    required = {"schema_version", "identity", "status", "terminal", "checks", "statistics", "evidence"} | FLAGS
    if (type(report) is not dict or set(report) != required or type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["identity"] != identity or report["terminal"] is not True or report["status"] != "completed"
            or any(report[name] is not False for name in FLAGS)
            or report["checks"] != {name: True for name in CHECKS}
            or any(type(flag) is not bool for flag in report["checks"].values())
            or report["statistics"] != {"diagnostic_count": 1} or type(report["statistics"]["diagnostic_count"]) is not int):
        _fail("A completed diagnostic is distinct from certification or financial approval")
    _safe_identity(identity)
    evidence = report["evidence"]
    if type(evidence) is not dict or set(evidence) != {"observation", "deployment_verification", "storage_preflight"}:
        _fail("Only the fixed certification observation and source evidence may leave cloud")
    _observation(evidence["observation"], plan)
    if evidence["storage_preflight"] is None:
        if evidence["observation"]["synthetic"] is not True:
            _fail("Real certification requires its live SDK capacity observation")
    else:
        from .engineering_storage import validate_capacity_observation
        validate_capacity_observation(evidence["storage_preflight"])
        if any(evidence["storage_preflight"][name] != count for name, count in plan.to_dict()["capacity"].items()):
            _fail("SDK capacity observation differs from the frozen requirement")
    from .deployment_observation import validate_deployment_observation
    validate_deployment_observation(evidence["deployment_verification"], deployment_hash=identity["deployment_hash"])
    return True


class CertificationTaskBridge(EngineeringTaskBridge):
    """One shared authoritative ledger; strict native input/dispatch required."""
    def __init__(self, registry, plan):
        if type(plan) is not CertificationTaskPlan:
            raise TypeError("A validated CertificationTaskPlan is required")
        self.registry, self.store, self.plan = registry, registry.store, plan
        self.adapter, self.completion_source = None, None
        self.package = {"engineering_task_schema_version": 1, "plan": plan.to_dict()}
        self.config_id = content_hash(self.package)

    def _operation(self, stage):
        if stage != "research":
            _fail("Certification diagnostics are Research-only")
        return "certification-plan:" + self.plan.hash + ":research"

    def claim(self, stage="research", *, allocation="normal", retry_of=None, reason=None):
        return self.registry.begin_attempt(self.config_id, stage, allocation=allocation,
            operation_key=self._operation(stage), retry_of=retry_of, reason=reason)

    def submit(self, *args, **kwargs):
        _fail("Use precharged claim, immutable input preparation and source-bound native dispatch")

    def record_submission(self, *args, **kwargs):
        _fail("Certification submissions require the fixed native settle_result path")

    def consume_completion(self, *args, **kwargs):
        _fail("Certification completions require the fixed native settle_result path")

    def _submission_metadata(self, receipt):
        super()._submission_metadata(receipt)
        proof = _native_proof(self.store, receipt["identity"]["attempt_id"])
        if proof["submission_sha256"] != content_hash(receipt):
            _fail("Certification submission differs from its fixed native parser receipt")

    def _completion_metadata(self, observed):
        super()._completion_metadata(observed)
        proof = _native_proof(self.store, observed["platform"]["identity"]["attempt_id"])
        if proof["completion_sha256"] != content_hash(observed):
            _fail("Certification completion differs from its fixed native parser receipt")

    def _report_metadata(self, report):
        validate_report(report, self.plan, report.get("identity") if type(report) is dict else None)

    def _cloud_report(self, report, payload):
        validate_report(report, self.plan, payload["identity"])
        admitted = admitted_input(self, payload["identity"]["attempt_id"])
        validate_observation_binding(report["evidence"], admitted["payload"]["deployment_manifest"], payload["identity"]["deployment_hash"])
        return True


def prepare_input(bridge, attempt, manifest):
    record = bridge._record(attempt)
    key = _ADMISSION + record["attempt_id"] + ".json"
    if bridge.store.exists(key):
        existing = admitted_input(bridge, record["attempt_id"])
        if existing["payload"]["deployment_manifest"] != manifest:
            _fail("An admitted certification input cannot acquire a new manifest")
        return existing
    if record["status"] != "started":
        _fail("Only an undispatched charged certification task may prepare input")
    version, _ = parse_manifest(manifest)
    if version != 2 or content_hash(manifest) != bridge.plan.to_dict()["deployment_hash"]:
        _fail("New certification inputs require their exact explicit version2 deployment")
    payload = dict(bridge.payload(record["attempt_id"]), deployment_manifest=manifest)
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode("utf-8")) + "\n"
    if len(text) > 60800:
        _fail("Certification input exceeds the observed source-file character bound")
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"], "deployment_hash": payload["identity"]["deployment_hash"],
                  "input_hash": sha256(text.encode("utf-8")).hexdigest()}
    admission = {"schema_version": 1, "payload": payload, "deployment": deployment, "cloud_input_path": "_collection_task_input.py"}
    with bridge.store.locked(bridge.registry.LOCK):
        current = bridge.registry._replay()["attempts"][record["attempt_id"]]
        if current["status"] != "started" or current.get("external_id") is not None:
            _fail("Finalized or accepted certification attempts cannot create fresh input")
        bridge.store.write_once(key, canonical_json(admission))
    return admission


def admitted_input(bridge, attempt):
    record = bridge._record(attempt)
    raw = bridge.store.read_bytes(_ADMISSION + record["attempt_id"] + ".json")
    admission = _json(raw)
    if (type(admission) is not dict or set(admission) != {"schema_version", "payload", "deployment", "cloud_input_path"}
            or type(admission["schema_version"]) is not int or admission["schema_version"] != 1
            or canonical_json(admission) != raw or admission["cloud_input_path"] != "_collection_task_input.py"):
        _fail("Original canonical certification admission is required")
    payload = admission["payload"]
    context(payload)
    version, _ = parse_manifest(payload.get("deployment_manifest"))
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode("utf-8")) + "\n"
    expected = {"source_manifest_hash": payload["identity"]["source_manifest_hash"], "deployment_hash": payload["identity"]["deployment_hash"],
                "input_hash": sha256(text.encode()).hexdigest()}
    if (version != 2 or payload != dict(bridge.payload(attempt), deployment_manifest=payload["deployment_manifest"])
            or content_hash(payload["deployment_manifest"]) != payload["identity"]["deployment_hash"] or admission["deployment"] != expected):
        _fail("Original certification input or deployment changed")
    return admission


def cell_source(payload, deployment):
    context(payload)
    # Original preparation and canonical artifact recovery may have different
    # dict insertion order. Entry source must depend on typed JSON semantics.
    identity = json.loads(canonical_json(payload["identity"]))
    if (type(deployment) is not dict or set(deployment) != {"source_manifest_hash", "deployment_hash", "input_hash"}
            or any(not _hash(item) for item in deployment.values())
            or any(deployment[name] != payload["identity"][name] for name in ("source_manifest_hash", "deployment_hash"))):
        _fail("An original source-bound input deployment is required")
    return ("import ast as _ast, hashlib as _hashlib, json as _json, importlib as _importlib, sys as _sys\n"
        "from pathlib import Path as _Path\n"
        "for _name in list(_sys.modules):\n"
        "    if _name == 'qresearch' or _name.startswith('qresearch.'):\n"
        "        _sys.modules.pop(_name, None)\n"
        "_importlib.invalidate_caches()\n"
        "import qresearch as _qresearch\n"
        "_root = _Path(_qresearch.__file__).resolve().parent.parent\n"
        "_raw = (_root / '_collection_task_input.py').read_bytes()\n"
        "if _hashlib.sha256(_raw).hexdigest() != " + repr(deployment["input_hash"]) + ":\n"
        "    raise ValueError('Frozen certification input identity differs')\n"
        "_tree = _ast.parse(_raw.decode('utf-8-sig'))\n"
        "if (len(_tree.body) != 1 or not isinstance(_tree.body[0], _ast.Assign) or len(_tree.body[0].targets) != 1\n"
        "        or not isinstance(_tree.body[0].targets[0], _ast.Name) or _tree.body[0].targets[0].id != 'TASK_INPUT_JSON'\n"
        "        or not isinstance(_tree.body[0].value, _ast.Constant) or not isinstance(_tree.body[0].value.value, str)):\n"
        "    raise ValueError('Certification input must be one inert JSON assignment')\n"
        "_payload = _json.loads(_tree.body[0].value.value)\n"
        "if _payload.get('identity') != " + repr(identity) + ":\n"
        "    raise ValueError('Frozen certification attempt identity differs')\n"
        "from qresearch.certification_tasks import run_cloud_task, stdout_marker\n"
        "_result = run_cloud_task(_payload)\n"
        "print(stdout_marker(_result, _payload))\n")


def reserve_dispatch(bridge, attempt, read_cell_envelope):
    admission = admitted_input(bridge, attempt)
    payload, deployment = admission["payload"], admission["deployment"]
    native, raw = _tool(read_cell_envelope, "mcp__quantconnect__jupyter_read_cell", payload)
    if (type(native) is not dict or set(native) != {"cellType", "source"} or native["cellType"] != "code"
            or type(native["source"]) is not list or any(type(line) is not str for line in native["source"])
            or "".join(native["source"]) != cell_source(payload, deployment)):
        _fail("Actual source readback does not match the fixed certification entry")
    binding = {"schema_version": 1, "protocol": "certification_native_research_v1", "identity": payload["identity"],
        "deployment": deployment, "arguments": raw["arguments"], "cell_source_sha256": sha256(cell_source(payload, deployment).encode()).hexdigest(),
        "cell_read_response_sha256": raw["response_sha256"]}
    key = _BINDING + payload["identity"]["attempt_id"] + ".json"
    with bridge.store.locked(bridge.registry.LOCK):
        record = bridge.registry._replay()["attempts"][payload["identity"]["attempt_id"]]
        if bridge.store.exists(key):
            if bridge.store.read_bytes(key) != canonical_json(binding):
                _fail("Reserved certification dispatch cannot be retargeted")
            return {"should_execute": False, "binding": binding, "budget_charged": False}
        if record["status"] != "started" or record.get("external_id") is not None:
            _fail("Only a charged undispatched certification task may reserve execution")
        bridge.store.write_once(key, canonical_json(binding))
    return {"should_execute": True, "binding": binding, "budget_charged": False}


def run_certification_task(payload, *, store, calendar, ingestor=None, synthetic=False, source_root=None):
    """Execute inside a precharged trusted Research cell, using cloud refs only."""
    plan = context(payload)
    if type(synthetic) is not bool or not synthetic and getattr(store, "residency", None) != "quantconnect_cloud":
        _fail("Real certification rows must remain in QuantConnect Cloud")
    version, _ = parse_manifest(payload.get("deployment_manifest"))
    if version != 2:
        _fail("New certification tasks require explicit version2 source identity")
    source_observation = verify_deployment_observation(payload["deployment_manifest"], plan.to_dict()["deployment_hash"], source_root=source_root)
    capacity_observation = None
    if not synthetic:
        capacity_observation = store.preflight_capacity(**plan.to_dict()["capacity"])
    refs = plan.to_dict()["input_refs"]
    args = {"liquidity_refs": refs["liquidity"], "financial_refs": refs["financial"], "membership_refs": refs["membership"],
        "price_refs": refs["prices"], "security_master_refs": refs["security_master"], "corporate_action_refs": refs["corporate_actions"]}
    observation = audit_data_certification(store, plan.certification_plan, calendar=calendar, ingestor=ingestor, synthetic=synthetic, **args)
    report = {"schema_version": 1, "identity": payload["identity"], "status": "completed", "terminal": True,
        "checks": {name: True for name in CHECKS}, "statistics": {"diagnostic_count": 1}, **{name: False for name in FLAGS},
        "evidence": {"observation": observation, "deployment_verification": source_observation, "storage_preflight": capacity_observation}}
    validate_report(report, plan, payload["identity"])
    validate_observation_binding(report["evidence"], payload["deployment_manifest"], plan.to_dict()["deployment_hash"])
    store.write_once(payload["report_key"], canonical_json(report))
    return {"cloud_report": report, "report_ref": {"key": payload["report_key"], "sha256": content_hash(report)}}


def run_cloud_task(payload):
    """Fixed QC bootstrap; no history/fetch and no caller-chosen executable code."""
    plan = context(payload)
    binding = plan.to_dict()["source_binding"]
    if binding is not None and binding["synthetic"] is not False:
        _fail("The production cloud entry cannot read synthetic-classified inputs")
    from AlgorithmImports import Resolution
    from QuantConnect.Research import QuantBook
    from .quantconnect import ObjectStoreArtifactStore, ExchangeCalendar
    qb = QuantBook()
    qb.set_time_zone("America/New_York")
    # Never inherit QuantBook's current-date security/calendar frontier. The
    # exclusive endpoint may be2024-01-01, so use its preceding NY day.
    frontier = aware(plan.certification_plan.to_dict()["end_exclusive"]) - timedelta(days=1)
    qb.set_start_date(frontier.year, frontier.month, frontier.day)
    security = qb.add_equity("SPY", Resolution.DAILY)
    store = ObjectStoreArtifactStore(qb.object_store, plan.to_dict()["store_prefix"], read_only=False, single_producer=True)
    ingest = HistoricalBatchIngestor(store, **binding) if binding is not None else None
    return run_certification_task(payload, store=store, calendar=ExchangeCalendar(security.exchange.hours), ingestor=ingest)


def stdout_marker(wrapper, payload):
    plan = context(payload)
    if type(wrapper) is not dict or set(wrapper) != {"cloud_report", "report_ref"}:
        _fail("Only fixed aggregate certification metadata may be printed")
    validate_report(wrapper["cloud_report"], plan, payload["identity"])
    validate_observation_binding(wrapper["cloud_report"]["evidence"], payload["deployment_manifest"], plan.to_dict()["deployment_hash"])
    if wrapper["report_ref"] != {"key": payload["report_key"], "sha256": content_hash(wrapper["cloud_report"])}:
        _fail("Certification output reference changed")
    encoded = base64.b64encode(canonical_json(wrapper)).decode("ascii")
    if len(encoded) > 64000:
        _fail("Certification metadata output exceeds its bound")
    return "AQRP_ENGINEERING_JSON " + encoded


def research_observation(payload, deployment, envelope, *, dispatch_binding):
    plan = context(payload)
    native, raw, _ = _research_execution_native(envelope, payload)
    binding = dispatch_binding
    expected_keys = {"schema_version", "protocol", "identity", "deployment", "arguments", "cell_source_sha256", "cell_read_response_sha256"}
    if (type(binding) is not dict or set(binding) != expected_keys or type(binding["schema_version"]) is not int or binding["schema_version"] != 1
            or binding["protocol"] != "certification_native_research_v1" or binding["identity"] != payload["identity"]
            or binding["deployment"] != deployment or binding["arguments"] != raw["arguments"]
            or not _hash(binding["cell_read_response_sha256"])
            or binding["cell_source_sha256"] != sha256(cell_source(payload, deployment).encode()).hexdigest()):
        raise ReceiptParseError("Original certification dispatch binding is required")
    external = "qc-research:" + str(payload["identity"]["project_id"]) + ":" + payload["identity"]["attempt_id"]
    submission = {"identity": payload["identity"], "identity_kind": payload["external_identity_kind"], "external_id": external,
                  "accepted": True, "status": "submitted", "deployment": deployment, "raw_receipt": raw}
    platform = {"identity": dict(payload["identity"], external_id=external), "status": "completed", "terminal": True,
                "deployment": deployment, "raw_receipt": raw}
    try:
        traces = _research_error(native, raw["arguments"]["index"])
    except ReceiptParseError:
        traces = None
    if traces is not None:
        raw.update(native_research_error=True, error_output_count=1, traceback_line_count=traces,
                   dispatch_binding_sha256=content_hash(binding))
        platform["status"] = "runtime_error"
        return {"submission": submission, "completion": {"platform": platform}}
    encoded = _research_stdout(native, cell_index=raw["arguments"]["index"])
    if not encoded or len(encoded) > 64000:
        raise ReceiptParseError("Missing or unbounded certification marker")
    try:
        decoded = base64.b64decode(encoded, validate=True)
        if base64.b64encode(decoded).decode("ascii") != encoded:
            raise ValueError
        wrapper = _json(decoded.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise ReceiptParseError("Invalid certification marker") from None
    stdout_marker(wrapper, payload)
    raw.update(marker_count=1, stdout_only=True)
    return {"submission": submission, "completion": {"platform": platform, **wrapper}}


def settle_result(bridge, attempt, envelope):
    admission = admitted_input(bridge, attempt)
    encoded = bridge.store.read_bytes(_BINDING + attempt + ".json")
    binding = _json(encoded)
    if canonical_json(binding) != encoded:
        _fail("Certification dispatch binding is not canonical")
    observed = research_observation(admission["payload"], admission["deployment"], envelope, dispatch_binding=binding)
    proof = {"schema_version": 1, "protocol": "fixed_certification_native_receipt_v1", "identity": admission["payload"]["identity"],
        "binding_sha256": sha256(encoded).hexdigest(), "native_result_sha256": content_hash(envelope["result"]),
        "parsed_observation_sha256": content_hash(observed), "submission_sha256": content_hash(observed["submission"]),
        "completion_sha256": content_hash(observed["completion"])}
    bridge.store.write_once("certification/native-receipts/" + attempt + ".json", canonical_json(proof))
    record = bridge._record(attempt)
    if record["status"] in {"completed", "failed"}:
        submission = bridge._recorded_submission(admission["payload"])
        if submission["receipt_ref"]["sha256"] != content_hash(observed["submission"]):
            _fail("A different native certification receipt cannot replace a settled task")
        bridge._completion_contract(admission["payload"], submission, observed["completion"])
        return bridge._attempt(record)
    # Public callback entry points are deliberately unavailable for this new
    # task kind. Only this fixed parser creates the immutable native receipt;
    # virtual metadata validators and Registry guards check it even if a caller
    # explicitly invokes an ordinary base-class method.
    EngineeringTaskBridge.record_submission(bridge, attempt, observed["submission"])
    return EngineeringTaskBridge.consume_completion(bridge, attempt, completion_source=lambda _: observed["completion"])


def _canonical_document(store, key, digest=None):
    raw = store.read_bytes(key)
    value = _json(raw)
    if canonical_json(value) != raw or digest is not None and sha256(raw).hexdigest() != digest:
        _fail("Original immutable certification receipt bytes changed")
    return value


def _native_proof(store, attempt):
    proof = _canonical_document(store, "certification/native-receipts/" + attempt + ".json")
    keys = {"schema_version", "protocol", "identity", "binding_sha256", "native_result_sha256",
            "parsed_observation_sha256", "submission_sha256", "completion_sha256"}
    if (type(proof) is not dict or set(proof) != keys or type(proof["schema_version"]) is not int or proof["schema_version"] != 1
            or proof["protocol"] != "fixed_certification_native_receipt_v1" or type(proof["identity"]) is not dict
            or proof["identity"].get("attempt_id") != attempt
            or any(not _hash(proof[name]) for name in keys - {"schema_version", "protocol", "identity"})):
        _fail("An original fixed-parser certification native receipt is required")
    _safe_identity(proof["identity"])
    return proof


def validate_registry_transition(store, package, record, kind, *, fields=None, result=None):
    """Pure certification-only terminal guard, safe while Registry.LOCK held.

    Never calls a Registry/Bridge method or replays the journal. The trusted
    operator/parser, native tool observations and filesystem writer are the
    operational boundary; hashes do not authenticate a remote issuer.
    """
    attempt = record["attempt_id"]
    admission = _canonical_document(store, _ADMISSION + attempt + ".json")
    if (type(admission) is not dict or set(admission) != {"schema_version", "payload", "deployment", "cloud_input_path"}
            or type(admission["schema_version"]) is not int or admission["schema_version"] != 1
            or admission["cloud_input_path"] != "_collection_task_input.py"):
        _fail("Original certification admission is required for lifecycle transitions")
    payload, deployment = admission["payload"], admission["deployment"]
    plan = context(payload)
    identity = payload["identity"]
    if (payload["plan"] != package["plan"] or identity["attempt_id"] != attempt or identity["config_id"] != record["config_id"]
            or record["stage"] != "research" or record["operation_key"] != "certification-plan:" + plan.hash + ":research"):
        _fail("Certification Registry transition belongs to another admission")
    version, _ = parse_manifest(payload.get("deployment_manifest"))
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode("utf-8")) + "\n"
    if (version != 2 or content_hash(payload["deployment_manifest"]) != identity["deployment_hash"]
            or deployment != {"source_manifest_hash": identity["source_manifest_hash"], "deployment_hash": identity["deployment_hash"],
                              "input_hash": sha256(text.encode()).hexdigest()}):
        _fail("Original certification input bytes or deployment changed")
    proof = _native_proof(store, attempt)
    binding = _canonical_document(store, _BINDING + attempt + ".json", proof["binding_sha256"])
    expected_binding = {"schema_version", "protocol", "identity", "deployment", "arguments", "cell_source_sha256", "cell_read_response_sha256"}
    if (type(binding) is not dict or set(binding) != expected_binding or type(binding["schema_version"]) is not int or binding["schema_version"] != 1
            or binding["protocol"] != "certification_native_research_v1" or binding["identity"] != identity or proof["identity"] != identity
            or binding["deployment"] != deployment or not _hash(binding["cell_read_response_sha256"])
            or binding["cell_source_sha256"] != sha256(cell_source(payload, deployment).encode()).hexdigest()
            or type(binding["arguments"]) is not dict or set(binding["arguments"]) != {"projectId", "index"}
            or type(binding["arguments"]["projectId"]) is not int or binding["arguments"]["projectId"] != identity["project_id"]
            or type(binding["arguments"]["index"]) is not int or binding["arguments"]["index"] < 0):
        _fail("Original source/cell-bound certification dispatch is required")
    external = "qc-research:" + str(identity["project_id"]) + ":" + attempt
    saved = _canonical_document(store, "engineering/submissions/" + attempt + ".json")
    expected_saved = {"external_id", "identity", "deployment", "receipt_ref", "identity_kind"}
    if (type(saved) is not dict or set(saved) != expected_saved or saved["identity"] != identity or saved["deployment"] != deployment
            or saved["external_id"] != external or saved["identity_kind"] != "logical_research_execution_receipt"
            or saved["receipt_ref"] != {"key": "engineering/evidence/" + attempt + "/submission/" + proof["submission_sha256"] + ".json", "sha256": proof["submission_sha256"]}):
        _fail("Certification accepted pointer differs from the original native receipt")
    submission = _canonical_document(store, saved["receipt_ref"]["key"], proof["submission_sha256"])
    if (type(submission) is not dict or set(submission) != {"identity", "identity_kind", "external_id", "accepted", "status", "deployment", "raw_receipt"}
            or submission["identity"] != identity or submission["identity_kind"] != saved["identity_kind"] or submission["external_id"] != external
            or submission["deployment"] != deployment or submission["accepted"] is not True or submission["status"] != "submitted"):
        _fail("Only the matching native certification submission may transition")
    raw = submission["raw_receipt"]
    if (type(raw) is not dict or raw.get("tool_name") != "mcp__quantconnect__jupyter_execute_cell"
            or raw.get("arguments") != binding["arguments"] or raw.get("response_sha256") != proof["native_result_sha256"]):
        _fail("Certification native tool receipt is not bound to its original dispatch")
    fields = fields or {}
    if kind == "pending":
        if fields.get("external_id") != external or fields.get("details") != saved:
            _fail("Certification pending state requires its exact native accepted pointer")
        return
    ref = (result.get("platform_evidence_ref") if kind == "completed" and type(result) is dict else
           fields.get("error", {}).get("evidence_ref") if type(fields.get("error")) is dict else None)
    expected_ref = {"key": "engineering/evidence/" + attempt + "/completion/" + proof["completion_sha256"] + ".json", "sha256": proof["completion_sha256"]}
    if ref != expected_ref:
        _fail("Certification terminal state requires its original native completion evidence")
    completion = _canonical_document(store, ref["key"], ref["sha256"])
    if content_hash({"submission": submission, "completion": completion}) != proof["parsed_observation_sha256"]:
        _fail("Certification parsed native observation changed")
    platform = completion.get("platform") if type(completion) is dict else None
    if (type(platform) is not dict or set(platform) != {"identity", "status", "terminal", "deployment", "raw_receipt"}
            or platform["identity"] != dict(identity, external_id=external) or platform["terminal"] is not True
            or platform["deployment"] != deployment or platform["raw_receipt"] != raw):
        _fail("Certification platform metadata differs from the original native execution")
    if kind == "failed":
        if (set(completion) != {"platform"} or platform["status"] != "runtime_error"
                or fields.get("reconciliation") != ref["sha256"]
                or fields.get("error") != {"platform_status": "runtime_error", "evidence_ref": ref}):
            _fail("Certification failure requires its bound native notebook-error receipt")
        return
    if (kind != "completed" or type(result) is not dict or set(result) != {"scope", "identity", "external_id", "cloud_report", "report_ref", "platform_evidence_ref", "financial_evidence"}
            or set(completion) != {"platform", "cloud_report", "report_ref"} or platform["status"] != "completed"
            or result["scope"] != "engineering" or result["identity"] != identity or result["external_id"] != external
            or result["financial_evidence"] is not False or result["cloud_report"] != completion["cloud_report"]
            or result["report_ref"] != completion["report_ref"] or fields.get("external_id", external) != external):
        _fail("Certification result must be the exact parsed native diagnostic metadata")
    validate_report(completion["cloud_report"], plan, identity)
    validate_observation_binding(completion["cloud_report"]["evidence"], payload["deployment_manifest"], identity["deployment_hash"])
    if result["report_ref"] != {"key": payload["report_key"], "sha256": content_hash(result["cloud_report"])}:
        _fail("Certification result reference changed")
