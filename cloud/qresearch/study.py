"""Versioned study contracts and dispatcher-verified audit evidence.

These validators establish shape, identity and explicit design bindings. They
do not certify market coverage, prove an economic mechanism, sign an audit, or
authorize a remote execution. Issuer allowlists and expected hashes must come
from the trusted dispatcher, never from an LLM proposal.
"""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import math
import re
from collections.abc import Mapping

from .contracts import DEVELOPMENT_END, NY, aware
from .artifacts import canonical_json, content_hash, validate_key
from .factors import FactorSpec, OPERATORS, OPERATOR_ALIASES


class StudyValidationError(ValueError):
    """The frozen study or its evidence is incomplete or inconsistent."""


def _document(value, name):
    if not isinstance(value, Mapping):
        raise StudyValidationError(name + " must be an object")
    try:
        return json.loads(canonical_json(dict(value)))
    except (ValueError, TypeError) as exc:
        raise StudyValidationError(name + " must contain finite JSON values") from exc


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise StudyValidationError(name + " must be a nonempty string")
    return value


def _sha(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise StudyValidationError(name + " must be a lowercase SHA256 digest")
    return value


def _number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise StudyValidationError(name + " must be finite numeric data")
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise StudyValidationError(name + " is outside its permitted range")
    return value


def _complete(value, name):
    """A semantic rule may be a named rule or a nonempty structured object."""
    if isinstance(value, str):
        return _text(value, name)
    if isinstance(value, Mapping) and value:
        result = _document(value, name)
        if _has_unknown(result):
            raise StudyValidationError(name + " contains unspecified values")
        return result
    raise StudyValidationError(name + " must be an explicit rule or nonempty object")


def _has_unknown(value):
    if value is None:
        return True
    if isinstance(value, Mapping):
        return any(_has_unknown(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_unknown(item) for item in value)
    return False


def _local_bound(value, name):
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return aware(datetime.fromisoformat(value).replace(tzinfo=NY))
        except ValueError as exc:
            raise StudyValidationError(name + " is not a valid NY calendar date") from exc
    try:
        return aware(value)
    except (ValueError, TypeError) as exc:
        raise StudyValidationError(name + " needs an explicit zone, or an NY calendar date") from exc


def _reserved_feature(name):
    tokens = re.split(r"[^a-z0-9]+", name.lower())
    return any(t in {"label", "labels", "target", "targets", "future", "forward",
                     "formation", "entry", "exit", "available", "sid"} for t in tokens)


def _validate_acceptance(raw):
    result = _document(raw, "preregistered_acceptance")
    if set(result) != {"logic", "metrics"} or result["logic"] != "all":
        raise StudyValidationError("Acceptance requires frozen all-of metric rules")
    if not isinstance(result["metrics"], list) or not result["metrics"]:
        raise StudyValidationError("Acceptance metric rules cannot be empty")
    names = set()
    for metric in result["metrics"]:
        item = _document(metric, "acceptance metric")
        if set(item) != {"name", "operator", "value", "min_observations", "scope"}:
            raise StudyValidationError("Each acceptance rule needs its metric, bound, sample floor and development scope")
        name = _text(item["name"], "acceptance.name")
        if name in names:
            raise StudyValidationError("Acceptance metric names must be unique")
        names.add(name)
        if item["operator"] not in {"gt", "gte", "lt", "lte", "eq"}:
            raise StudyValidationError("Unknown acceptance comparison")
        _number(item["value"], "acceptance.value")
        if type(item["min_observations"]) is not int or item["min_observations"] < 1:
            raise StudyValidationError("Acceptance requires a positive observation floor")
        if item["scope"] not in {"training", "validation", "development"}:
            raise StudyValidationError("Final-test results cannot select the research design")
    return result


def validate_trading_spec(raw, *, purpose):
    """Validate explicit trading design, without inventing fees or risk limits."""
    result = _document(raw, "trading_spec")
    required = {"schema_version", "capital", "account_type", "position_construction",
                "rebalance_rule", "entry_rule", "exit_rule", "costs", "fills", "risk",
                "stress_tests", "orders_enabled"}
    if not required <= set(result) or type(result.get("schema_version")) is not int or result["schema_version"] != 1:
        raise StudyValidationError("A complete version-1 trading specification is required")
    if result.get("status") == "template_not_registered":
        raise StudyValidationError("An unregistered trading template cannot execute")
    if _number(result["capital"], "capital", 0) == 0:
        raise StudyValidationError("Capital must be positive")
    _text(result["account_type"], "account_type")
    for key in ("position_construction", "rebalance_rule", "entry_rule", "exit_rule"):
        _complete(result[key], key)
    if type(result["orders_enabled"]) is not bool:
        raise StudyValidationError("orders_enabled must be explicit boolean data")
    costs = _document(result["costs"], "costs")
    if set(costs) != {"commission", "spread", "slippage", "impact", "borrow"}:
        raise StudyValidationError("Commission, spread, slippage, impact and borrow must all be declared")
    for name, raw_cost in costs.items():
        cost = _document(raw_cost, "costs." + name)
        if not {"model", "parameters", "unit"} <= set(cost):
            raise StudyValidationError("Each cost requires a model, parameters and units")
        model = _text(cost["model"], name + ".model")
        _text(cost["unit"], name + ".unit")
        parameters = _document(cost["parameters"], name + ".parameters")
        if not parameters or _has_unknown(parameters):
            raise StudyValidationError("Cost parameters cannot be omitted or unknown")
        numeric = [x for x in parameters.values() if type(x) in (int, float)]
        for value in numeric:
            _number(value, name + ".parameter", 0)
        explicitly_zero = model in {"zero", "none", "disabled", "not_applicable"} or (numeric and all(x == 0 for x in numeric))
        if explicitly_zero:
            _text(cost.get("zero_cost_reason"), name + ".zero_cost_reason")
    fills = _document(result["fills"], "fills")
    required_fills = {"order_type", "participation_cap", "stale_data_policy", "partial_fill_policy",
                      "corporate_action_and_delisting_rules"}
    if not required_fills <= set(fills):
        raise StudyValidationError("Fill timing, stale data, partial fills and corporate actions require rules")
    for name in required_fills - {"participation_cap"}:
        _complete(fills[name], "fills." + name)
    if _number(fills["participation_cap"], "participation_cap", 0, 1) == 0:
        raise StudyValidationError("Participation cap must be positive")
    risk = _document(result["risk"], "risk")
    required_risk = {"gross_exposure", "net_exposure", "single_security", "issuer", "sector", "beta", "drawdown"}
    if not required_risk <= set(risk):
        raise StudyValidationError("Exposure, concentration, beta and drawdown limits are required")
    for name in required_risk:
        bound = risk[name]
        if isinstance(bound, Mapping):
            if set(bound) != {"min", "max"}:
                raise StudyValidationError("Risk intervals need exactly min and max")
            lower, upper = _number(bound["min"], name + ".min"), _number(bound["max"], name + ".max")
            if lower > upper:
                raise StudyValidationError("Risk interval is reversed")
        else:
            value = _number(bound, "risk." + name, 0)
            if name not in {"net_exposure", "beta"} and value == 0:
                raise StudyValidationError("Risk cap must be positive")
            if name == "drawdown" and value > 1:
                raise StudyValidationError("Drawdown limit must be a fraction at most one")
    if not isinstance(result["stress_tests"], list) or not result["stress_tests"]:
        raise StudyValidationError("Stress scenarios must be preregistered")
    if any(not isinstance(x, Mapping) or not x for x in result["stress_tests"]):
        raise StudyValidationError("Stress scenarios must be nonempty structured objects")
    return result


@dataclass(frozen=True)
class StudySpec:
    canonical_json: str
    configuration_hash: str
    factor_specs: tuple

    @classmethod
    def from_dict(cls, document, *, field_catalog, require_trading=False, operator_catalog=None):
        from .labels import LabelProtocol
        from .models import ModelSpec
        data = _document(document, "StudySpec")
        permitted = {"schema_version", "study_id", "purpose", "synthetic", "timezone", "research_phase",
                     "factor_specs", "model_spec", "label_spec", "trading_spec", "data_binding", "development",
                     "final_evaluation", "preregistered_acceptance", "fixed_model_hash", "frozen_factor_hashes",
                     "feature_bindings", "component_hashes", "rolling_validation", "operator_catalog"}
        if set(data) - permitted:
            raise StudyValidationError("Unknown StudySpec fields: " + str(sorted(set(data) - permitted)))
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise StudyValidationError("Unsupported StudySpec schema version")
        _text(data.get("study_id"), "study_id")
        purpose = data.get("purpose")
        if purpose == "engineering":
            purpose = data["purpose"] = "engineering_fixture"
        if purpose not in {"engineering_fixture", "research"}:
            raise StudyValidationError("Purpose must distinguish synthetic engineering from research")
        if type(data.get("synthetic")) is not bool or data["synthetic"] != (purpose == "engineering_fixture"):
            raise StudyValidationError("Engineering fixtures must be synthetic; research cannot masquerade as a fixture")
        if data.get("timezone") != "America/New_York":
            raise StudyValidationError("Study timezone must be America/New_York")
        if data.get("research_phase") not in {"factor", "model"}:
            raise StudyValidationError("Explicit factor/model research phase required")
        if not field_catalog:
            raise StudyValidationError("A trusted nonempty field catalog is required")
        raw_factors = data.get("factor_specs")
        if not isinstance(raw_factors, list) or not raw_factors:
            raise StudyValidationError("At least one frozen FactorSpec is required")
        if any(not isinstance(x, Mapping) or type(x.get("schema_version")) is not int or x["schema_version"] != 1 for x in raw_factors):
            raise StudyValidationError("Factor specifications require version1")
        specs = tuple(FactorSpec.from_dict(x, field_catalog=field_catalog) for x in raw_factors)
        if len({x.factor_id for x in specs}) != len(specs):
            raise StudyValidationError("Factor IDs must be unique")
        if any(_reserved_feature(x.factor_id) for x in specs):
            raise StudyValidationError("Factor output identities cannot use label or metadata namespaces")
        approved_ops = set(OPERATORS)
        if operator_catalog is not None:
            approved_ops &= {OPERATOR_ALIASES.get(x, x) for x in operator_catalog}
        if any(not set(spec.allowed_operators) <= approved_ops for spec in specs):
            raise StudyValidationError("Factor operators exceed the trusted operator catalog")
        if "operator_catalog" in data:
            declared = {OPERATOR_ALIASES.get(x, x) for x in data["operator_catalog"]}
            if not declared <= approved_ops or any(not set(s.allowed_operators) <= declared for s in specs):
                raise StudyValidationError("Declared operator catalog does not match approved operations")
        model = ModelSpec.from_dict(data.get("model_spec"))
        label = LabelProtocol.from_dict(data.get("label_spec"))
        model_doc, label_doc = model.to_dict(), label.to_dict()
        if model_doc.get("purpose") != purpose or label_doc.get("purpose") != purpose:
            raise StudyValidationError("Model, label and study purposes must match")
        if model_doc.get("target_kind") != label_doc.get("target_kind"):
            raise StudyValidationError("Model target and execution label disagree")
        features = tuple(model_doc["features"])
        if any(_reserved_feature(x) for x in features):
            raise StudyValidationError("Labels and metadata cannot be model features")
        bindings = data.get("feature_bindings", {x: x for x in features})
        if not isinstance(bindings, dict) or set(bindings) != set(features) or not set(bindings.values()) <= {s.factor_id for s in specs}:
            raise StudyValidationError("Every model feature must bind to a declared factor output")
        data["feature_bindings"] = bindings
        if data["research_phase"] == "factor":
            if data.get("fixed_model_hash") != model.configuration_hash:
                raise StudyValidationError("Factor research must bind its exact fixed model design hash")
        else:
            if set(data.get("frozen_factor_hashes", [])) != {x.configuration_hash for x in specs}:
                raise StudyValidationError("Model research requires the exact frozen factor set")
        binding = _document(data.get("data_binding"), "data_binding")
        if set(binding) != {"data_version", "universe_hash", "code_hash"}:
            raise StudyValidationError("Pinned data, universe and implementation identities required")
        _text(binding["data_version"], "data_version")
        _sha(binding["universe_hash"], "universe_hash")
        _sha(binding["code_hash"], "code_hash")
        development = _document(data.get("development"), "development")
        if set(development) != {"start", "end_exclusive"}:
            raise StudyValidationError("Explicit development half-open interval required")
        start, end = _local_bound(development["start"], "start"), _local_bound(development["end_exclusive"], "end_exclusive")
        if start >= end or end > DEVELOPMENT_END:
            raise StudyValidationError("Development cannot read the final-test interval")
        data["development"] = {"start": start.isoformat(), "end_exclusive": end.isoformat()}
        final = _document(data.get("final_evaluation", {"execution_enabled": False}), "final_evaluation")
        if final.get("execution_enabled") is not False:
            raise StudyValidationError("Independent final execution is disabled in the development contract")
        if final.get("feedback_to_research_for_changes", False) is not False:
            raise StudyValidationError("Final-test feedback cannot enter research selection")
        if final.get("whole_window_is_untouched_independent_holdout", False) is not False:
            raise StudyValidationError("Prior2024-2025 exposure cannot be erased")
        if final.get("start", "2024-01-01") != "2024-01-01" or final.get("end", "2026-10-23") != "2026-10-23":
            raise StudyValidationError("Final interval must preserve the user's fixed dates")
        data["final_evaluation"] = final
        if purpose == "research":
            rolling = {"first_training_year": 2010, "training_years": 8, "validation_years": 1, "step_years": 1, "rounds": 6}
            if data.get("rolling_validation") != rolling:
                raise StudyValidationError("Research must preserve all six fixed8+1 rolling windows")
            data["preregistered_acceptance"] = _validate_acceptance(data.get("preregistered_acceptance"))
            for spec in specs:
                raw = spec.to_dict()
                for key in ("availability_contract", "label_entry_exit_contract", "baseline_and_incrementality_test", "preregistered_acceptance"):
                    _complete(raw.get(key), "FactorSpec." + key)
                if not isinstance(raw["label_entry_exit_contract"], dict) or raw["label_entry_exit_contract"].get("label_protocol_hash") != label.configuration_hash:
                    raise StudyValidationError("Factor label contract must bind the exact LabelProtocol hash")
                if data["research_phase"] == "factor" and raw.get("fixed_model_binding") != {"model_hash": model.configuration_hash}:
                    raise StudyValidationError("FactorSpec must bind the same fixed model as its study")
                if raw["preregistered_acceptance"] != {"acceptance_hash": content_hash(data["preregistered_acceptance"])}:
                    raise StudyValidationError("FactorSpec acceptance must bind the study's exact registered rule set")
        trading = data.get("trading_spec")
        if require_trading and trading is None:
            raise StudyValidationError("Trading stage requires a complete frozen trading specification")
        if trading is not None:
            data["trading_spec"] = validate_trading_spec(trading, purpose=purpose)
        component_hashes = {"factors": {x.factor_id: x.configuration_hash for x in specs},
                            "model": model.configuration_hash, "label": label.configuration_hash,
                            "trading": content_hash(data["trading_spec"]) if trading is not None else None}
        if "component_hashes" in data and data["component_hashes"] != component_hashes:
            raise StudyValidationError("Supplied component hashes do not match frozen specifications")
        data["component_hashes"] = component_hashes
        data["factor_specs"] = [x.to_dict() for x in specs]
        data["model_spec"], data["label_spec"] = model_doc, label_doc
        serialized = canonical_json(data).decode("utf-8")
        return cls(serialized, content_hash(data), specs)

    @property
    def study_hash(self):
        return self.configuration_hash

    @property
    def hash(self):
        return self.configuration_hash

    def to_dict(self):
        return json.loads(self.canonical_json)

    def identity(self):
        data = self.to_dict()
        return {"configuration_hash": self.configuration_hash, "purpose": data["purpose"],
                "data_binding": data["data_binding"], "component_hashes": data["component_hashes"]}


@dataclass(frozen=True)
class AuditEvidence:
    canonical_json: str
    evidence_hash: str
    passed: bool

    @classmethod
    def from_dict(cls, raw, *, expected_subject_hash=None, expected_source_hash=None, allowed_issuers=None):
        data = _document(raw, "AuditEvidence")
        required = {"schema_version", "audit_id", "issuer", "issuer_kind", "created_at", "subject_hash",
                    "source_hash", "checks", "evidence_refs", "scope"}
        if set(data) != required or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise StudyValidationError("An audit needs its versioned issuer, subject, implementation, checks and evidence references")
        _text(data["audit_id"], "audit_id")
        if (not isinstance(allowed_issuers, (list, tuple, set, frozenset)) or not allowed_issuers
                or any(not isinstance(x, str) or not x for x in allowed_issuers)
                or data["issuer_kind"] != "fixed_program" or data["issuer"] not in allowed_issuers):
            raise StudyValidationError("Audit issuer must be trusted by the dispatcher; LLM approval is not evidence")
        if data["scope"] not in {"engineering", "research"}:
            raise StudyValidationError("Audit scope must distinguish engineering and research")
        if (data["subject_hash"] != _sha(expected_subject_hash, "expected_subject_hash") or
                data["source_hash"] != _sha(expected_source_hash, "expected_source_hash")):
            raise StudyValidationError("Audit subject or source does not match the dispatched study")
        try:
            aware(data["created_at"])
        except (ValueError, TypeError) as exc:
            raise StudyValidationError("Audit creation time must be timezone aware") from exc
        if not isinstance(data["checks"], list) or not data["checks"]:
            raise StudyValidationError("Audit check records cannot be empty")
        names, outcomes = set(), []
        for raw_check in data["checks"]:
            check = _document(raw_check, "audit check")
            if set(check) != {"name", "passed", "evidence_hash"} or type(check["passed"]) is not bool:
                raise StudyValidationError("Audit checks require a named boolean outcome and evidence digest")
            if _text(check["name"], "check.name") in names:
                raise StudyValidationError("Audit check names must be unique")
            names.add(check["name"])
            _sha(check["evidence_hash"], "check.evidence_hash")
            outcomes.append(check["passed"])
        if not isinstance(data["evidence_refs"], list) or not data["evidence_refs"]:
            raise StudyValidationError("Audit requires immutable evidence references")
        for raw_reference in data["evidence_refs"]:
            reference = _document(raw_reference, "evidence reference")
            if set(reference) != {"key", "sha256"}:
                raise StudyValidationError("Evidence references need a key and its content hash")
            _text(reference["key"], "evidence key")
            validate_key(reference["key"])
            _sha(reference["sha256"], "evidence.sha256")
            if reference["sha256"] not in {x["evidence_hash"] for x in data["checks"]}:
                raise StudyValidationError("Each evidence reference must support a named check")
        if not {x["evidence_hash"] for x in data["checks"]} <= {x["sha256"] for x in data["evidence_refs"]}:
            raise StudyValidationError("Every check requires a resolvable evidence reference")
        encoded = canonical_json(data).decode("utf-8")
        return cls(encoded, content_hash(data), all(outcomes))

    @property
    def configuration_hash(self):
        return self.evidence_hash

    @property
    def hash(self):
        return self.evidence_hash

    def to_dict(self):
        return json.loads(self.canonical_json)

    def require_passed(self):
        if not self.passed:
            raise StudyValidationError("Audit contains failed checks")
        return self

    def verify_references(self, store):
        """Resolve immutable evidence bytes before a dispatcher advances a stage."""
        for reference in self.to_dict()["evidence_refs"]:
            if sha256(store.read_bytes(reference["key"])).hexdigest() != reference["sha256"]:
                raise StudyValidationError("Audit evidence bytes do not match the declared immutable reference")
        return self
