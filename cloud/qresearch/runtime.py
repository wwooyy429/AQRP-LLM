"""In-cloud batch evaluation using the same pure calculation code as LEAN."""
from dataclasses import replace
from collections.abc import Mapping
import json
import pandas as pd
from .artifacts import canonical_json, content_hash
from .cache import merge_requests
from .contracts import DataRequest, aware, canonical_membership, formation_index, digest
from .factors import FactorSpec, evaluate_factors, structure_similarity
from .point_in_time import causal_window
from .audits import FORMULA_ISSUER, COVERAGE_ISSUER, verify_evidence
from .pipeline import _registered_subject
from .study import StudySpec


def execution_plan_identity(request, decisions, sids, policies, expected_events,
                            max_age=None, membership=None):
    """Canonical execution metadata, not an approval or coverage certificate.

    A trusted coverage producer must record this complete object and its hash
    in the immutable observed audit report. A caller-created matching dictionary
    cannot authorize a market computation by itself.
    """
    if not isinstance(request, DataRequest):
        raise ValueError("A validated DataRequest is required")
    times = tuple(aware(value) for value in decisions)
    names = tuple(sorted(sids))
    if (not times or len(set(times)) != len(times) or tuple(sorted(times)) != times
            or not names or len(set(names)) != len(names)):
        raise ValueError("Execution plan needs sorted unique formations and permanent SIDs")
    if not isinstance(policies, Mapping) or set(policies) != set(request.fields):
        raise ValueError("Execution policies must describe exactly the registered request fields")
    if any(value not in {"exact_session", "latest_available"} for value in policies.values()):
        raise ValueError("Unknown execution availability policy")
    raw_prices = {"open", "high", "low", "close", "volume", "dollar_volume"}
    if any(policies[name] != "exact_session" for name in raw_prices & set(policies)):
        raise ValueError("Price windows must preserve exact completed sessions")
    ages = max_age or {}
    if not isinstance(ages, Mapping) or set(ages) != {name for name, policy in policies.items() if policy == "latest_available"}:
        raise ValueError("Only carried financial fields require explicit maximum ages")
    age_identity = {}
    for name, value in ages.items():
        age = pd.Timedelta(value)
        if pd.isna(age) or age <= pd.Timedelta(0):
            raise ValueError("Execution maximum ages must be positive")
        age_identity[name] = str(age)
    if not isinstance(expected_events, Mapping):
        raise ValueError("Completed-session mapping is required")
    events = {aware(key): aware(value) for key, value in expected_events.items()}
    if set(events) != set(times) or any(events[time] >= time for time in times):
        raise ValueError("Each formation needs its actual preceding completed session")
    if any(not request.start <= events[time] < request.end for time in times):
        raise ValueError("Completed sessions must lie inside the frozen request")
    index = formation_index(times)
    membership = canonical_membership(membership)
    if (not membership.index.equals(index)
            or not membership.columns.is_unique or set(membership.columns) != set(names)
            or membership.isna().any().any()
            or not all(pd.api.types.is_bool_dtype(kind) for kind in membership.dtypes)):
        raise ValueError("An explicit causal boolean historical membership matrix is required")
    member_identity = {"index": [time.isoformat() for time in times], "columns": list(names),
                       "data": membership.reindex(columns=names).to_numpy(dtype=bool).tolist()}
    return {"schema_version": 1, "request": request.identity(),
            "decisions": [time.isoformat() for time in times], "sids": list(names),
            "policies": dict(policies), "max_age": age_identity,
            "expected_events": [[time.isoformat(), events[time].isoformat()] for time in times],
            "membership_hash": content_hash(member_identity)}


class ResearchEngine:
    """Market payloads and computed exposures stay in authorized cloud storage.

    Budget admission belongs immediately outside the remote Research execution,
    not inside each factor or each fold. This engine never submits a backtest.
    """
    def __init__(self, cache, *, code_version=None, research_approval=None, synthetic=False,
                 study=None, registered_configuration=None, field_catalog=None, operator_catalog=None):
        if not synthetic and getattr(cache.store, "residency", None) != "quantconnect_cloud":
            raise ValueError("Real market data require QuantConnect cloud storage")
        self.cache = cache
        self.synthetic = synthetic
        if not code_version and not synthetic:
            raise ValueError("Bind the frozen implementation hash before real factor calculation")
        self.code_version = code_version or "synthetic"
        self.research_approval = research_approval
        self.study = study
        self.registered_configuration = registered_configuration
        self.field_catalog = field_catalog
        self.operator_catalog = operator_catalog

    def _authorize(self, specs, request, decisions, sids, policies, expected_events, max_age, membership):
        """Bind actual inputs to the registered study and observed plan evidence."""
        if not isinstance(self.study, StudySpec):
            raise ValueError("Market computation requires a validated registered StudySpec")
        for catalog, name in ((self.field_catalog, "field_catalog"), (self.operator_catalog, "operator_catalog")):
            if (not isinstance(catalog, (Mapping, list, tuple, set, frozenset))
                    or any(not isinstance(value, str) or not value.strip() for value in catalog)):
                raise ValueError("Trusted dispatcher must supply an explicit " + name)
        validated = StudySpec.from_dict(self.study.to_dict(), field_catalog=self.field_catalog,
                                       operator_catalog=self.operator_catalog, require_trading=True)
        document = validated.to_dict()
        if document["purpose"] != "research" or validated.configuration_hash != self.study.configuration_hash:
            raise ValueError("Engineering or altered study cannot authorize market computation")
        subject_hash = _registered_subject(validated, self.registered_configuration,
                                           self.cache.store, required=True)
        binding, components = document["data_binding"], document["component_hashes"]
        if self.code_version != binding["code_hash"]:
            raise ValueError("Implementation differs from the frozen registered study")
        expected_factors = {spec.configuration_hash for spec in validated.factor_specs}
        if {spec.configuration_hash for spec in specs} != expected_factors or len(specs) != len(validated.factor_specs):
            raise ValueError("Actual factors differ from the registered study")
        expected_fields = {field for spec in validated.factor_specs for field in spec.allowed_fields}
        if (not isinstance(request, DataRequest) or set(request.fields) != expected_fields
                or request.normalization != "raw" or request.data_version != binding["data_version"]
                or request.universe_hash != binding["universe_hash"]):
            raise ValueError("Actual data request differs from the frozen registered study")
        start, end = aware(document["development"]["start"]), aware(document["development"]["end_exclusive"])
        if (request.start < start or request.end > end
                or any(not start <= aware(time) < end for time in decisions)):
            raise ValueError("Request or formations exceed the registered development interval")
        if not isinstance(self.research_approval, Mapping):
            raise ValueError("Referenced audit evidence and a certified execution plan are required")
        approval = self.research_approval
        # Legacy annotations may be checked for consistency, but never confer
        # authority. All actual bindings above come from the registered package.
        legacy = {"study_hash": validated.configuration_hash, "configuration_hash": subject_hash,
                  "fixed_model_hash": components["model"], "label_contract_hash": components["label"],
                  "factor_hashes": sorted(expected_factors), "data_version": binding["data_version"],
                  "universe_hash": binding["universe_hash"],
                  "preregistered_comparison_hash": content_hash({spec.factor_id:
                      spec.to_dict()["baseline_and_incrementality_test"] for spec in validated.factor_specs})}
        for key, expected in legacy.items():
            if key in approval:
                actual = sorted(approval[key]) if key == "factor_hashes" and isinstance(approval[key], (list, tuple)) else approval[key]
                if actual != expected:
                    raise ValueError("Free approval annotation conflicts with the registered study: " + key)
        for key in ("formula_timing_audit_passed", "coverage_audit_passed"):
            if key in approval and approval[key] is not True:
                raise ValueError("Approval annotation conflicts with required observed audit success")
        actual_plan = execution_plan_identity(request, decisions, sids, policies, expected_events, max_age, membership)
        plan_hash = content_hash(actual_plan)
        declared_plan = approval.get("execution_plan")
        if (not isinstance(declared_plan, dict) or declared_plan != actual_plan
                or content_hash(declared_plan) != plan_hash or approval.get("plan_hash") != plan_hash):
            raise ValueError("Actual execution plan is missing or differs from the supplied plan metadata")
        evidence_documents = approval.get("audit_evidence")
        if not isinstance(evidence_documents, Mapping) or set(evidence_documents) != {"formula_timing", "data_coverage"}:
            raise ValueError("Both fixed-program audits are required")
        report_hashes = {}
        for purpose, issuer, checks in (
                ("formula_timing", FORMULA_ISSUER, ("validated_study_contract", "source_hash_matches_binding", "restricted_factor_compilation", "development_only")),
                ("data_coverage", COVERAGE_ISSUER, ("historical_universe_coverage", "actual_availability_verified", "source_revision_pinned", "development_only", "execution_plan_bound"))):
            raw = evidence_documents[purpose]
            raw = raw.to_dict() if hasattr(raw, "to_dict") else raw
            evidence = verify_evidence(self.cache.store, raw, subject_hash=subject_hash,
                         source_hash=binding["code_hash"], issuer=issuer, required_checks=checks, scope="research")
            evidence.verify_references(self.cache.store)
            references = evidence.to_dict()["evidence_refs"]
            report_hashes[purpose] = sorted(reference["sha256"] for reference in references)
            if purpose == "data_coverage":
                for reference in references:
                    report = json.loads(self.cache.store.read_bytes(reference["key"]))
                    if (report.get("execution_plan") != actual_plan or report.get("plan_hash") != plan_hash
                            or content_hash(report.get("execution_plan")) != plan_hash):
                        raise ValueError("Coverage evidence does not certify this execution plan; market computation remains disabled")
        return {"registered_configuration_hash": subject_hash, "study_hash": validated.configuration_hash,
                "execution_plan_hash": plan_hash, "audit_report_hashes": report_hashes}

    def prepare(self, requests):
        plan = merge_requests(requests)
        for request in plan:
            self.cache.prefetch(request)
        return plan

    def evaluate(self, specs, request, decisions, sids, policies, expected_events, max_age=None, membership=None):
        specs = tuple(specs)
        if not specs or any(not isinstance(spec, FactorSpec) for spec in specs):
            raise ValueError("Validated frozen FactorSpec objects required")
        specs = tuple(sorted(specs, key=lambda spec: spec.configuration_hash))
        decisions, sids = tuple(aware(value) for value in decisions), tuple(sorted(sids))
        policies = dict(policies)
        expected_events = {aware(key): aware(value) for key, value in dict(expected_events).items()}
        max_age = dict(max_age or {})
        if membership is not None:
            membership = canonical_membership(membership)
            if not membership.columns.is_unique or set(membership.columns) != set(sids):
                raise ValueError("Historical membership must cover every formation and union SID exactly")
            membership = membership.reindex(columns=sids)
        authorization = None
        if not self.synthetic:
            authorization = self._authorize(specs, request, decisions, sids, policies,
                                             expected_events, max_age, membership)
        if not set(sids) <= set(request.sids):
            raise ValueError("Window SIDs must be in the prefetched plan")
        if not self.synthetic and membership is None:
            raise ValueError("Dynamic universe requires historical formation-by-SID membership")
        for spec in specs:
            if not set(spec.allowed_fields) <= set(request.fields):
                raise ValueError("Declare the union of all factor fields before prefetch")
        identity = {"schema": 1, "code_version": self.code_version,
                    "research_approval_hash": content_hash(authorization) if authorization else
                        digest(self.research_approval) if self.research_approval else None,
                    "registered_authorization": authorization,
                    "factors": [s.configuration_hash for s in specs],
                    "data_request": request.identity(), "decisions": [x.isoformat() for x in decisions],
                    "sids": list(sids), "policies": policies,
                    "expected_events": [[k.isoformat(), expected_events[k].isoformat()] for k in decisions],
                    "max_age": {k: str(v) for k, v in (max_age or {}).items()},
                    "membership": None if membership is None else membership.astype(int).to_dict(orient="split")}
        if identity["membership"] is not None:
            identity["membership"]["index"] = [x.isoformat() for x in membership.index]
        key = "factor-results/v1/" + digest(identity) + ".json"
        with self.cache.store.locked(key):
            if self.cache.store.exists(key):
                return json.loads(self.cache.store.read_bytes(key))
            first_event = min(expected_events.values())
            if max_age:
                first_event = min(first_event, min(decisions) - max(pd.Timedelta(x) for x in max_age.values()))
            read_start = max(request.start, first_event)
            read_end = min(request.end, max(decisions) + pd.Timedelta(microseconds=1))
            records = self.cache.read(replace(request, start=read_start, end=read_end), allow_fetch=False)
            window = causal_window(records, decisions, tuple(sids), policies, expected_events, max_age, membership)
            values = evaluate_factors(specs, window)
            if membership is not None:
                values = values.loc[membership.iloc[-1].reindex(values.index)]
            # A result is encoded in cloud storage only; the caller must not print
            # these exposure rows through the connector or copy them into source.
            payload = {"identity": identity, "as_of": window.as_of.isoformat(),
                       "values": json.loads(values.to_json(orient="split")),
                       "structural_comparisons": [
                           {"left": specs[i].factor_id, "right": specs[j].factor_id,
                            **structure_similarity(specs[i], specs[j])}
                           for i in range(len(specs)) for j in range(i + 1, len(specs))]}
            self.cache.store.write_once(key, canonical_json(payload))
            return payload


def readiness(configuration):
    """Report explicit gates without treating an empty host as a valid strategy."""
    missing = []
    for name in ("active_factor", "active_model", "active_trading_rules"):
        if not configuration.get(name):
            missing.append(name)
    if configuration.get("data", {}).get("coverage_status") != "certified":
        missing.append("historical_PIT_coverage")
    if not configuration.get("workflow", {}).get("orders_enabled", False):
        missing.append("orders_disabled")
    missing.append("portfolio_LEAN_adapter_unregistered")
    if not configuration.get("research", {}).get("final_evaluation", {}).get("independent_executor_configured", False):
        final_status = "independent_executor_missing"
    else:
        final_status = "frozen_handoff_required"
    return {"infrastructure": "implemented", "strategy_ready": not missing,
            "missing_strategy_contracts": missing, "final_evaluation": final_status}
