"""Engineering grants and joint-task admission for the shared Registry.

The mixin uses the host Registry's existing transaction lock, journal replay and
budget charging methods. It owns no store or counters and never submits cloud
work. Public errors are defined here and re-exported by registry.py so either
module can be imported first without circular imports.
"""
from hashlib import sha256
import json
import re
from typing import Any

from .artifacts import canonical_json, content_hash
from .engineering_rounds import RESOURCES, validate_grant, validate_round_id


class RegistryError(RuntimeError):
    """Invalid registration or lifecycle operation."""


class BudgetExceeded(RegistryError):
    """A normal, reserve, or aggregate budget would be exceeded."""


class CorruptRegistry(RegistryError):
    """The journal or its referenced immutable metadata is inconsistent."""


_OPEN_STATES = {"started", "pending", "ambiguous"}


class RegistryEngineeringMixin:
    """Host contract: store, LOCK, _replay, _append and shared budget helpers.

    Every mutating method keeps the authoritative Registry transaction lock.
    Dynamic imports for strict task schemas occur only when validating a plan.
    """
    def _read_round_reference(self, reference: dict, namespace: str) -> dict:
        if (not isinstance(reference, dict) or set(reference) != {"key", "sha256"}
                or not isinstance(reference["sha256"], str)
                or re.fullmatch("[0-9a-f]{64}", reference["sha256"]) is None
                or reference["key"] != "engineering/rounds/" + namespace + "/" + reference["sha256"] + ".json"):
            raise ValueError("Invalid engineering round content reference")
        data = self.store.read_bytes(reference["key"])
        document = json.loads(data)
        if canonical_json(document) != data or sha256(data).hexdigest() != reference["sha256"]:
            raise ValueError("Engineering round reference bytes changed")
        return document


    @staticmethod
    def _round_reference(document: dict, namespace: str) -> dict:
        digest = content_hash(document)
        return {"key": "engineering/rounds/" + namespace + "/" + digest + ".json", "sha256": digest}


    @staticmethod
    def _round_usage(state: dict, record: dict) -> dict:
        selected = set(record["config_ids"])
        return {"configurations": sum(identity in state["configs"] for identity in selected),
                **{stage: sum(item["config_id"] in selected and item["stage"] == stage
                              for item in state["attempts"].values()) for stage in ("research", "lean")}}


    def _reservations(self, state: dict, kind: str) -> dict:
        reserved = {"normal": 0, "reserve": 0, "total": 0}
        for record in state["engineering_rounds"].values():
            if record["status"] == "open":
                unused = record["grant"]["limits"][kind] - self._round_usage(state, record)[kind]
                if unused < 0:
                    raise CorruptRegistry("Engineering round exceeded its immutable limit")
                reserved[record["grant"]["allocation"]] += unused
                reserved["total"] += unused
        return reserved


    def _charge_reserved(self, state: dict, kind: str, allocation: str, identity: str) -> None:
        """Charge once, preserving unused grants against every other entry point."""
        if not state["engineering_rounds"]:
            self._charge_current(state, kind, allocation)
            return
        if allocation not in {"normal", "reserve"}:
            raise ValueError("Allocation must be normal or reserve")
        own_id = state["engineering_round_configs"].get(identity)
        own = state["engineering_rounds"].get(own_id)
        if own is not None:
            if own["status"] != "open" or allocation != own["grant"]["allocation"]:
                raise BudgetExceeded("Engineering round is closed or uses another allocation")
            if self._round_usage(state, own)[kind] >= own["grant"]["limits"][kind]:
                raise BudgetExceeded("Authorized engineering round limit reached for " + kind)
        reserved = self._reservations(state, kind)
        if own is not None:
            reserved[allocation] -= 1
            reserved["total"] -= 1
        for part in ("normal", "reserve", "total"):
            proposed = self._effective_usage(state)[kind][part] + (part in {allocation, "total"})
            if proposed + reserved[part] > state["limits"][kind][part]:
                raise BudgetExceeded("Remaining " + kind + " " + part + " capacity is reserved")
        self._charge_current(state, kind, allocation)


    def _validate_round_binding(self, state: dict, record: dict, package: dict) -> None:
        if record["status"] != "open":
            raise RegistryError("Closed engineering round cannot bind a configuration")
        if not self._is_engineering_package(package):
            raise ValueError("Engineering round requires a complete engineering package")
        # Additional rounds admit only the strict frozen collection/joint schemas;
        # a generic marker or a mutable plan name is not an authorization route.
        if (self._collection_plan(package) is None and self._joint_engineering_plan(package) is None
                and self._inventory_plan(package) is None):
            raise ValueError("Additional rounds require a frozen collection or joint task")
        if self._inventory_plan(package) is not None:
            grant = record["grant"]
            if (grant["schema_version"] != 2 or grant["allocation"] != "normal"
                    or grant["limits"] != {"configurations": 1, "research": 1, "lean": 0}):
                raise RegistryError("Inventory round must be explicitly version2 normal1/1/0")
        if package["plan"]["project_id"] != record["grant"]["project_id"]:
            raise RegistryError("Configuration project differs from the authorized round")
        identity = content_hash(package)
        if identity in state["configs"] or identity in state["engineering_round_configs"]:
            raise RegistryError("Round binding requires a new, uncharged configuration identity")
        if len(record["config_ids"]) >= record["grant"]["limits"]["configurations"]:
            raise BudgetExceeded("All authorized configuration binding slots are used")
        self._enforce_engineering_project(state, package)


    def _validate_round_authorization(self, state: dict, grant: dict, authorization: dict,
                                      packages: list[dict]) -> dict:
        validate_grant(grant, authorization, state["limits"],
            configuration_cycle_id=state["configuration_cycle"]["cycle_id"])
        round_id = grant["round_id"]
        if round_id in state["engineering_rounds"]:
            raise RegistryError("Engineering round identity is already immutable")
        if any(item["status"] == "open" and item["grant"]["project_id"] == grant["project_id"]
               for item in state["engineering_rounds"].values()):
            raise RegistryError("Close the existing project round before another authorization")
        if not isinstance(packages, list) or not 1 <= len(packages) <= grant["limits"]["configurations"]:
            raise ValueError("Authorization requires one or more bounded full configurations")
        record = {"grant": grant, "status": "open", "config_ids": [], "initial_config_ids": []}
        # Validate the whole transaction before publishing any immutable artifact.
        candidate = dict(state, engineering_round_configs=dict(state["engineering_round_configs"]))
        for package in packages:
            self._validate_round_binding(candidate, record, package)
            identity = content_hash(package)
            record["config_ids"].append(identity)
            candidate["engineering_round_configs"][identity] = round_id
        record["initial_config_ids"] = list(record["config_ids"])
        for kind in RESOURCES:
            reserved = self._reservations(state, kind)
            for part in (grant["allocation"], "total"):
                if self._effective_usage(state)[kind][part] + reserved[part] + grant["limits"][kind] > state["limits"][kind][part]:
                    raise BudgetExceeded("Engineering grant exceeds remaining " + kind + " " + part + " capacity")
        return record


    def _replay_round_authorized(self, state: dict, event: dict) -> None:
        if set(event) != {"kind", "grant_ref", "configuration_refs", "recorded_at"}:
            raise CorruptRegistry("Unexpected engineering authorization event fields")
        grant = self._read_round_reference(event["grant_ref"], "authorizations")
        authorization = self._read_round_reference(grant["authorization_ref"], "user-authorizations")
        if not isinstance(event["configuration_refs"], list):
            raise ValueError("Round configuration references must be a list")
        packages = [self._read_round_reference(item, "configurations") for item in event["configuration_refs"]]
        record = self._validate_round_authorization(state, grant, authorization, packages)
        state["engineering_rounds"][grant["round_id"]] = record
        for identity in record["config_ids"]:
            state["engineering_round_configs"][identity] = grant["round_id"]


    def authorize_engineering_round(self, grant: dict, full_configs: list[dict],
                                    authorization_document: dict) -> dict:
        """Trusted operator only: reserve existing quota without an execution debit.

        The human authorization must be checked by the operator. A caller able
        to write this ledger is trusted; hashes do not prove human provenance.
        The LLM proposal interface never calls this method.
        """
        # Freeze caller-owned objects before acquiring the transaction lock.
        grant, packages, authorization = json.loads(canonical_json([grant, full_configs, authorization_document]))
        if not isinstance(grant, dict):
            raise ValueError("Engineering round grant must be an object")
        validate_round_id(grant.get("round_id"))
        with self.store.locked(self.LOCK):
            state = self._replay()
            old = state["engineering_rounds"].get(grant["round_id"])
            if old is not None:
                original_authorization = self._read_round_reference(old["grant"]["authorization_ref"],
                                                                     "user-authorizations")
                if (old["grant"] != grant or old["initial_config_ids"] != [content_hash(item) for item in packages]
                        or canonical_json(original_authorization) != canonical_json(authorization)):
                    raise RegistryError("Engineering round identity cannot be overwritten")
                return self._round_snapshot(state, old)
            for package in packages:
                self._require_current_joint_storage(package)
            record = self._validate_round_authorization(state, grant, authorization, packages)
            grant_ref = self._round_reference(grant, "authorizations")
            references = [self._round_reference(item, "configurations") for item in packages]
            self.store.write_once(grant["authorization_ref"]["key"], canonical_json(authorization))
            self.store.write_once(grant_ref["key"], canonical_json(grant))
            for reference, package in zip(references, packages):
                self.store.write_once(reference["key"], canonical_json(package))
            self._append({"kind": "engineering_round_authorized", "grant_ref": grant_ref,
                          "configuration_refs": references})
            return self._round_snapshot(state, record)


    def bind_engineering_configuration(self, round_id: str, full_config: dict) -> str:
        """Explicitly bind a new repair hash; never expand the original grant."""
        validate_round_id(round_id)
        package = json.loads(canonical_json(full_config))
        identity = content_hash(package)
        with self.store.locked(self.LOCK):
            state = self._replay()
            if round_id not in state["engineering_rounds"]:
                raise RegistryError("Unknown engineering round")
            record = state["engineering_rounds"][round_id]
            if state["engineering_round_configs"].get(identity) == round_id:
                return identity
            self._require_current_joint_storage(package)
            self._validate_round_binding(state, record, package)
            reference = self._round_reference(package, "configurations")
            self.store.write_once(reference["key"], canonical_json(package))
            self._append({"kind": "engineering_round_configuration_bound", "round_id": round_id,
                          "configuration_ref": reference})
            return identity


    @staticmethod
    def _validate_round_close(state: dict, record: dict, reason: str) -> None:
        if record["status"] != "open" or not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
            raise RegistryError("Closing a round requires its open state and a bounded reason")
        if any(item["config_id"] in record["config_ids"] and item["status"] in _OPEN_STATES
               for item in state["attempts"].values()):
            raise RegistryError("Unresolved round tasks require reconciliation before close")


    def close_engineering_round(self, round_id: str, reason: str) -> dict:
        validate_round_id(round_id)
        with self.store.locked(self.LOCK):
            state = self._replay()
            if round_id not in state["engineering_rounds"]:
                raise RegistryError("Unknown engineering round")
            record = state["engineering_rounds"][round_id]
            if record["status"] == "closed" and record["close_reason"] == reason:
                return self._round_snapshot(state, record)
            self._validate_round_close(state, record, reason)
            self._append({"kind": "engineering_round_closed", "round_id": round_id, "reason": reason})
            record.update(status="closed", close_reason=reason)
            return self._round_snapshot(state, record)


    def _round_snapshot(self, state: dict, record: dict) -> dict:
        return json.loads(canonical_json({**record, "usage": self._round_usage(state, record)}))


    def engineering_rounds_snapshot(self) -> dict:
        with self.store.locked(self.LOCK):
            state = self._replay()
            return {identity: self._round_snapshot(state, record)
                    for identity, record in state["engineering_rounds"].items()}


    @staticmethod
    def _is_engineering_package(package: dict) -> bool:
        if not isinstance(package, dict):
            return False
        plan = package.get("plan")
        marked = "engineering_task_schema_version" in package
        engineering_plan = isinstance(plan, dict) and plan.get("scope") == "engineering"
        collection = RegistryEngineeringMixin._collection_candidate(plan)
        inventory = RegistryEngineeringMixin._inventory_candidate(plan)
        if not marked and not engineering_plan and not collection and not inventory:
            return False
        if (type(package.get("engineering_task_schema_version")) is not int
                or package["engineering_task_schema_version"] != 1
                or set(package) != {"engineering_task_schema_version", "plan"}
                or not engineering_plan):
            raise ValueError("Engineering packages require their complete fixed schema marker")
        if inventory:
            RegistryEngineeringMixin._inventory_plan(package)
        elif collection:
            RegistryEngineeringMixin._collection_plan(package)
        elif plan.get("schema_version") in {2, 3, 4}:
            # A joint pilot is one complete engineering configuration, never an
            # unvalidated bag of child jobs. Replays use its frozen catalog;
            # the dispatcher separately checks the trusted current catalog.
            from .engineering_tasks import EngineeringTaskPlan
            frozen = EngineeringTaskPlan.from_dict(plan, discovered_project_ids=(plan.get("project_id"),),
                                                  historical_decode=True)
            if frozen.to_dict() != plan:
                raise ValueError("Joint engineering registration requires its frozen canonical plan")
        return True


    @staticmethod
    def _inventory_candidate(plan: Any) -> bool:
        return isinstance(plan, dict) and (plan.get("task_kind") == "object_store_inventory"
            or "inventory_policy" in plan or "worker_sha256" in plan)


    @staticmethod
    def _inventory_plan(package: dict):
        if not isinstance(package, dict) or not RegistryEngineeringMixin._inventory_candidate(package.get("plan")):
            return None
        if (set(package) != {"engineering_task_schema_version", "plan"}
                or type(package.get("engineering_task_schema_version")) is not int
                or package["engineering_task_schema_version"] != 1):
            raise ValueError("Inventory tasks require their fixed engineering package marker")
        from .storage_inventory_tasks import InventoryTaskPlan
        raw = package["plan"]
        frozen = InventoryTaskPlan.from_dict(raw, discovered_project_ids=(raw.get("project_id"),))
        if frozen.to_dict() != raw:
            raise ValueError("Inventory registration requires its canonical frozen plan")
        return frozen


    def _inventory_admission(self, state, config_id, stage, operation_key, *, retry_of=None, allocation="normal"):
        package = json.loads(self.store.read_bytes("configurations/" + config_id + ".json"))
        plan = self._inventory_plan(package)
        if plan is None:
            return
        if (stage != "research" or operation_key != "object-store-inventory:" + plan.hash + ":research"
                or retry_of is not None or allocation != "normal"):
            raise RegistryError("Inventory permits one fixed normal Research operation and no retry")
        own_id = state["engineering_round_configs"].get(config_id)
        if own_id is None:
            raise BudgetExceeded("Inventory requires an explicit user-authorized engineering round")
        grant = state["engineering_rounds"][own_id]["grant"]
        if (grant["schema_version"] != 2 or grant["allocation"] != "normal"
                or grant["limits"] != {"configurations": 1, "research": 1, "lean": 0}):
            raise RegistryError("Inventory requires a version2 normal grant bounded to1 configuration/1 Research/0 LEAN")
        if any(r["config_id"] == config_id and r["stage"] == stage for r in state["attempts"].values()):
            raise RegistryError("Inventory has no second execution or retry")


    @staticmethod
    def _collection_candidate(plan: Any) -> bool:
        # Reserved collection shape must not become an unbounded generic task
        # by dropping the envelope marker or changing scope/task_kind.
        return isinstance(plan, dict) and (plan.get("task_kind") in {"historical_collection", "data_certification"}
            or "collection_plan" in plan or "field_catalog" in plan or "certification_plan" in plan
            or "input_refs" in plan or "source_binding" in plan)


    @staticmethod
    def _collection_plan(package: dict):
        if not isinstance(package, dict) or not RegistryEngineeringMixin._collection_candidate(package.get("plan")):
            return None
        plan = package["plan"]
        if (set(package) != {"engineering_task_schema_version", "plan"}
                or type(package.get("engineering_task_schema_version")) is not int
                or package["engineering_task_schema_version"] != 1):
            raise ValueError("Collection tasks require the shared engineering package marker")
        # Certification is an explicit new Research-only schema. Reserved keys
        # cannot downgrade to generic engineering by changing just task_kind.
        if (plan.get("task_kind") == "data_certification" or "certification_plan" in plan
                or "input_refs" in plan or "source_binding" in plan):
            from .certification_tasks import CertificationTaskPlan
            catalog = plan.get("certification_plan", {}).get("financial_catalog") if isinstance(plan.get("certification_plan"), dict) else None
            frozen = CertificationTaskPlan.from_dict(plan,
                discovered_project_ids=(plan.get("project_id"),), financial_catalog=catalog)
            if frozen.to_dict() != plan:
                raise ValueError("Certification registration requires its frozen canonical plan")
            return frozen
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
        prefix = "certification-plan:" if plan is not None and plan.to_dict().get("task_kind") == "data_certification" else "collection-plan:"
        if plan is not None and (stage != "research"
                or operation_key != prefix + plan.hash + ":research"):
            raise RegistryError("Collection tasks permit only their fixed Research operation")


    @staticmethod
    def _joint_engineering_plan(package: dict):
        """Return strict v2/v3/v4 metadata; legacy v1 claims stay unchanged."""
        if not RegistryEngineeringMixin._is_engineering_package(package) or package["plan"].get("schema_version") not in {2, 3, 4}:
            return None
        from .engineering_tasks import EngineeringTaskPlan
        plan = package["plan"]
        return EngineeringTaskPlan.from_dict(plan, discovered_project_ids=(plan["project_id"],),
                                             historical_decode=True)


    @staticmethod
    def _require_current_joint_storage(package: dict) -> None:
        """New admission stays strict while persisted package decoding survives."""
        if (isinstance(package, dict) and isinstance(package.get("plan"), dict)
                and package["plan"].get("schema_version") in {2, 3, 4}
                and package["plan"].get("scope") == "engineering"):
            from .engineering_tasks import EngineeringTaskPlan
            document = package["plan"]
            EngineeringTaskPlan.from_dict(document,
                discovered_project_ids=(document.get("project_id"),))


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
        self._require_current_joint_storage(package)
        identity = content_hash(package)
        own_id = state["engineering_round_configs"].get(identity)
        if package["plan"].get("task_kind") == "data_certification" and own_id is None:
            raise BudgetExceeded("Certification requires an explicitly user-authorized engineering round")
        if self._inventory_plan(package) is not None:
            if kind == "lean" or own_id is None:
                raise BudgetExceeded("Inventory requires its explicit Research-only round")
            grant = state["engineering_rounds"][own_id]["grant"]
            if (grant["schema_version"] != 2 or grant["allocation"] != "normal"
                    or grant["limits"] != {"configurations": 1, "research": 1, "lean": 0}):
                raise RegistryError("Inventory requires its exact version2 normal1/1/0 grant")
        if own_id is not None:
            record = state["engineering_rounds"][own_id]
            if record["status"] != "open" or self._round_usage(state, record)[kind] >= record["grant"]["limits"][kind]:
                raise BudgetExceeded("Authorized engineering round limit reached for " + kind)
            return
        # The original round retains its exact stop. Explicit subsequent grants
        # neither increase this cap nor turn old charged identities into new work.
        selected = self._engineering_config_ids(state) - set(state["engineering_round_configs"])
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
        if kind not in RESOURCES:
            raise ValueError("Unknown engineering admission resource")
        encoded = canonical_json(full_config)
        identity = sha256(encoded).hexdigest()
        with self.store.locked(self.LOCK):
            state = self._replay()
            package = json.loads(encoded)
            collection = self._collection_plan(package)
            if collection is not None and kind == "lean":
                raise RegistryError("Collection tasks permit only Research admission")
            if self._inventory_plan(package) is not None and kind == "lean":
                raise RegistryError("Inventory permits only Research admission")
            if kind == "configurations" and identity in state["configs"]:
                return
            same = [record for record in state["attempts"].values()
                    if record["config_id"] == identity and record["stage"] == kind]
            if same and same[-1]["status"] in _OPEN_STATES | {"completed"}:
                return
            if collection is not None or kind != "configurations":
                self._enforce_engineering_project(state, package)
            self._enforce_engineering_limit(state, kind, package)

    def _certification_transition(self, state: dict, record: dict, kind: str, *, fields=None, result=None) -> None:
        """New explicit certification tasks require original native proof.

        Called under LOCK, including replay; no Registry/Bridge public reader
        may be called from the pure metadata validator.
        """
        package = json.loads(self.store.read_bytes("configurations/" + record["config_id"] + ".json"))
        if not isinstance(package, dict) or not isinstance(package.get("plan"), dict) or package["plan"].get("task_kind") != "data_certification":
            return
        from .certification_tasks import validate_registry_transition
        try:
            validate_registry_transition(self.store, package, record, kind, fields=fields, result=result)
        except (KeyError, TypeError, ValueError, OSError) as error:
            raise RegistryError("Certification transition requires original fixed-parser native evidence") from error


    def _inventory_transition(self, state: dict, record: dict, kind: str, *, fields=None, result=None) -> None:
        package = json.loads(self.store.read_bytes("configurations/" + record["config_id"] + ".json"))
        if self._inventory_plan(package) is None:
            return
        from .storage_inventory_tasks import validate_registry_transition
        try:
            validate_registry_transition(self.store, package, record, kind, fields=fields, result=result)
        except (KeyError, TypeError, ValueError, OSError) as error:
            raise RegistryError("Inventory transition requires original fixed-parser native evidence") from error


