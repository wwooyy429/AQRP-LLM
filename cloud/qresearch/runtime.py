"""In-cloud batch evaluation using the same pure calculation code as LEAN."""
from dataclasses import replace
import json
import pandas as pd
from .artifacts import canonical_json
from .cache import merge_requests
from .contracts import digest
from .factors import FactorSpec, evaluate_factors, structure_similarity
from .point_in_time import causal_window
from .audits import FORMULA_ISSUER, COVERAGE_ISSUER, verify_evidence


class ResearchEngine:
    """Market payloads and computed exposures stay in authorized cloud storage.

    Budget admission belongs immediately outside the remote Research execution,
    not inside each factor or each fold. This engine never submits a backtest.
    """
    def __init__(self, cache, *, code_version=None, research_approval=None, synthetic=False):
        if not synthetic and getattr(cache.store, "residency", None) != "quantconnect_cloud":
            raise ValueError("Real market data require QuantConnect cloud storage")
        self.cache = cache
        self.synthetic = synthetic
        if not code_version and not synthetic:
            raise ValueError("Bind the frozen implementation hash before real factor calculation")
        self.code_version = code_version or "synthetic"
        self.research_approval = research_approval

    def prepare(self, requests):
        plan = merge_requests(requests)
        for request in plan:
            self.cache.prefetch(request)
        return plan

    def evaluate(self, specs, request, decisions, sids, policies, expected_events, max_age=None, membership=None):
        specs = tuple(sorted(specs, key=lambda spec: spec.configuration_hash))
        decisions, sids = tuple(decisions), tuple(sorted(sids))
        if membership is not None:
            membership = membership.reindex(columns=sids)
        if not specs or any(not isinstance(spec, FactorSpec) for spec in specs):
            raise ValueError("Validated frozen FactorSpec objects required")
        if not self.synthetic:
            approval = self.research_approval or {}
            required = ("formula_timing_audit_passed", "coverage_audit_passed", "fixed_model_hash",
                        "label_contract_hash", "preregistered_comparison_hash")
            if any(not approval.get(key) for key in required):
                raise ValueError("Registered research protocol and coverage/timing audits are required before market factor evaluation")
            evidence = approval.get("audit_evidence", {})
            for purpose, issuer, checks in (
                    ("formula_timing", FORMULA_ISSUER, ("validated_study_contract", "source_hash_matches_binding", "restricted_factor_compilation", "development_only")),
                    ("data_coverage", COVERAGE_ISSUER, ("historical_universe_coverage", "actual_availability_verified", "source_revision_pinned", "development_only"))):
                verify_evidence(self.cache.store, evidence.get(purpose),
                                subject_hash=approval.get("study_hash"), source_hash=self.code_version,
                                issuer=issuer, required_checks=checks, scope="research")
            if (set(approval.get("factor_hashes", [])) != {s.configuration_hash for s in specs} or
                    approval.get("data_version") != request.data_version or
                    approval.get("universe_hash") != request.universe_hash):
                raise ValueError("Research approval does not match frozen factors/data/universe")
        if not set(sids) <= set(request.sids):
            raise ValueError("Window SIDs must be in the prefetched plan")
        if not self.synthetic and membership is None:
            raise ValueError("Dynamic universe requires historical formation-by-SID membership")
        for spec in specs:
            if not set(spec.allowed_fields) <= set(request.fields):
                raise ValueError("Declare the union of all factor fields before prefetch")
        identity = {"schema": 1, "code_version": self.code_version,
                    "research_approval_hash": digest(self.research_approval) if self.research_approval else None,
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
