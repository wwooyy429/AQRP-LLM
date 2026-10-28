"""Budgeted, metadata-only bridge for a fixed QC engineering fixture.

This does not open the production research controller. Trusted adapters observe
actual platform receipts; a trusted completion source reads delivered terminal
results and the cloud report. Their provenance is an operational trust boundary,
not a cryptographic signature. LLM output is never a completion source.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re

from .artifacts import canonical_json, content_hash, validate_key
from .contracts import DataRequest, aware
from .registry import Attempt
from .workflow import SubmissionRejected
from .deployment_sources import parse_manifest
from .deployment_observation import validate_deployment_observation, validate_observation_binding


class EngineeringTaskError(ValueError):
    """An engineering plan, receipt, or transition is not admissible."""


def submission_protocol(payload, deployment):
    """Pin the pre-dispatch accepted-publication ordering for new LEAN jobs."""
    return {"schema_version": 1, "protocol": "accepted_identity_before_original_receipt_v1",
            "identity": payload["identity"], "deployment": deployment}


def _hash(value, name):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise EngineeringTaskError(name + " requires a canonical SHA-256")
    return value


def _mapping(value, name):
    if not isinstance(value, dict):
        raise EngineeringTaskError(name + " must be a JSON object")
    return value


def _string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise EngineeringTaskError(name + " must be a nonempty string")
    return value


def _time(value):
    stamp = aware(value)
    if stamp is None or str(stamp) == "NaT":
        raise EngineeringTaskError("Missing time is prohibited")
    return stamp


_IDENTITY_FIELDS = {"plan_hash", "config_id", "attempt_id", "stage", "project_id",
                    "source_manifest_hash", "deployment_hash", "data_request_hash"}
_FLAGS = {"market_values_exported", "economic_factor_tested", "final_data_accessed",
          "full_US200_coverage_certified", "actual_availability_verified"}
JOINT_PROBE_FIELDS = {"dollar_volume", "has_fundamental_data", "time", "end_time"}
JOINT_PROBE_CHECKS = {"collection_windows_completed", "collection_cache_only_replay", "collection_nonempty"}
_PROBE_FLAGS = {"full_historical_US200_certified", "actual_availability_certified",
                "research_certified", "row_values_exported", "financial_vintage_certified"}
_COUNT_FIELDS = {
    "research": {"record_count", "history_calls_first", "history_calls_second", "expected_formation_count"},
    "lean": {"data_event_count", "slice_count", "orders_submitted", "runtime_error_count",
             "dividend_event_count", "split_event_count", "delisting_event_count", "mapping_event_count"},
}
_RAW_ROW_KEYS = {"rows", "row", "values", "value", "panel", "panels", "dataframe", "dataframes",
                 "data", "records", "record", "prices", "price", "bars", "bar", "trades", "trade",
                 "holdings", "positions", "orders", "equitycurve", "charts", "statistics", "performance",
                 "returns", "labels", "targets", "output", "outputs", "stdout", "stderr"}


def _safe_raw_metadata(raw, *, depth=0, text_list=False):
    """Reject row containers before any receipt bytes can reach local storage.

    Native tool metadata may have differing keys. Only bounded scalar metadata,
    objects and explicit error/warning text lists are accepted. This cannot
    certify absence of arbitrarily encoded information in a trusted tool string.
    """
    if depth > 8:
        raise EngineeringTaskError("Platform metadata nesting exceeds the fixed boundary")
    if isinstance(raw, dict):
        if len(raw) > 128:
            raise EngineeringTaskError("Platform metadata object is too large")
        for key, value in raw.items():
            if not isinstance(key, str) or len(key) > 256:
                raise EngineeringTaskError("Platform metadata keys must be bounded strings")
            normalized = key.lower().replace("_", "").replace("-", "").replace(" ", "")
            if normalized in _RAW_ROW_KEYS:
                raise EngineeringTaskError("Row-level data and market outputs cannot enter local receipts: " + key)
            _safe_raw_metadata(value, depth=depth + 1, text_list=text_list or normalized in {"errors", "warnings"})
    elif isinstance(raw, list):
        if not text_list or len(raw) > 32 or any(not isinstance(item, str) or len(item) > 4096 for item in raw):
            raise EngineeringTaskError("Only bounded platform error/warning text lists are metadata")
    elif isinstance(raw, str):
        if len(raw) > 4096:
            raise EngineeringTaskError("Platform metadata strings must be bounded")
    elif raw is None or type(raw) in {bool, int}:
        return
    elif type(raw) is float and math.isfinite(raw):
        return
    else:
        raise EngineeringTaskError("Unsupported platform metadata value")


def _safe_reference(raw):
    raw = _mapping(raw, "content-addressed cloud reference")
    if set(raw) != {"key", "sha256"}:
        raise EngineeringTaskError("Cloud evidence references contain only key and sha256")
    validate_key(raw["key"])
    _hash(raw["sha256"], "cloud reference sha256")


def _safe_identity(raw, *, external=False):
    raw = _mapping(raw, "engineering identity")
    if set(raw) != _IDENTITY_FIELDS | ({"external_id"} if external else set()):
        raise EngineeringTaskError("Unknown engineering identity fields cannot carry output data")
    for name in ("plan_hash", "config_id", "source_manifest_hash", "deployment_hash", "data_request_hash"):
        _hash(raw[name], name)
    if (not isinstance(raw["attempt_id"], str) or re.fullmatch("[0-9a-f]{32}", raw["attempt_id"]) is None
            or type(raw["project_id"]) is not int or raw["project_id"] <= 0 or raw["stage"] not in _COUNT_FIELDS):
        raise EngineeringTaskError("Invalid fixed engineering identity metadata")
    if external:
        value = _string(raw["external_id"], "external identity")
        if len(value) > 256 or "\n" in value or "\r" in value:
            raise EngineeringTaskError("External identity is not bounded platform metadata")


def _safe_evidence(raw):
    raw = _mapping(raw, "engineering evidence metadata")
    allowed = {"coverage_report_ref", "cache_payload_refs", "coverage_certification_gaps",
               "lean_engine_version", "vendor_revision_known", "received_bar_ref", "corporate_action_ref",
               "unobserved_action_types_are_not_certified", "runtime_environment", "collection_probe",
               "deployment_verification", "storage_preflight", "collection_storage", "receiver_storage"}
    if not set(raw) <= allowed:
        raise EngineeringTaskError("Unknown engineering evidence cannot carry row-level data")
    for name, value in raw.items():
        if name in {"storage_preflight", "collection_storage", "receiver_storage"}:
            from .engineering_storage import (validate_capacity_observation,
                validate_collection_evidence, validate_encoding_metadata)
            {"storage_preflight": validate_capacity_observation,
             "collection_storage": validate_collection_evidence,
             "receiver_storage": validate_encoding_metadata}[name](value)
        elif name == "deployment_verification":
            try:
                validate_deployment_observation(value)
            except ValueError:
                raise EngineeringTaskError("Invalid deployment verification evidence") from None
        elif name == "collection_probe":
            _safe_collection_probe(value)
        elif name.endswith("_ref"):
            _safe_reference(value)
        elif name == "cache_payload_refs":
            if not isinstance(value, list) or len(value) > 5:
                raise EngineeringTaskError("Only bounded cloud cache references may leave cloud")
            for reference in value:
                _safe_reference(reference)
        elif name == "coverage_certification_gaps":
            from .coverage import RESEARCH_GAPS
            if value != list(RESEARCH_GAPS):
                raise EngineeringTaskError("Coverage gaps must be the fixed program observations")
        elif name == "lean_engine_version":
            if not isinstance(value, str) or not value or len(value) > 100 or "\n" in value or "\r" in value:
                raise EngineeringTaskError("Invalid engine version metadata")
        elif name == "runtime_environment":
            if (not isinstance(value, dict) or set(value) != {"python", "pandas", "numpy", "lean"}
                    or any(not isinstance(version, str) or not version or len(version) > 100 or "\n" in version or "\r" in version for version in value.values())):
                raise EngineeringTaskError("Runtime environment contains version strings only")
        elif name == "vendor_revision_known" and value is not False:
            raise EngineeringTaskError("The historical vendor revision is not certified")
        elif name == "unobserved_action_types_are_not_certified" and value is not True:
            raise EngineeringTaskError("Unobserved corporate-action types remain uncertified")


def _safe_collection_probe(raw):
    """Only fixed aggregate observations and one cloud reference may leave QC."""
    required = {"schema_version", "plan_hash", "receipt_ref", "window_count", "record_count",
                "source_fetch_calls", "reused_windows", "empty_windows", "cache_only_source_fetch_calls",
                "missing_values"} | _PROBE_FLAGS
    version = raw.get("schema_version") if isinstance(raw, dict) else None
    occurrence_counts = {"duplicate_projection_records", "conflicting_projection_records"}
    if type(version) is int and version == 2:
        required |= occurrence_counts | {"observation_policy"}
    if not isinstance(raw, dict) or set(raw) != required or type(version) is not int or version not in {1, 2}:
        raise EngineeringTaskError("Only the fixed joint collection observation summary is permitted")
    if version == 2 and (raw["observation_policy"] != "retain_source_occurrences"
            or any(type(raw[name]) is not int or not 0 <= raw[name] <= 2000000 for name in occurrence_counts)):
        raise EngineeringTaskError("Occurrence collection requires its fixed policy and bounded counts")
    _hash(raw["plan_hash"], "collection probe plan hash")
    _safe_reference(raw["receipt_ref"])
    if any(raw[name] is not False for name in _PROBE_FLAGS):
        raise EngineeringTaskError("Collection observation cannot certify financial or availability history")
    for name in ("window_count", "record_count", "source_fetch_calls", "reused_windows", "empty_windows", "cache_only_source_fetch_calls"):
        maximum = 2000000 if name == "record_count" else 40
        if type(raw[name]) is not int or not 0 <= raw[name] <= maximum:
            raise EngineeringTaskError("Collection observation counts exceed the fixed pilot bounds")
    missing = raw["missing_values"]
    if (not isinstance(missing, dict) or set(missing) != JOINT_PROBE_FIELDS
            or any(type(value) is not int or not 0 <= value <= raw["record_count"] for value in missing.values())):
        raise EngineeringTaskError("Only selected-field missing counts may leave the collection pilot")
    if (raw["window_count"] != 40 or raw["source_fetch_calls"] + raw["reused_windows"] != 40
            or raw["empty_windows"] > raw["window_count"] or raw["cache_only_source_fetch_calls"] != 0
            or not raw["window_count"] - raw["empty_windows"] <= raw["record_count"] <= (raw["window_count"] - raw["empty_windows"]) * 50000):
        raise EngineeringTaskError("Collection observation does not prove complete cache-only replay")
    if version == 2 and not (0 <= raw["conflicting_projection_records"] <= raw["duplicate_projection_records"]
            <= raw["record_count"] - (raw["window_count"] - raw["empty_windows"])):
        raise EngineeringTaskError("Occurrence ambiguity counts disagree with the observed record count")


def validate_joint_report(report, document):
    """Bind the optional summary to this exact parent; v1 stays unchanged."""
    if "deployment_verification" in report.get("evidence", {}):
        try:
            validate_deployment_observation(report["evidence"]["deployment_verification"],
                                           deployment_hash=document["deployment_hash"])
        except ValueError:
            raise EngineeringTaskError("Deployment evidence differs from the frozen plan") from None
    summary = report.get("evidence", {}).get("collection_probe")
    applicable = document["schema_version"] in {2, 3, 4} and report["identity"]["stage"] == "research"
    storage = report.get("evidence", {})
    storage_keys = {"storage_preflight", "collection_storage", "receiver_storage"}
    if document["schema_version"] not in {3, 4} and storage_keys & set(storage):
        raise EngineeringTaskError("Storage evidence requires an explicit storage-policy plan")
    if document["schema_version"] in {3, 4} and report["status"] == "completed":
        from .engineering_storage import validate_capacity_observation, validate_collection_evidence
        capacity = storage.get("storage_preflight")
        validate_capacity_observation(capacity)
        if any(capacity[k] != v for k, v in document["storage_policy"]["capacity"][report["identity"]["stage"]].items()):
            raise EngineeringTaskError("Capacity observation differs from the frozen reservation")
        if report["identity"]["stage"] == "research":
            reuse = storage.get("collection_storage")
            validate_collection_evidence(reuse)
            policy = document["storage_policy"]["collection_cache"]
            if (reuse["mode"] != "verified_legacy" or reuse["origin_receipt_ref"] != policy["legacy"]["receipt_ref"]
                    or reuse["storage_plan_hash"] != policy["legacy"]["plan_hash"]
                    or reuse["verified_window_count"] != 40 or reuse["provider_calls"] != 0
                    or "receiver_storage" in storage):
                raise EngineeringTaskError("Cache reuse differs from its frozen legacy origin")
        else:
            if "receiver_storage" not in storage or "collection_storage" in storage:
                raise EngineeringTaskError("Completed receiver requires its bounded encoding evidence")
            encoded = storage["receiver_storage"]
            reference = storage.get("received_bar_ref")
            if document["schema_version"] == 4:
                from .engineering_storage import validate_reference_metadata
                validate_reference_metadata(encoded)
                digest, extension = encoded["manifest_sha256"], ".json"
                if encoded["record_count"] != report["statistics"]["data_event_count"] * len(document["request_template"]["fields"]):
                    raise EngineeringTaskError("Receiver reference count differs from actual received events")
            else:
                if encoded.get("encoding") != "zlib_json_v1":
                    raise EngineeringTaskError("Retired encoding metadata differs")
                digest, extension = encoded["stored_sha256"], ".zlib"
            expected = (document["report_namespace"] + "/received/" + report["identity"]["attempt_id"]
                        + "/" + digest + extension)
            if reference != {"key": expected, "sha256": digest}:
                raise EngineeringTaskError("Receiver evidence differs from its actual payload reference")
    if not applicable:
        if summary is not None:
            raise EngineeringTaskError("Collection probe metadata belongs only to v2 Research")
        return
    if summary is None:
        if report["status"] == "completed":
            raise EngineeringTaskError("Completed joint Research requires its collection observation")
        return
    _safe_collection_probe(summary)
    from .collection import HistoricalCollectionPlan
    probe = document["collection_probe"]
    plan = HistoricalCollectionPlan.from_dict(probe["collection_plan"], field_catalog=probe["field_catalog"])
    expected_key = document["report_namespace"] + "/collection-probes/" + content_hash(document) + "/" + report["identity"]["attempt_id"] + ".json"
    if (summary["plan_hash"] != plan.hash or summary["receipt_ref"]["key"] != expected_key
            or summary["schema_version"] != plan.to_dict()["schema_version"]):
        raise EngineeringTaskError("Collection observation differs from this parent's frozen probe")
    if document["schema_version"] in {3, 4}:
        from .collection_storage import data_identity
        reuse = storage["collection_storage"]
        policy = document["storage_policy"]["collection_cache"]
        if (reuse["requested_plan_hash"] != plan.hash
                or reuse["data_identity_hash"] != content_hash(data_identity(plan, policy["processing_contract_sha256"]))
                or summary["source_fetch_calls"] != reuse["provider_calls"]
                or summary["reused_windows"] != reuse["reused_windows"]
                or report["statistics"]["history_calls_first"] != 0
                or report["statistics"]["history_calls_second"] != 0):
            raise EngineeringTaskError("Cache evidence differs from the frozen cache-only request")
    checks = report["checks"]
    if (not JOINT_PROBE_CHECKS <= set(checks)
            or checks["collection_windows_completed"] != (summary["window_count"] == 40)
            or checks["collection_cache_only_replay"] != (summary["cache_only_source_fetch_calls"] == 0)
            or checks["collection_nonempty"] != (summary["record_count"] > 0)):
        raise EngineeringTaskError("Collection checks disagree with the actual bounded observation")


@dataclass(frozen=True, init=False)
class EngineeringTaskPlan:
    """A canonical, fixed two-stock 2018 data-plumbing plan, not a factor.

    ``discovered_project_ids`` is supplied by the trusted platform dispatcher
    after list_projects, never extracted from the candidate document itself.
    The deployment/source hashes exclude per-attempt generated input, whose
    separately observed hash is bound by each submission and completion receipt.
    """
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use EngineeringTaskPlan.from_dict with trusted discovered project IDs")

    @classmethod
    def from_dict(cls, raw, *, discovered_project_ids, probe_field_catalog=None):
        value = _mapping(json.loads(canonical_json(raw)), "engineering plan")
        required = {"schema_version", "plan_id", "scope", "project_id", "source_manifest_hash",
                    "deployment_hash", "request_mode", "observation_window", "required_checks",
                    "max_retries", "report_namespace", "orders_enabled", "financial_metrics_enabled",
                    "economic_factor", "economic_model"}
        mode = value.get("request_mode")
        mode_keys = {"request_template", "symbol_resolution"} if mode == "symbol_resolution" else {"data_request"}
        version = value.get("schema_version")
        extra = {"collection_probe"} if type(version) is int and version in {2, 3, 4} else set()
        if type(version) is int and version in {3, 4}:
            extra.add("storage_policy")
        if set(value) != required | mode_keys | extra or type(version) is not int or version not in {1, 2, 3, 4}:
            raise EngineeringTaskError("A complete versioned engineering plan is required; unknown overrides are prohibited")
        if value["scope"] != "engineering" or value["orders_enabled"] is not False or value["financial_metrics_enabled"] is not False:
            raise EngineeringTaskError("This bridge permits engineering without orders or financial metrics only")
        if value["economic_factor"] is not None or value["economic_model"] is not None:
            raise EngineeringTaskError("Economic factors and models cannot enter this bridge")
        _string(value["plan_id"], "plan_id")
        project = value["project_id"]
        ids = tuple(discovered_project_ids)
        if type(project) is not int or project <= 0 or any(type(i) is not int for i in ids) or project not in ids:
            raise EngineeringTaskError("Use a project returned by the trusted list_projects call")
        for key in ("source_manifest_hash", "deployment_hash"):
            _hash(value[key], key)
        if version in {2, 3, 4}:
            if mode != "symbol_resolution":
                raise EngineeringTaskError("Joint pilot requires the fixed historical two-symbol resolver")
            from .collection import HistoricalCollectionPlan
            probe = value["collection_probe"]
            if not isinstance(probe, dict) or set(probe) != {"collection_plan", "field_catalog"}:
                raise EngineeringTaskError("Joint engineering requires one explicit bounded collection probe")
            catalog = probe["field_catalog"]
            if not isinstance(catalog, dict) or set(catalog) != JOINT_PROBE_FIELDS:
                raise EngineeringTaskError("Joint pilot permits only its four observed liquidity/clock fields")
            if probe_field_catalog is not None and catalog != {name: probe_field_catalog.get(name) for name in JOINT_PROBE_FIELDS}:
                raise EngineeringTaskError("Joint probe catalog differs from the trusted source catalog")
            child = HistoricalCollectionPlan.from_dict(probe["collection_plan"], field_catalog=catalog)
            cp = child.to_dict()
            if (cp["source_manifest_hash"] != value["source_manifest_hash"] or set(cp["fields"]) != JOINT_PROBE_FIELDS
                    or _time(cp["start"]) != _time("2018-01-01T00:00:00-05:00")
                    or _time(cp["end_exclusive"]) != _time("2018-02-10T00:00:00-05:00")
                    or cp["calendar_days_per_request"] != 1 or cp["max_batch_records"] != 1000
                    or cp["max_records_per_window"] != 50000):
                raise EngineeringTaskError("Joint collection probe must match the frozen 40-day development pilot")
            value["collection_probe"] = {"collection_plan": cp, "field_catalog": child.field_catalog}
            if version in {3, 4}:
                from .engineering_storage import validate_storage_policy
                validate_storage_policy(value["storage_policy"], child, plan_version=version)
        validate_key(value["report_namespace"])
        if mode == "symbol_resolution":
            template = _mapping(value["request_template"], "request_template")
            expected = {"dataset", "fields", "start", "end", "data_version", "universe_hash", "normalization", "timezone"}
            if set(template) != expected:
                raise EngineeringTaskError("Declare the complete SID-free request template")
            resolver = _mapping(value["symbol_resolution"], "symbol_resolution")
            if set(resolver) != {"tickers", "as_of", "method"} or resolver["tickers"] != ["AAPL", "MSFT"]:
                raise EngineeringTaskError("Only the fixed AAPL/MSFT engineering resolution fixture is supported")
            if resolver["method"] != "QuantBook.add_equity/as-of fixed fixture":
                raise EngineeringTaskError("An explicit historical fixture resolver is required")
            # Validate dates/fields without pretending these sentinels are real SIDs.
            request = DataRequest(**dict(template, fields=tuple(template["fields"]), sids=("template-only-A", "template-only-B")))
            if _time(resolver["as_of"]) != _time(request.end):
                raise EngineeringTaskError("The fixed fixture resolution frontier must equal the history end")
        elif mode == "resolved":
            request = DataRequest(**value["data_request"])
            if len(request.sids) != 2:
                raise EngineeringTaskError("Only two pre-resolved permanent SIDs are supported")
            value["data_request"] = request.identity()
        else:
            raise EngineeringTaskError("Unknown request resolution mode")
        if (request.dataset not in {"US Equities", "us_equity_daily"} or request.normalization != "raw"
                or not set(request.fields) <= {"open", "high", "low", "close", "volume"}):
            raise EngineeringTaskError("Only declared raw daily OHLCV is permitted")
        _hash(request.universe_hash, "fixture universe_hash")
        if (request.start != _time("2018-01-01T00:00:00-05:00")
                or request.end != _time("2019-01-01T00:00:00-05:00")):
            raise EngineeringTaskError("Declare the actual full-year 2018 cache fetch, not just the observation window")
        window = _mapping(value["observation_window"], "observation_window")
        if set(window) != {"start", "end_exclusive"}:
            raise EngineeringTaskError("Explicit observation bounds are required")
        start, end = _time(window["start"]), _time(window["end_exclusive"])
        if not _time(request.start) <= start < end <= _time(request.end):
            raise EngineeringTaskError("Observation dates must lie inside the fixed 2018 history request")
        value["observation_window"] = {"start": start.isoformat(), "end_exclusive": end.isoformat()}
        for key in ("required_checks", "max_retries"):
            if set(_mapping(value[key], key)) != {"research", "lean"}:
                raise EngineeringTaskError("Both engineering stages must be explicitly bounded")
        for stage in ("research", "lean"):
            checks = value["required_checks"][stage]
            if (not isinstance(checks, list) or not checks
                    or any(not isinstance(x, str) or re.fullmatch("[a-z][a-z0-9_]*", x) is None for x in checks)
                    or len(set(checks)) != len(checks)):
                raise EngineeringTaskError("Named unique required checks are required")
            retries = value["max_retries"][stage]
            if type(retries) is not int or not 0 <= retries <= 2:
                raise EngineeringTaskError("Retries must be preregistered and bounded from zero through two")
        if version in {2, 3, 4} and not JOINT_PROBE_CHECKS <= set(value["required_checks"]["research"]):
            raise EngineeringTaskError("Joint Research must require the complete bounded collection observation")
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json(value))
        return result

    def to_dict(self):
        return json.loads(self._encoded)

    @property
    def hash(self):
        return content_hash(self.to_dict())

    configuration_hash = hash

    @property
    def request_hash(self):
        value = self.to_dict()
        request = ({"request_template": value["request_template"], "symbol_resolution": value["symbol_resolution"]}
                   if value["request_mode"] == "symbol_resolution" else value["data_request"])
        if value["schema_version"] in {2, 3, 4}:
            request = {"market_request": request, "collection_probe": value["collection_probe"]}
        return content_hash(request)


class EngineeringTaskBridge:
    """One authoritative Registry; no second budget counter or polling loop.

    Registry enforces the shared engineering-round stop atomically with every
    new configuration/attempt debit, including direct Bridge and Registry use.

    ``adapter`` implements submit_research/submit_backtest(payload,
    operation_key=...). ``completion_source(payload)`` is trusted program I/O,
    returning platform terminal metadata plus the cloud metadata report and its
    immutable reference. It must observe actual tool results, not LLM approvals.
    Direct free dictionaries cannot be passed to consume_completion.
    """
    def __init__(self, registry, plan, *, adapter=None, completion_source=None):
        if not isinstance(plan, EngineeringTaskPlan):
            raise TypeError("A validated EngineeringTaskPlan is required")
        self.registry, self.store, self.plan = registry, registry.store, plan
        self.adapter, self.completion_source = adapter, completion_source
        self.package = {"engineering_task_schema_version": 1, "plan": plan.to_dict()}
        self.config_id = content_hash(self.package)

    def register(self, *, allocation="normal"):
        return self.registry.register_config(self.package, allocation=allocation)

    def _operation(self, stage):
        if stage not in {"research", "lean"}:
            raise EngineeringTaskError("Only engineering research/lean stages are permitted")
        return "engineering-plan:" + self.plan.hash + ":" + stage

    def _records(self):
        return self.registry.snapshot()["attempts"]

    def _record(self, attempt):
        identity = attempt.attempt_id if isinstance(attempt, Attempt) else attempt
        matches = [x for x in self._records() if x["attempt_id"] == identity]
        if (len(matches) != 1 or matches[0]["config_id"] != self.config_id
                or matches[0]["operation_key"] != self._operation(matches[0]["stage"])):
            raise EngineeringTaskError("Attempt does not belong to this exact registered task plan")
        return matches[0]

    @staticmethod
    def _attempt(record):
        return Attempt(**{key: record.get(key) for key in ("attempt_id", "config_id", "stage", "operation_key",
                       "status", "allocation", "result_key", "external_id")}, should_execute=False)

    def _research_result(self):
        records = [x for x in self._records() if x["config_id"] == self.config_id and x["stage"] == "research"]
        if not records or records[-1]["status"] != "completed":
            raise EngineeringTaskError("LEAN requires the verified completed Research resolution first")
        return self.registry.read_result(records[-1]["attempt_id"])

    def claim(self, stage, *, allocation="normal", retry_of=None, reason=None):
        operation = self._operation(stage)
        document = self.plan.to_dict()
        if stage == "lean":
            self._research_result()
        with self.store.locked("engineering/project-claim/" + str(document["project_id"])):
            records = self._records()
            for record in records:
                if record["status"] not in {"started", "pending", "ambiguous"}:
                    continue
                package = json.loads(self.store.read_bytes("configurations/" + record["config_id"] + ".json"))
                if (package.get("engineering_task_schema_version") == 1
                        and package["plan"]["project_id"] == document["project_id"]
                        and record["config_id"] != self.config_id):
                    raise EngineeringTaskError("Unresolved engineering work on this project must be reconciled before another plan")
            previous = [x for x in records if x["config_id"] == self.config_id and x["stage"] == stage]
            if retry_of is not None and len(previous) >= 1 + document["max_retries"][stage]:
                raise EngineeringTaskError("Preregistered retry bound reached")
            return self.registry.begin_attempt(self.config_id, stage, allocation=allocation,
                       operation_key=operation, retry_of=retry_of, reason=reason)

    def payload(self, attempt):
        record = self._record(attempt)
        document = self.plan.to_dict()
        identity = {"plan_hash": self.plan.hash, "config_id": self.config_id,
                    "attempt_id": record["attempt_id"], "stage": record["stage"],
                    "project_id": document["project_id"], "source_manifest_hash": document["source_manifest_hash"],
                    "deployment_hash": document["deployment_hash"], "data_request_hash": self.plan.request_hash}
        payload = {"plan": document, "identity": identity,
                   "report_key": document["report_namespace"] + "/reports/" + self.plan.hash + "/" + record["stage"] + "/" + record["attempt_id"] + ".json",
                   "external_identity_kind": "logical_research_execution_receipt" if record["stage"] == "research" else "quantconnect_backtest_id"}
        if record["stage"] == "lean":
            payload["research_resolution"] = self._research_result()["cloud_report"].get("resolution")
        return payload

    def _save(self, attempt_id, kind, value):
        encoded = canonical_json(value)
        digest = content_hash(value)
        key = "engineering/evidence/" + attempt_id + "/" + kind + "/" + digest + ".json"
        self.store.write_once(key, encoded)
        return {"key": key, "sha256": digest}

    def _submission_key(self, attempt_id):
        return "engineering/submissions/" + attempt_id + ".json"

    def _recorded_submission(self, payload):
        """Read and validate the original checked submission, without a lock.

        Both live settlement and dependency admission use this exact loader.
        It reads immutable metadata only; it must not call Registry/payload
        helpers because dependency admission already owns the transaction lock.
        """
        identity = payload["identity"]
        attempt = identity["attempt_id"]
        try:
            encoded = self.store.read_bytes(self._submission_key(attempt))
            submission = json.loads(encoded)
            required = {"external_id", "identity", "deployment", "receipt_ref", "identity_kind"}
            if (canonical_json(submission) != encoded or not isinstance(submission, dict)
                    or set(submission) != required or submission["identity"] != identity
                    or submission["identity_kind"] != payload["external_identity_kind"]):
                raise EngineeringTaskError("Recorded submission differs from the frozen task")
            self._deployment(submission["deployment"])
            external = _string(submission["external_id"], "recorded external identity")
            if len(external) > 256 or "\n" in external or "\r" in external:
                raise EngineeringTaskError("Recorded external identity is invalid")
            if (identity["stage"] == "research" and external !=
                    "qc-research:" + str(identity["project_id"]) + ":" + attempt):
                raise EngineeringTaskError("Recorded Research identity differs from this attempt")
            ref = submission["receipt_ref"]
            _safe_reference(ref)
            expected_key = "engineering/evidence/" + attempt + "/submission/" + ref["sha256"] + ".json"
            if ref["key"] != expected_key:
                raise EngineeringTaskError("Original submission reference differs from this attempt")
            original = self.store.read_bytes(ref["key"])
            receipt = json.loads(original)
            if canonical_json(receipt) != original or content_hash(receipt) != ref["sha256"]:
                raise EngineeringTaskError("Original submission reference bytes changed")
            self._submission_metadata(_mapping(receipt, "original submission observation"))
            if (receipt.get("accepted") is not True or not receipt["raw_receipt"]
                    or any(receipt.get(name) != submission[name] for name in
                           ("identity", "identity_kind", "deployment", "external_id"))):
                raise EngineeringTaskError("Original accepted submission observation is missing or inconsistent")
            if (identity["stage"] == "lean" and (receipt["raw_receipt"].get("success") is not True
                    or receipt["raw_receipt"].get("backtestId") != external)):
                raise EngineeringTaskError("Original LEAN submission is not a backtest acknowledgement")
            return submission
        except (KeyError, TypeError, ValueError, FileNotFoundError) as exc:
            raise EngineeringTaskError("A matching original checked submission is required") from exc

    def _deployment(self, raw):
        raw = _mapping(raw, "deployment observation")
        document = self.plan.to_dict()
        if set(raw) != {"source_manifest_hash", "deployment_hash", "input_hash"}:
            raise EngineeringTaskError("Bind separately verified source deployment and generated input hashes")
        if any(raw[key] != document[key] for key in ("source_manifest_hash", "deployment_hash")):
            raise EngineeringTaskError("Observed source deployment differs from the registered plan")
        _hash(raw["input_hash"], "generated input hash")
        return raw

    def _submission_metadata(self, receipt):
        required = {"identity", "identity_kind", "accepted", "deployment", "raw_receipt"}
        if not required <= set(receipt) or set(receipt) - required - {"external_id", "status"}:
            raise EngineeringTaskError("Unknown submission metadata fields are prohibited")
        _safe_identity(receipt["identity"])
        self._deployment(receipt["deployment"])
        _safe_raw_metadata(_mapping(receipt["raw_receipt"], "platform submission metadata"))
        if type(receipt["accepted"]) is not bool:
            raise EngineeringTaskError("Submission acceptance must be an observed boolean")
        if receipt["identity_kind"] not in {"logical_research_execution_receipt", "quantconnect_backtest_id"}:
            raise EngineeringTaskError("Unknown external identity kind")
        if receipt.get("external_id") is not None:
            external = _string(receipt["external_id"], "external identity")
            if len(external) > 256 or "\n" in external or "\r" in external:
                raise EngineeringTaskError("External identity must be bounded metadata")
        if "status" in receipt and receipt["status"] not in {"submitted", "pending", "completed", "compiled", "rejected", "failed"}:
            raise EngineeringTaskError("Submission status is not an output-data field")

    def _report_metadata(self, report):
        report = _mapping(report, "cloud engineering report")
        required = {"schema_version", "identity", "status", "terminal", "checks", "statistics"} | _FLAGS
        if not required <= set(report) or set(report) - required - {"resolution", "evidence"}:
            raise EngineeringTaskError("Unknown cloud report fields cannot leave cloud")
        if type(report["schema_version"]) is not int or report["schema_version"] != 1:
            raise EngineeringTaskError("A fixed versioned engineering report is required")
        _safe_identity(report["identity"])
        if report["status"] not in {"completed", "failed"} or report["terminal"] is not True:
            raise EngineeringTaskError("Cloud report is not a terminal engineering observation")
        if any(report[name] is not False for name in _FLAGS):
            raise EngineeringTaskError("Engineering limitations cannot be upgraded by a receipt")
        checks = _mapping(report["checks"], "engineering checks")
        if any(re.fullmatch("[a-z][a-z0-9_]{0,95}", key) is None or type(value) is not bool for key, value in checks.items()):
            raise EngineeringTaskError("Engineering checks contain named boolean observations only")
        statistics = _mapping(report["statistics"], "engineering counts")
        if not set(statistics) <= _COUNT_FIELDS[report["identity"]["stage"]] or any(type(value) is not int or value < 0 for value in statistics.values()):
            raise EngineeringTaskError("Only fixed nonnegative engineering counts may leave cloud")
        self._resolution(report, report["identity"]["stage"])
        _safe_evidence(report.get("evidence", {}))
        validate_joint_report(report, self.plan.to_dict())

    def _completion_metadata(self, observed):
        observed = _mapping(observed, "delivered completion metadata")
        if "platform" not in observed or set(observed) - {"platform", "cloud_report", "report_ref"}:
            raise EngineeringTaskError("Unknown completion fields cannot be stored locally")
        platform = _mapping(observed["platform"], "platform completion metadata")
        if set(platform) != {"identity", "terminal", "status", "deployment", "raw_receipt"}:
            raise EngineeringTaskError("Unknown platform observation fields cannot carry output data")
        _safe_identity(platform["identity"], external=True)
        self._deployment(platform["deployment"])
        if type(platform["terminal"]) is not bool or platform["status"] not in {"completed", "failed", "runtime_error", "compile_error", "compiled", "submitted", "pending"}:
            raise EngineeringTaskError("Invalid platform observation metadata")
        _safe_raw_metadata(_mapping(platform["raw_receipt"], "actual platform terminal metadata"))
        if observed.get("cloud_report") is not None:
            self._report_metadata(observed["cloud_report"])
            _safe_reference(observed.get("report_ref"))
        elif observed.get("report_ref") is not None:
            raise EngineeringTaskError("A report reference without a report is incomplete")

    def record_submission(self, attempt, observed_receipt):
        """Trusted adapter acknowledgement only; even 'completed' means pending.

        For Research there is no native job ID: use the explicit logical receipt
        qc-research:<project>:<attempt>. LEAN must retain its platform backtest ID.
        """
        record, receipt = self._record(attempt), json.loads(canonical_json(observed_receipt))
        payload = self.payload(record["attempt_id"])
        self._submission_metadata(_mapping(receipt, "submission receipt"))
        if receipt.get("identity") != payload["identity"] or receipt.get("identity_kind") != payload["external_identity_kind"]:
            raise EngineeringTaskError("Submission receipt belongs to another source, plan, project or attempt")
        raw = _mapping(receipt.get("raw_receipt"), "actual raw platform receipt")
        if not raw:
            raise EngineeringTaskError("An actual submission observation is required")
        deployment = self._deployment(receipt.get("deployment"))
        if record["stage"] == "lean" and receipt.get("accepted") is False:
            return self.record_rejection(attempt, receipt)
        if receipt.get("accepted") is not True:
            with self.store.locked(self.registry.LOCK):
                reference = self._save(record["attempt_id"], "submission", receipt)
                return self.registry._transition_locked(record["attempt_id"], "failed",
                    error={"reason": "Observed platform rejection", "receipt_ref": reference}, reconciliation=None)
        external_id = _string(receipt.get("external_id"), "observed external identity")
        if record["stage"] == "research" and external_id != "qc-research:" + str(payload["identity"]["project_id"]) + ":" + record["attempt_id"]:
            raise EngineeringTaskError("Research must be labelled as its logical execution receipt, not a fabricated platform job ID")
        if record["stage"] == "lean" and (raw.get("success") is not True or raw.get("backtestId") != external_id):
            raise EngineeringTaskError("A compile receipt is not a backtest submission; retain the actual returned backtestId")
        with self.store.locked(self.registry.LOCK):
            current = self.registry._replay()["attempts"][record["attempt_id"]]
            if current["status"] == "failed":
                raise EngineeringTaskError("A rejected or failed attempt cannot acquire an accepted submission")
            # Publish the canonical accepted identity before its full evidence.
            # A crash then leaves an accepted pointer that blocks rejection;
            # replaying this same receipt repairs the missing original/journal.
            digest = content_hash(receipt)
            reference = {"key": "engineering/evidence/" + record["attempt_id"] + "/submission/" + digest + ".json",
                         "sha256": digest}
            saved = {"external_id": external_id, "identity": payload["identity"], "deployment": deployment,
                      "receipt_ref": reference, "identity_kind": payload["external_identity_kind"]}
            self.store.write_once(self._submission_key(record["attempt_id"]), canonical_json(saved))
            self._save(record["attempt_id"], "submission", receipt)
            if current["status"] == "completed":
                return self._attempt(current)
            if current["status"] == "ambiguous":
                # Preserve ambiguity; an acknowledgement cannot make it pending.
                return self._attempt(current)
            return self.registry._transition_locked(record["attempt_id"], "pending", external_id=external_id, details=saved)

    def record_rejection(self, attempt, observed_receipt):
        """Settle only a definite native compile rejection before acceptance.

        Trusted fixed parsers supply metadata, never a free LLM failure flag.
        The same Registry transaction serializes accepted-pointer publication,
        rejection evidence and transition. No nested Registry reader is called
        while that lock is owned. Counters and retry policy remain unchanged.
        """
        record = self._record(attempt)
        payload = self.payload(record["attempt_id"])
        receipt = json.loads(canonical_json(observed_receipt))
        self._submission_metadata(_mapping(receipt, "native rejection receipt"))
        if (record["stage"] != "lean" or set(receipt) !=
                {"identity", "identity_kind", "accepted", "status", "deployment", "raw_receipt"}
                or receipt["identity"] != payload["identity"]
                or receipt["identity_kind"] != "quantconnect_backtest_id"
                or receipt["accepted"] is not False or receipt["status"] != "rejected"):
            raise EngineeringTaskError("A native rejection must identify this exact unaccepted LEAN attempt")
        raw = receipt["raw_receipt"]
        keys = {"tool_name", "response_sha256", "arguments_sha256", "success", "rejected", "error_format",
                "error_count", "error_file_count", "warning_count", "settlement_eligible"}
        if (set(raw) != keys or raw["tool_name"] != "mcp__quantconnect__create_backtest"
                or raw["success"] is not False or raw["rejected"] is not True
                or raw["settlement_eligible"] is not True or raw["error_format"] != "file_map"
                or any(type(raw[name]) is not int for name in ("error_count", "error_file_count", "warning_count"))
                or not 1 <= raw["error_file_count"] <= raw["error_count"] or raw["warning_count"] < 0):
            raise EngineeringTaskError("Unclassified native errors cannot settle an uncertain submission")
        _hash(raw["response_sha256"], "native rejection response")
        _hash(raw["arguments_sha256"], "native rejection arguments")
        try:
            protocol = self.store.read_bytes("engineering/submission-protocol/" + record["attempt_id"] + ".json")
            if protocol != canonical_json(submission_protocol(payload, receipt["deployment"])):
                raise EngineeringTaskError("Native rejection requires the exact pre-dispatch submission protocol")
            encoded = self.store.read_bytes("engineering/admitted-inputs/" + record["attempt_id"] + ".json")
            admission = json.loads(encoded)
            admitted_payload = admission["payload"]
            manifest = admitted_payload["deployment_manifest"]
            text = "TASK_INPUT_JSON = " + repr(canonical_json(admitted_payload).decode("utf-8")) + "\n"
            if (canonical_json(admission) != encoded
                    or set(admission) != {"payload", "deployment", "input_path", "cloud_input_path"}
                    or admission["input_path"] != "audit/task_inputs/" + record["attempt_id"] + ".py"
                    or admission["cloud_input_path"] != "_engineering_task_input.py"
                    or admitted_payload != dict(payload, deployment_manifest=manifest)
                    or not isinstance(manifest, dict) or not manifest
                    or content_hash(manifest) != payload["identity"]["deployment_hash"]
                    or admission["deployment"] != receipt["deployment"]
                    or sha256(text.encode("utf-8")).hexdigest() != receipt["deployment"]["input_hash"]):
                raise EngineeringTaskError("Native rejection differs from the original admitted input")
            parse_manifest(manifest)
        except (KeyError, TypeError, ValueError, FileNotFoundError) as exc:
            raise EngineeringTaskError("A rejection requires canonical original admitted-input evidence") from exc
        digest = content_hash(receipt)
        reference = {"key": "engineering/evidence/" + record["attempt_id"] + "/rejection/" + digest + ".json", "sha256": digest}
        error = {"reason": "Observed native compile rejection", "receipt_ref": reference}
        with self.store.locked(self.registry.LOCK):
            current = self.registry._replay()["attempts"][record["attempt_id"]]
            if (current["config_id"] != self.config_id or current["stage"] != "lean"
                    or current["operation_key"] != self._operation("lean")
                    or current.get("external_id") is not None or self.store.exists(self._submission_key(record["attempt_id"]))):
                raise EngineeringTaskError("Accepted submission identities cannot be overwritten by a rejection")
            if current["status"] == "failed":
                try:
                    same_original = self.store.read_bytes(reference["key"]) == canonical_json(receipt)
                except FileNotFoundError:
                    same_original = False
                if (current.get("error") != error or current.get("reconciliation") != digest or not same_original):
                    raise EngineeringTaskError("Only the identical recorded rejection may be read idempotently")
                return self._attempt(current)
            if current["status"] not in {"started", "ambiguous"}:
                raise EngineeringTaskError("Only an unresolved unaccepted submission can settle a rejection")
            self._save(record["attempt_id"], "rejection", receipt)
            return self.registry._transition_locked(record["attempt_id"], "failed", error=error, reconciliation=digest)

    def submit(self, stage, *, allocation="normal", retry_of=None, reason=None):
        callback = getattr(self.adapter, "submit_research" if stage == "research" else "submit_backtest", None)
        if not callable(callback):
            raise EngineeringTaskError("A trusted platform adapter is required before claiming budget")
        attempt = self.claim(stage, allocation=allocation, retry_of=retry_of, reason=reason)
        if not attempt.should_execute:
            return attempt
        try:
            receipt = callback(self.payload(attempt), operation_key=attempt.operation_key)
        except SubmissionRejected as exc:
            return self.registry.fail(attempt, str(exc))
        except Exception as exc:
            return self.registry.ambiguous(attempt, reason="Submission outcome unknown: " + type(exc).__name__)
        try:
            return self.record_submission(attempt, receipt)
        except Exception:
            self.registry.ambiguous(attempt, reason="Accepted outcome or identity could not be safely recorded")
            raise

    def _resolution(self, report, stage):
        document = self.plan.to_dict()
        if document["request_mode"] != "symbol_resolution":
            if report.get("resolution") is not None:
                raise EngineeringTaskError("Pre-resolved plans cannot export an unregistered resolution payload")
            return
        resolution = _mapping(report.get("resolution"), "observed SID resolution")
        required = {"resolved_request_hash", "resolved_registry_hash", "resolution_artifact_hash", "tickers", "ticker_count", "permanent_sid_count", "method"}
        if not required <= set(resolution) or set(resolution) - required - {"resolved_registry_ref", "resolved_request_ref"}:
            raise EngineeringTaskError("Complete fixed-fixture resolution metadata is required")
        for name in ("resolved_request_hash", "resolved_registry_hash", "resolution_artifact_hash"):
            _hash(resolution[name], name)
        if (resolution["tickers"] != document["symbol_resolution"]["tickers"]
                or type(resolution["ticker_count"]) is not int or resolution["ticker_count"] != 2
                or type(resolution["permanent_sid_count"]) is not int or resolution["permanent_sid_count"] != 2
                or resolution["method"] != document["symbol_resolution"]["method"]):
            raise EngineeringTaskError("Resolution does not identify the two permanent SIDs of the fixed fixture")
        refs = {}
        for name, digest in (("resolved_registry_ref", "resolved_registry_hash"), ("resolved_request_ref", "resolved_request_hash")):
            if name in resolution:
                ref = _mapping(resolution[name], name)
                if set(ref) != {"key", "sha256"} or ref["sha256"] != resolution[digest]:
                    raise EngineeringTaskError("Resolved cloud reference does not match its content identity")
                validate_key(ref["key"])
                refs[name] = ref
        if refs and (len(refs) != 2 or content_hash(refs) != resolution["resolution_artifact_hash"]):
            raise EngineeringTaskError("Resolved registry/request bundle identity differs")
        if stage == "lean" and resolution != self._research_result()["cloud_report"]["resolution"]:
            raise EngineeringTaskError("LEAN must use the exact verified Research SID registry and request")

    def _cloud_report(self, report, payload):
        report = _mapping(report, "cloud engineering report")
        self._report_metadata(report)
        admission_key = "engineering/admitted-inputs/" + payload["identity"]["attempt_id"] + ".json"
        if self.store.exists(admission_key):
            try:
                admission = json.loads(self.store.read_bytes(admission_key))
                validate_observation_binding(report.get("evidence", {}),
                    admission["payload"]["deployment_manifest"], payload["identity"]["deployment_hash"])
            except (KeyError, TypeError, ValueError):
                raise EngineeringTaskError("Deployment evidence differs from the original admitted input") from None
        elif "deployment_verification" in report.get("evidence", {}):
            raise EngineeringTaskError("Versioned deployment evidence requires the original admitted input") from None
        if (type(report.get("schema_version")) is not int or report.get("schema_version") != 1 or report.get("identity") != payload["identity"]
                or report.get("terminal") is not True or report.get("status") not in {"completed", "failed"}):
            raise EngineeringTaskError("Cloud report belongs to another execution or is not final")
        for name in ("market_values_exported", "economic_factor_tested", "final_data_accessed", "full_US200_coverage_certified", "actual_availability_verified"):
            if report.get(name) is not False:
                raise EngineeringTaskError("Engineering evidence must preserve its data, economic and availability limitations")
        checks = _mapping(report.get("checks"), "observed engineering checks")
        required = self.plan.to_dict()["required_checks"][payload["identity"]["stage"]]
        if not set(required) <= set(checks) or any(type(x) is not bool for x in checks.values()):
            raise EngineeringTaskError("Observed checks must contain every preregistered check")
        stats = _mapping(report.get("statistics"), "observed engineering counts")
        if any(type(value) is not int or value < 0 for value in stats.values()):
            raise EngineeringTaskError("Engineering statistics contain nonnegative integer counts only, never market performance or arrays")
        stage = payload["identity"]["stage"]
        expected = {"record_count": (1, None), "history_calls_second": (0, 0)} if stage == "research" else {
            "data_event_count": (1, None), "orders_submitted": (0, 0), "runtime_error_count": (0, 0)}
        if "corporate_action_received" in required:
            expected["dividend_event_count"] = (1, None)
        counts_passed = True
        for name, (lower, upper) in expected.items():
            value = stats.get(name)
            if type(value) is not int or value < 0:
                raise EngineeringTaskError("Actual engineering counts must be nonnegative integers: " + name)
            counts_passed &= value >= lower and (upper is None or value <= upper)
        self._resolution(report, stage)
        return report["status"] == "completed" and counts_passed and all(checks[name] for name in required)

    def _completion_contract(self, payload, submission, observed):
        """Validate one terminal against its original submission; no writes.

        Research validation does not call any Registry method and is safe under
        its transaction lock. Live LEAN settlement additionally verifies the
        Research resolution through its existing public path, outside that lock.
        Return status and pass flag separately: a terminal failure is evidence,
        but never a completed Research dependency.
        """
        self._completion_metadata(observed)
        platform = _mapping(observed.get("platform"), "platform terminal observation")
        expected = dict(payload["identity"], external_id=submission["external_id"])
        if (platform.get("identity") != expected or platform.get("terminal") is not True
                or platform.get("deployment") != submission["deployment"]):
            raise EngineeringTaskError("Terminal platform evidence does not match the recorded task and input")
        raw = _mapping(platform.get("raw_receipt"), "actual platform terminal receipt")
        if not raw:
            raise EngineeringTaskError("An actual platform receipt is required")
        status = platform.get("status")
        if status in {"failed", "runtime_error", "compile_error"}:
            return status, False
        if status != "completed":
            raise EngineeringTaskError("Submission or compilation success is not execution completion")
        report = observed.get("cloud_report")
        passed = self._cloud_report(report, payload)
        report_ref = _mapping(observed.get("report_ref"), "cloud report reference")
        if set(report_ref) != {"key", "sha256"} or report_ref["key"] != payload["report_key"] or report_ref["sha256"] != content_hash(report):
            raise EngineeringTaskError("Cloud report reference does not identify the expected immutable report")
        return status, passed

    def consume_completion(self, attempt, *, completion_source=None):
        """Read a delivered completion; never poll or accept a free status flag."""
        record = self._record(attempt)
        if record["status"] in {"completed", "failed"}:
            return self._attempt(record)
        source = self.completion_source if completion_source is None else completion_source
        if not callable(source):
            raise EngineeringTaskError("A trusted completion reader is required; a free result dictionary is not evidence")
        payload = self.payload(record["attempt_id"])
        submission = self._recorded_submission(payload)
        payload["external_id"] = submission["external_id"]
        observed = source(json.loads(canonical_json(payload)))
        # Check the entire contract before saving any rejected observation.
        # Rows accidentally returned by trusted I/O must remain cloud-only.
        status, passed = self._completion_contract(payload, submission, observed)
        reference = self._save(record["attempt_id"], "completion", observed)
        if status in {"failed", "runtime_error", "compile_error"}:
            return self.registry.fail(record["attempt_id"], {"platform_status": status, "evidence_ref": reference}, reconciliation=reference["sha256"])
        if not passed:
            return self.registry.fail(record["attempt_id"], {"reason": "Observed engineering checks failed", "evidence_ref": reference}, reconciliation=reference["sha256"])
        result = {"scope": "engineering", "identity": payload["identity"], "external_id": submission["external_id"],
                  "cloud_report": observed["cloud_report"], "report_ref": observed["report_ref"], "platform_evidence_ref": reference,
                  "financial_evidence": False}
        return self.registry.complete(record["attempt_id"], result, external_id=submission["external_id"])

    def read_result(self, attempt):
        record = self._record(attempt)
        return self.registry.read_result(record["attempt_id"])
