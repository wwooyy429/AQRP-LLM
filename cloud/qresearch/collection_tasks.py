"""Research-only collection tasks on the existing engineering budget ledger.

Trusted dispatchers provide project discovery, catalogs, native observations and
deployment readbacks. No constructor, report or LLM document grants execution.
"""
from dataclasses import dataclass
import json

from .artifacts import canonical_json, content_hash, validate_key
from .collection import HistoricalCollectionPlan
from .engineering_tasks import (EngineeringTaskBridge, EngineeringTaskError,
                                _hash, _safe_identity, _safe_reference)
from .workflow import SubmissionRejected


CHECKS = {"all_windows_completed", "cache_only_replay_zero_fetch", "same_completed_refs",
          "source_identity_matches", "cloud_rows_not_exported", "development_only"}
FLAGS = {"market_values_exported", "economic_factor_tested", "final_data_accessed",
         "full_US200_coverage_certified", "actual_availability_verified"}
COUNTS = {"window_count", "record_count", "source_fetch_calls", "reused_windows", "empty_windows",
          "cache_only_source_fetch_calls"}


@dataclass(frozen=True, init=False)
class CollectionTaskPlan:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use from_dict with trusted project discovery and source catalog")

    @classmethod
    def from_dict(cls, raw, *, discovered_project_ids, field_catalog):
        required = {"schema_version", "task_kind", "scope", "plan_id", "project_id",
                    "source_manifest_hash", "deployment_hash", "collection_plan", "field_catalog",
                    "report_namespace", "max_retries"}
        if not isinstance(raw, dict) or set(raw) != required:
            raise EngineeringTaskError("A complete frozen collection task is required")
        value = json.loads(canonical_json(raw))
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["task_kind"] != "historical_collection" or value["scope"] != "engineering"):
            raise EngineeringTaskError("Only engineering historical collection is supported")
        if (not isinstance(value["plan_id"], str) or not value["plan_id"].strip()
                or len(value["plan_id"]) > 256):
            raise EngineeringTaskError("A bounded nonempty task name is required")
        ids = tuple(discovered_project_ids)
        if (type(value["project_id"]) is not int or value["project_id"] <= 0
                or any(type(item) is not int or item <= 0 for item in ids) or value["project_id"] not in ids):
            raise EngineeringTaskError("Use only IDs returned by trusted list_projects")
        for key in ("source_manifest_hash", "deployment_hash"):
            _hash(value[key], key)
        validate_key(value["report_namespace"])
        if type(value["max_retries"]) is not int or not 0 <= value["max_retries"] <= 2:
            raise EngineeringTaskError("Explicit retry bound must be between zero and two")
        collection = HistoricalCollectionPlan.from_dict(value["collection_plan"], field_catalog=field_catalog)
        if (collection.to_dict()["source_manifest_hash"] != value["source_manifest_hash"]
                or value["field_catalog"] != collection.field_catalog):
            raise EngineeringTaskError("Source identity and selected trusted catalog must match the frozen collection")
        value["collection_plan"] = collection.to_dict()
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json(value))
        return result

    def to_dict(self):
        return json.loads(self._encoded)

    @property
    def hash(self):
        return content_hash(self.to_dict())

    @property
    def collection_plan(self):
        value = self.to_dict()
        return HistoricalCollectionPlan.from_dict(value["collection_plan"], field_catalog=value["field_catalog"])

    @property
    def request_hash(self):
        return self.collection_plan.hash


def validate_report(report, plan, identity):
    """Exact metadata whitelist shared by worker, parser and completion bridge."""
    required = {"schema_version", "identity", "status", "terminal", "checks", "statistics", "evidence"} | FLAGS
    if (not isinstance(report, dict) or set(report) != required
            or type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["identity"] != identity or report["terminal"] is not True
            or report["status"] not in {"completed", "failed"}):
        raise EngineeringTaskError("Collection report is not final metadata of this exact attempt")
    _safe_identity(identity)
    if identity["stage"] != "research" or any(report[key] is not False for key in FLAGS):
        raise EngineeringTaskError("Collection cannot grant financial, final or coverage approval")
    checks, counts, evidence = report["checks"], report["statistics"], report["evidence"]
    if (not isinstance(checks, dict) or set(checks) != CHECKS or any(type(v) is not bool for v in checks.values())
            or report["status"] != ("completed" if all(checks.values()) else "failed")):
        raise EngineeringTaskError("Only fixed program checks may decide collection status")
    collection = plan.collection_plan
    occurrences = collection.to_dict()["schema_version"] == 2
    expected_counts = COUNTS | ({"duplicate_projection_records", "conflicting_projection_records"} if occurrences else set())
    if (not isinstance(counts, dict) or set(counts) != expected_counts
            or any(type(v) is not int or v < 0 for v in counts.values())):
        raise EngineeringTaskError("Collection exports fixed nonnegative integer counts only")
    windows = len(collection.windows())
    if (counts["window_count"] != windows or counts["source_fetch_calls"] + counts["reused_windows"] != windows
            or counts["empty_windows"] > windows or counts["cache_only_source_fetch_calls"] != 0
            or counts["record_count"] > windows * collection.to_dict()["max_records_per_window"]):
        raise EngineeringTaskError("Collection counts violate the frozen windows or no-refetch contract")
    if occurrences and not (0 <= counts["conflicting_projection_records"] <= counts["duplicate_projection_records"]
            <= counts["record_count"] - (windows - counts["empty_windows"])):
        raise EngineeringTaskError("Occurrence ambiguity counts disagree with collected records")
    expected_evidence = {"collection_receipt_ref", "collection_plan_hash", "missing_values"} | ({"observation_policy"} if occurrences else set())
    if (not isinstance(evidence, dict) or set(evidence) != expected_evidence
            or evidence["collection_plan_hash"] != collection.hash):
        raise EngineeringTaskError("Only source-bound collection references and field gap counts may leave cloud")
    if occurrences and evidence["observation_policy"] != "retain_source_occurrences":
        raise EngineeringTaskError("Occurrence evidence requires the frozen observation policy")
    _safe_reference(evidence["collection_receipt_ref"])
    expected_key = plan.to_dict()["report_namespace"] + "/receipts/" + identity["attempt_id"] + ".json"
    if evidence["collection_receipt_ref"]["key"] != expected_key:
        raise EngineeringTaskError("Collection receipt belongs to another task or attempt")
    missing = evidence["missing_values"]
    if (not isinstance(missing, dict) or set(missing) != set(collection.field_catalog)
            or any(type(v) is not int or not 0 <= v <= counts["record_count"] for v in missing.values())):
        raise EngineeringTaskError("Missing-field counts must match the trusted projection")
    return report["status"] == "completed"


class CollectionTaskBridge(EngineeringTaskBridge):
    """Reuse the established evidence/transition pipeline and single Registry.

    Registry rechecks type, operation, retries, project protection and budgets
    under its transaction lock even for callers bypassing this bridge.
    """
    def __init__(self, registry, plan, *, adapter=None, completion_source=None):
        if not isinstance(plan, CollectionTaskPlan):
            raise TypeError("A validated CollectionTaskPlan is required")
        self.registry, self.store, self.plan = registry, registry.store, plan
        self.adapter, self.completion_source = adapter, completion_source
        self.package = {"engineering_task_schema_version": 1, "plan": plan.to_dict()}
        self.config_id = content_hash(self.package)

    def _operation(self, stage):
        if stage != "research":
            raise EngineeringTaskError("Collection is Research-only; no LEAN or trading dispatch")
        return "collection-plan:" + self.plan.hash + ":research"

    def claim(self, stage="research", *, allocation="normal", retry_of=None, reason=None):
        return self.registry.begin_attempt(self.config_id, stage, allocation=allocation,
            operation_key=self._operation(stage), retry_of=retry_of, reason=reason)

    def _report_metadata(self, report):
        identity = report.get("identity") if isinstance(report, dict) else None
        validate_report(report, self.plan, identity)

    def _cloud_report(self, report, payload):
        return validate_report(report, self.plan, payload["identity"])

    def submit(self, stage="research", *, allocation="normal", retry_of=None, reason=None):
        self._operation(stage)
        callback = getattr(self.adapter, "submit_research", None)
        if not callable(callback):
            raise EngineeringTaskError("A trusted adapter is required before claiming budget")
        attempt = self.claim(stage, allocation=allocation, retry_of=retry_of, reason=reason)
        if not attempt.should_execute:
            return attempt
        try:
            receipt = callback(self.payload(attempt), operation_key=attempt.operation_key)
        except SubmissionRejected:
            return self.registry.fail(attempt, "Trusted adapter rejected collection submission")
        except Exception as exc:
            return self.registry.ambiguous(attempt, reason="Submission outcome unknown: " + type(exc).__name__)
        try:
            return self.record_submission(attempt, receipt)
        except Exception:
            self.registry.ambiguous(attempt, reason="Collection acknowledgement could not be safely recorded")
            raise
