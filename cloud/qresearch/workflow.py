"""Durable development workflow, with budget admission before remote work.

This module never polls, executes a model prompt, opens final-test data, or
submits an order. An injected adapter owns approved remote I/O. The controller
persists its state and delegates accounting to the existing Registry; it is
not a second budget ledger. Real row-level market payloads must remain in QC.
"""
from copy import deepcopy
from datetime import datetime
import json
import math
import re

from .artifacts import canonical_json, content_hash, decode_events
from .contracts import DEVELOPMENT_END, aware
from .registry import BudgetExceeded


class WorkflowError(RuntimeError):
    """Invalid transition, missing evidence, or unapproved execution."""


class SubmissionRejected(WorkflowError):
    """Adapter positively observed rejection before a remote job was accepted.

    A timeout/connection error MUST NOT be wrapped in this exception. Its
    remote outcome is unknown and is recorded as ambiguous instead.
    """


_IDENTITY_HASHES = ("code_hash", "data_hash", "universe_hash", "label_hash",
                    "factor_set_hash", "model_hash", "trading_hash")
_OPERATORS = {">=", ">", "<=", "<", "=="}
_TRANSITIONS = {
    "registered": {"audited", "blocked"},
    "audited": {"data_ready", "blocked"},
    "data_ready": {"research_claimed", "blocked"},
    "research_claimed": {"research_submitted", "research_completed", "research_failed", "research_ambiguous"},
    "research_submitted": {"research_completed", "research_failed", "research_ambiguous"},
    "research_ambiguous": {"research_completed", "research_failed"},
    "research_failed": {"research_claimed", "blocked", "development_archived"},
    "research_completed": {"research_passed", "research_rejected"},
    "research_rejected": {"development_archived"},
    "research_passed": {"lean_claimed", "blocked"},
    "lean_claimed": {"lean_submitted", "lean_completed", "lean_failed", "lean_ambiguous"},
    "lean_submitted": {"lean_completed", "lean_failed", "lean_ambiguous"},
    "lean_ambiguous": {"lean_completed", "lean_failed"},
    "lean_failed": {"lean_claimed", "blocked", "development_archived"},
    "lean_completed": {"lean_passed", "lean_rejected"},
    "lean_rejected": {"development_archived"},
    "lean_passed": {"development_archived"},
    "blocked": {"development_archived"},
    "development_archived": {"frozen"},
    "frozen": set(),
}


def _hash(value, label):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise WorkflowError(label + " must be a canonical SHA-256 identity")
    return value


def _count(value, label, positive=False):
    if type(value) is not int or value < int(positive):
        raise WorkflowError(label + " must be a bounded nonnegative integer")
    return value


def _rules(rules):
    if not isinstance(rules, list) or not rules:
        raise WorkflowError("Every stage needs explicit preregistered acceptance rules")
    for rule in rules:
        if (not isinstance(rule, dict) or set(rule) != {"field", "op", "value"}
                or not isinstance(rule["field"], str)
                or re.fullmatch(r"(statistics|checks)\.[A-Za-z][A-Za-z0-9_]*", rule["field"]) is None
                or rule["op"] not in _OPERATORS):
            raise WorkflowError("Rules require an explicit statistics/check field, comparator and value")
        value = rule["value"]
        if isinstance(value, bool):
            if not rule["field"].startswith("checks.") or rule["op"] != "==":
                raise WorkflowError("Boolean checks permit explicit equality only")
        elif type(value) not in (int, float) or not math.isfinite(value):
            raise WorkflowError("Acceptance thresholds must be finite numbers or boolean checks")


def _campaign(raw):
    value = json.loads(canonical_json(raw))
    required = {"schema_version", "phase", "scope", "fixed_trading_hash", "audit_issuers",
                "required_audit_checks", "max_candidates", "max_research_retries",
                "max_lean_retries", "decision_rules"}
    if not required <= set(value) or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise WorkflowError("A complete versioned campaign policy is required")
    if value["phase"] not in {"factor", "model"} or value["scope"] not in {"engineering", "research"}:
        raise WorkflowError("Only registered development factor/model campaigns are supported")
    _hash(value["fixed_trading_hash"], "fixed_trading_hash")
    pin = "fixed_model_hash" if value["phase"] == "factor" else "fixed_factor_set_hash"
    _hash(value.get(pin), pin)
    _count(value["max_candidates"], "max_candidates", positive=True)
    for stage in ("research", "lean"):
        _count(value["max_" + stage + "_retries"], "max retries")
        _rules(value["decision_rules"].get(stage))
    if (not isinstance(value["audit_issuers"], list) or not value["audit_issuers"]
            or any(not isinstance(x, str) or not x for x in value["audit_issuers"])):
        raise WorkflowError("Trusted fixed-program audit issuers must be declared")
    for purpose in ("formula_timing", "data_coverage"):
        checks = value["required_audit_checks"].get(purpose)
        if not isinstance(checks, list) or not checks or any(not isinstance(x, str) or not x for x in checks):
            raise WorkflowError("Required named audit checks must be declared per purpose")
    return value


class WorkflowController:
    """One state machine per full configuration, using one authoritative Registry.

    Adapter protocol: submit_research(payload, operation_key=...) and
    submit_backtest(payload, operation_key=...) return {external_id, status}.
    Even a receipt saying 'completed' is only recorded as submitted; an explicit
    matching terminal result must be consumed separately. No implicit polling.

    Audit validator protocol matches AuditEvidence.from_dict. A validator is a
    trusted program component, never an LLM callback that supplies approval bits.
    """

    def __init__(self, registry, adapter, *, campaign, audit_validator=None,
                 field_catalog=None, operator_catalog=None):
        self.registry, self.store, self.adapter = registry, registry.store, adapter
        self.campaign = _campaign(campaign)
        self.campaign_hash = content_hash(self.campaign)
        self.audit_validator = audit_validator
        self.field_catalog = deepcopy(field_catalog)
        self.operator_catalog = deepcopy(operator_catalog)
        self.store.write_once("workflow/campaigns/" + self.campaign_hash + ".json",
                              canonical_json(self.campaign))

    def _stream(self, config_id):
        _hash(config_id, "config_id")
        return "workflow/" + self.campaign_hash + "/" + config_id + ".jsonl"

    def _lock(self, config_id):
        return "workflow/transaction/" + self.campaign_hash + "/" + config_id

    def _identity(self, raw):
        identity = json.loads(canonical_json(raw))
        if not set(identity) <= set(_IDENTITY_HASHES) | {"data_end_exclusive", "data_version"}:
            raise WorkflowError("Unknown identity fields cannot supply unregistered execution overrides")
        for key in _IDENTITY_HASHES:
            _hash(identity.get(key), key)
        end = aware(identity.get("data_end_exclusive"))
        if end > DEVELOPMENT_END:
            raise WorkflowError("Final-test data are unavailable to the development controller")
        if identity["trading_hash"] != self.campaign["fixed_trading_hash"]:
            raise WorkflowError("Trading design changed during a fixed campaign")
        pin, target = (("fixed_model_hash", "model_hash") if self.campaign["phase"] == "factor"
                       else ("fixed_factor_set_hash", "factor_set_hash"))
        if identity[target] != self.campaign[pin]:
            raise WorkflowError("Pinned factor/model design changed during this campaign")
        identity["data_end_exclusive"] = end.isoformat()
        return identity

    def _configuration(self, config_id):
        value = json.loads(self.store.read_bytes("configurations/" + config_id + ".json"))
        if content_hash(value) != config_id or value.get("campaign_hash") != self.campaign_hash:
            raise WorkflowError("Configuration belongs to another campaign or has changed")
        if value.get("workflow_schema_version") != 1:
            raise WorkflowError("Unsupported workflow configuration")
        self._identity(value["identity"])
        if self.campaign["scope"] == "research":
            self._validated_study(value["study"], value["identity"])
        return value

    def _validated_study(self, full_config, identity):
        """Production scope cannot register an arbitrary JSON approval package.

        data_hash identifies the declared source/version binding. Raw-data
        snapshot integrity still needs the separate coverage audit; this digest
        must not be described as certification of vendor data contents.
        """
        from .study import StudySpec
        if not self.field_catalog:
            raise WorkflowError("Production studies require a trusted field catalog")
        raw = full_config.to_dict() if isinstance(full_config, StudySpec) else full_config
        study = StudySpec.from_dict(raw, field_catalog=self.field_catalog,
                                   operator_catalog=self.operator_catalog, require_trading=True)
        document = study.to_dict()
        if document["purpose"] != "research" or document["research_phase"] != self.campaign["phase"]:
            raise WorkflowError("Study purpose/phase does not match its research campaign")
        components, binding = document["component_hashes"], document["data_binding"]
        expected = {"code_hash": binding["code_hash"], "data_hash": content_hash(binding),
                    "universe_hash": binding["universe_hash"], "label_hash": components["label"],
                    "factor_set_hash": content_hash(components["factors"]), "model_hash": components["model"],
                    "trading_hash": components["trading"],
                    "data_end_exclusive": aware(document["development"]["end_exclusive"]).isoformat()}
        if any(identity.get(key) != value for key, value in expected.items()):
            raise WorkflowError("Workflow identity does not match the study's actual frozen components")
        if "data_version" in identity and identity["data_version"] != binding["data_version"]:
            raise WorkflowError("Workflow data version differs from the frozen study")
        return study

    def register(self, full_config, identity, *, allocation="normal"):
        identity = self._identity(identity)
        if self.campaign["scope"] == "research":
            full_config = self._validated_study(full_config, identity).to_dict()
        package = {"workflow_schema_version": 1, "study": full_config, "identity": identity,
                   "campaign_hash": self.campaign_hash}
        config_id = content_hash(package)
        with self.store.locked("workflow/register/" + self.campaign_hash):
            snapshot = self.registry.snapshot()
            existing = snapshot["config_ids"]
            count = sum(json.loads(self.store.read_bytes("configurations/" + key + ".json")).get(
                "campaign_hash") == self.campaign_hash for key in existing)
            if config_id not in existing and count >= self.campaign["max_candidates"]:
                raise WorkflowError("Preregistered candidate count reached")
            registered = self.registry.register_config(package, allocation=allocation)
            with self.store.locked(self._lock(registered)):
                if not self.store.exists(self._stream(registered)):
                    self.store.append_event(self._stream(registered), {"kind": "initialized", "schema_version": 1,
                        "config_id": registered, "campaign_hash": self.campaign_hash,
                        "identity_hash": content_hash(identity)})
                self._state(registered)
            return registered

    def _state(self, config_id):
        package = self._configuration(config_id)
        records = decode_events(self.store.read_bytes(self._stream(config_id)))
        if not records or records[0]["event"] != {"kind": "initialized", "schema_version": 1,
                "config_id": config_id, "campaign_hash": self.campaign_hash,
                "identity_hash": content_hash(package["identity"])}:
            raise WorkflowError("Workflow journal initialization mismatch")
        state = {"config_id": config_id, "campaign_hash": self.campaign_hash, "status": "registered",
                 "identity": package["identity"], "attempts": {}, "results": {}, "decisions": {},
                 "audits": {}, "payload_hashes": {}, "archive": None}
        mutable = {"attempts", "results", "decisions", "audits", "payload_hashes", "archive", "reason", "freeze"}
        for envelope in records[1:]:
            event = envelope["event"]
            if event.get("kind") == "audit_rejected":
                if (event.get("at_state") != state["status"]
                        or state["status"] not in {"registered", "audited"}):
                    raise WorkflowError("Audit rejection record has an invalid state")
                continue
            if (event.get("kind") != "transition" or event.get("from") != state["status"]
                    or event.get("to") not in _TRANSITIONS[state["status"]]
                    or not set(event.get("updates", {})) <= mutable):
                raise WorkflowError("Invalid persisted workflow transition")
            state.update(event["updates"])
            state["status"] = event["to"]
        return state

    def _transition(self, state, target, **updates):
        if target not in _TRANSITIONS[state["status"]]:
            raise WorkflowError("Invalid transition " + state["status"] + " -> " + target)
        self.store.append_event(self._stream(state["config_id"]), {"kind": "transition",
            "from": state["status"], "to": target, "updates": updates})
        state.update(deepcopy(updates))
        state["status"] = target
        return state

    def _audit(self, state, raw, purpose):
        try:
            from .audits import verify_evidence
            if not isinstance(raw, dict) or raw.get("issuer") not in self.campaign["audit_issuers"]:
                raise WorkflowError("Audit issuer is not in the dispatcher's trusted allowlist")
            # Checking reference hashes alone does not bind the envelope's
            # outcome bits to the observed report. The strong verifier checks
            # both the immutable bytes and their actual named observations.
            evidence = verify_evidence(self.store, raw, subject_hash=state["config_id"],
                source_hash=state["identity"]["code_hash"], issuer=raw["issuer"],
                required_checks=self.campaign["required_audit_checks"][purpose],
                scope=self.campaign["scope"], require_passed=False)
            if self.audit_validator is not None:
                additional = self.audit_validator(raw, expected_subject_hash=state["config_id"],
                    expected_source_hash=state["identity"]["code_hash"], allowed_issuers=self.campaign["audit_issuers"])
                if not callable(getattr(additional, "to_dict", None)) or additional.to_dict() != evidence.to_dict():
                    raise WorkflowError("Additional audit validation cannot replace observed evidence")
            if (not callable(getattr(evidence, "to_dict", None))
                    or not callable(getattr(evidence, "verify_references", None))
                    or type(getattr(evidence, "passed", None)) is not bool):
                raise WorkflowError("A verified evidence object is required, not an approval boolean")
            evidence.verify_references(self.store)
            document = evidence.to_dict()
            names = {entry["name"] for entry in document["checks"]}
            if (document.get("scope") != self.campaign["scope"] or
                    not set(self.campaign["required_audit_checks"][purpose]) <= names):
                raise WorkflowError("Audit evidence scope or required checks do not match")
        except Exception as exc:
            # Retain rejected gates; never swallow the validation exception.
            self.store.append_event(self._stream(state["config_id"]), {"kind": "audit_rejected",
                "at_state": state["status"], "purpose": purpose, "error_type": type(exc).__name__})
            raise
        key = "workflow/evidence/" + content_hash(document) + ".json"
        self.store.write_once(key, canonical_json(document))
        audits = dict(state["audits"], **{purpose: {"key": key, "hash": content_hash(document)}})
        target = ("audited" if purpose == "formula_timing" else "data_ready") if evidence.passed else "blocked"
        return self._transition(state, target, audits=audits,
                                reason=None if evidence.passed else "Audit checks failed: " + purpose)

    def audit(self, config_id, evidence):
        with self.store.locked(self._lock(config_id)):
            state = self._state(config_id)
            if state["status"] != "registered":
                raise WorkflowError("Formula/time audit must follow registration")
            return deepcopy(self._audit(state, evidence, "formula_timing"))

    def data_ready(self, config_id, evidence):
        with self.store.locked(self._lock(config_id)):
            state = self._state(config_id)
            if state["status"] != "audited":
                raise WorkflowError("Data coverage audit must follow formula/time audit")
            return deepcopy(self._audit(state, evidence, "data_coverage"))

    def _operation(self, config_id, stage):
        return "workflow:" + self.campaign_hash + ":" + config_id + ":" + stage

    def _request_key(self, config_id, stage):
        return "workflow/requests/" + self.campaign_hash + "/" + config_id + "/" + stage + ".json"

    def _attempt_records(self, config_id, stage):
        return [record for record in self.registry.snapshot()["attempts"]
                if record["config_id"] == config_id and record["stage"] == stage
                and record["operation_key"] == self._operation(config_id, stage)]

    def _result(self, state, stage, attempt, external_id, result):
        if (not isinstance(result, dict) or result.get("terminal") is not True
                or result.get("status") not in {"completed", "failed"}
                or result.get("external_id") != external_id
                or result.get("config_id") != state["config_id"] or result.get("stage") != stage
                or result.get("attempt_id") != attempt["attempt_id"]
                or result.get("identity_hash") != content_hash(state["identity"])
                or result.get("operation_key") != self._operation(state["config_id"], stage)):
            raise WorkflowError("Only a matching terminal execution result can finish a stage")
        if attempt.get("external_id") is not None and external_id != attempt["external_id"]:
            raise WorkflowError("Terminal task identity differs from its submission receipt")
        if not isinstance(external_id, str) or not external_id:
            raise WorkflowError("An observed external task identity is required")
        canonical_json(result)
        return result

    def _recover(self, state):
        """Replay Registry writes missing a workflow transition, without resubmit."""
        for stage in ("research", "lean"):
            records = self._attempt_records(state["config_id"], stage)
            if not records:
                continue
            attempt = records[-1]
            finished = state["results"].get(stage)
            if finished and finished["attempt_id"] == attempt["attempt_id"]:
                continue
            if state["attempts"].get(stage, {}).get("attempt_id") != attempt["attempt_id"]:
                key = self._request_key(state["config_id"], stage)
                if not self.store.exists(key):
                    raise WorkflowError("Attempt has no frozen request plan; explicit reconciliation required")
                request_hash = content_hash(json.loads(self.store.read_bytes(key)))
                attempts = dict(state["attempts"], **{stage: {"attempt_id": attempt["attempt_id"],
                    "external_id": attempt.get("external_id"), "status": attempt["status"]}})
                hashes = dict(state["payload_hashes"], **{stage: request_hash})
                self._transition(state, stage + "_claimed", attempts=attempts, payload_hashes=hashes)
            registry_status = attempt["status"]
            if registry_status == "completed":
                result = self.registry.read_result(attempt["attempt_id"])
                self._result(state, stage, attempt, attempt["external_id"], result)
                results = dict(state["results"], **{stage: {"attempt_id": attempt["attempt_id"],
                    "hash": content_hash(result), "key": attempt["result_key"], "status": "completed"}})
                self._transition(state, stage + "_completed", results=results)
            elif registry_status == "failed":
                results = dict(state["results"], **{stage: {"attempt_id": attempt["attempt_id"], "status": "failed"}})
                self._transition(state, stage + "_failed", results=results, reason="Remote attempt failed")
            elif registry_status in {"pending", "ambiguous"}:
                target = stage + ("_submitted" if registry_status == "pending" else "_ambiguous")
                attempts = dict(state["attempts"], **{stage: {"attempt_id": attempt["attempt_id"],
                    "external_id": attempt.get("external_id"), "status": registry_status}})
                if state["status"] != target:
                    self._transition(state, target, attempts=attempts)
        return state

    def status(self, config_id):
        with self.store.locked(self._lock(config_id)):
            return deepcopy(self._recover(self._state(config_id)))

    def submit(self, config_id, stage, payload, *, allocation="normal", retry_of=None, reason=None):
        if stage not in {"research", "lean"}:
            raise WorkflowError("Final evaluation belongs to an independent executor")
        if self.campaign["scope"] == "research":
            # Stage 0/1 supplies the durable controller and contract checks.
            # Production dispatch stays closed until a real QC task-plan and
            # publication adapter can bind the exact registered source/data.
            raise WorkflowError("Market dispatch is disabled until its QC task-plan adapter is certified")
        if not isinstance(payload, dict) or "_workflow" in payload:
            raise WorkflowError("Task payload must be metadata with no reserved workflow envelope")
        payload_hash = content_hash(payload)
        with self.store.locked(self._lock(config_id)):
            state = self._recover(self._state(config_id))
            records = self._attempt_records(config_id, stage)
            if records and records[-1]["status"] != "failed":
                return deepcopy(state)
            prerequisite = "data_ready" if stage == "research" else "research_passed"
            if state["status"] not in {prerequisite, stage + "_failed"}:
                raise WorkflowError("Stage prerequisites have not passed")
            pinned_payload = state["payload_hashes"].get(stage)
            if pinned_payload is not None and pinned_payload != payload_hash:
                raise WorkflowError("Changed payload requires a new full configuration")
            if records:
                if retry_of is None:
                    return deepcopy(state)
                if len(records) > self.campaign["max_" + stage + "_retries"]:
                    self._transition(state, "blocked", reason="Preregistered repair count reached")
                    raise WorkflowError("Preregistered repair count reached")
            # Freeze the request before admission, so a crash between the
            # Registry debit and workflow claim cannot lose its identity.
            self.store.write_once(self._request_key(config_id, stage), canonical_json(payload))
            try:
                attempt = self.registry.begin_attempt(config_id, stage, allocation=allocation,
                    operation_key=self._operation(config_id, stage), retry_of=retry_of, reason=reason)
            except BudgetExceeded:
                self._transition(state, "blocked", reason="Execution budget exhausted")
                raise
            if not attempt.should_execute:
                return deepcopy(self._recover(state))
            attempts = dict(state["attempts"], **{stage: {"attempt_id": attempt.attempt_id,
                              "external_id": None, "status": "started"}})
            payload_hashes = dict(state["payload_hashes"], **{stage: payload_hash})
            self._transition(state, stage + "_claimed", attempts=attempts, payload_hashes=payload_hashes)
            enriched = dict(payload, _workflow={"config_id": config_id, "identity_hash": content_hash(state["identity"]),
                "identity": state["identity"], "stage": stage, "attempt_id": attempt.attempt_id,
                "operation_key": self._operation(config_id, stage)})
            method = self.adapter.submit_research if stage == "research" else self.adapter.submit_backtest
            try:
                receipt = method(enriched, operation_key=self._operation(config_id, stage))
                if (not isinstance(receipt, dict) or not isinstance(receipt.get("external_id"), str)
                        or not receipt["external_id"] or receipt.get("status") not in {"submitted", "accepted", "queued", "completed"}):
                    raise WorkflowError("Submission receipt omitted an accepted external task identity")
            except SubmissionRejected as exc:
                self.registry.fail(attempt, {"type": "confirmed_rejection", "reason": str(exc)})
                return deepcopy(self._recover(state))
            except Exception as exc:
                self.registry.ambiguous(attempt, reason="Submission outcome unknown: " + type(exc).__name__)
                return deepcopy(self._recover(state))
            self.registry.pending(attempt, external_id=receipt["external_id"],
                                  details={"receipt_status": receipt["status"]})
            return deepcopy(self._recover(state))

    def consume_result(self, config_id, stage, external_id, result):
        if stage not in {"research", "lean"}:
            raise WorkflowError("Final-test results cannot enter development feedback")
        with self.store.locked(self._lock(config_id)):
            state = self._recover(self._state(config_id))
            records = self._attempt_records(config_id, stage)
            if not records:
                raise WorkflowError("No submitted attempt exists")
            attempt = records[-1]
            self._result(state, stage, attempt, external_id, result)
            if attempt["status"] == "completed":
                if self.registry.read_result(attempt["attempt_id"]) != result:
                    raise WorkflowError("Completed result cannot be replaced")
                return deepcopy(state)
            key = "workflow/terminal-evidence/" + content_hash(result) + ".json"
            self.store.write_once(key, canonical_json(result))
            if result["status"] == "failed":
                self.registry.fail(attempt["attempt_id"], {"terminal_evidence_key": key}, reconciliation=content_hash(result))
            else:
                self.registry.complete(attempt["attempt_id"], result, external_id=external_id)
            return deepcopy(self._recover(state))

    def decide(self, config_id, stage):
        if stage not in {"research", "lean"}:
            raise WorkflowError("Only development decisions are supported")
        with self.store.locked(self._lock(config_id)):
            state = self._recover(self._state(config_id))
            if stage in state["decisions"]:
                return deepcopy(state)
            if state["status"] != stage + "_completed":
                raise WorkflowError("A completed computation is required before evaluation")
            result = self.registry.read_result(state["results"][stage]["attempt_id"])
            outcomes = []
            for rule in self.campaign["decision_rules"][stage]:
                namespace, name = rule["field"].split(".")
                actual = result.get(namespace, {}).get(name)
                threshold = rule["value"]
                if isinstance(threshold, bool):
                    valid = type(actual) is bool
                else:
                    valid = type(actual) in (int, float) and math.isfinite(actual)
                if not valid:
                    passed = False
                elif rule["op"] == ">=":
                    passed = actual >= threshold
                elif rule["op"] == ">":
                    passed = actual > threshold
                elif rule["op"] == "<=":
                    passed = actual <= threshold
                elif rule["op"] == "<":
                    passed = actual < threshold
                else:
                    passed = actual == threshold
                outcomes.append({"rule": rule, "passed": bool(passed), "missing_or_invalid": not valid})
            accepted = all(item["passed"] for item in outcomes)
            verdict = ("insufficient_evidence" if any(item["missing_or_invalid"] for item in outcomes)
                       else "accepted" if accepted else "rejected")
            decisions = dict(state["decisions"], **{stage: {"accepted": accepted, "verdict": verdict, "rules": outcomes,
                "result_hash": state["results"][stage]["hash"], "policy_hash": self.campaign_hash}})
            return deepcopy(self._transition(state, stage + ("_passed" if accepted else "_rejected"), decisions=decisions))

    def archive(self, config_id, *, note=""):
        with self.store.locked(self._lock(config_id)):
            state = self._recover(self._state(config_id))
            if state["status"] in {"development_archived", "frozen"}:
                return deepcopy(state)
            if "development_archived" not in _TRANSITIONS[state["status"]]:
                raise WorkflowError("Unresolved tasks or uncomputed decisions cannot be archived")
            verdict = "accepted" if state["status"] == "lean_passed" else (
                "rejected" if state["status"].endswith("_rejected") else "insufficient_evidence")
            for stage in ("lean", "research"):
                if state["status"] == stage + "_rejected":
                    verdict = state["decisions"][stage]["verdict"]
            return deepcopy(self._transition(state, "development_archived", archive={"verdict": verdict,
                "note": str(note), "final_test_performed": False}))

    def freeze(self, config_id):
        with self.store.locked(self._lock(config_id)):
            state = self._recover(self._state(config_id))
            if state["status"] == "frozen":
                return deepcopy(state)
            if state["status"] != "development_archived" or state["archive"]["verdict"] != "accepted":
                raise WorkflowError("Only an accepted archived development design can be frozen")
            package = {"schema_version": 1, "config_id": config_id, "identity": state["identity"],
                "campaign_hash": self.campaign_hash, "audits": state["audits"],
                "development_results": state["results"], "decisions": state["decisions"],
                "final_execution_enabled": False, "independent_executor_required": True}
            key = "workflow/frozen/" + content_hash(package) + ".json"
            self.store.write_once(key, canonical_json(package))
            return deepcopy(self._transition(state, "frozen", freeze={"key": key, "hash": content_hash(package)}))
