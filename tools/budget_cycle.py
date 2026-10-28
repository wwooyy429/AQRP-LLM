"""Trusted operator: start an explicitly authorized configuration budget cycle.

This command never clears the baseline or journal, resets Research/LEAN, submits
cloud work, enables final testing, or purchases resources. The operator must
verify the actual human instruction before applying its content-bound metadata.
"""
import argparse
import json
from pathlib import Path

from research import ROOT, read_json, write_changed
from budget_revision import _open_existing_registry
from qresearch.artifacts import canonical_json
from qresearch.registry import _normalize_limits, _normalize_usage


_BUDGET_KEYS = {"configurations": "full_configurations",
                "research": "research_execution_attempts",
                "lean": "lean_submission_attempts"}
_USAGE_KEYS = {
    "configurations": ("configuration_budget_charges", "configuration_normal_used", "configuration_reserve_used"),
    "research": ("research_execution_attempts", "research_normal_used", "research_reserve_used"),
    "lean": ("lean_submission_attempts", "lean_normal_used", "lean_reserve_used"),
}


def project_cycle(budget, *, limits, usage, configuration_cycle):
    """Keep cumulative usage fields and expose current configuration capacity.

    Capacity can be less than lifetime configuration usage after a reset. Only
    the active configuration-cycle usage is compared to that capacity; Research
    and LEAN remain bounded by their cumulative counters.
    """
    if (type(budget) is not dict
            or any(type(budget.get(name)) is not dict for name in ("limits", "allocations", "usage"))):
        raise ValueError("A complete existing budget projection is required")
    _normalize_limits(budget["limits"], budget["allocations"])
    _normalize_usage(budget["usage"])
    limits = _normalize_limits(limits, None)
    usage = _normalize_usage(usage)
    # The configuration-cycle value comes from Registry replay, not the mutable
    # projection. Refuse internally inconsistent API results before publishing.
    if (type(configuration_cycle) is not dict
            or configuration_cycle.get("capacity") != limits["configurations"]
            or configuration_cycle.get("lifetime_usage") != usage["configurations"]
            or type(configuration_cycle.get("usage")) is not dict
            or set(configuration_cycle["usage"]) != {"normal", "reserve", "total"}):
        raise ValueError("Configuration cycle differs from replayed usage")
    for stage in _BUDGET_KEYS:
        checked = configuration_cycle["usage"] if stage == "configurations" else usage[stage]
        if any(type(checked.get(part)) is not int or not 0 <= checked[part] <= limits[stage][part]
               for part in ("normal", "reserve", "total")):
            raise ValueError("Active budget usage exceeds its capacity")
    if (configuration_cycle["usage"]["normal"] + configuration_cycle["usage"]["reserve"]
            != configuration_cycle["usage"]["total"]):
        raise ValueError("Configuration cycle allocation usage does not sum")
    for name in ("extra_spend_USD", "extra_resource_purchases", "optimization_jobs"):
        if name in budget["limits"] and (type(budget["limits"][name]) is not int or budget["limits"][name] != 0):
            raise ValueError("Configuration cycles cannot grant spend or resources")
    if budget.get("final_evaluation_execution_enabled", False) is not False:
        raise ValueError("Configuration cycles cannot enable final evaluation")
    result = json.loads(canonical_json(budget))
    for stage, key in _BUDGET_KEYS.items():
        result["limits"][key] = limits[stage]["total"]
        result["allocations"][key] = dict(limits[stage])
        for field, part in zip(_USAGE_KEYS[stage], ("total", "normal", "reserve")):
            result["usage"][field] = usage[stage][part]
    result["configuration_cycle"] = json.loads(canonical_json(configuration_cycle))
    return result


def apply_cycle(cycle, authorization, *, registry=None):
    """Durable event first, atomic projection second; identical retry recovers."""
    registry = _open_existing_registry() if registry is None else registry
    path = ROOT / "config" / "budget.json"
    with registry.store.locked(registry.LOCK):
        state = registry._replay()
        project_cycle(read_json(path), limits=state["limits"], usage=state["usage"],
                      configuration_cycle=registry._configuration_cycle_snapshot(state))
    accepted = registry.authorize_configuration_cycle(cycle, authorization)
    with registry.store.locked(registry.LOCK):
        state = registry._replay()
        active = registry._configuration_cycle_snapshot(state)
        projected = project_cycle(read_json(path), limits=state["limits"], usage=state["usage"],
                                  configuration_cycle=active)
        changed = write_changed(path, json.dumps(projected, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        usage = json.loads(canonical_json(state["usage"]))
    return {"authorization": accepted, "configuration_cycle": active,
            "budget_projection_changed": changed, "lifetime_usage": usage,
            "configuration_registrations": 0, "Research_executions": 0, "LEAN_submissions": 0,
            "cloud_calls": 0, "final_test_enabled": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--cycle-file", type=Path, required=True)
    apply.add_argument("--authorization-file", type=Path, required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    if args.command == "apply":
        result = apply_cycle(read_json(args.cycle_file), read_json(args.authorization_file))
    else:
        registry = _open_existing_registry()
        result = {"configuration_cycle": registry.configuration_cycle_snapshot(),
                  "lifetime_registry": registry.snapshot()}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
