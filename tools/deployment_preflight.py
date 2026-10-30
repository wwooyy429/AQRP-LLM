"""Pure readback-reference audit; no provider, dispatch, storage or certification.

Keep actual read_project envelopes containing notebooks in authorized cloud
memory. This function does not persist them; its CLI is for synthetic or otherwise
permitted input files only. Notebook/non-Python contents are never output or
included in the returned source digest. Matching this reference does not certify
worker source, the cloud file inventory, data coverage or budget admission.
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
from qresearch.artifacts import content_hash, validate_key
from qresearch.deployment_sources import build_manifest, parse_manifest
from qresearch.engineering_data import source_bytes_sha256
from qresearch.engineering_receipts import _native, _json


class DeploymentPreflightError(ValueError):
    """Input metadata cannot establish the requested source reference."""


def _fail(message):
    raise DeploymentPreflightError(message)


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _path(value):
    try:
        validate_key(value)
        if len(value) > 160 or "\x7f" in value:
            _fail("Project source paths must be bounded metadata")
        value.encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        _fail("Project source paths must be safe relative POSIX metadata")
    return value


def _manifest(value, expected_hash):
    if not isinstance(value, dict) or not value or not _digest(expected_hash):
        _fail("An explicit nonempty frozen manifest and its hash are required")
    try:
        version, records = parse_manifest(value)
    except (ValueError, TypeError):
        _fail("Frozen implementation manifest is invalid")
    aliases = set()
    for name, record in records.items():
        _path(name)
        if (not name.endswith(".py") or "__pycache__" in name.split("/")
                or name == "_engineering_task_input.py" or not _digest(record["source_sha256"])
                or name.casefold() in aliases):
            _fail("Frozen implementation paths and hashes are invalid or ambiguous")
        aliases.add(name.casefold())
    if content_hash(value) != expected_hash:
        _fail("Frozen deployment manifest hash does not match")
    return version, records


def _project_ids(observation):
    if isinstance(observation, dict) and "tool_name" in observation:
        if (set(observation) != {"tool_name", "arguments", "result"}
                or observation["tool_name"] != "mcp__quantconnect__list_projects"):
            _fail("A successful project listing observation is required")
        args = observation["arguments"]
        if not isinstance(args, dict) or set(args) - {"query", "page"}:
            _fail("Unknown project-listing arguments")
        if "page" in args and (type(args["page"]) is not int or args["page"] < 1):
            _fail("Project-listing pages start at one")
        if "query" in args and not isinstance(args["query"], str):
            _fail("Project-listing query must be text")
        native = _native(observation["result"])
    else:
        native = _native(observation)
    if (not isinstance(native, dict) or native.get("success") is not True
            or set(native) - {"success", "errors", "projects", "page", "totalPages", "nextPage"}
            or native.get("errors") not in (None, []) or not isinstance(native.get("projects"), list)):
        _fail("Project listing did not succeed")
    for key in ("page", "totalPages"):
        if key in native and (type(native[key]) is not int or native[key] < 1):
            _fail("Project listing page metadata is invalid")
    if "nextPage" in native and native["nextPage"] is not None and (
            type(native["nextPage"]) is not int or native["nextPage"] < 1):
        _fail("Project listing next-page metadata is invalid")
    ids = set()
    for record in native["projects"]:
        if (not isinstance(record, dict) or set(record) - {"projectId", "name", "language"}
                or type(record.get("projectId")) is not int or record["projectId"] < 1
                or record["projectId"] in ids or ("name" in record and not isinstance(record["name"], str))
                or ("language" in record and (not isinstance(record["language"], str)
                    or record["language"] not in {"Py", "C#"}))):
            _fail("Project listing identities are invalid or duplicated")
        ids.add(record["projectId"])
    return ids


def read_project_preflight(tool_envelope, projects_record, frozen_manifest, deployment_hash, *, project_id, input_sha256=None):
    """Compare only returned Python sources to the explicit frozen contract."""
    version, records = _manifest(frozen_manifest, deployment_hash)
    manifest = {name: record["source_sha256"] for name, record in records.items()}
    if type(project_id) is not int or project_id < 1 or project_id not in _project_ids(projects_record):
        _fail("The expected project must come from the successful listing")
    if input_sha256 is not None and not _digest(input_sha256):
        _fail("The optional frozen input hash must be canonical SHA-256")
    if (not isinstance(tool_envelope, dict) or set(tool_envelope) != {"tool_name", "arguments", "result"}
            or tool_envelope["tool_name"] != "mcp__quantconnect__read_project"
            or not isinstance(tool_envelope["arguments"], dict)
            or set(tool_envelope["arguments"]) != {"projectId"}
            or type(tool_envelope["arguments"]["projectId"]) is not int
            or tool_envelope["arguments"]["projectId"] != project_id):
        _fail("Read-project tool arguments do not identify the expected project")
    native = _native(tool_envelope["result"])
    if (not isinstance(native, dict) or set(native) - {"success", "errors", "project"}
            or native.get("success") is not True or native.get("errors") not in (None, [])):
        _fail("The native project source read did not succeed")
    project = native.get("project")
    if (not isinstance(project, dict) or set(project) != {"projectId", "name", "language", "files"}
            or type(project["projectId"]) is not int or project["projectId"] != project_id
            or project["language"] != "Py" or not isinstance(project["name"], str)
            or not isinstance(project["files"], list)):
        _fail("Returned project identity or source shape is invalid")
    sources, source_bytes, aliases, input_observed, ignored = {}, {}, set(), None, 0
    ignored_generated = 0
    for file in project["files"]:
        if (not isinstance(file, dict) or set(file) != {"filePath", "content"}
                or not isinstance(file["content"], str)):
            _fail("Returned source entries must be registered path/text objects")
        name = _path(file["filePath"])
        if name.casefold() in aliases:
            _fail("Returned project paths are duplicated or ambiguous")
        aliases.add(name.casefold())
        if not name.lower().endswith(".py"):
            ignored += 1
            continue
        if version == 2 and name == "_collection_task_input.py":
            # A separate collection task's inert input is not implementation
            # source or the engineering input whose exact hash is requested.
            # Never parse, hash or export its contents through this readback.
            ignored_generated += 1
            continue
        try:
            raw = file["content"].encode("utf-8")
            if name == "_engineering_task_input.py":
                input_observed = hashlib.sha256(raw).hexdigest()
            else:
                sources[name] = source_bytes_sha256(raw)
                source_bytes[name] = raw
        except (ValueError, UnicodeError):
            _fail("Returned Python source is not valid UTF-8 text")
    # A PROJECT readback is the author's declared source, not a packaged
    # worker artifact. Even a v2 policy must preserve its original EOF count
    # here; canonical worker equivalence cannot approve a different project.
    observed_manifest = sources
    observed_records = None
    if version == 2 and source_bytes:
        try:
            observed_manifest = build_manifest(source_bytes)
            _, observed_records = parse_manifest(observed_manifest)
        except (ValueError, TypeError):
            _fail("Returned Python source cannot establish its declared source identity")
    elif version == 2:
        # There is no valid nonempty observed manifest to hash. Retain the
        # missing-file diagnostics without manufacturing a valid empty policy.
        observed_manifest = None
    missing = sorted(set(manifest) - set(sources))
    extra = sorted(set(sources) - set(manifest))
    different = sorted(name for name in set(manifest) & set(sources) if manifest[name] != sources[name])
    if observed_records is not None:
        different = sorted(name for name in set(records) & set(observed_records)
                           if records[name] != observed_records[name])
    matches = not missing and not extra and not different
    input_bound = input_sha256 is not None and input_observed == input_sha256
    result = {"schema_version": 1, "kind": "returned_source_reference_preflight", "project_id": project_id,
        "expected_manifest_hash": deployment_hash,
        "observed_source_reference_hash": content_hash(observed_manifest) if observed_manifest is not None else None,
        "expected_implementation_count": len(manifest), "observed_implementation_count": len(sources),
        "missing_from_returned_reference": missing, "unexpected_in_returned_reference": extra,
        "different_paths": different, "files": [{"path":name, "expected_sha256":manifest.get(name),
            "observed_sha256":sources.get(name)} for name in sorted(set(manifest) | set(sources))],
        "ignored_non_python_file_count": ignored, "input_expected": input_sha256 is not None,
        "input_observed_sha256": input_observed, "input_binding_verified": input_bound,
        "source_reference_matches": matches, "preflight_passed": matches and (input_sha256 is None or input_bound),
        "ready_to_dispatch": False, "budget_admission_performed": False,
        "worker_source_verified": False, "full_cloud_inventory_certified": False,
        "financial_evidence": False}
    if version == 2:
        result.update(deployment_manifest_schema_version=2,
                      source_identity_policy=frozen_manifest["source_identity_policy"],
                      ignored_generated_input_file_count=ignored_generated)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-tool-file", required=True, type=Path)
    parser.add_argument("--projects-file", required=True, type=Path)
    parser.add_argument("--manifest-file", required=True, type=Path)
    parser.add_argument("--deployment-hash", required=True)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--input-sha256")
    args = parser.parse_args()
    try:
        manifest = _json(args.manifest_file.read_text(encoding="utf-8-sig"))
        if isinstance(manifest, dict) and "source_files" in manifest:
            manifest = manifest.get("deployment_manifest", manifest["source_files"])
        result = read_project_preflight(_json(args.project_tool_file.read_text(encoding="utf-8-sig")),
            _json(args.projects_file.read_text(encoding="utf-8-sig")), manifest, args.deployment_hash,
            project_id=args.project_id, input_sha256=args.input_sha256)
    except (ValueError, TypeError, OSError):
        print(json.dumps({"preflight_passed":False,"ready_to_dispatch":False,"error":"Invalid deployment preflight input metadata"}))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result["preflight_passed"] else 1)


if __name__ == "__main__":
    main()
