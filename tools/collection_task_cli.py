"""Local metadata/accounting helpers; no QC/network execution capability."""
from pathlib import Path
import hashlib
import json
import re

from qresearch.artifacts import canonical_json, content_hash
from qresearch.deployment_sources import parse_manifest
from qresearch.engineering_data import verify_deployment
from qresearch.collection_tasks import CollectionTaskPlan, CollectionTaskBridge
from qresearch.collection_execution import collection_research_observation
from research import ROOT, read_json, write_changed, open_registry, export_usage
from stages import source_manifest


def built_deployment_manifest():
    """Select the explicit new policy while retaining legacy build compatibility."""
    record = read_json(ROOT / "audit/deployment.json")
    if not isinstance(record, dict) or "source_files" not in record:
        raise ValueError("A built local deployment manifest is required")
    manifest = record.get("deployment_manifest", record["source_files"])
    version, records = parse_manifest(manifest)
    if version == 2:
        # New admissions must prove the author's original source, even though
        # an admitted worker may later use the declared bounded EOF policy.
        # The v1 branch retains the historical preparation/recovery contract.
        verify_deployment(manifest, content_hash(manifest), source_root=ROOT / "cloud", require_source_bytes=True)
        observed = {path.relative_to(ROOT / "cloud").as_posix()
                    for path in (ROOT / "cloud").rglob("*")
                    if path.is_file() and path.suffix.lower() == ".py" and "__pycache__" not in path.parts
                    and path.relative_to(ROOT / "cloud").as_posix()
                        not in {"_engineering_task_input.py", "_collection_task_input.py"}}
        if observed != set(records):
            raise ValueError("The complete managed local Python set differs from the frozen deployment")
    return manifest


def execution_source_manifest():
    """Pin code/config/budget POLICY, not its mutable charged-usage projection.

    The independent review manifest remains the full stages.source_manifest.
    Register/claim legitimately update usage; that cannot invalidate their own
    frozen input or require a fresh configuration charge.
    """
    files = dict(source_manifest()["source_files"])
    budget = read_json(ROOT / "config/budget.json")
    budget.pop("usage", None)
    # This is a replayed allowance/usage projection, not calculation policy.
    # Its immutable cycle identity is separately bound by the Registry grant.
    budget.pop("configuration_cycle", None)
    files["config/budget.json"] = hashlib.sha256(canonical_json(budget)).hexdigest()
    return {"source_files": files, "source_hash": content_hash({"schema": "collection_execution_sources_v1", "source_files": files})}


def freeze_task(raw, listing, *, field_catalog):
    if (not isinstance(listing, dict) or listing.get("success") is not True
            or not isinstance(listing.get("projects"), list)):
        raise ValueError("Actual successful list_projects metadata is required")
    ids = [item["projectId"] for item in listing["projects"]]
    raw = json.loads(canonical_json(raw))
    if not isinstance(raw.get("collection_plan"), dict):
        raise ValueError("Fill the explicit collection interval and source version before freezing")
    digest = execution_source_manifest()["source_hash"]
    raw["source_manifest_hash"] = digest
    raw["collection_plan"]["source_manifest_hash"] = digest
    raw["deployment_hash"] = content_hash(built_deployment_manifest())
    selected = raw["collection_plan"].get("fields", [])
    # The proposed document cannot redefine the trusted source field semantics.
    expected = {path: field_catalog[path] for path in selected if path in field_catalog}
    if raw.get("field_catalog") is not None and raw["field_catalog"] != expected:
        raise ValueError("Proposed task catalog differs from the trusted source catalog")
    raw["field_catalog"] = expected
    plan = CollectionTaskPlan.from_dict(raw, discovered_project_ids=ids, field_catalog=field_catalog)
    registry = open_registry()
    key, listing_key = "collection/frozen-plans/" + plan.hash + ".json", "collection/project-listings/" + content_hash(listing) + ".json"
    registry.store.write_once(key, canonical_json(plan.to_dict()))
    registry.store.write_once(listing_key, canonical_json(listing))
    pointer = {"plan_key": key, "plan_hash": plan.hash,
               "project_listing_ref": {"key": listing_key, "sha256": content_hash(listing)}}
    write_changed(ROOT / "audit/collection_current.json", json.dumps(pointer, indent=2) + "\n")
    return dict(pointer, configuration_registered=False, execution_started=False)


def current_bridge(*, field_catalog):
    pointer, registry = read_json(ROOT / "audit/collection_current.json"), open_registry()
    raw = json.loads(registry.store.read_bytes(pointer["plan_key"]))
    reference = pointer["project_listing_ref"]
    listing = json.loads(registry.store.read_bytes(reference["key"]))
    if content_hash(raw) != pointer["plan_hash"] or content_hash(listing) != reference["sha256"] or listing.get("success") is not True:
        raise ValueError("Frozen collection task or discovery evidence changed")
    plan = CollectionTaskPlan.from_dict(raw, discovered_project_ids=[x["projectId"] for x in listing["projects"]], field_catalog=field_catalog)
    return CollectionTaskBridge(registry, plan)


def bridge_for_attempt(attempt, *, registry=None):
    """Resolve historical results from charged immutable identity, not today.

    The catalog was checked when this configuration was admitted. Reusing that
    persisted catalog for settlement grants no new registration/dispatch rights.
    """
    if not isinstance(attempt, str) or re.fullmatch(r"[0-9a-f]{32}", attempt) is None:
        raise ValueError("An existing canonical collection attempt ID is required")
    registry = open_registry() if registry is None else registry
    matches = [record for record in registry.snapshot()["attempts"] if record["attempt_id"] == attempt]
    if len(matches) != 1:
        raise ValueError("Unknown charged collection attempt")
    record = matches[0]
    encoded = registry.store.read_bytes("configurations/" + record["config_id"] + ".json")
    package = json.loads(encoded)
    if (canonical_json(package) != encoded or content_hash(package) != record["config_id"]
            or set(package) != {"engineering_task_schema_version", "plan"}
            or type(package["engineering_task_schema_version"]) is not int or package["engineering_task_schema_version"] != 1
            or not isinstance(package["plan"], dict) or package["plan"].get("task_kind") != "historical_collection"):
        raise ValueError("Attempt does not identify an immutable collection configuration")
    raw = package["plan"]
    plan = CollectionTaskPlan.from_dict(raw, discovered_project_ids=(raw["project_id"],), field_catalog=raw["field_catalog"])
    bridge = CollectionTaskBridge(registry, plan)
    if bridge.config_id != record["config_id"]:
        raise ValueError("Persisted collection configuration is not canonical")
    bridge._record(attempt)
    return bridge


def admitted_input(bridge, attempt):
    """Check persisted input bytes/bindings without reading new source files."""
    record = bridge._record(attempt)
    encoded = bridge.store.read_bytes("collection/admitted-inputs/" + record["attempt_id"] + ".json")
    admission = json.loads(encoded)
    expected_path = "audit/collection_task_inputs/" + record["attempt_id"] + ".py"
    if (canonical_json(admission) != encoded or not isinstance(admission, dict)
            or set(admission) != {"payload", "deployment", "input_path", "cloud_input_path"}
            or admission["input_path"] != expected_path or admission["cloud_input_path"] != "_collection_task_input.py"):
        raise ValueError("Admitted collection input shape or destination changed")
    payload = admission["payload"]
    if not isinstance(payload, dict) or not isinstance(payload.get("deployment_manifest"), dict) or not payload["deployment_manifest"]:
        raise ValueError("Original deployment manifest is missing")
    manifest = payload["deployment_manifest"]
    # Only validate the persisted contract; do not upgrade/rebind old inputs.
    parse_manifest(manifest)
    if (payload != dict(bridge.payload(record["attempt_id"]), deployment_manifest=manifest)
            or content_hash(manifest) != bridge.plan.to_dict()["deployment_hash"]):
        raise ValueError("Admitted input differs from its immutable registered attempt")
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode("utf-8")) + "\n"
    expected = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    if admission["deployment"] != expected:
        raise ValueError("Original admitted input hash or deployment identity changed")
    path = ROOT / expected_path
    if path.exists() and path.read_bytes() != text.encode("utf-8"):
        raise ValueError("Stored local input bytes differ from the admitted payload")
    return admission


def prepare_task(bridge, attempt):
    record = bridge._record(attempt)
    if record["status"] not in {"started", "pending", "ambiguous"}:
        raise ValueError("Finalized collection tasks cannot create a fresh remote input")
    if bridge.store.exists("collection/admitted-inputs/" + record["attempt_id"] + ".json"):
        return admitted_input(bridge, record["attempt_id"])
    payload = bridge.payload(attempt)
    manifest = built_deployment_manifest()
    if (content_hash(manifest) != bridge.plan.to_dict()["deployment_hash"]
            or execution_source_manifest()["source_hash"] != bridge.plan.to_dict()["source_manifest_hash"]):
        raise ValueError("Re-freeze a new source-bound task after implementation or catalog changes")
    payload["deployment_manifest"] = manifest
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode("utf-8")) + "\n"
    path = ROOT / "audit/collection_task_inputs" / (record["attempt_id"] + ".py")
    # Immutable local input, distinct from the old in-flight engineering input.
    if path.exists() and path.read_bytes() != text.encode("utf-8"):
        raise ValueError("Previously admitted collection input bytes cannot change")
    write_changed(path, text)
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                  "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    admission = {"payload": payload, "deployment": deployment, "input_path": path.relative_to(ROOT).as_posix(),
                 "cloud_input_path": "_collection_task_input.py"}
    bridge.store.write_once("collection/admitted-inputs/" + record["attempt_id"] + ".json", canonical_json(admission))
    return admission


def verify_current_source(bridge):
    if (execution_source_manifest()["source_hash"] != bridge.plan.to_dict()["source_manifest_hash"]
            or content_hash(built_deployment_manifest()) != bridge.plan.to_dict()["deployment_hash"]):
        raise ValueError("Re-freeze source and deployment before new configuration or Research charging")


def execute_metadata_command(args, *, field_catalog=None):
    if args.command == "freeze-task":
        if args.task_file is None or args.projects_file is None:
            raise ValueError("freeze-task requires an explicit task file and actual project listing")
        return freeze_task(read_json(args.task_file), read_json(args.projects_file), field_catalog=field_catalog)
    if args.command == "task-status":
        registry = open_registry()
        if getattr(args, "attempt", None):
            bridge_for_attempt(args.attempt, registry=registry)
        return registry.snapshot()
    if args.command in {"research-result", "prepare-task"}:
        if not args.attempt:
            raise ValueError("An existing precharged attempt ID is required")
        bridge = bridge_for_attempt(args.attempt)
    else:
        bridge = current_bridge(field_catalog=field_catalog)
    try:
        if args.command in {"register-task", "claim-task"}:
            verify_current_source(bridge)
        if args.command == "register-task":
            return {"config_id": bridge.register(allocation=args.allocation), "plan_hash": bridge.plan.hash}
        if args.command == "claim-task":
            return vars(bridge.claim(allocation=args.allocation, retry_of=args.retry_of, reason=args.reason))
        if not args.attempt:
            raise ValueError("An existing precharged attempt ID is required")
        if args.command == "prepare-task":
            return prepare_task(bridge, args.attempt)
        if args.command == "research-result":
            if args.tool_file is None:
                raise ValueError("An actual native completed Research observation is required")
            admission = admitted_input(bridge, args.attempt)
            parsed = collection_research_observation(admission["payload"], admission["deployment"], read_json(args.tool_file),
                field_catalog=bridge.plan.to_dict()["field_catalog"])
            bridge.record_submission(args.attempt, parsed["submission"])
            return vars(bridge.consume_completion(args.attempt, completion_source=lambda _: parsed["completion"]))
        raise ValueError("Unknown collection metadata command")
    finally:
        export_usage(bridge.registry)
