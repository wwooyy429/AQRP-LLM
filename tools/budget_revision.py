"""Trusted operator for an explicitly approved, append-only budget revision.

The actual human exchange must be checked before applying its transcription.
Hashes bind metadata; they do not authenticate a human. This command neither
registers configurations nor submits Research/LEAN, enables final testing, or
purchases resources. The immutable baseline remains the Registry constructor
input. config/budget.json is only a projection of replayed effective policy.
"""
import argparse
import json
from pathlib import Path

from research import ROOT, open_registry, read_json, write_changed
from qresearch.artifacts import canonical_json
from qresearch.registry import RegistryError, _normalize_limits, _normalize_usage


_BUDGET_KEYS = {"configurations": "full_configurations",
                "research": "research_execution_attempts",
                "lean": "lean_submission_attempts"}
_USAGE_KEYS = {
    "configurations": ("configuration_budget_charges", "configuration_normal_used", "configuration_reserve_used"),
    "research": ("research_execution_attempts", "research_normal_used", "research_reserve_used"),
    "lean": ("lean_submission_attempts", "lean_normal_used", "lean_reserve_used"),
}


def project_budget(budget, snapshot):
    """Copy only ledger limits, allocations and usage into the existing policy.

    Unrelated declarations and constraints retain their values. No counter is
    inferred from a mutable projection and no usage is reset or refunded.
    """
    if type(snapshot) is dict and "configuration_cycle" in snapshot:
        from budget_cycle import project_cycle
        return project_cycle(budget, limits=snapshot["limits"], usage=snapshot["usage"],
                             configuration_cycle=snapshot["configuration_cycle"])
    if (type(budget) is not dict or type(snapshot) is not dict
            or any(type(budget.get(name)) is not dict for name in ("limits", "allocations", "usage"))
            or any(type(snapshot.get(name)) is not dict for name in ("limits", "usage"))):
        raise ValueError("A complete budget projection and replayed snapshot are required")
    for name in ("limits", "usage"):
        if (set(snapshot[name]) != set(_BUDGET_KEYS)
                or any(type(value) is not dict or set(value) != {"normal", "reserve", "total"}
                       for value in snapshot[name].values())):
            raise ValueError("Budget snapshot contains an unsupported resource shape")
    # Validate old projection counters before any revision can be persisted.
    # A stale, well-formed projection is recoverable from the authoritative
    # event stream, including the gap after a previous projection-write crash.
    _normalize_limits(budget["limits"], budget["allocations"])
    _normalize_usage(budget["usage"])
    limits = _normalize_limits(snapshot["limits"], None)
    usage = _normalize_usage(snapshot["usage"])
    if any(usage[stage][part] > limits[stage][part]
           for stage in _BUDGET_KEYS for part in ("normal", "reserve", "total")):
        raise ValueError("Budget snapshot usage exceeds its effective limit")
    for name in ("extra_spend_USD", "extra_resource_purchases", "optimization_jobs"):
        if name in budget["limits"] and (type(budget["limits"][name]) is not int or budget["limits"][name] != 0):
            raise ValueError("Budget revision cannot grant extra spend or resources")
    if ("final_evaluation_execution_enabled" in budget
            and budget["final_evaluation_execution_enabled"] is not False):
        raise ValueError("Budget revision cannot enable final evaluation")
    result = json.loads(canonical_json(budget))
    for stage, key in _BUDGET_KEYS.items():
        result["limits"][key] = limits[stage]["total"]
        result["allocations"][key] = dict(limits[stage])
        for field, part in zip(_USAGE_KEYS[stage], ("total", "normal", "reserve")):
            result["usage"][field] = usage[stage][part]
    return result


def _open_existing_registry():
    """Never let a revision/status request bootstrap a replacement ledger."""
    root = ROOT / "audit" / "runtime"
    if (not (root / "registry" / "baseline.json").is_file()
            or not (root / "registry" / "events.jsonl").is_file()):
        raise RegistryError("Budget revision requires the existing immutable baseline and journal")
    registry = open_registry()
    if Path(registry.store.root).resolve() != root.resolve():
        raise RegistryError("Budget projection and Registry must share one authoritative root")
    return registry


def apply_revision(revision, authorization, *, registry=None):
    """Append once, then atomically publish the effective budget projection.

    Failure after the durable event is not rolled back. Reapplying the identical
    authorization recovers its projection without another revision or debit.
    The Registry transaction lock also serializes projection with other ledger
    activity; no nested snapshot/limits getter is used while holding that lock.
    """
    registry = _open_existing_registry() if registry is None else registry
    path = ROOT / "config" / "budget.json"
    def projection(state):
        snapshot = {"limits": state["limits"], "usage": state["usage"]}
        cycle = registry._configuration_cycle_snapshot(state)
        if cycle["sequence"] > 0:
            snapshot["configuration_cycle"] = cycle
        return snapshot
    with registry.store.locked(registry.LOCK):
        state = registry._replay()
        project_budget(read_json(path), projection(state))
    accepted = registry.authorize_budget_revision(revision, authorization)
    with registry.store.locked(registry.LOCK):
        state = registry._replay()
        projected = project_budget(read_json(path), projection(state))
        changed = write_changed(path, json.dumps(projected, ensure_ascii=False, indent=2) + "\n")
        limits, usage = json.loads(canonical_json(state["limits"])), json.loads(canonical_json(state["usage"]))
    return {"authorization": accepted, "budget_projection_changed": changed,
            "limits": limits, "usage": usage, "cloud_calls": 0,
            "configuration_registrations": 0, "Research_executions": 0, "LEAN_submissions": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--revision-file", type=Path, required=True)
    apply.add_argument("--authorization-file", type=Path, required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    if args.command == "apply":
        result = apply_revision(read_json(args.revision_file), read_json(args.authorization_file))
    else:
        result = _open_existing_registry().snapshot()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return result


if __name__ == "__main__":
    main()
