"""Read-only, fixed-evidence assessment of the sixteen inventory015 candidates.

This program never loads a Research cell, provider, registry, or Object Store.
Its only conclusion is retention while evidence is insufficient.  It has no
path which produces a deletion command or grants disposal permission.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIXED_AUDIT_COMMIT = "46d281d3ca800148b57123edd426d096bbfc1d1e"
MAIN_PROJECT = 38436695
OTHER_PROJECTS = {38433216, 38437839, 38433336, 38432534}
INPUT_HASHES = {
    "audit/review_packages/storage_inventory015/settled_result.json": "87e7afb7b2bd478e50995143497807dae0dc9892b8808d9474940b37c36ab9f7",
    "audit/review_packages/storage_inventory015/plan_preview.stdout.txt": "cdc8a299c1894240d57aea38042674702be731976ba3b167740fd356e4e29ba1",
    "audit/review_packages/storage_inventory015/actual_analysis.stdout.txt": "c588c4f04091607319a44c0cf5bba4c8896df059c35378d2acfdcc968b0fcf5b",
    "audit/review_packages/storage_inventory012/review_pool.json": "9dfb2d83d3438dfb700b7264645a71403f8f3e9cc500e745011eecf86e80af7c",
    "config/budget.json": "7caf45cf2109e23caf92bebd6516909a5ee750294c1b9ef6f78720bc82cce888",
}
_GROUP_ROWS = {
    "aqrp/engineering/v2/historical-snapshots/v1/objects/": [
        ("336ac7d05cf90bb3db468f457d2bb10158866e7f55a9c6d42641070fd8dd8336", 197062),
        ("3a5c15e7af890c6bd5a7209ab2c30dedf9c93f60b0b1d19e5ab3255eccaa5108", 197137),
        ("3c83c5657ddc06c1adf7ee748ef686970830ca7eef5244e3b26ef08094d27b68", 196994),
        ("3dcbf5bafc8ecd471e172c7911ea905d2d90cdc5bf92bd3e22ff12dd5c21566c", 197079),
        ("6dc05520fea94b197441fc489f7dd08ee6d7ef41999613ced80f57558454eb93", 196994),
        ("b70c7dcfbb1ea18f740564b0f244286eda29721ca62d44c4f551f85c1df05051", 197137),
        ("bf6d935ccd5cdb3433b2b01009e167f4fa22a9a307cb02b5102b2f7406e0aeb1", 197079),
        ("c7fccd5ce63bd2ac1194cef31426666a303b9779d4d17b2eb02cd0c13a69657c", 197062),
        ("db44c3a1fca89e6033c69d7b79bc58ea1213efd65485bf1ddf86cd803bbf2707", 197192),
        ("e7902abff8749bcb3c182235b1df69f3c65bb30c9843486b7d9dd70e872c58a2", 197192),
    ],
    "aqrp/engineering/v2/historical-snapshots/v2/objects/": [
        ("1f8a988e5fa5502d10e1840d5ad4210b739651477dbdffdfd66594d29aaabfcb", 224051),
        ("233ee594609deac9643ae90d7da0cd3eb729bce425926653a54a277d4277dd08", 224055),
        ("6a5a38b63c99fb8016567ccb0613b3aa4c44ac66e62976dff063e22409c6284a", 223008),
    ],
    "generic-research/v1/feature-cache/v1/objects/": [
        ("3dbf2cc2d2584af110aad65afd1c47155cc7095077fd0792119ed8bfffd323c0", 66768),
        ("4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945", 2),
        ("ef4b7c48749a22bbc9788a979da82fec3c3ce5942611c478f9361cb94654ff29", 64090),
    ],
}
EXPECTED_POOL = {prefix + token + ".json": size
                 for prefix, rows in _GROUP_ROWS.items() for token, size in rows}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _native(envelope):
    """An error envelope is unknown evidence, never an empty successful page."""
    _require(type(envelope) is dict, "Native envelope must be an object")
    _require(type(envelope.get("isError", False)) is bool, "Invalid native error flag")
    if envelope.get("isError") is True:
        return None
    structured = envelope.get("structuredContent")
    decoded = []
    for item in envelope.get("content", []):
        if type(item) is dict and item.get("type") == "text":
            try:
                value = json.loads(item["text"])
            except (TypeError, ValueError):
                continue
            if type(value) is dict:
                decoded.append(value)
    if structured is not None:
        _require(type(structured) is dict, "Invalid native structured content")
        _require(all(item == structured for item in decoded), "Conflicting native representations")
        return structured
    _require(len(decoded) == 1, "One native JSON response required")
    return decoded[0]


def source_assessment(source_checks):
    _require(type(source_checks) is dict and source_checks.get("schema_version") == 1,
             "Invalid source-check document")
    for name in ("new_Research_executions", "new_LEAN_submissions", "Object_Store_reads_or_deletes"):
        _require(type(source_checks.get(name)) is int and source_checks[name] == 0,
                 "Source checks must be metadata/source-only")
    listing = _native(source_checks.get("project_listing"))
    _require(type(listing) is dict and listing.get("success") is True,
             "Successful native project listing required")
    projects = listing.get("projects")
    _require(type(projects) is list and all(type(x) is dict for x in projects), "Invalid project listing")
    ids = [x.get("projectId") for x in projects]
    _require(all(type(x) is int for x in ids) and len(ids) == len(set(ids)), "Invalid listed IDs")
    _require({MAIN_PROJECT} | OTHER_PROJECTS <= set(ids), "All checked project IDs must be listed")
    observations = source_checks.get("observations")
    _require(type(observations) is list, "Native observations required")
    pages, other, reads = {}, {}, {}
    for observation in observations:
        _require(type(observation) is dict and set(observation) == {"args", "result"}, "Invalid observation")
        args = observation["args"]
        _require(type(args) is dict and type(args.get("projectId")) is int
                 and args["projectId"] in ids, "Unlisted project operation")
        body = _native(observation["result"])
        if "query" in args:
            _require(set(args) == {"projectId", "query", "page"} and args["query"] == "object_store"
                     and type(args["page"]) is int, "Unexpected source-search arguments")
            if args["projectId"] == MAIN_PROJECT:
                page = args["page"]
                _require(page in range(1, 6) and page not in pages, "Duplicate or unexpected main search page")
                _require(type(body) is dict and body.get("totalPages") == 5
                         and body.get("totalMatches") == 50 and type(body.get("matches")) is list,
                         "Main source-search page incomplete")
                _require(len(body["matches"]) == 10, "Native main page must contain ten matches")
                pages[page] = body["matches"]
            else:
                pid = args["projectId"]
                _require(pid in OTHER_PROJECTS and pid not in other and args["page"] == 1,
                         "Unexpected cross-project search")
                _require(body is None and observation["result"].get("isError") is True,
                         "This fixed round records unavailable cross-project evidence")
                other[pid] = {"project_id": pid, "native_isError": True,
                    "consumer_status": "unknown_native_error", "matches": None,
                    "not_evidence_of_no_consumers": True}
        else:
            _require(set(args) == {"projectId", "filePath"} and args["projectId"] == MAIN_PROJECT,
                     "Unexpected source-read arguments")
            path = args["filePath"]
            _require(path in {"engineering_smoke.py", "qresearch/cache.py", "qresearch/collection.py"}
                     and path not in reads and type(body) is dict and set(body) == {"content", "filePath", "fileSize"}
                     and body["filePath"] == path and type(body["content"]) is str
                     and type(body["fileSize"]) is int and body["fileSize"] == len(body["content"]),
                     "Missing or repeated source read")
            raw = body["content"].encode("utf-8")
            reads[path] = {"file_path": path, "native_content_sha256": sha256(raw).hexdigest(),
                           "native_content_bytes": len(raw)}
    _require(set(pages) == set(range(1, 6)) and set(other) == OTHER_PROJECTS and len(reads) == 3,
             "Incomplete native source checks")
    matches = [row for page in sorted(pages) for row in pages[page]]
    positions = []
    for row in matches:
        _require(type(row) is dict and set(row) == {"filePath", "lineNumber", "line"}
                 and type(row["filePath"]) is str and type(row["lineNumber"]) is int
                 and row["lineNumber"] > 0 and type(row["line"]) is str,
                 "Malformed source match")
        positions.append((row["filePath"], row["lineNumber"]))
    _require(len(set(positions)) == 50, "Duplicated source-search page contents")
    _require(any(x["filePath"] == "engineering_smoke.py" and "generic-research/v1" in x["line"]
                 for x in matches), "Observed generic-cache consumer missing")
    return {"main_project": MAIN_PROJECT, "main_search_pages": 5, "main_search_matches": 50,
        "main_search_complete_for_literal_query_only": True,
        "cross_project_consumers": [other[pid] for pid in sorted(other)],
        "source_files": [reads[path] for path in sorted(reads)],
        "all_consumers_certified": False, "dynamic_and_external_consumers_certified": False,
        "source_search_is_not_an_Object_Store_reference_closure": True}


def assess(report, pool, source_checks):
    """Pure conservative assessment; main additionally validates the full report.

    Inputs are the complete inventory015 report, its sixteen candidate records,
    and this round's original native source-check envelopes.  This fixed round
    deliberately has no successful-deletion branch, even if inputs are extended.
    """
    _require(type(report) is dict and report.get("status") == "completed", "Completed inventory required")
    expected_retention = {"all_objects_retained": True,
        "global_reference_closure": False, "confirmed_reclaimable_bytes": 0,
        "potential_reclaimable_bytes": None, "safe_deletion_authorized": False,
        "final_test_enabled": False}
    retention = report.get("retention")
    _require(type(retention) is dict and set(retention) == set(expected_retention)
             and all(type(retention[name]) is type(value) and retention[name] == value
                     for name, value in expected_retention.items()),
             "Inventory retention gates must remain closed")
    _require(type(pool) is list and len(pool) == 16, "Exact sixteen-candidate pool required")
    objects = report.get("objects")
    _require(type(objects) is list and len(objects) == 488, "Exact observed inventory required")
    by_key = {}
    for item in objects:
        _require(type(item) is dict and type(item.get("key")) is str and item["key"] not in by_key
                 and type(item.get("size_bytes")) is int and item["size_bytes"] >= 0
                 and item.get("deletion_authorized") is False, "Invalid or duplicate inventory object")
        by_key[item["key"]] = item
    _require(sum(x["size_bytes"] for x in objects) == 52374905, "Inventory byte total changed")
    pool_map = {}
    for item in pool:
        _require(type(item) is dict and set(item) == {"key", "exact_size_bytes", "role", "content_status",
                 "content_sha256", "was_in_old13_priority_pool", "local_reference_claims_not_authenticated_edges",
                 "review_reason", "not_a_global_unreferenced_proof", "deletion_authorized", "retained"}
                 and type(item.get("key")) is str and item["key"] not in pool_map,
                 "Invalid or duplicate pool key")
        key = item["key"]
        _require(key in EXPECTED_POOL and type(item.get("exact_size_bytes")) is int
                 and item["exact_size_bytes"] == EXPECTED_POOL[key], "Fixed pool key or byte size changed")
        _require(item.get("deletion_authorized") is False and item.get("retained") is True
                 and item.get("content_status") == "not_read" and item.get("content_sha256") is None,
                 "Candidate content or retention claim changed")
        _require(item.get("not_a_global_unreferenced_proof") is True,
                 "Pool must not turn missing bounded edges into global proof")
        _require(key in by_key and by_key[key]["size_bytes"] == item["exact_size_bytes"]
                 and by_key[key]["content_status"] == "not_read"
                 and by_key[key]["content_sha256"] is None and by_key[key]["role"] == item.get("role")
                 == ("historical_payload" if "/historical-snapshots/" in key else "other_unread"),
                 "Candidate disagrees with the native inventory")
        pool_map[key] = item
    _require(set(pool_map) == set(EXPECTED_POOL), "Incomplete fixed pool")
    references = report.get("references")
    _require(type(references) is list and len(references) == 229, "Fixed typed graph required")
    incoming = Counter()
    for edge in references:
        _require(type(edge) is dict and edge.get("source_key") in by_key and edge.get("target_key") in by_key
                 and edge.get("target_exists") is True and edge.get("content_hash_verified") is True,
                 "Invalid typed reference")
        target = by_key[edge["target_key"]]
        _require(type(target.get("content_sha256")) is str
                 and edge.get("expected_sha256") == edge.get("actual_sha256") == target["content_sha256"],
                 "Unverified typed target")
        incoming[edge["target_key"]] += 1
    _require(not any(incoming[key] for key in EXPECTED_POOL), "Observed incoming reference changes fixed candidate premise")
    source = source_assessment(source_checks)
    unknown = [item for item in objects if item.get("content_status") == "retained_unknown_schema"]
    _require(len(unknown) == 20, "Fixed unknown-metadata boundary changed")
    rows = []
    for key in sorted(EXPECTED_POOL):
        item = by_key[key]
        reasons = ["actual_payload_content_hash_and_header_unavailable",
            "no_incoming_edge_in_bounded_graph_is_not_global_unreferenced_proof",
            "twenty_unknown_schema_metadata_objects_not_transitively_resolved",
            "four_cross_project_native_errors_leave_consumers_unknown",
            "dynamic_and_external_consumers_not_certified",
            "retention_ownership_restore_and_disposition_not_independently_accepted"]
        reasons.append("unfinished_historical_intent_and_batch_identity_need_cloud_reconciliation"
            if "/historical-snapshots/" in key else "old_shared_cache_manifest_and_owner_need_cloud_reconciliation")
        rows.append({"key": key, "exact_size_bytes": item["size_bytes"], "role": item["role"],
            "content_status": item["content_status"], "content_sha256": None,
            "actual_content_hash_verified": False, "incoming_edges_in_bounded_graph": incoming[key],
            "classification": "retain_insufficient_evidence", "blocked_reasons": reasons,
            "retained": True, "deletion_authorized": False})
    groups = [{"prefix": prefix, "objects": len(values),
               "exact_physical_bytes": sum(size for _, size in values), "retained": True}
              for prefix, values in sorted(_GROUP_ROWS.items())]
    return {"schema_version": 1, "kind": "fixed_pool_retention_assessment_not_deletion_manifest",
        "objects": rows, "group_totals": groups, "candidate_count": 16,
        "candidate_exact_physical_bytes": sum(EXPECTED_POOL.values()),
        "physical_bytes_are_not_reclaimable_bytes": True, "source_checks": source,
        "unknown_schema_metadata_objects": 20, "global_reference_closure_complete": False,
        "confirmed_reclaimable_objects": [], "confirmed_reclaimable_bytes": 0,
        "potential_reclaimable_total_bytes": None, "deletion_authorized": False,
        "basename_used_as_actual_payload_hash": False, "two_byte_object_assumed_empty": False,
        "equal_size_assumed_duplicate": False, "failed_or_old_status_used_as_garbage_proof": False,
        "all_objects_intents_and_historical_receipts_retained": True,
        "new_Research_executions": 0, "new_LEAN_submissions": 0, "cloud_deletions": 0,
        "budget_changes": 0, "independent_acceptance": False, "stage2_accepted": False,
        "financial_evidence": False, "final_test_enabled": False}


def _read_fixed(relative):
    raw = (ROOT / relative).read_bytes()
    _require(sha256(raw).hexdigest() == INPUT_HASHES[relative], "Fixed input bytes changed: " + relative)
    return json.loads(raw)


def _historical_audit_hash_comparison(report):
    """Compare original git-tracked audit blobs, not changing workspace files.

    Exact raw SHA equality only: no JSON reserialization, compressed payload
    decoding, prefix joining, or similarity can substitute for a cloud original.
    The fixed pre016 commit excludes this report and all new outputs by design.
    """
    listing = subprocess.run(["git", "ls-tree", "-rz", FIXED_AUDIT_COMMIT, "--", "audit"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    entries = []
    for item in listing.split(b"\0"):
        if not item:
            continue
        header, raw_path = item.split(b"\t", 1)
        mode, kind, oid = header.split()
        _require(kind == b"blob" and mode in {b"100644", b"100755"}, "Unexpected audit Git entry")
        path = raw_path.decode("utf-8")
        _require(not path.startswith("audit/review_packages/reclaim_pool016/"), "Self-scan prohibited")
        entries.append((oid, path))
    query = b"".join(oid + b"\n" for oid, _ in entries)
    batch = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, input=query,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    targets = defaultdict(list)
    for item in report["objects"]:
        if item["content_status"] == "retained_unknown_schema":
            targets[item["content_sha256"]].append(item["key"])
    offset, byte_count, matches = 0, 0, []
    for oid, path in entries:
        end = batch.index(b"\n", offset)
        header = batch[offset:end].split()
        _require(len(header) == 3 and header[0] == oid and header[1] == b"blob", "Invalid Git blob response")
        size = int(header[2]); offset = end + 1
        raw = batch[offset:offset + size]; offset += size
        _require(len(raw) == size and batch[offset:offset + 1] == b"\n", "Truncated Git audit blob")
        offset += 1; byte_count += size
        digest = sha256(raw).hexdigest()
        if digest in targets:
            matches.append({"git_path": path, "raw_sha256": digest,
                            "matching_cloud_metadata_keys": sorted(targets[digest])})
    _require(offset == len(batch), "Unexpected Git blob trailer")
    return {"fixed_git_commit": FIXED_AUDIT_COMMIT, "git_tracked_audit_files": len(entries),
        "raw_bytes_compared": byte_count, "unknown_cloud_metadata_objects": 20,
        "distinct_unknown_cloud_raw_hashes": len(targets), "exact_raw_matches": matches,
        "new016_outputs_and_untracked_files_excluded": True,
        "compressed_originals_not_decoded_by_this_comparison": True,
        "scope": "Exact SHA256 of raw Git-tracked audit blobs at the fixed pre016 commit only",
        "not_a_cloud_reference_closure_or_absence_proof": True}


def main():
    sys.path.insert(0, str(ROOT / "cloud"))
    from qresearch.storage_inventory import validate_report

    result = _read_fixed("audit/review_packages/storage_inventory015/settled_result.json")
    preview = _read_fixed("audit/review_packages/storage_inventory015/plan_preview.stdout.txt")
    original = _read_fixed("audit/review_packages/storage_inventory015/actual_analysis.stdout.txt")
    old = _read_fixed("audit/review_packages/storage_inventory012/review_pool.json")
    _read_fixed("config/budget.json")
    report = validate_report(result["report"], preview["plan"]["inventory_policy"], result["identity"])
    _require(result["status"] == report["status"] == "completed", "Native completion mismatch")
    _require(original["input_settled_result_sha256"] == INPUT_HASHES[
        "audit/review_packages/storage_inventory015/settled_result.json"], "Original analysis input mismatch")
    pool = original["payload_review_pool_without_observed_typed_incoming_edges"]
    old_keys = {item["path"] for item in old["objects_for_priority_review"]}
    _require(len(old_keys) == 13 and old_keys < set(EXPECTED_POOL), "Original thirteen-candidate pool changed")
    checks_path = HERE / "cloud_source_checks.json"
    checks_raw = checks_path.read_bytes()
    output = assess(report, pool, json.loads(checks_raw))
    output["fixed_input_raw_sha256"] = INPUT_HASHES
    output["cloud_source_checks_raw_sha256"] = sha256(checks_raw).hexdigest()
    output["original13_preserved"] = True
    output["historical_audit_raw_hash_comparison"] = _historical_audit_hash_comparison(report)
    output["budget_configuration_raw_identity_unchanged"] = True
    output["native015_inventory_replayed_offline"] = True
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
