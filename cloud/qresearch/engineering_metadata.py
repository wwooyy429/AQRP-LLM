"""Fixed metadata-only receipt boundaries shared by engineering tasks.

Kept in a readable module below the cloud per-file source limit. This module
has no dispatcher, budget authority or market-data I/O.
"""
import math
import re
from .artifacts import validate_key
from .contracts import aware
from .deployment_observation import validate_deployment_observation


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


