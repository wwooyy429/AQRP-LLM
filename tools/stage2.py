"""Prepare and account for one fixed QC engineering job; no network calls.

Only trusted tool observations pass through the fixed receipt parsers. This CLI
does not call a provider, poll a backtest, certify historical coverage, or trade.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import canonical_json, content_hash
from qresearch.deployment_sources import parse_manifest
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge, EngineeringTaskError, submission_protocol
from qresearch.engineering_data import verify_deployment
from qresearch.registry import BudgetExceeded
from research import read_json, write_changed, open_registry, export_usage
from stages import source_manifest


def _write(path, document):
    write_changed(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def local_deployment_preflight(*, expected_hash=None):
    """Check the declared build against physical local sources before writing.

    This establishes a local prerequisite only. It does not certify a cloud
    readback, worker packaging, market coverage or permission to dispatch.
    """
    record = read_json(ROOT / "audit" / "deployment.json")
    if not isinstance(record, dict) or "source_files" not in record:
        raise ValueError("A built local deployment manifest is required")
    manifest = record.get("deployment_manifest", record["source_files"])
    version, records = parse_manifest(manifest)
    expected = content_hash(manifest) if expected_hash is None else expected_hash
    verify_deployment(manifest, expected, source_root=ROOT / "cloud", require_source_bytes=True)
    generated = {"_engineering_task_input.py"}
    if version == 2:
        generated.add("_collection_task_input.py")
    observed = {path.relative_to(ROOT / "cloud").as_posix()
                for path in (ROOT / "cloud").rglob("*")
                if path.is_file() and path.suffix.lower() == ".py" and "__pycache__" not in path.parts
                and path.relative_to(ROOT / "cloud").as_posix() not in generated}
    if observed != set(records):
        raise ValueError("The complete managed local Python set differs from the frozen deployment")
    return manifest


def freeze(projects, *, plan_file=None, preview=False):
    if projects.get("success") is not True or not isinstance(projects.get("projects"), list):
        raise ValueError("An actual successful QC project listing is required")
    ids = [item["projectId"] for item in projects["projects"]]
    raw = read_json(plan_file or ROOT / "config" / "engineering.json")
    raw["project_id"] = read_json(ROOT / "config" / "quantconnect.json")["active_project_id"]
    raw["source_manifest_hash"] = source_manifest()["source_hash"]
    probe_catalog = None
    if raw.get("schema_version") in {2, 3, 4}:
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
    deployment = local_deployment_preflight()
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
    # Every plan version shares the same project input. Check before any
    # pointer/plan/listing write, under the ledger's transaction lock.
    with registry.store.locked(registry.LOCK):
        registry._enforce_engineering_project(registry._replay(), {"engineering_task_schema_version": 1, "plan": plan.to_dict()})
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


def bridge_for_attempt(attempt, *, registry=None):
    """Recover a charged Engineering task without consulting mutable pointers.

    The configuration was admitted with its project/source/catalog at dispatch.
    Reading it again authorizes settlement only, not a new charge or dispatch.
    """
    if not isinstance(attempt, str) or re.fullmatch(r"[0-9a-f]{32}", attempt) is None:
        raise ValueError("An existing canonical engineering attempt ID is required")
    registry = open_registry() if registry is None else registry
    records = [item for item in registry.snapshot()["attempts"] if item["attempt_id"] == attempt]
    if len(records) != 1:
        raise ValueError("Unknown charged engineering attempt")
    record = records[0]
    encoded = registry.store.read_bytes("configurations/" + record["config_id"] + ".json")
    package = json.loads(encoded)
    if (canonical_json(package) != encoded or content_hash(package) != record["config_id"]
            or not isinstance(package, dict) or set(package) != {"engineering_task_schema_version", "plan"}
            or type(package["engineering_task_schema_version"]) is not int or package["engineering_task_schema_version"] != 1
            or not isinstance(package["plan"], dict) or package["plan"].get("task_kind") == "historical_collection"):
        raise ValueError("Attempt does not identify an immutable Engineering configuration")
    raw = package["plan"]
    plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=(raw.get("project_id"),))
    bridge = EngineeringTaskBridge(registry, plan)
    if bridge.config_id != record["config_id"]:
        raise ValueError("Persisted Engineering configuration is not canonical")
    bridge._record(attempt)
    return bridge


def admitted_input(bridge, attempt):
    """Validate original metadata and input bytes for either plan version."""
    record = bridge._record(attempt)
    encoded = bridge.store.read_bytes("engineering/admitted-inputs/" + record["attempt_id"] + ".json")
    admission = json.loads(encoded)
    expected_path = "audit/task_inputs/" + record["attempt_id"] + ".py"
    legacy_keys = {"payload", "deployment", "input_path", "cloud_input_path"}
    if (canonical_json(admission) != encoded or not isinstance(admission, dict)
            or set(admission) not in (legacy_keys, legacy_keys | {"research_entry_protocol"})
            or admission["input_path"] != expected_path or admission["cloud_input_path"] != "_engineering_task_input.py"):
        raise ValueError("Original engineering input shape or destination changed")
    payload = admission["payload"]
    if not isinstance(payload, dict) or not isinstance(payload.get("deployment_manifest"), dict) or not payload["deployment_manifest"]:
        raise ValueError("Original engineering deployment manifest is missing")
    manifest = payload["deployment_manifest"]
    # Validate the original contract without replacing its version, EOF policy
    # or bytes with today's built manifest. Settlement is not a new admission.
    parse_manifest(manifest)
    if (payload != dict(bridge.payload(record["attempt_id"]), deployment_manifest=manifest)
            or content_hash(manifest) != bridge.plan.to_dict()["deployment_hash"]):
        raise ValueError("Original engineering input differs from its frozen attempt")
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode("utf-8")) + "\n"
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
        "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    if admission["deployment"] != deployment:
        raise ValueError("Original engineering input hash or deployment changed")
    if "research_entry_protocol" in admission:
        from qresearch.engineering_receipts import research_entry_protocol
        if (record["stage"] != "research" or canonical_json(admission["research_entry_protocol"])
                != canonical_json(research_entry_protocol(payload, deployment))):
            raise ValueError("Original Research admission protocol identity changed")
    path = ROOT / expected_path
    if path.exists() and path.read_bytes() != text.encode("utf-8"):
        raise ValueError("Local engineering input bytes differ from the admitted payload")
    return admission


def prepare(bridge, attempt):
    # Serialize only this input publication, separately from Registry's lock.
    # Snapshot/payload validation below must remain free to take that lock.
    record = bridge._record(attempt)
    with bridge.store.locked("engineering/prepare/" + record["attempt_id"]):
        return _prepare_input(bridge, record["attempt_id"])


def _prepare_input(bridge, attempt):
    record = bridge._record(attempt)
    if bridge.store.exists("engineering/admitted-inputs/" + record["attempt_id"] + ".json"):
        return admitted_input(bridge, record["attempt_id"])
    if record["status"] not in {"started", "pending", "ambiguous"}:
        raise ValueError("Finalized engineering attempts cannot create fresh input")
    payload = bridge.payload(attempt)
    manifest = joint_preflight(bridge)
    payload["deployment_manifest"] = manifest
    text = "TASK_INPUT_JSON = " + repr(canonical_json(payload).decode()) + "\n"
    path = ROOT / "audit" / "task_inputs" / (attempt + ".py")
    if path.exists() and path.read_bytes() != text.encode("utf-8"):
        raise ValueError("Previously prepared engineering input bytes cannot change")
    write_changed(path, text)
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
        "deployment_hash": payload["identity"]["deployment_hash"],
        "input_hash": hashlib.sha256(text.encode()).hexdigest()}
    admission = {"payload": payload, "deployment": deployment,
        "input_path": path.relative_to(ROOT).as_posix(), "cloud_input_path": "_engineering_task_input.py"}
    if record["stage"] == "research":
        from qresearch.engineering_receipts import research_entry_protocol
        # Protocol identity is published atomically with the admission itself.
        # A later sidecar write fault must never turn a new task into legacy.
        admission["research_entry_protocol"] = research_entry_protocol(payload, deployment)
    bridge.store.write_once("engineering/admitted-inputs/" + attempt + ".json", canonical_json(admission))
    if record["stage"] == "lean":
        # A new dispatch can rely on the accepted-pointer-before-original
        # publication protocol only when it was pinned before returning input.
        # Existing admission recovery above deliberately never backfills this.
        bridge.store.write_once("engineering/submission-protocol/" + attempt + ".json",
                                canonical_json(submission_protocol(payload, deployment)))
    else:
        # Old admitted input recovery above must never manufacture this marker.
        # It pins that this new admission requires the fixed no-catch Research
        # entry before a dispatch binding can be written. Started alone does
        # not establish that a legacy cell was never sent to the platform.
        bridge.store.write_once("engineering/research-entry-protocol/" + attempt + ".json",
                                canonical_json(admission["research_entry_protocol"]))
    return admission


def joint_preflight(bridge):
    document = bridge.plan.to_dict()
    manifest = local_deployment_preflight(expected_hash=document["deployment_hash"])
    if document["schema_version"] not in {2, 3, 4}:
        # Legacy full manifests included mutable budget usage. Rechecking that
        # identity here would invalidate a v1 plan after its own first debit.
        # Its frozen physical implementation remains strictly checked above;
        # v2 provides the stable controller/catalog identity for new pilots.
        return manifest
    from collection_task_cli import execution_source_manifest
    from stage2_collection import catalog
    EngineeringTaskPlan.from_dict(document, discovered_project_ids=(document["project_id"],), probe_field_catalog=catalog())
    if (execution_source_manifest()["source_hash"] != document["source_manifest_hash"]
            or content_hash(manifest) != document["deployment_hash"]):
        raise ValueError("Joint engineering source and deployment must be frozen before new charging")
    return manifest


def research_cell(bridge, attempt):
    """Produce the fixed no-catch entry only; this does not authorize a call."""
    record = bridge._record(attempt)
    if record["stage"] != "research":
        raise EngineeringTaskError("Only a Research attempt has a Research cell")
    from qresearch.engineering_receipts import research_cell_source
    admission = admitted_input(bridge, attempt)
    source = research_cell_source(admission["payload"], admission["deployment"])
    return {"source": source, "cell_source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "execution_started": False, "budget_charged": False, "ready_to_dispatch": False}


def _research_dispatch_key(attempt):
    return "engineering/research-dispatch/" + attempt + ".json"


def _read_research_dispatch(bridge, payload, deployment, *, require_dispatch=False):
    from qresearch.engineering_receipts import _research_binding
    key = _research_dispatch_key(payload["identity"]["attempt_id"])
    if not bridge.store.exists(key):
        if require_dispatch:
            _read_research_entry_protocol(bridge, payload, deployment)
            raise EngineeringTaskError("New Research entries require their original dispatch binding before settlement")
        return None
    _read_research_entry_protocol(bridge, payload, deployment)
    encoded = bridge.store.read_bytes(key)
    binding = json.loads(encoded)
    if canonical_json(binding) != encoded:
        raise EngineeringTaskError("Original Research dispatch binding is not canonical")
    _research_binding(binding, payload, deployment, binding.get("arguments") if isinstance(binding, dict) else None)
    return binding


def _read_research_entry_protocol(bridge, payload, deployment):
    from qresearch.engineering_receipts import research_entry_protocol
    expected = canonical_json(research_entry_protocol(payload, deployment))
    key = "engineering/research-entry-protocol/" + payload["identity"]["attempt_id"] + ".json"
    if not bridge.store.exists(key) or bridge.store.read_bytes(key) != expected:
        raise EngineeringTaskError("Original Research entry protocol is required; legacy inputs cannot be backfilled")


def research_dispatch(bridge, attempt, tool_envelope):
    """Pin actual read-cell source once before dispatch; repeat never reruns.

    A missing response after this marker stays unresolved. This method cannot
    know whether the caller sent the subsequent API request, so its marker may
    not be deleted/backfilled to obtain another free execution. The trusted
    dispatcher supplies the actual source-read observation and performs the
    single precharged call only when should_execute is true.
    """
    record = bridge._record(attempt)
    if record["stage"] != "research":
        raise EngineeringTaskError("Only a charged Research attempt can pin a Research dispatch")
    admission = admitted_input(bridge, attempt)
    payload, deployment = admission["payload"], admission["deployment"]
    from qresearch.engineering_receipts import research_dispatch_binding
    binding = research_dispatch_binding(payload, deployment, tool_envelope)
    _read_research_entry_protocol(bridge, payload, deployment)
    existing = _read_research_dispatch(bridge, payload, deployment)
    if existing is not None:
        if existing != binding:
            raise EngineeringTaskError("A previous Research dispatch cannot be retargeted")
        return {"binding": existing, "should_execute": False, "budget_charged": False}
    joint_preflight(bridge)
    with bridge.store.locked(bridge.registry.LOCK):
        current = bridge.registry._replay()["attempts"][record["attempt_id"]]
        if (current["status"] != "started" or current.get("external_id") is not None
                or bridge.store.exists(bridge._submission_key(record["attempt_id"]))):
            raise EngineeringTaskError("Only an undispatched started Research attempt can pin new execution")
        key = _research_dispatch_key(record["attempt_id"])
        if bridge.store.exists(key):
            encoded = bridge.store.read_bytes(key)
            if encoded != canonical_json(binding):
                raise EngineeringTaskError("A concurrent Research dispatch differs")
            return {"binding": binding, "should_execute": False, "budget_charged": False}
        bridge.store.write_once(key, canonical_json(binding))
    return {"binding": binding, "should_execute": True, "budget_charged": False}


def settle_research_result(bridge, attempt, tool_envelope):
    """Parse before writes and retain exact failed-result replay semantics."""
    from qresearch.engineering_receipts import research_observation
    admission = admitted_input(bridge, attempt)
    payload, deployment = admission["payload"], admission["deployment"]
    entry_key = "engineering/research-entry-protocol/" + payload["identity"]["attempt_id"] + ".json"
    # New admissions pin their protocol in the same immutable record; a fault
    # publishing its sidecar cannot silently downgrade them to legacy. Older
    # admissions with a pinned sidecar (including original f5d) retain that gate.
    require_dispatch = "research_entry_protocol" in admission or bridge.store.exists(entry_key)
    binding = _read_research_dispatch(bridge, payload, deployment, require_dispatch=require_dispatch)
    observed = research_observation(payload, deployment, tool_envelope,
        dispatch_binding=binding, dispatch_required=require_dispatch)
    record = bridge._record(attempt)
    if record["status"] == "failed":
        # The general Bridge deliberately rejects a new accepted submission
        # after failure. Replays here require both immutable original receipts,
        # not merely the same logical id or another apparently failed cell.
        original = bridge._recorded_submission(payload)
        receipt = observed["submission"]
        if original["receipt_ref"]["sha256"] != content_hash(receipt):
            raise EngineeringTaskError("A different Research receipt cannot replace the original failure")
        bridge._completion_contract(payload, original, observed["completion"])
        digest = content_hash(observed["completion"])
        expected = {"key": "engineering/evidence/" + attempt + "/completion/" + digest + ".json", "sha256": digest}
        if (not isinstance(record.get("error"), dict) or record["error"].get("evidence_ref") != expected
                or bridge.store.read_bytes(expected["key"]) != canonical_json(observed["completion"])):
            raise EngineeringTaskError("Original Research terminal evidence differs")
        return bridge._attempt(record)
    bridge.record_submission(attempt, observed["submission"])
    return bridge.consume_completion(attempt, completion_source=lambda _: observed["completion"])


def _limits(bridge, kind):
    # Compatibility/status preview only. Registry transactions recheck the
    # shared stop condition atomically with registration or attempt charging.
    try:
        bridge.registry.check_engineering_admission(bridge.package, kind)
    except BudgetExceeded as exc:
        raise ValueError(str(exc)) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preview", "freeze", "register", "claim", "prepare", "research-cell", "research-dispatch", "research-result", "backtest-submission", "backtest-rejection", "backtest-result", "status"))
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
    if args.command == "status":
        registry = open_registry()
        if args.attempt:
            bridge_for_attempt(args.attempt, registry=registry)
        print(json.dumps(registry.snapshot(), ensure_ascii=True))
        return
    if args.command in {"prepare", "research-cell", "research-dispatch", "research-result", "backtest-submission", "backtest-rejection", "backtest-result"}:
        if not args.attempt:
            parser.error("--attempt is required for an existing charged task")
        bridge = bridge_for_attempt(args.attempt)
    else:
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
    elif args.command == "research-cell":
        result = research_cell(bridge, args.attempt)
    elif args.command == "research-dispatch":
        if not args.tool_file:
            parser.error("--tool-file with the actual read-cell observation is required")
        result = research_dispatch(bridge, args.attempt, read_json(args.tool_file))
    else:
        if not args.attempt or not args.tool_file:
            parser.error("--attempt and --tool-file with actual tool metadata required")
        from qresearch.engineering_receipts import research_observation, backtest_submission, backtest_rejection, backtest_observation
        admitted = admitted_input(bridge, args.attempt)
        payload, deployment = admitted["payload"], admitted["deployment"]
        native = read_json(args.tool_file)
        if args.command == "research-result":
            result = vars(settle_research_result(bridge, args.attempt, native))
        elif args.command == "backtest-submission":
            result = vars(bridge.record_submission(args.attempt, backtest_submission(payload, deployment, native)))
        elif args.command == "backtest-rejection":
            result = vars(bridge.record_rejection(args.attempt, backtest_rejection(payload, deployment, native)))
        else:
            if not args.logs_file:
                parser.error("--logs-file with actual completed-job log observations required")
            record = bridge._record(args.attempt)
            observed = backtest_observation(payload, deployment, record["external_id"], native, read_json(args.logs_file))
            result = vars(bridge.consume_completion(args.attempt, completion_source=lambda _: observed))
    if args.command not in {"research-cell", "research-dispatch"}:
        export_usage(bridge.registry)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
