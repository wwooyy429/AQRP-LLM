"""Reconcile permitted inventory015 audit metadata; no writes or cloud calls.

The absence of an incoming edge in this bounded, typed graph is a review cue,
never a complete unreferenced-object proof or permission to delete anything.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.storage_inventory import validate_report


NAMESPACES = (
    "aqrp/engineering/v2/historical-snapshots/v1",
    "aqrp/engineering/v2/historical-snapshots/v2",
    "aqrp/engineering/v2/feature-cache/v1",
    "aqrp/engineering/v2/coverage-inputs/v1",
    "aqrp/engineering/v2/audit-evidence",
    "aqrp/engineering/v2/engineering",
    "aqrp/engineering/v2/cache",
    "generic-research/v1",
)


def namespace(key):
    for prefix in NAMESPACES:
        if key == prefix or key.startswith(prefix + "/"):
            return prefix
    return "other_namespace_retained"


def summary(items):
    return {"objects": len(items), "exact_physical_bytes": sum(x["size_bytes"] for x in items)}


def main():
    result_path = HERE / "settled_result.json"
    result = json.loads(result_path.read_bytes())
    preview = json.loads((HERE / "plan_preview.stdout.txt").read_bytes())
    policy = preview["plan"]["inventory_policy"]
    report = validate_report(result["report"], policy, result["identity"])
    assert result["status"] == report["status"] == "completed"
    assert result["identity"]["plan_hash"] == preview["plan_hash"]
    assert result["identity"]["config_id"] == preview["configuration_hash"]
    assert report["metadata_observation_stable"] and report["details_complete"]
    assert report["capacity_before"] == report["capacity_after"]
    capacity = report["capacity_after"]
    objects, references = report["objects"], report["references"]
    by_key = {item["key"]: item for item in objects}
    assert len(by_key) == len(objects) == capacity["used_files"]
    assert sum(item["size_bytes"] for item in objects) == capacity["used_size_bytes"]
    ordered_sizes = [[key, by_key[key]["size_bytes"]] for key in sorted(by_key)]
    fingerprint = sha256(json.dumps(ordered_sizes, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    assert fingerprint == capacity["key_size_sha256"]

    incoming, outgoing = Counter(), Counter()
    for edge in references:
        assert edge["source_key"] in by_key and edge["target_key"] in by_key
        target = by_key[edge["target_key"]]
        assert edge["target_exists"] is True and edge["content_hash_verified"] is True
        assert target["content_sha256"] == edge["actual_sha256"] == edge["expected_sha256"]
        incoming[edge["target_key"]] += 1
        outgoing[edge["source_key"]] += 1

    groups, parent_groups = defaultdict(list), defaultdict(list)
    hashes = defaultdict(list)
    for item in objects:
        groups[namespace(item["key"])].append(item)
        parent_groups[item["key"].rsplit("/", 1)[0]].append(item)
        if item["content_sha256"] is not None:
            hashes[item["content_sha256"]].append(item)
    namespace_rows = [{"namespace": name, **summary(items),
        "content_status_counts": dict(sorted(Counter(x["content_status"] for x in items).items())),
        "retained": True} for name, items in sorted(groups.items())]
    assert sum(row["objects"] for row in namespace_rows) == len(objects)
    assert sum(row["exact_physical_bytes"] for row in namespace_rows) == capacity["used_size_bytes"]

    old_pool = json.loads((HERE.parent / "storage_inventory012/review_pool.json").read_bytes())
    old_assessment = json.loads((HERE.parent / "storage_inventory012/object_assessment.pagination_fixed.json").read_bytes())
    prior_UI_keys = {item["path"] for item in old_assessment["objects"]}
    local_roots = json.loads((HERE.parent / "storage_inventory012/local_reference_roots.json").read_bytes())
    claims = defaultdict(list)
    for claim in local_roots.get("reference_roots", []) + local_roots.get("other_prefix_reference_roots", []):
        if type(claim) is dict and type(claim.get("object_store_key")) is str:
            claims[claim["object_store_key"]].append(claim)
    old_keys = {item["path"] for item in old_pool["objects_for_priority_review"]}
    assert len(old_keys) == 13 and old_keys <= set(by_key)
    old_status = []
    for key in sorted(old_keys):
        item = by_key[key]
        old_status.append({"key": key, "exact_size_bytes": item["size_bytes"],
            "role": item["role"], "content_status": item["content_status"],
            "actual_content_hash_verified": item["content_sha256"] is not None,
            "incoming_edges_in_this_typed_graph": incoming[key],
            "local_reference_claims_not_authenticated_edges": len(claims[key]),
            "deletion_authorized": False, "retained": True})

    # Include the old shared-cache objects as explicitly unclassified payloads.
    no_incoming_payloads = []
    for item in objects:
        if "/objects/" not in item["key"] or incoming[item["key"]]:
            continue
        no_incoming_payloads.append({"key": item["key"], "exact_size_bytes": item["size_bytes"],
            "role": item["role"], "content_status": item["content_status"],
            "content_sha256": item["content_sha256"],
            "was_in_old13_priority_pool": item["key"] in old_keys,
            "local_reference_claims_not_authenticated_edges": len(claims[item["key"]]),
            "review_reason": "no_incoming_edge_in_this_incomplete_typed_graph",
            "not_a_global_unreferenced_proof": True, "deletion_authorized": False,
            "retained": True})

    repeated_hashes = []
    for token, items in sorted(hashes.items()):
        if len(items) < 2:
            continue
        sizes = {item["size_bytes"] for item in items}
        assert len(sizes) == 1
        repeated_hashes.append({"reported_raw_sha256": token, "objects": len(items),
            "size_per_object_bytes": next(iter(sizes)),
            "physical_bytes_across_paths": sum(item["size_bytes"] for item in items),
            "paths": [item["key"] for item in items],
            "roles": sorted({item["role"] for item in items}),
            "all_under_historical_resolution_paths": all("/resolutions/" in item["key"] for item in items),
            "comparison_evidence": "same_cloud_computed_full_object_SHA256_and_exact_size",
            "byte_by_byte_pair_comparison_performed": False,
            "hash_equality_is_not_release_permission": True, "retained": True,
            "deletion_authorized": False})

    subtrees = old_pool["all_historical_receipt_subtrees_preserved"]
    subtree_rows = []
    for prefix in subtrees:
        items = [item for item in objects if item["key"].startswith(prefix + "/")]
        subtree_rows.append({"prefix": prefix, **summary(items),
            "content_read_objects": sum(x["content_sha256"] is not None for x in items),
            "retained": True, "content_reference_closure_verified": False})
    old_total = sum(by_key[key]["size_bytes"] for key in old_keys)
    new_candidates = [x for x in no_incoming_payloads if not x["was_in_old13_priority_pool"]]
    assert all(x["content_sha256"] is None and x["content_status"] == "not_read" for x in no_incoming_payloads)
    unknown_schema_count = sum(x["content_status"] == "retained_unknown_schema" for x in objects)
    unread_count = sum(x["content_status"] == "not_read" for x in objects)
    deficit = max(0, capacity["lean_required_bytes"] - capacity["free_size_bytes"])
    assert all(item["deletion_authorized"] is False for item in objects)
    assert report["retention"]["global_reference_closure"] is False
    assert report["retention"]["confirmed_reclaimable_bytes"] == 0
    assert report["retention"]["potential_reclaimable_bytes"] is None
    output = {
        "kind": "fixed_post_native_inventory_metadata_analysis_not_deletion_approval",
        "input_settled_result_sha256": sha256(result_path.read_bytes()).hexdigest(),
        "native_identity": result["identity"], "capacity_observation": capacity,
        "two_matching_metadata_passes_not_atomic_snapshot": True,
        "lean_frozen_byte_envelope_shortfall_bytes": deficit,
        "full_LEAN_file_count_capacity_or_reservation_not_certified": True,
        "namespace_leaf_only_totals": namespace_rows,
        "leaf_parent_totals": [{"parent": name, **summary(items)} for name,items in sorted(parent_groups.items())],
        "role_counts": dict(sorted(Counter(x["role"] for x in objects).items())),
        "content_status_counts": dict(sorted(Counter(x["content_status"] for x in objects).items())),
        "prior_UI_vs_current_SDK_metadata": {
            "prior_UI_leaf_objects": len(prior_UI_keys),
            "prior_UI_keys_still_observed": len(prior_UI_keys & set(by_key)),
            "prior_UI_keys_not_observed_now": sorted(prior_UI_keys - set(by_key)),
            "additional_enumerated_keys": sorted(set(by_key) - prior_UI_keys),
            "additional_keys_are_not_claimed_newly_created": True,
            "prior_UI_unvisited_subtrees_did_not_previously_certify_their_children": True,
        },
        "typed_reference_summary": {"edges": len(references), "different_sources": len(outgoing),
            "different_targets": len(incoming), "all_observed_targets_exist_and_hash_match": True,
            "by_kind": dict(sorted(Counter(x["kind"] for x in references).items())),
            "scope": "known metadata schemas and authorized development payloads only; unknown consumers/receipts stay outside this graph"},
        "old13_priority_pool": {"all_present": True, "objects": old_status,
            "exact_physical_bytes": old_total, "bytes_are_not_reclaimable_space": True},
        "payload_review_pool_without_observed_typed_incoming_edges": no_incoming_payloads,
        "payload_review_pool_summary": {"objects": len(no_incoming_payloads),
            "exact_physical_bytes": sum(x["exact_size_bytes"] for x in no_incoming_payloads),
            "old13_objects": len(old_keys), "old13_exact_physical_bytes": old_total,
            "new_objects": len(new_candidates),
            "new_exact_physical_bytes": sum(x["exact_size_bytes"] for x in new_candidates),
            "not_a_deletion_manifest_or_potential_reclaim_estimate": True},
        "actual_raw_hash_repeat_groups": repeated_hashes,
        "historical_receipt_subtrees": subtree_rows,
        "evidence_gaps": [
            f"{unknown_schema_count} content-read metadata objects use unrecognized schemas; their transitive references are not decoded",
            f"{unread_count} objects remain content-unread, including all{len(no_incoming_payloads)} bounded-graph payload review candidates",
            f"{report['read_summary']['missing_metadata_keys']} locally/UI claimed allowlist keys were not found; local claims include historical/synthetic placeholders",
            "cross-project dynamic and external consumers are not certified by this typed graph",
            "no raw headers or payload hashes were inspected for the16 review candidates",
            "historical retention responsibility and safe deletion have not been independently accepted",
        ],
        "required_before_any_disposition": [
            "Obtain authorized cloud-resident candidate headers and raw hashes without opening unapproved final-window content",
            "Resolve all relevant historical receipt/configuration/schema references and unknown/dynamic consumers",
            "Bind ownership, restore/retention responsibility, exact keys/bytes and a frozen disposition procedure",
            "Independently review the exact candidate evidence; obtain explicit user deletion authorization only after a concrete safe manifest exists",
            "Recheck capacity and source identities before any later admitted execution; never lower the frozen73728B envelope",
        ],
        "mtime_or_failed_status_used_as_garbage_proof": False,
        "same_basename_or_equal_display_size_used_as_duplicate_proof": False,
        "all_objects_and_history_retained": True,
        "global_reference_closure_complete": False,
        "confirmed_reclaimable_objects": [], "confirmed_reclaimable_bytes": 0,
        "potential_reclaimable_total_bytes": None, "cloud_calls": 0,
        "Registry_or_budget_changes": 0, "new_Research_or_LEAN_executions": 0,
        "cloud_deletions": 0, "independent_acceptance": False,
        "stage2_accepted": False, "financial_evidence": False, "final_test_enabled": False,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
