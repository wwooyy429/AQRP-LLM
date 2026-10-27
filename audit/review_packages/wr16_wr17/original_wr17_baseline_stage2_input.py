"""Prepare and account for one fixed QC engineering job; no network calls.

Only trusted tool observations pass through the fixed receipt parsers. This CLI
does not call a provider, poll a backtest, certify historical coverage, or trade.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import canonical_json, content_hash
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.registry import BudgetExceeded
from research import read_json, write_changed, open_registry, export_usage
from stages import source_manifest


def _write(path, document):
    write_changed(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def freeze(projects, *, plan_file=None, preview=False):
    if projects.get("success") is not True or not isinstance(projects.get("projects"), list):
        raise ValueError("An actual successful QC project listing is required")
    ids = [item["projectId"] for item in projects["projects"]]
    raw = read_json(plan_file or ROOT / "config" / "engineering.json")
    raw["project_id"] = read_json(ROOT / "config" / "quantconnect.json")["active_project_id"]
    raw["source_manifest_hash"] = source_manifest()["source_hash"]
    probe_catalog = None
    if raw.get("schema_version") == 2:
        from stage2_collection import catalog
        from collection_task_cli import execution_source_manifest
        probe_catalog = catalog()
        raw["source_manifest_hash"] = execution_source_manifest()["source_hash"]
        probe = raw.get("collection_probe")
        if not isinstance(probe, dict) or set(probe) != {"collection_plan", "field_catalog"} or not isinstance(probe["collection_plan"], dict):
            raise ValueError("Fill the complete joint collection probe before freezing")
        selected = probe["collection_plan"].get("fields", [])
        expected = {name: probe_catalog[name] for name in selected if name in probe_catalog}
        if probe["field_catalog"] is not None and probe["field_catalog"] != expected:
            raise ValueError("Joint pilot cannot override the trusted source catalog")
        probe["field_catalog"] = expected
        probe["collection_plan"]["source_manifest_hash"] = raw["source_manifest_hash"]
    deployment = read_json(ROOT / "audit" / "deployment.json")["source_files"]
    raw["deployment_hash"] = content_hash(deployment)
    # Raw snapshot identity is independent of controller/parser code changes.
    # Failed/corrupt source snapshots require an explicit new data_version;
    # editing unrelated software must not automatically download prices again.
    raw["request_template"]["universe_hash"] = content_hash({"scope": "fixed_engineering_fixture",
        "resolution": raw["symbol_resolution"], "not_historical_US200": True})
    plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=ids, probe_field_catalog=probe_catalog)
    if preview:
        return {"plan_hash": plan.hash, "configuration_hash": content_hash({"engineering_task_schema_version": 1, "plan": plan.to_dict()}),
                "source_manifest_hash": raw["source_manifest_hash"], "deployment_hash": raw["deployment_hash"],
                "plan": plan.to_dict(), "configuration_registered": False, "execution_started": False,
                "ready_to_dispatch": False, "budget_admission_performed": False}
    registry = open_registry()
    key = "engineering/frozen-plans/" + plan.hash + ".json"
    proof_key = "engineering/project-listings/" + content_hash(projects) + ".json"
    reference = {"schema_version": 1, "plan_key": key, "plan_hash": plan.hash,
        "project_listing_ref": {"key": proof_key, "sha256": content_hash(projects)},
        "configuration_registered": False, "execution_started": False}
    if raw["schema_version"] == 2:
        # A freeze must not replace the old task's settlement pointer while its
        # project input is unresolved. No new identity/slot may bypass it.
        with registry.store.locked(registry.LOCK):
            registry._enforce_engineering_project(registry._replay(), {"engineering_task_schema_version": 1, "plan": plan.to_dict()})
            registry.store.write_once(key, canonical_json(plan.to_dict()))
            registry.store.write_once(proof_key, canonical_json(projects))
            _write(ROOT / "audit" / "engineering_current.json", reference)
    else:
        registry.store.write_once(key, canonical_json(plan.to_dict()))
        registry.store.write_once(proof_key, canonical_json(projects))
        _write(ROOT / "audit" / "engineering_current.json", reference)
    return reference


def current_bridge():
    pointer = read_json(ROOT / "audit" / "engineering_current.json")
    registry = open_registry()
    plan_doc = json.loads(registry.store.read_bytes(pointer["plan_key"]))
    listing_ref = pointer["project_listing_ref"]
    listing = json.loads(registry.store.read_bytes(listing_ref["key"]))
    if content_hash(listing) != listing_ref["sha256"] or content_hash(plan_doc) != pointer["plan_hash"]:
        raise ValueError("Frozen task or project-listing evidence changed")
    plan = EngineeringTaskPlan.from_dict(plan_doc,
        discovered_project_ids=[item["projectId"] for item in listing["projects"]])
    return EngineeringTaskBridge(registry, plan)


def prepare(bridge, attempt):
    payload = bridge.payload(attempt)
    if bridge.plan.to_dict()["schema_version"] == 2:
        key = "engineering/admitted-inputs/" + attempt + ".json"
        if bridge.store.exists(key):
            admission = json.loads(bridge.store.read_bytes(key))
            if not isinstance(admission, dict):
                raise ValueError("Original joint admitted input must be a metadata object")
            expected_payload = dict(payload, deployment_manifest=admission.get("payload", {}).get("deployment_manifest"))
            text = "TASK_INPUT_JSON = " + repr(canonical_json(expected_payload).decode()) + "\n"
            expected_deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": hashlib.sha256(text.encode()).hexdigest()}
            expected_path = "audit/task_inputs/" + attempt + ".py"
            path = ROOT / expected_path
            if (not isinstance(admission, dict) or set(admission) != {"payload", "deployment", "input_path", "cloud_input_path"}
                    or admission["payload"] != expected_payload or admission["deployment"] != expected_deployment
                    or admission["input_path"] != expected_path or admission["cloud_input_path"] != "_engineering_task_input.py"
                    or content_hash(expected_payload["deployment_manifest"]) != payload["identity"]["deployment_hash"]
                    or (path.exists() and path.read_bytes() != text.encode())):
                raise ValueError("Original joint admitted input differs from its immutable attempt")
            return admission
        if bridge._record(attempt)["status"] not in {"started", "pending", "ambiguous"}:
            raise ValueError("Finalized joint attempts cannot create fresh input")
        joint_preflight(bridge)
    manifest = read_json(ROOT / "audit" / "deployment.json")["source_files"]
    if content_hash(manifest) != bridge.plan.to_dict()["deployment_hash"]:
        raise ValueError("Re-freeze and register a new plan after changing implementation")
    payload["deployment_manifest"] = manifest
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode()) + "\n"
    path = ROOT / "audit" / "task_inputs" / (attempt + ".py")
    write_changed(path, text)
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
        "deployment_hash": payload["identity"]["deployment_hash"],
        "input_hash": hashlib.sha256(text.encode()).hexdigest()}
    admission = {"payload": payload, "deployment": deployment,
        "input_path": path.relative_to(ROOT).as_posix(), "cloud_input_path": "_engineering_task_input.py"}
    bridge.store.write_once("engineering/admitted-inputs/" + attempt + ".json", canonical_json(admission))
    return admission


def joint_preflight(bridge):
    document = bridge.plan.to_dict()
    if document["schema_version"] != 2:
        return
    from collection_task_cli import execution_source_manifest
    from stage2_collection import catalog
    EngineeringTaskPlan.from_dict(document, discovered_project_ids=(document["project_id"],), probe_field_catalog=catalog())
    if (execution_source_manifest()["source_hash"] != document["source_manifest_hash"]
            or content_hash(read_json(ROOT / "audit/deployment.json")["source_files"]) != document["deployment_hash"]):
        raise ValueError("Joint engineering source and deployment must be frozen before new charging")


def _limits(bridge, kind):
    # Compatibility/status preview only. Registry transactions recheck the
    # shared stop condition atomically with registration or attempt charging.
    try:
        bridge.registry.check_engineering_admission(bridge.package, kind)
    except BudgetExceeded as exc:
        raise ValueError(str(exc)) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preview", "freeze", "register", "claim", "prepare", "research-result", "backtest-submission", "backtest-result", "status"))
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--projects-file", type=Path)
    parser.add_argument("--tool-file", type=Path)
    parser.add_argument("--logs-file", type=Path)
    parser.add_argument("--attempt")
    parser.add_argument("--stage", choices=("research", "lean"))
    parser.add_argument("--allocation", choices=("normal", "reserve"), default="normal")
    parser.add_argument("--retry-of")
    parser.add_argument("--reason")
    args = parser.parse_args()
    if args.command in {"preview", "freeze"}:
        if not args.projects_file:
            parser.error("--projects-file requires actual list_projects metadata")
        print(json.dumps(freeze(read_json(args.projects_file), plan_file=args.plan_file, preview=args.command == "preview")))
        return
    bridge = current_bridge()
    if args.command in {"register", "claim"}:
        joint_preflight(bridge)
    if args.command == "register":
        result = {"config_id": bridge.register(allocation=args.allocation), "plan_hash": bridge.plan.hash}
    elif args.command == "claim":
        if not args.stage:
            parser.error("--stage required")
        result = vars(bridge.claim(args.stage, allocation=args.allocation,
            retry_of=args.retry_of, reason=args.reason))
    elif args.command == "prepare":
        if not args.attempt:
            parser.error("--attempt required")
        result = prepare(bridge, args.attempt)
    elif args.command == "status":
        result = bridge.registry.snapshot()
    else:
        if not args.attempt or not args.tool_file:
            parser.error("--attempt and --tool-file with actual tool metadata required")
        from qresearch.engineering_receipts import research_observation, backtest_submission, backtest_observation
        admitted = json.loads(bridge.store.read_bytes("engineering/admitted-inputs/" + args.attempt + ".json"))
        payload, deployment = admitted["payload"], admitted["deployment"]
        native = read_json(args.tool_file)
        if args.command == "research-result":
            observed = research_observation(payload, deployment, native)
            bridge.record_submission(args.attempt, observed["submission"])
            result = vars(bridge.consume_completion(args.attempt, completion_source=lambda _: observed["completion"]))
        elif args.command == "backtest-submission":
            result = vars(bridge.record_submission(args.attempt, backtest_submission(payload, deployment, native)))
        else:
            if not args.logs_file:
                parser.error("--logs-file with actual completed-job log observations required")
            record = bridge._record(args.attempt)
            observed = backtest_observation(payload, deployment, record["external_id"], native, read_json(args.logs_file))
            result = vars(bridge.consume_completion(args.attempt, completion_source=lambda _: observed))
    export_usage(bridge.registry)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
