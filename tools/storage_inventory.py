"""Prepare/account one explicitly granted inventory cell; never calls QC itself."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import canonical_json, content_hash
from qresearch.storage_inventory_tasks import (InventoryTaskPlan, InventoryTaskBridge,
    WORKER_PATH, prepare_input, admitted_input, cell_source, reserve_dispatch, settle_result)
from qresearch.registry import RegistryError
from research import read_json, write_changed, open_registry, export_usage
from deployment_preflight import _project_ids


def worker_identity():
    path = ROOT / "cloud" / WORKER_PATH
    raw = path.read_bytes()
    normalized = path.read_text(encoding="utf-8-sig").encode("utf-8")
    if raw != normalized or b"\x00" in raw or len(raw.decode("utf-8")) > 60800:
        raise ValueError("Inventory worker must be canonical LF UTF8 source within the platform limit")
    digest = sha256(raw).hexdigest()
    return {"path": WORKER_PATH, "worker_sha256": digest, "source_manifest_hash": digest,
            "characters": len(raw.decode("utf-8"))}


def preview(raw, projects):
    value = json.loads(canonical_json(raw))
    worker = worker_identity()
    value.update({key: worker[key] for key in ("worker_sha256", "source_manifest_hash")})
    plan = InventoryTaskPlan.from_dict(value, discovered_project_ids=_project_ids(projects))
    package = {"engineering_task_schema_version": 1, "plan": plan.to_dict()}
    return {"plan": plan.to_dict(), "plan_hash": plan.hash, "package": package,
        "configuration_hash": content_hash(package), "worker_source": worker,
        "ready_to_dispatch": False, "configuration_registered": False, "execution_started": False}


def freeze(raw, projects):
    result = preview(raw, projects)
    registry = open_registry()
    plan_key = "object-store-inventory/frozen-plans/" + result["plan_hash"] + ".json"
    listing_key = "object-store-inventory/project-listings/" + content_hash(projects) + ".json"
    pointer = {"plan_key": plan_key, "plan_hash": result["plan_hash"],
        "project_listing_ref": {"key": listing_key, "sha256": content_hash(projects)}}
    with registry.store.locked(registry.LOCK):
        registry._enforce_engineering_project(registry._replay(), result["package"])
        registry.store.write_once(plan_key, canonical_json(result["plan"]))
        registry.store.write_once(listing_key, canonical_json(projects))
        write_changed(ROOT / "audit/inventory_current.json", json.dumps(pointer, ensure_ascii=False, indent=2) + "\n")
    return dict(pointer, configuration_registered=False, execution_started=False)


def current_bridge():
    pointer = read_json(ROOT / "audit/inventory_current.json")
    registry = open_registry()
    raw = registry.store.read_bytes(pointer["plan_key"])
    plan_doc = json.loads(raw)
    reference = pointer["project_listing_ref"]
    projects_raw = registry.store.read_bytes(reference["key"])
    projects = json.loads(projects_raw)
    if (canonical_json(plan_doc) != raw or content_hash(plan_doc) != pointer["plan_hash"]
            or canonical_json(projects) != projects_raw or content_hash(projects) != reference["sha256"]):
        raise ValueError("Frozen inventory plan/project metadata changed")
    return InventoryTaskBridge(registry, InventoryTaskPlan.from_dict(plan_doc,
        discovered_project_ids=_project_ids(projects)))


def bridge_for_attempt(attempt):
    if type(attempt) is not str or re.fullmatch(r"[0-9a-f]{32}", attempt) is None:
        raise ValueError("An original inventory attempt is required")
    registry = open_registry()
    records = [r for r in registry.snapshot()["attempts"] if r["attempt_id"] == attempt]
    if len(records) != 1: raise ValueError("Unknown inventory attempt")
    raw = registry.store.read_bytes("configurations/" + records[0]["config_id"] + ".json")
    package = json.loads(raw)
    if (canonical_json(package) != raw or content_hash(package) != records[0]["config_id"]
            or type(package) is not dict or set(package) != {"engineering_task_schema_version", "plan"}
            or type(package["engineering_task_schema_version"]) is not int or package["engineering_task_schema_version"] != 1):
        raise ValueError("Original inventory package is invalid")
    plan = InventoryTaskPlan.from_dict(package["plan"], discovered_project_ids=(package["plan"]["project_id"],))
    bridge = InventoryTaskBridge(registry, plan)
    bridge._record(attempt)
    return bridge


def preflight(bridge):
    worker = worker_identity()
    if any(worker[key] != bridge.plan.to_dict()[key] for key in ("worker_sha256", "source_manifest_hash")):
        raise ValueError("Inventory worker must remain frozen before dispatch")
    return worker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preview", "freeze", "register", "claim", "prepare", "cell", "dispatch", "result", "status"))
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--projects-file", type=Path)
    parser.add_argument("--tool-file", type=Path)
    parser.add_argument("--attempt")
    parser.add_argument("--allocation", choices=("normal",), default="normal")
    args = parser.parse_args(argv)
    try:
        if args.command in {"preview", "freeze"}:
            if args.plan_file is None or args.projects_file is None:
                raise ValueError("Actual project listing and explicit inventory plan required")
            result = (preview if args.command == "preview" else freeze)(read_json(args.plan_file),read_json(args.projects_file))
        elif args.command == "status":
            result = open_registry().snapshot()
        else:
            bridge = bridge_for_attempt(args.attempt) if args.command in {"prepare", "cell", "dispatch", "result"} else current_bridge()
            if args.command in {"register", "claim", "prepare", "cell", "dispatch"}: preflight(bridge)
            if args.command == "register": result = {"configuration_hash":bridge.register(allocation=args.allocation)}
            elif args.command == "claim": result = vars(bridge.claim(allocation=args.allocation))
            elif args.command == "prepare": result = prepare_input(bridge,args.attempt)
            elif args.command == "cell":
                admission = admitted_input(bridge,args.attempt)
                result = {"source":cell_source(admission["payload"]),"cell_source_sha256":admission["cell_source_sha256"],"ready_to_dispatch":False}
            elif args.command == "dispatch":
                if args.tool_file is None: raise ValueError("Actual native read-cell envelope required")
                result = reserve_dispatch(bridge,args.attempt,read_json(args.tool_file))
            else:
                if args.tool_file is None: raise ValueError("Actual native execute-cell envelope required")
                result = vars(settle_result(bridge,args.attempt,read_json(args.tool_file)))
            if args.command not in {"cell", "dispatch"}: export_usage(bridge.registry)
    except (ValueError,TypeError,KeyError,OSError,RegistryError):
        print(json.dumps({"ready_to_dispatch":False,"error":"Invalid or unavailable inventory metadata; reconcile original task before retry","financial_evidence":False}))
        return 2
    print(json.dumps(result,ensure_ascii=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
