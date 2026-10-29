"""Trusted local certification dispatcher/accounting CLI; no network calls.

Real references are cloud-resident. This CLI accepts metadata/native aggregate
receipts only, requires a separately user-authorized Registry grant and never
calls a provider, executes a cell, polls a backtest or changes a budget limit.
"""
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
from qresearch.certification_tasks import (CertificationTaskPlan, CertificationTaskBridge,
    prepare_input, admitted_input, cell_source, reserve_dispatch, settle_result)
from qresearch.engineering_receipts import _json
from qresearch.registry import RegistryError
from research import read_json, write_changed, open_registry, export_usage
from collection_task_cli import execution_source_manifest, built_deployment_manifest
from deployment_preflight import _project_ids


def _write(path, value):
    write_changed(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def catalog():
    fields = read_json(ROOT / "config/source_catalog.json")["fields"]
    return {name: {"unit": spec["unit"], "period_accessor": spec["period_accessor"]}
            for name, spec in fields.items() if type(spec) is dict and spec.get("role") == "as_reported_financial_value"
            and spec.get("kind") == "number" and type(spec.get("unit")) is str and type(spec.get("period_accessor")) is str}


def preview(raw, projects):
    ids = _project_ids(projects)
    value = json.loads(canonical_json(raw))
    digest = execution_source_manifest()["source_hash"]
    value["source_manifest_hash"] = digest
    value["certification_plan"]["source_manifest_hash"] = digest
    value["deployment_hash"] = content_hash(built_deployment_manifest())
    plan = CertificationTaskPlan.from_dict(value, discovered_project_ids=ids, financial_catalog=catalog())
    return {"plan": plan.to_dict(), "plan_hash": plan.hash,
            "package": {"engineering_task_schema_version": 1, "plan": plan.to_dict()},
            "configuration_hash": content_hash({"engineering_task_schema_version": 1, "plan": plan.to_dict()}),
            "ready_to_dispatch": False, "budget_admission_performed": False, "financial_evidence": False}


def freeze(raw, projects):
    result = preview(raw, projects)
    registry = open_registry()
    key = "certification/frozen-plans/" + result["plan_hash"] + ".json"
    listing_key = "certification/project-listings/" + content_hash(projects) + ".json"
    pointer = {"plan_key": key, "plan_hash": result["plan_hash"],
               "project_listing_ref": {"key": listing_key, "sha256": content_hash(projects)}}
    with registry.store.locked(registry.LOCK):
        registry._enforce_engineering_project(registry._replay(), result["package"])
        registry.store.write_once(key, canonical_json(result["plan"]))
        registry.store.write_once(listing_key, canonical_json(projects))
        _write(ROOT / "audit/certification_current.json", pointer)
    return dict(pointer, configuration_registered=False, execution_started=False)


def current_bridge():
    pointer = read_json(ROOT / "audit/certification_current.json")
    registry = open_registry()
    raw = _json(registry.store.read_bytes(pointer["plan_key"]))
    ref = pointer["project_listing_ref"]
    listing = _json(registry.store.read_bytes(ref["key"]))
    if content_hash(raw) != pointer["plan_hash"] or content_hash(listing) != ref["sha256"]:
        raise ValueError("Frozen certification metadata changed")
    plan = CertificationTaskPlan.from_dict(raw, discovered_project_ids=_project_ids(listing), financial_catalog=catalog())
    return CertificationTaskBridge(registry, plan)


def bridge_for_attempt(attempt, *, registry=None):
    if type(attempt) is not str or re.fullmatch(r"[0-9a-f]{32}", attempt) is None:
        raise ValueError("Existing canonical certification attempt is required")
    registry = open_registry() if registry is None else registry
    found = [item for item in registry.snapshot()["attempts"] if item["attempt_id"] == attempt]
    if len(found) != 1:
        raise ValueError("Unknown certification attempt")
    record = found[0]
    raw = registry.store.read_bytes("configurations/" + record["config_id"] + ".json")
    package = _json(raw)
    if (canonical_json(package) != raw or content_hash(package) != record["config_id"]
            or type(package) is not dict or set(package) != {"engineering_task_schema_version", "plan"}
            or type(package["engineering_task_schema_version"]) is not int or package["engineering_task_schema_version"] != 1):
        raise ValueError("Original certification package identity changed")
    value = package["plan"]
    plan = CertificationTaskPlan.from_dict(value, discovered_project_ids=(value.get("project_id"),),
        financial_catalog=value.get("certification_plan", {}).get("financial_catalog"))
    bridge = CertificationTaskBridge(registry, plan)
    bridge._record(attempt)
    return bridge


def preflight(bridge):
    manifest = built_deployment_manifest()
    if (content_hash(manifest) != bridge.plan.to_dict()["deployment_hash"]
            or execution_source_manifest()["source_hash"] != bridge.plan.to_dict()["source_manifest_hash"]):
        raise ValueError("Certification source must be frozen before admission/dispatch")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preview", "freeze", "register", "claim", "prepare", "cell", "dispatch", "result", "status"))
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--projects-file", type=Path)
    parser.add_argument("--tool-file", type=Path)
    parser.add_argument("--attempt")
    parser.add_argument("--allocation", choices=("normal", "reserve"), default="normal")
    args = parser.parse_args(argv)
    try:
        if args.command in {"preview", "freeze"}:
            if args.plan_file is None or args.projects_file is None:
                raise ValueError("Actual project listing and explicit plan are required")
            result = (preview if args.command == "preview" else freeze)(read_json(args.plan_file), read_json(args.projects_file))
        elif args.command == "status":
            result = open_registry().snapshot()
        else:
            bridge = bridge_for_attempt(args.attempt) if args.command in {"prepare", "cell", "dispatch", "result"} else current_bridge()
            if args.command in {"register", "claim", "prepare", "dispatch"}:
                manifest = preflight(bridge)
            if args.command == "register":
                result = {"configuration_hash": bridge.register(allocation=args.allocation)}
            elif args.command == "claim":
                result = vars(bridge.claim(allocation=args.allocation))
            elif args.command == "prepare":
                result = prepare_input(bridge, args.attempt, manifest)
                text = "TASK_INPUT_JSON = " + repr(canonical_json(result["payload"]).decode()) + "\n"
                path = ROOT / "audit/certification_task_inputs" / (args.attempt + ".py")
                if path.exists() and path.read_bytes() != text.encode():
                    raise ValueError("Previously prepared certification source changed")
                write_changed(path, text)
                result = dict(result, input_path=path.relative_to(ROOT).as_posix())
            elif args.command == "cell":
                admission = admitted_input(bridge, args.attempt)
                source = cell_source(admission["payload"], admission["deployment"])
                result = {"source": source, "cell_source_sha256": sha256(source.encode()).hexdigest(), "ready_to_dispatch": False}
            elif args.command == "dispatch":
                if args.tool_file is None:
                    raise ValueError("Actual read-cell tool response is required")
                result = reserve_dispatch(bridge, args.attempt, read_json(args.tool_file))
            else:
                if args.tool_file is None:
                    raise ValueError("Actual native execute-cell response is required")
                result = vars(settle_result(bridge, args.attempt, read_json(args.tool_file)))
            if args.command not in {"cell", "dispatch"}:
                export_usage(bridge.registry)
    except (ValueError, TypeError, KeyError, OSError, RegistryError):
        print(json.dumps({"ready_to_dispatch": False, "error": "Invalid or unavailable certification metadata; reconcile original evidence before retry", "financial_evidence": False}))
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
