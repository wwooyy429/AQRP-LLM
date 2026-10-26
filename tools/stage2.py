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
from research import read_json, write_changed, open_registry, export_usage
from stages import source_manifest


def _write(path, document):
    write_changed(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def freeze(projects):
    if projects.get("success") is not True or not isinstance(projects.get("projects"), list):
        raise ValueError("An actual successful QC project listing is required")
    ids = [item["projectId"] for item in projects["projects"]]
    raw = read_json(ROOT / "config" / "engineering.json")
    raw["project_id"] = read_json(ROOT / "config" / "quantconnect.json")["active_project_id"]
    raw["source_manifest_hash"] = source_manifest()["source_hash"]
    deployment = read_json(ROOT / "audit" / "deployment.json")["source_files"]
    raw["deployment_hash"] = content_hash(deployment)
    raw["request_template"]["data_version"] += "-" + raw["deployment_hash"][:16]
    raw["request_template"]["universe_hash"] = content_hash({"scope": "fixed_engineering_fixture",
        "resolution": raw["symbol_resolution"], "not_historical_US200": True})
    plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=ids)
    registry = open_registry()
    key = "engineering/frozen-plans/" + plan.hash + ".json"
    registry.store.write_once(key, canonical_json(plan.to_dict()))
    proof_key = "engineering/project-listings/" + content_hash(projects) + ".json"
    registry.store.write_once(proof_key, canonical_json(projects))
    reference = {"schema_version": 1, "plan_key": key, "plan_hash": plan.hash,
        "project_listing_ref": {"key": proof_key, "sha256": content_hash(projects)},
        "configuration_registered": False, "execution_started": False}
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


def _limits(bridge, kind):
    # A local engineering stop condition, in addition to the user's global caps.
    # One normal job and one explicit repair per stage/config, including failures.
    snapshot = bridge.registry.snapshot()
    selected = []
    for config in snapshot["config_ids"]:
        package = json.loads(bridge.store.read_bytes("configurations/" + config + ".json"))
        if (package.get("engineering_task_schema_version") == 1
                and package["plan"]["plan_id"] == bridge.plan.to_dict()["plan_id"]):
            selected.append(config)
    if kind == "configurations":
        count = len(selected)
        if bridge.config_id in selected:
            return
    else:
        attempts = [x for x in snapshot["attempts"] if x["config_id"] in selected and x["stage"] == kind]
        same = [x for x in attempts if x["config_id"] == bridge.config_id]
        if same and same[-1]["status"] in {"completed", "started", "pending", "ambiguous"}:
            return  # Registry returns reuse/unresolved, never a fresh submission.
        count = len(attempts)
    if count >= 2:
        raise ValueError("Stage2 engineering stop condition reached; no further configuration or execution")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "register", "claim", "prepare", "research-result", "backtest-submission", "backtest-result", "status"))
    parser.add_argument("--projects-file", type=Path)
    parser.add_argument("--tool-file", type=Path)
    parser.add_argument("--logs-file", type=Path)
    parser.add_argument("--attempt")
    parser.add_argument("--stage", choices=("research", "lean"))
    parser.add_argument("--allocation", choices=("normal", "reserve"), default="normal")
    parser.add_argument("--retry-of")
    parser.add_argument("--reason")
    args = parser.parse_args()
    if args.command == "freeze":
        if not args.projects_file:
            parser.error("--projects-file requires actual list_projects metadata")
        print(json.dumps(freeze(read_json(args.projects_file))))
        return
    bridge = current_bridge()
    if args.command == "register":
        _limits(bridge, "configurations")
        result = {"config_id": bridge.register(allocation=args.allocation), "plan_hash": bridge.plan.hash}
    elif args.command == "claim":
        if not args.stage:
            parser.error("--stage required")
        _limits(bridge, args.stage)
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
