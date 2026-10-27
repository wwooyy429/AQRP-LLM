"""Event-sourced experiment identity, budget charging, and submission claims.

Call begin_attempt immediately before an actual remote Research execution or
LEAN submission. Only its should_execute=True claimant may submit. Charges are
durable before that return, and failures do not refund them. Never interpret a
submission receipt or successful compile as a completed backtest: complete is
reserved for checked final output from the finished external task.

An operation_key is a stable logical operation (for example a frozen fold), not
a random token per invocation. Failed operations require an explicit retry_of;
unresolved/ambiguous work fails closed. The registry is metadata only and must
not be used to store QuantConnect market or financial data locally.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping
from uuid import uuid4

from .artifacts import ArtifactConflict, canonical_json, content_hash, decode_events


class RegistryError(RuntimeError):
    """Invalid registration or lifecycle operation."""


class BudgetExceeded(RegistryError):
    """A normal, reserve, or aggregate budget would be exceeded."""


class CorruptRegistry(RegistryError):
    """The journal or its referenced immutable metadata is inconsistent."""


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    config_id: str
    stage: str
    operation_key: str
    status: str
    should_execute: bool
    allocation: str
    result_key: str
    external_id: str | None = None


_BUDGET_KEYS = {
    "configurations": "full_configurations",
    "research": "research_execution_attempts",
    "lean": "lean_submission_attempts",
}
_HISTORICAL_USAGE = {
    "configurations": ("configuration_budget_charges", "configuration_normal_used", "configuration_reserve_used"),
    "research": ("research_execution_attempts", "research_normal_used", "research_reserve_used"),
    "lean": ("lean_submission_attempts", "lean_normal_used", "lean_reserve_used"),
}
_OPEN_STATES = {"started", "pending", "ambiguous"}


def _counter(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(label + " must be a nonnegative integer")
    return value


def _normalize_limits(limits: Mapping[str, Any], allocations: Mapping[str, Any] | None) -> dict:
    normalized = {}
    for stage, budget_key in _BUDGET_KEYS.items():
        raw = limits.get(budget_key, limits.get(stage))
        split = (allocations or {}).get(budget_key, (allocations or {}).get(stage))
        if isinstance(raw, dict):
            split = raw
            raw = raw.get("total")
        if split is None:
            raise ValueError("Normal/reserve allocations are required for " + budget_key)
        normal = _counter(split.get("normal"), stage + ".normal")
        reserve = _counter(split.get("reserve"), stage + ".reserve")
        total = _counter(raw if raw is not None else split.get("total"), stage + ".total")
        if normal + reserve != total or split.get("total", total) != total:
            raise ValueError("Allocation totals do not match for " + stage)
        normalized[stage] = {"total": total, "normal": normal, "reserve": reserve}
    return normalized


def _normalize_usage(usage: Mapping[str, Any]) -> dict:
    result = {}
    for stage, keys in _HISTORICAL_USAGE.items():
        if isinstance(usage.get(stage), dict):
            raw = usage[stage]
            normal, reserve = raw.get("normal", 0), raw.get("reserve", 0)
            total = raw.get("total", normal + reserve)
        else:
            total = usage.get(keys[0], 0)
            normal = usage.get(keys[1], total)
            reserve = usage.get(keys[2], 0)
        result[stage] = {"total": _counter(total, stage + ".total"),
                         "normal": _counter(normal, stage + ".normal"),
                         "reserve": _counter(reserve, stage + ".reserve")}
        if result[stage]["normal"] + result[stage]["reserve"] != result[stage]["total"]:
            raise ValueError("Usage allocations do not sum to total for " + stage)
    return result


class Registry:
    """One ledger and content-addressed artifacts; no timestamp directories.

    Pass the whole budget document as limits to consume its limits, allocations,
    and initial usage, or pass those three mappings separately. Reopening a store
    requires the same initial baseline; all subsequent usage comes from replay.
    Each config/stage/operation has one completed result path. Repairs are journal
    entries; they do not create snapshot copies. An economic, model, preprocessing,
    or trading-rule change belongs in a newly registered full configuration.
    """

    JOURNAL = "registry/events.jsonl"
    LOCK = "registry/transaction"
    # The fixed engineering round allows one run and one repair per resource.
    # This is an admission policy on the authoritative ledger, not a separate
    # counter keyed by a mutable plan name, project, allocation or store object.
    ENGINEERING_STOP_LIMIT = 2

    def __init__(self, store: Any, limits: Mapping[str, Any],
                 usage: Mapping[str, Any] | None = None,
                 allocations: Mapping[str, Any] | None = None) -> None:
        self.store = store
        if "limits" in limits:
            document = limits
            usage = document.get("usage", {}) if usage is None else usage
            allocations = document.get("allocations") if allocations is None else allocations
            limits = document["limits"]
        self.limits = _normalize_limits(limits, allocations)
        self.initial_usage = _normalize_usage(usage or {})
        self._validate_usage(self.initial_usage)
        with self.store.locked(self.LOCK):
            if not self.store.exists(self.JOURNAL):
                self._append({"kind": "initialized", "schema_version": 1,
                              "limits": self.limits, "initial_usage": self.initial_usage})
            self._replay()

    def _validate_usage(self, usage: dict) -> None:
        for stage, counts in usage.items():
            for allocation in ("normal", "reserve", "total"):
                if counts[allocation] > self.limits[stage][allocation]:
                    raise BudgetExceeded("{} {} budget exhausted".format(stage, allocation))

    def _charge(self, usage: dict, stage: str, allocation: str) -> None:
        if allocation not in {"normal", "reserve"}:
            raise ValueError("Allocation must be normal or reserve")
        proposed = {key: dict(value) for key, value in usage.items()}
        proposed[stage][allocation] += 1
        proposed[stage]["total"] += 1
        self._validate_usage(proposed)
        usage[stage] = proposed[stage]

    def _append(self, event: dict) -> None:
        event = dict(event, recorded_at=datetime.now(timezone.utc).isoformat())
        self.store.append_event(self.JOURNAL, event)

    @staticmethod
    def _operation_id(operation_key: str) -> str:
        if not isinstance(operation_key, str) or not operation_key.strip():
            raise ValueError("operation_key must be a stable nonempty string")
        return sha256(operation_key.encode("utf-8")).hexdigest()

    @classmethod
    def result_key(cls, config_id: str, stage: str, operation_key: str = "default") -> str:
        cls._validate_identity(config_id, stage)
        return "results/{}/{}/{}.json".format(config_id, stage, cls._operation_id(operation_key))

    @staticmethod
    def _validate_identity(config_id: str, stage: str | None = None) -> None:
        if not isinstance(config_id, str) or re.fullmatch("[0-9a-f]{64}", config_id) is None:
            raise ValueError("config_id must be a canonical SHA-256 identity")
        if stage is not None and stage not in {"research", "lean"}:
            raise ValueError("Stage must be research or lean")

    def _replay(self) -> dict:
        records = decode_events(self.store.read_bytes(self.JOURNAL))
        if not records:
            raise CorruptRegistry("Registry has no initialization record")
        first = records[0]["event"]
        if (first.get("kind") != "initialized" or first.get("schema_version") != 1 or
                first.get("limits") != self.limits or first.get("initial_usage") != self.initial_usage):
            raise CorruptRegistry("Registry baseline differs from its persisted initialization")
        state = {"usage": {key: dict(value) for key, value in self.initial_usage.items()},
                 "configs": {}, "attempts": {}, "operations": {}, "imports": {}}
        try:
            for envelope in records[1:]:
                event = envelope["event"]
                kind = event["kind"]
                if kind in {"config_registered", "config_imported"}:
                    identity = event["config_id"]
                    self._validate_identity(identity)
                    if identity in state["configs"]:
                        raise CorruptRegistry("Configuration was charged twice")
                    data = self.store.read_bytes("configurations/" + identity + ".json")
                    if sha256(data).hexdigest() != identity or canonical_json(json.loads(data)) != data:
                        raise CorruptRegistry("Configuration artifact identity mismatch")
                    if kind == "config_registered":
                        self._charge(state["usage"], "configurations", event["allocation"])
                    else:
                        self._verify_import(json.loads(data), event["source_reference"], event["allocation"])
                        source_id = event["source_reference"]["configuration_id"]
                        if source_id in state["imports"]:
                            raise CorruptRegistry("A historical configuration was imported as multiple hashes")
                        used = sum(item["allocation"] == event["allocation"] for item in state["imports"].values())
                        if used >= self.initial_usage["configurations"][event["allocation"]]:
                            raise CorruptRegistry("Imported configurations exceed the preserved allocation usage")
                        state["imports"][source_id] = event
                    state["configs"][identity] = event
                elif kind == "attempt_started":
                    identity, stage, operation = event["config_id"], event["stage"], event["operation_key"]
                    self._validate_identity(identity, stage)
                    if identity not in state["configs"]:
                        raise CorruptRegistry("Attempt references an unregistered configuration")
                    attempt_id = event["attempt_id"]
                    operation_id = (identity, stage, self._operation_id(operation))
                    if attempt_id in state["attempts"]:
                        raise CorruptRegistry("Duplicate attempt identity")
                    old_id = state["operations"].get(operation_id)
                    if old_id is not None:
                        previous = state["attempts"][old_id]
                        if previous["status"] != "failed" or event.get("retry_of") != old_id:
                            raise CorruptRegistry("Attempt duplicates a non-retryable operation")
                    if any(item["config_id"] == identity and item["stage"] == stage and
                           item["status"] in _OPEN_STATES for item in state["attempts"].values()):
                        raise CorruptRegistry("Attempt overlaps unresolved work for the same config and stage")
                    self._charge(state["usage"], stage, event["allocation"])
                    record = dict(event, status="started", external_id=None)
                    if record["result_key"] != self.result_key(identity, stage, operation):
                        raise CorruptRegistry("Unexpected result destination")
                    state["attempts"][attempt_id] = record
                    state["operations"][operation_id] = attempt_id
                elif kind in {"pending", "ambiguous", "completed", "failed"}:
                    record = state["attempts"][event["attempt_id"]]
                    if record["status"] not in _OPEN_STATES:
                        raise CorruptRegistry("Finalized attempt received another state transition")
                    if kind == "failed" and record["status"] == "ambiguous" and not event.get("reconciliation"):
                        raise CorruptRegistry("Ambiguous attempt failed without reconciliation")
                    if kind == "pending" and record["status"] == "ambiguous":
                        raise CorruptRegistry("Ambiguous attempt was made pending without final reconciliation")
                    if kind == "completed":
                        result = self.store.read_bytes(record["result_key"])
                        if sha256(result).hexdigest() != event["result_sha256"]:
                            raise CorruptRegistry("Completed result bytes differ from journal")
                        if canonical_json(json.loads(result)) != result:
                            raise CorruptRegistry("Completed result is not canonical JSON")
                    record.update(event)
                    record["status"] = kind
                else:
                    raise CorruptRegistry("Unknown registry event: " + str(kind))
        except (KeyError, FileNotFoundError, ValueError, TypeError, BudgetExceeded) as exc:
            raise CorruptRegistry("Registry replay failed: " + str(exc)) from exc
        return state

    @staticmethod
    def _attempt(record: dict, *, should_execute: bool = False) -> Attempt:
        return Attempt(attempt_id=record["attempt_id"], config_id=record["config_id"],
                       stage=record["stage"], operation_key=record["operation_key"],
                       status=record["status"], should_execute=should_execute,
                       allocation=record["allocation"], result_key=record["result_key"],
                       external_id=record.get("external_id"))

    def register_config(self, full_config: dict, allocation: str = "normal") -> str:
        encoded = canonical_json(full_config)
        identity = sha256(encoded).hexdigest()
        with self.store.locked(self.LOCK):
            state = self._replay()
            if identity in state["configs"]:
                return identity
            package = json.loads(encoded)
            if (self._collection_plan(package) is not None
                    or (self._is_engineering_package(package) and package["plan"].get("schema_version") == 2)):
                self._enforce_engineering_project(state, package)
            self._enforce_engineering_limit(state, "configurations", package)
            self._charge(state["usage"], "configurations", allocation)
            self.store.write_once("configurations/" + identity + ".json", encoded)
            self._append({"kind": "config_registered", "config_id": identity, "allocation": allocation})
        return identity

    @staticmethod
    def _is_engineering_package(package: dict) -> bool:
        if not isinstance(package, dict):
            return False
        plan = package.get("plan")
        marked = "engineering_task_schema_version" in package
        engineering_plan = isinstance(plan, dict) and plan.get("scope") == "engineering"
        collection = Registry._collection_candidate(plan)
        if not marked and not engineering_plan and not collection:
            return False
        if (type(package.get("engineering_task_schema_version")) is not int
                or package["engineering_task_schema_version"] != 1
                or set(package) != {"engineering_task_schema_version", "plan"}
                or not engineering_plan):
            raise ValueError("Engineering packages require their complete fixed schema marker")
        if collection:
            Registry._collection_plan(package)
        elif plan.get("schema_version") == 2:
            # A joint pilot is one complete engineering configuration, never an
            # unvalidated bag of child jobs. Replays use its frozen catalog;
            # the dispatcher separately checks the trusted current catalog.
            from .engineering_tasks import EngineeringTaskPlan
            frozen = EngineeringTaskPlan.from_dict(plan, discovered_project_ids=(plan.get("project_id"),))
            if frozen.to_dict() != plan:
                raise ValueError("Joint engineering registration requires its frozen canonical plan")
        return True

    @staticmethod
    def _collection_candidate(plan: Any) -> bool:
        # Reserved collection shape must not become an unbounded generic task
        # by dropping the envelope marker or changing scope/task_kind.
        return isinstance(plan, dict) and (plan.get("task_kind") == "historical_collection"
            or "collection_plan" in plan or "field_catalog" in plan)

    @staticmethod
    def _collection_plan(package: dict):
        if not isinstance(package, dict) or not Registry._collection_candidate(package.get("plan")):
            return None
        plan = package["plan"]
        if (set(package) != {"engineering_task_schema_version", "plan"}
                or type(package.get("engineering_task_schema_version")) is not int
                or package["engineering_task_schema_version"] != 1):
            raise ValueError("Collection tasks require the shared engineering package marker")
        # This validates persisted shape/identity only. The trusted dispatcher
        # separately supplies actual discovered projects and trusted catalog.
        from .collection_tasks import CollectionTaskPlan
        frozen = CollectionTaskPlan.from_dict(plan,
            discovered_project_ids=(plan.get("project_id"),), field_catalog=plan.get("field_catalog"))
        if frozen.to_dict() != plan:
            raise ValueError("Collection registration requires the already frozen canonical plan")
        return frozen

    def _enforce_engineering_project(self, state: dict, package: dict) -> None:
        """A new charge cannot overlap unresolved engineering input on a project.

        Called only under the authoritative transaction lock. Existing logical
        operation reuse is handled before this guard, so cached reads stay free.
        """
        if not self._is_engineering_package(package):
            return
        project = package["plan"].get("project_id")
        if type(project) is not int or project <= 0:
            raise RegistryError("Engineering admission requires a positive project identity")
        for record in state["attempts"].values():
            if record["status"] not in _OPEN_STATES:
                continue
            old = json.loads(self.store.read_bytes("configurations/" + record["config_id"] + ".json"))
            if self._is_engineering_package(old) and old["plan"].get("project_id") == project:
                raise RegistryError("Unresolved engineering work on this project requires reconciliation")

    @staticmethod
    def _collection_operation(plan, stage: str, operation_key: str) -> None:
        if plan is not None and (stage != "research"
                or operation_key != "collection-plan:" + plan.hash + ":research"):
            raise RegistryError("Collection tasks permit only their fixed Research operation")

    @staticmethod
    def _joint_engineering_plan(package: dict):
        """Return the complete v2 contract, without changing legacy v1 claims."""
        if not Registry._is_engineering_package(package) or package["plan"].get("schema_version") != 2:
            return None
        from .engineering_tasks import EngineeringTaskPlan
        plan = package["plan"]
        return EngineeringTaskPlan.from_dict(plan, discovered_project_ids=(plan["project_id"],))

    @staticmethod
    def _joint_operation(plan, stage: str, operation_key: str) -> None:
        if plan is not None and operation_key != "engineering-plan:" + plan.hash + ":" + stage:
            raise RegistryError("Joint engineering permits only its fixed stage operation")

    def _joint_research_complete(self, state: dict, config_id: str, plan) -> None:
        """Validate the same parent's checked Research while already under LOCK.

        Do not call snapshot/read_result or Bridge.payload here: their public
        methods would reacquire the filesystem transaction lock. Replay has
        already verified the stored result's journal digest and canonical JSON.
        """
        operation = "engineering-plan:" + plan.hash + ":research"
        records = [record for record in state["attempts"].values()
                   if record["config_id"] == config_id and record["stage"] == "research"
                   and record["operation_key"] == operation]
        if not records or records[-1]["status"] != "completed":
            raise RegistryError("Joint LEAN requires completed Research for this exact plan first")
        record, document = records[-1], plan.to_dict()
        identity = {"plan_hash": plan.hash, "config_id": config_id,
                    "attempt_id": record["attempt_id"], "stage": "research",
                    "project_id": document["project_id"], "source_manifest_hash": document["source_manifest_hash"],
                    "deployment_hash": document["deployment_hash"], "data_request_hash": plan.request_hash}
        key = document["report_namespace"] + "/reports/" + plan.hash + "/research/" + record["attempt_id"] + ".json"
        external = "qc-research:" + str(document["project_id"]) + ":" + record["attempt_id"]
        try:
            result = json.loads(self.store.read_bytes(record["result_key"]))
            if (not isinstance(result, dict) or set(result) != {"scope", "identity", "external_id", "cloud_report",
                    "report_ref", "platform_evidence_ref", "financial_evidence"}
                    or result["scope"] != "engineering" or result["identity"] != identity
                    or result["external_id"] != external or record.get("external_id") != external
                    or result["financial_evidence"] is not False
                    or not isinstance(result["cloud_report"], dict)
                    or result["cloud_report"].get("identity") != identity):
                raise ValueError("Research result does not identify this checked parent")
            from .engineering_tasks import EngineeringTaskBridge, _safe_reference
            bridge = EngineeringTaskBridge(self, plan)
            reference = result["platform_evidence_ref"]
            _safe_reference(reference)
            if reference["key"] != "engineering/evidence/" + record["attempt_id"] + "/completion/" + reference["sha256"] + ".json":
                raise ValueError("Research completion reference differs from the attempt")
            encoded = self.store.read_bytes(reference["key"])
            if sha256(encoded).hexdigest() != reference["sha256"] or canonical_json(json.loads(encoded)) != encoded:
                raise ValueError("Research completion reference bytes changed")
            observed = json.loads(encoded)
            if not isinstance(observed, dict) or observed.get("cloud_report") != result["cloud_report"]:
                raise ValueError("Research completion report differs from its checked identity")
            payload = {"identity": identity, "report_key": key,
                       "external_identity_kind": "logical_research_execution_receipt"}
            submission = bridge._recorded_submission(payload)
            status, passed = bridge._completion_contract(payload, submission, observed)
            if (status != "completed" or passed is not True
                    or submission["external_id"] != external
                    or observed.get("cloud_report") != result["cloud_report"]
                    or observed.get("report_ref") != result["report_ref"]
                    or result["report_ref"] != {"key": key, "sha256": content_hash(result["cloud_report"])}):
                raise ValueError("Research completion does not prove the frozen dependency")
        except (KeyError, TypeError, ValueError, FileNotFoundError) as exc:
            raise RegistryError("Joint LEAN requires the verified same-plan Research result") from exc

    def _joint_admission(self, state: dict, config_id: str, stage: str, plan) -> None:
        if plan is None:
            return
        previous = [record for record in state["attempts"].values()
                    if record["config_id"] == config_id and record["stage"] == stage]
        if len(previous) >= 1 + plan.to_dict()["max_retries"][stage]:
            raise RegistryError("Preregistered joint engineering retry bound reached")
        if stage == "lean":
            self._joint_research_complete(state, config_id, plan)

    def _engineering_config_ids(self, state: dict) -> set[str]:
        return {identity for identity in state["configs"]
                if self._is_engineering_package(json.loads(
                    self.store.read_bytes("configurations/" + identity + ".json")))}

    def _enforce_engineering_limit(self, state: dict, kind: str, package: dict) -> None:
        """Check the round stop under LOCK immediately before a new charge.

        Every engineering registration and execution entry point reaches these
        Registry transactions, including callers which bypass the CLI/Bridge.
        Completed, unresolved and failed-without-retry reuse is resolved before
        this check; old failures and all allocations still count toward the cap.
        """
        if not self._is_engineering_package(package):
            return
        selected = self._engineering_config_ids(state)
        count = (len(selected) if kind == "configurations" else
                 sum(record["config_id"] in selected and record["stage"] == kind
                     for record in state["attempts"].values()))
        if count >= self.ENGINEERING_STOP_LIMIT:
            raise BudgetExceeded("Stage2 engineering stop condition reached for " + kind)

    def check_engineering_admission(self, full_config: dict, kind: str) -> None:
        """Read-only preview; actual mutations always recheck under the same lock.

        This is only for status/preflight reporting. It does not reserve a slot
        or grant permission to submit an external task.
        """
        if kind not in _BUDGET_KEYS:
            raise ValueError("Unknown engineering admission resource")
        encoded = canonical_json(full_config)
        identity = sha256(encoded).hexdigest()
        with self.store.locked(self.LOCK):
            state = self._replay()
            package = json.loads(encoded)
            collection = self._collection_plan(package)
            if collection is not None and kind == "lean":
                raise RegistryError("Collection tasks permit only Research admission")
            if kind == "configurations" and identity in state["configs"]:
                return
            same = [record for record in state["attempts"].values()
                    if record["config_id"] == identity and record["stage"] == kind]
            if same and same[-1]["status"] in _OPEN_STATES | {"completed"}:
                return
            if collection is not None or kind != "configurations":
                self._enforce_engineering_project(state, package)
            self._enforce_engineering_limit(state, kind, package)

    def _verify_import(self, full_config: dict, source_reference: dict, allocation: str) -> None:
        """Verify a copied historical charge receipt, not a newly invented waiver."""
        if allocation not in {"normal", "reserve"}:
            raise ValueError("Allocation must be normal or reserve")
        if not isinstance(source_reference, dict) or not all(
                key in source_reference for key in ("key", "sha256", "configuration_id")):
            raise RegistryError("Import requires source key, sha256, and configuration_id")
        if full_config.get("configuration_id") != source_reference["configuration_id"]:
            raise RegistryError("Full configuration must identify the existing authorized configuration")
        data = self.store.read_bytes(source_reference["key"])
        if sha256(data).hexdigest() != source_reference["sha256"]:
            raise RegistryError("Historical charge source hash mismatch")
        try:
            records = [json.loads(line) for line in data.decode("utf-8-sig").splitlines() if line.strip()]
            matching = [record for record in records if record.get("configuration_id") == source_reference["configuration_id"]]
        except (ValueError, UnicodeDecodeError, AttributeError) as exc:
            raise RegistryError("Historical source is not a valid configuration JSONL ledger") from exc
        if len(matching) != 1:
            raise RegistryError("Historical source must identify one unambiguous charged configuration")
        record = matching[0]
        charge = record.get("charge")
        prior = record.get("prior_configuration_charges_preserved")
        if (type(charge) is not int or charge <= 0 or type(prior) is not int or prior < 0 or
                record.get("allocation") != allocation or
                prior + charge > self.initial_usage["configurations"]["total"] or
                charge > self.initial_usage["configurations"][allocation]):
            raise RegistryError("Historical source is not covered by the preserved configuration usage")

    def import_existing_config(self, full_config: dict, source_reference: dict,
                               allocation: str = "normal") -> str:
        """Bootstrap an already charged configuration exactly once, with provenance.

        This explicit migration entry point is for the existing approved generic
        configuration. It is not a route for new hypotheses or repairs. Copy the
        original audit JSONL into the store first, then supply its immutable key,
        SHA-256, and legacy configuration_id. The initial usage remains unchanged.
        One legacy identity cannot subsequently be attached to a different hash.
        """
        encoded = canonical_json(full_config)
        identity = sha256(encoded).hexdigest()
        with self.store.locked(self.LOCK):
            state = self._replay()
            self._verify_import(full_config, source_reference, allocation)
            source_id = source_reference["configuration_id"]
            if source_id in state["imports"]:
                existing = state["imports"][source_id]
                if existing["config_id"] != identity or existing["source_reference"] != source_reference:
                    raise RegistryError("Existing configuration identity is already bound to another hash/source")
                return identity
            if identity in state["configs"]:
                raise RegistryError("Configuration is already registered; its charge cannot be refunded by import")
            self._enforce_engineering_limit(state, "configurations", json.loads(encoded))
            used = sum(item["allocation"] == allocation for item in state["imports"].values())
            if used >= self.initial_usage["configurations"][allocation]:
                raise RegistryError("Imports exceed the preserved allocation usage")
            self.store.write_once("configurations/" + identity + ".json", encoded)
            self._append({"kind": "config_imported", "config_id": identity,
                          "allocation": allocation, "source_reference": source_reference,
                          "charge": 0, "reason": "Previously authorized configuration charge preserved"})
        return identity

    def begin_attempt(self, config_id: str, stage: str, allocation: str = "normal",
                      operation_key: str | None = None, *, retry_of: str | None = None,
                      reason: str | None = None) -> Attempt:
        """Claim a logical operation, or return its existing state without charge.

        A failed operation remains failed unless retry_of names its last failed
        attempt and reason records the repair/rerun. Any unresolved operation for
        this configuration/stage blocks further submissions until reconciled.
        """
        self._validate_identity(config_id, stage)
        operation_key = "default" if operation_key is None else operation_key
        operation_id = (config_id, stage, self._operation_id(operation_key))
        with self.store.locked(self.LOCK):
            state = self._replay()
            if config_id not in state["configs"]:
                raise RegistryError("Register the complete configuration before execution")
            package = json.loads(self.store.read_bytes("configurations/" + config_id + ".json"))
            collection = self._collection_plan(package)
            self._collection_operation(collection, stage, operation_key)
            joint = self._joint_engineering_plan(package)
            self._joint_operation(joint, stage, operation_key)
            existing_id = state["operations"].get(operation_id)
            if existing_id:
                existing = state["attempts"][existing_id]
                if existing["status"] != "failed" or retry_of is None:
                    return self._attempt(existing)
                if retry_of != existing_id or not reason or not reason.strip():
                    raise RegistryError("A retry needs the last failed attempt_id and an explicit reason")
            elif retry_of is not None:
                raise RegistryError("retry_of must refer to this logical operation's last failed attempt")
            for record in state["attempts"].values():
                if record["config_id"] == config_id and record["stage"] == stage and record["status"] in _OPEN_STATES:
                    if joint is not None:
                        raise RegistryError("Unresolved joint engineering operation requires reconciliation")
                    return self._attempt(record)
            self._joint_admission(state, config_id, stage, joint)
            self._enforce_engineering_project(state, package)
            if collection is not None:
                previous = [record for record in state["attempts"].values()
                    if record["config_id"] == config_id and record["stage"] == stage]
                if len(previous) >= 1 + collection.to_dict()["max_retries"]:
                    raise RegistryError("Preregistered collection retry bound reached")
            self._enforce_engineering_limit(state, stage, package)
            self._charge(state["usage"], stage, allocation)
            record = {"kind": "attempt_started", "attempt_id": uuid4().hex,
                      "config_id": config_id, "stage": stage, "operation_key": operation_key,
                      "allocation": allocation, "retry_of": retry_of, "reason": reason,
                      "result_key": self.result_key(config_id, stage, operation_key)}
            self._append(record)
            return self._attempt(dict(record, status="started"), should_execute=True)

    @staticmethod
    def _attempt_id(attempt: Attempt | str) -> str:
        return attempt.attempt_id if isinstance(attempt, Attempt) else attempt

    def _transition(self, attempt: Attempt | str, kind: str, **fields: Any) -> Attempt:
        with self.store.locked(self.LOCK):
            return self._transition_locked(attempt, kind, **fields)

    def _transition_locked(self, attempt: Attempt | str, kind: str, **fields: Any) -> Attempt:
        """Existing transition body; caller must already own the Registry LOCK."""
        attempt_id = self._attempt_id(attempt)
        state = self._replay()
        if attempt_id not in state["attempts"]:
            raise RegistryError("Unknown attempt_id")
        record = state["attempts"][attempt_id]
        if record["status"] not in _OPEN_STATES:
            if record["status"] == kind:
                return self._attempt(record)
            raise RegistryError("Attempt already finalized as " + record["status"])
        if kind == "failed" and record["status"] == "ambiguous" and not fields.get("reconciliation"):
            raise RegistryError("An ambiguous submission requires an explicit reconciliation receipt")
        if kind == "pending" and record["status"] == "ambiguous":
            raise RegistryError("Ambiguous submission must be resolved by an observed final result or reconciliation")
        event = dict(fields, kind=kind, attempt_id=attempt_id)
        self._append(event)
        record.update(event)
        record["status"] = kind
        return self._attempt(record)

    def pending(self, attempt: Attempt | str, *, external_id: str, details: dict | None = None) -> Attempt:
        """Record an accepted asynchronous job, not a completed computation."""
        if not isinstance(external_id, str) or not external_id.strip():
            raise ValueError("An observed external task identity is required")
        return self._transition(attempt, "pending", external_id=external_id, details=details or {})

    def ambiguous(self, attempt: Attempt | str, *, reason: str, details: dict | None = None) -> Attempt:
        """Submission outcome is unknown; new attempts remain blocked."""
        if not reason:
            raise ValueError("An ambiguity reason is required")
        return self._transition(attempt, "ambiguous", reason=reason, details=details or {})

    def fail(self, attempt: Attempt | str, error: str | dict, *,
             reconciliation: str | None = None) -> Attempt:
        """Record failure without refund; ambiguous jobs need observed reconciliation."""
        return self._transition(attempt, "failed", error=error, reconciliation=reconciliation)

    def complete(self, attempt: Attempt | str, result: dict, *, external_id: str | None = None) -> Attempt:
        """Persist checked final metadata and finish exactly once.

        If a crash occurs after result publication but before the journal append,
        replay leaves the attempt unresolved. Repeating complete with the same
        bytes repairs that specific gap without another execution or charge.
        """
        encoded = canonical_json(result)
        attempt_id = self._attempt_id(attempt)
        with self.store.locked(self.LOCK):
            state = self._replay()
            if attempt_id not in state["attempts"]:
                raise RegistryError("Unknown attempt_id")
            record = state["attempts"][attempt_id]
            if record["status"] == "failed":
                raise RegistryError("A failed attempt cannot be completed; register an explicit retry")
            self.store.write_once(record["result_key"], encoded)
            if record["status"] == "completed":
                return self._attempt(record)
            event = {"kind": "completed", "attempt_id": attempt_id,
                     "result_sha256": sha256(encoded).hexdigest(),
                     "external_id": external_id if external_id is not None else record.get("external_id")}
            self._append(event)
            record.update(event)
            record["status"] = "completed"
            return self._attempt(record)

    def read_result(self, attempt: Attempt | str) -> dict:
        """Read a verified completed cache entry; pending bytes are not a result."""
        with self.store.locked(self.LOCK):
            state = self._replay()
            record = state["attempts"].get(self._attempt_id(attempt))
            if record is None or record["status"] != "completed":
                raise RegistryError("No completed result is available")
            return json.loads(self.store.read_bytes(record["result_key"]))

    def snapshot(self) -> dict:
        """Return persisted usage, identities and lifecycle metadata, with no data arrays."""
        with self.store.locked(self.LOCK):
            state = self._replay()
            return {"limits": self.limits, "usage": state["usage"],
                    "config_ids": sorted(state["configs"]),
                    "attempts": [dict(item) for item in state["attempts"].values()]}
