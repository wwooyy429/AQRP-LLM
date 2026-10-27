"""Cloud collection worker and native Research observation parser.

Imports perform no I/O. Only bounded metadata can leave the worker. Source rows
and the potentially long list of window references remain in QC Object Store.
"""
import base64
import json

from .artifacts import canonical_json, content_hash
from .collection import HistoricalSnapshotCollector
from .collection_tasks import CollectionTaskPlan, CHECKS, FLAGS, validate_report
from .engineering_data import verify_deployment
from .engineering_receipts import (_tool, _research_stdout, _json, ReceiptParseError)
from .engineering_tasks import EngineeringTaskError, _safe_identity
from .historical_source import QuantConnectSnapshotSource
from .quantconnect import ObjectStoreArtifactStore


def context(payload, *, field_catalog):
    required = {"plan", "identity", "report_key", "external_identity_kind"}
    if (not isinstance(payload, dict) or not required <= set(payload)
            or set(payload) - required - {"deployment_manifest"}):
        raise EngineeringTaskError("Only a frozen collection input is permitted")
    identity = payload["identity"]
    _safe_identity(identity)
    plan = CollectionTaskPlan.from_dict(payload["plan"], discovered_project_ids=(identity["project_id"],), field_catalog=field_catalog)
    value = plan.to_dict()
    expected = {"plan_hash": plan.hash, "config_id": content_hash({"engineering_task_schema_version": 1, "plan": value}),
                "stage": "research", "project_id": value["project_id"], "source_manifest_hash": value["source_manifest_hash"],
                "deployment_hash": value["deployment_hash"], "data_request_hash": plan.request_hash}
    key = value["report_namespace"] + "/reports/" + plan.hash + "/research/" + identity["attempt_id"] + ".json"
    if (any(identity[name] != wanted for name, wanted in expected.items())
            or payload["report_key"] != key or payload["external_identity_kind"] != "logical_research_execution_receipt"):
        raise EngineeringTaskError("Collection input differs from its registered source/task/attempt")
    return plan


def run_collection_task(payload, *, quantbook=None, field_catalog, api=None, store=None,
                        source=None, synthetic=False, source_root=None):
    """Called only by a trusted, precharged Research dispatcher.

    The payload is a frozen input binding, not a signed proof of budget payment.
    The local Registry transaction and trusted dispatcher enforce that boundary.
    Native exceptions leave collection intents intact; no value-bearing message
    is printed. Unknown remote outcomes require explicit reconciliation.
    """
    plan = context(payload, field_catalog=field_catalog)
    if type(synthetic) is not bool:
        raise EngineeringTaskError("Explicit synthetic classification required")
    if isinstance(payload.get("deployment_manifest"), dict) and "_collection_task_input.py" in payload["deployment_manifest"]:
        raise EngineeringTaskError("Generated input must remain outside the implementation manifest")
    verify_deployment(payload.get("deployment_manifest"), plan.to_dict()["deployment_hash"], source_root=source_root)
    if store is None:
        if quantbook is None:
            raise EngineeringTaskError("A cloud QuantBook and Object Store are required")
        store = ObjectStoreArtifactStore(quantbook.object_store, "aqrp/collection-tasks/v1", read_only=False, single_producer=True)
    if not synthetic and getattr(store, "residency", None) != "quantconnect_cloud":
        raise EngineeringTaskError("Real collection values stay in QuantConnect Cloud")
    collection_key = plan.to_dict()["report_namespace"] + "/receipts/" + payload["identity"]["attempt_id"] + ".json"
    reader = HistoricalSnapshotCollector(store, None, plan.collection_plan, synthetic=synthetic)
    if store.exists(collection_key):
        encoded = store.read_bytes(collection_key)
        receipt = json.loads(encoded)
        if (canonical_json(receipt) != encoded or not isinstance(receipt, dict)
                or set(receipt) != {"identity", "first", "cache_only_replay"} or receipt["identity"] != payload["identity"]):
            raise EngineeringTaskError("Saved collection metadata differs from this attempt")
        first, second = receipt["first"], receipt["cache_only_replay"]
        observed = reader.collect()
        if not isinstance(first, dict) or set(first) != set(observed) or second != observed:
            raise EngineeringTaskError("Saved collection replay differs from verified cloud cache")
        if any(first[name] != value for name, value in observed.items() if name not in {"provider_calls", "reused_windows"}):
            raise EngineeringTaskError("Saved collection counts or references differ from verified cache")
    else:
        if source is None:
            if quantbook is None:
                raise EngineeringTaskError("A Research source is required")
            raw_collection = plan.collection_plan.to_dict()
            options = ({"observation_policy": raw_collection["observation_policy"]}
                       if raw_collection["schema_version"] == 2 else {})
            source = QuantConnectSnapshotSource(quantbook, plan.collection_plan.field_catalog, api=api, **options)
        first = HistoricalSnapshotCollector(store, source, plan.collection_plan, synthetic=synthetic).collect()
        second = reader.collect()
        receipt = {"identity": payload["identity"], "first": first, "cache_only_replay": second}
    store.write_once(collection_key, canonical_json(receipt))
    flags = {name: False for name in FLAGS}
    checks = {name: True for name in CHECKS}
    checks["all_windows_completed"] = first["window_count"] == len(plan.collection_plan.windows())
    checks["cache_only_replay_zero_fetch"] = second["provider_calls"] == 0
    checks["same_completed_refs"] = first["window_refs"] == second["window_refs"]
    counts = {"window_count": first["window_count"], "record_count": first["record_count"],
              "source_fetch_calls": first["provider_calls"], "reused_windows": first["reused_windows"],
              "empty_windows": first["empty_windows"], "cache_only_source_fetch_calls": second["provider_calls"]}
    report = {"schema_version": 1, "identity": payload["identity"], "terminal": True,
              "status": "completed" if all(checks.values()) else "failed", "checks": checks,
              "statistics": counts, **flags, "evidence": {"collection_plan_hash": plan.request_hash,
              "collection_receipt_ref": {"key": collection_key, "sha256": content_hash(receipt)},
              "missing_values": first["missing_values"]}}
    if plan.collection_plan.to_dict()["schema_version"] == 2:
        counts.update({name: first[name] for name in ("duplicate_projection_records", "conflicting_projection_records")})
        report["evidence"]["observation_policy"] = first["observation_policy"]
    validate_report(report, plan, payload["identity"])
    store.write_once(payload["report_key"], canonical_json(report))
    return {"cloud_report": report, "report_ref": {"key": payload["report_key"], "sha256": content_hash(report)}}


def stdout_marker(wrapper, *, payload, field_catalog):
    """Return exactly one metadata marker, never a market-data display."""
    plan = context(payload, field_catalog=field_catalog)
    if not isinstance(wrapper, dict) or set(wrapper) != {"cloud_report", "report_ref"}:
        raise EngineeringTaskError("Only checked collection metadata may be printed")
    validate_report(wrapper["cloud_report"], plan, payload["identity"])
    if wrapper["report_ref"] != {"key": payload["report_key"], "sha256": content_hash(wrapper["cloud_report"])}:
        raise EngineeringTaskError("Printed report reference changed")
    encoded = base64.b64encode(canonical_json(wrapper)).decode("ascii")
    if len(encoded) > 64000:
        raise EngineeringTaskError("Collection metadata report exceeds the fixed output bound")
    return "AQRP_ENGINEERING_JSON " + encoded


def collection_research_observation(payload, deployment, tool_envelope, *, field_catalog):
    """Parse an actually delivered completed cell; no calls or status polling."""
    plan = context(payload, field_catalog=field_catalog)
    if (not isinstance(deployment, dict) or set(deployment) != {"source_manifest_hash", "deployment_hash", "input_hash"}
            or any(deployment[key] != payload["identity"][key] for key in ("source_manifest_hash", "deployment_hash"))):
        raise ReceiptParseError("Actual deployment differs from the admitted collection task")
    from .engineering_tasks import _hash
    _hash(deployment["input_hash"], "input hash")
    native, raw = _tool(tool_envelope, "mcp__quantconnect__jupyter_execute_cell", payload)
    encoded = _research_stdout(native)
    if not encoded or len(encoded) > 64000:
        raise ReceiptParseError("Collection marker is missing or unbounded")
    try:
        decoded = base64.b64decode(encoded, validate=True)
        if base64.b64encode(decoded).decode("ascii") != encoded:
            raise ValueError
        wrapper = _json(decoded.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise ReceiptParseError("Invalid collection metadata marker") from None
    if not isinstance(wrapper, dict) or set(wrapper) != {"cloud_report", "report_ref"}:
        raise ReceiptParseError("Only the collection report and content reference may leave cloud")
    validate_report(wrapper["cloud_report"], plan, payload["identity"])
    expected_ref = {"key": payload["report_key"], "sha256": content_hash(wrapper["cloud_report"])}
    if wrapper["report_ref"] != expected_ref:
        raise ReceiptParseError("Collection report reference changed")
    external = "qc-research:" + str(payload["identity"]["project_id"]) + ":" + payload["identity"]["attempt_id"]
    raw.update(marker_count=1, stdout_only=True)
    submission = {"identity": payload["identity"], "identity_kind": payload["external_identity_kind"],
                  "external_id": external, "accepted": True, "status": "submitted", "deployment": deployment, "raw_receipt": raw}
    completion = {"platform": {"identity": dict(payload["identity"], external_id=external), "status": "completed",
                  "terminal": True, "deployment": deployment, "raw_receipt": raw}, **wrapper}
    return {"submission": submission, "completion": completion}
