"""Read-only UI metadata reconciliation; no cloud execution or deletion API.

This program joins observed UI names to local *claims* without promoting either
into raw-byte or reference-closure evidence. Inputs and output stay in this
audit packet. UI table rows may be virtualized: completeness requires all
unique entries, not merely the expected page number.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re


PACKET = Path(__file__).resolve().parent
EVIDENCE_PACKET = PACKET.parent / "storage_inventory012"
HEX_NAME = re.compile(r"([0-9a-f]{64})(?:\.json)?\Z")
# Full labels only. ASCII tokens and bounded integers prevent substring,
# signed-number, Unicode-digit and unbounded numeric-token interpretations.
RANGE = re.compile(r"([0-9]+)[ \t]*to[ \t]*([0-9]+)[ \t]*of[ \t]*([0-9]+)", re.I | re.ASCII)
PAGE = re.compile(r"Page[ \t]*([0-9]+)[ \t]*of[ \t]*([0-9]+)", re.I | re.ASCII)
SIZE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(B|KB|MB|GB)\Z", re.I)


def key_path(value, *, root=False):
    if not isinstance(value, str) or value != value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid UI path metadata")
    if value == "" and root:
        return value
    if not value or "\\" in value or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError("Invalid UI path metadata")
    return value


def under(key, prefix):
    prefix = prefix.rstrip("/")
    return key == prefix or key.startswith(prefix + "/")


def display_number(text):
    """Nominal SI conversion of a rounded UI label, never physical bytes."""
    match = SIZE.fullmatch(text.strip()) if isinstance(text, str) else None
    if match is None:
        return None
    try:
        value = Decimal(match[1]) * (Decimal(1000) ** {"B": 0, "KB": 1, "MB": 2, "GB": 3}[match[2].upper()])
    except InvalidOperation:
        return None
    return str(value)


def digest_role(path):
    parts = path.split("/")
    match = HEX_NAME.fullmatch(parts[-1])
    if match is None:
        return {"digest_token": None, "role": "not_a_digest_filename"}
    parents = set(parts[:-1])
    if parents & {"windows", "manifests", "intents"}:
        role = "identity_digest_name_not_content_hash"
    elif (("feature-cache/v1/objects/" in path)
          or re.search(r"historical-snapshots/v[12]/objects/", path)):
        role = "expected_payload_content_digest_name_unverified"
    else:
        role = "unclassified_digest_name"
    return {"digest_token": match[1], "role": role,
            "filename_suffix": ".json" if parts[-1].endswith(".json") else None,
            "raw_object_hash_verified": False}


def protected_reason(path, roots, namespace_roots, families):
    reasons = []
    matches = roots.get(path, [])
    if matches:
        reasons.append("direct_local_reference_claim")
    namespaces = [prefix for prefix in namespace_roots if under(path, prefix)]
    if namespaces:
        reasons.append("locally_claimed_protected_namespace")
    family_matches = [prefix for prefix in families if under(path, prefix)]
    if family_matches:
        reasons.append("code_derived_protected_data_or_history_family")
    parts = set(path.split("/"))
    if (parts & {"windows", "manifests", "intents", "reports", "resolutions", "collection-probes", "audit-evidence"}
            or path.endswith("/cache")):
        reasons.append("historical_manifest_intent_receipt_or_event_metadata")
    if not reasons:
        reasons.append("reference_status_unknown_preserve")
    return reasons, matches, namespaces, family_matches


def analyze(observation_doc, local_doc, rule_doc):
    observations = observation_doc.get("observations")
    if not isinstance(observations, list):
        raise ValueError("UI observations list is required")
    roots = defaultdict(list)
    for record in local_doc.get("reference_roots", []) + local_doc.get("other_prefix_reference_roots", []):
        if isinstance(record, dict) and isinstance(record.get("object_store_key"), str):
            roots[key_path(record["object_store_key"])].append(record)
    namespaces = []
    for record in local_doc.get("namespace_keep_roots", []):
        if isinstance(record, dict) and isinstance(record.get("object_store_prefix"), str):
            namespaces.append(key_path(record["object_store_prefix"].rstrip("/")))
    prefixes = set()
    resolution = local_doc.get("physical_key_resolution", {})
    for name in ("engineering_store_prefix", "collection_task_store_prefix"):
        if isinstance(resolution.get(name), str):
            prefixes.add(key_path(resolution[name]))
    for rule in rule_doc.get("namespace_rules", []):
        for prefix in rule.get("known_fixed_prefixes", []):
            prefixes.add(key_path(prefix))
    families = set()
    for prefix in prefixes:
        for family in local_doc.get("code_derived_protected_families", []):
            relative = family.get("relative_prefix", family.get("relative_key"))
            if isinstance(relative, str):
                families.add(prefix + "/" + relative.rstrip("/"))

    directories = defaultdict(lambda: {"rows": {}, "observations": [], "totals": set(), "page_totals": set(),
        "pages": set(), "invalid_paging": [], "invalid_rows": [], "conflicts": [], "repeated_row_observations": 0,
        "range_observations": [], "positions": {}, "key_positions": {}, "position_conflicts": [],
        "key_position_conflicts": [], "invalid_range_row_counts": []})
    for index, observation in enumerate(observations):
        path = key_path(observation["path"], root=True)
        directory = directories[path]
        directory["observations"].append(index)
        valid_ranges, valid_pages, observation_keys = [], [], []
        paging = observation.get("paging")
        if not isinstance(paging, list):
            directory["invalid_paging"].append({"observation_index": index,
                "reason": "UI_paging_must_be_a_list"})
            paging = []
        for text in paging:
            if not isinstance(text, str):
                directory["invalid_paging"].append({"observation_index": index,
                    "reason": "UI_paging_label_must_be_text"})
                continue
            label = text.strip(" \t")
            match = RANGE.fullmatch(label)
            if match:
                if any(len(token) > 7 for token in match.groups()):
                    directory["invalid_paging"].append({"observation_index": index, "reason": "invalid_UI_range"})
                    continue
                start, end, total = map(int, match.groups())
                if (0 <= total <= 1000000 and ((total == 0 and start == end == 0)
                        or (total > 0 and 1 <= start <= end <= total))):
                    directory["totals"].add(total)
                    valid_ranges.append((start, end, total))
                else:
                    directory["invalid_paging"].append({"observation_index": index, "reason": "invalid_UI_range"})
                continue
            match = PAGE.fullmatch(label)
            if match:
                if any(len(token) > 6 for token in match.groups()):
                    directory["invalid_paging"].append({"observation_index": index, "reason": "invalid_UI_page_count"})
                    continue
                page, count = map(int, match.groups())
                if 1 <= page <= count <= 100000 or page == count == 0:
                    directory["pages"].add(page)
                    directory["page_totals"].add(count)
                    valid_pages.append((page, count))
                else:
                    directory["invalid_paging"].append({"observation_index": index, "reason": "invalid_UI_page_count"})
                continue
            directory["invalid_paging"].append({"observation_index": index,
                "reason": "unrecognized_or_ambiguous_UI_paging_label"})
        if len(valid_pages) != 1:
            directory["invalid_paging"].append({"observation_index": index,
                "reason": "one_unambiguous_UI_page_label_required"})
        if len(valid_ranges) != 1:
            directory["invalid_paging"].append({"observation_index": index,
                "reason": "one_unambiguous_UI_range_label_required"})
        for row in observation.get("rows", []):
            try:
                if not isinstance(row, dict):
                    raise ValueError("Invalid row")
                name = key_path(row["name"])
                if "/" in name:
                    raise ValueError("UI row must be one displayed basename")
                physical = path + "/" + name if path else name
                kind = row["type"]
                if not isinstance(kind, str) or not kind:
                    raise ValueError("Missing UI type")
                exact = row.get("exact_bytes")
                if exact is not None and (type(exact) is not int or exact < 0):
                    raise ValueError("Invalid reported exact-byte metadata")
                value = {"path": physical, "parent": path, "display_name": name, "type": kind,
                    "is_folder": kind.casefold() == "folder", "display_size": row.get("display_size"),
                    "last_modified": row.get("last_modified"), "exact_bytes_reported": exact}
                observation_keys.append(physical)
                if physical in directory["rows"]:
                    directory["repeated_row_observations"] += 1
                    old = directory["rows"][physical]
                    if value != old["value"]:
                        directory["conflicts"].append({"path": physical, "first": old["value"], "later": value,
                                                      "observation_index": index})
                    old["observation_indexes"].append(index)
                else:
                    directory["rows"][physical] = {"value": value, "observation_indexes": [index]}
            except (KeyError, ValueError, TypeError):
                directory["invalid_rows"].append({"observation_index": index, "reason": "invalid_UI_row_metadata"})
        if any(page == count == 0 for page, count in valid_pages) and (
                valid_ranges != [(0, 0, 0)] or observation.get("rows") != []):
            directory["invalid_paging"].append({"observation_index": index,
                "reason": "empty_page_requires_empty_listing"})
        if len(valid_ranges) != 1:
            directory["invalid_range_row_counts"].append({"observation_index": index,
                "reason": "one_unambiguous_UI_range_required"})
            continue
        start, end, total = valid_ranges[0]
        expected_rows = 0 if total == 0 else end - start + 1
        row_count_matches = len(observation_keys) == expected_rows
        unique_in_observation = len(set(observation_keys)) == len(observation_keys)
        directory["range_observations"].append({"observation_index": index, "start": start, "end": end,
            "total": total, "observed_rows": len(observation_keys), "expected_rows": expected_rows,
            "row_count_matches_range": row_count_matches,
            "keys_unique_within_observation": unique_in_observation})
        if not row_count_matches or not unique_in_observation:
            directory["invalid_range_row_counts"].append({"observation_index": index,
                "reason": "UI_range_row_count_or_uniqueness_mismatch"})
            continue
        for position, physical in zip(range(start, end + 1), observation_keys):
            old = directory["positions"].get(position)
            if old is not None and old != physical:
                directory["position_conflicts"].append({"position": position, "first_path": old,
                    "later_path": physical, "observation_index": index})
            else:
                directory["positions"][position] = physical
            old_position = directory["key_positions"].get(physical)
            if old_position is not None and old_position != position:
                directory["key_position_conflicts"].append({"path": physical, "first_position": old_position,
                    "later_position": position, "observation_index": index})
            else:
                directory["key_positions"][physical] = position

    directory_results = []
    all_entries = {}
    complete_directories = set()
    for path, directory in sorted(directories.items()):
        total = next(iter(directory["totals"])) if len(directory["totals"]) == 1 else None
        page_total = next(iter(directory["page_totals"])) if len(directory["page_totals"]) == 1 else None
        missing_pages = sorted(set(range(1, page_total + 1)) - directory["pages"]) if page_total is not None else None
        unique = len(directory["rows"])
        positions = sorted(directory["positions"])
        range_complete = total is not None and len(positions) == total and (
            total == 0 or positions == list(range(1, total + 1)))
        positions_consistent = not directory["position_conflicts"] and not directory["key_position_conflicts"]
        complete = (total is not None and unique == total and range_complete and positions_consistent
                    and not directory["invalid_range_row_counts"] and not directory["invalid_paging"]
                    and not directory["invalid_rows"] and not directory["conflicts"])
        if complete:
            complete_directories.add(path)
        directory_results.append({"path": path, "observation_indexes": directory["observations"],
            "unique_entries_observed": unique, "UI_expected_total": total,
            "UI_total_claims": sorted(directory["totals"]), "UI_page_total_claims": sorted(directory["page_totals"]),
            "pages_observed": sorted(directory["pages"]), "missing_pages": missing_pages,
            "page_count_layouts_varied": len(directory["page_totals"]) > 1,
            "completeness_basis": "Each observed range has exactly its ordered row count; position-to-key and key-to-position are consistent; one total and full position coverage; unique physical count matches total",
            "page_count_labels_are_layout_metadata_not_a_substitute_for_range_proof": True,
            "range_observations": directory["range_observations"],
            "observed_positions": len(positions), "range_position_coverage_complete": range_complete,
            "position_to_key_consistent": positions_consistent,
            "position_to_key_map_sha256": sha256(json.dumps(sorted(directory["positions"].items()), ensure_ascii=False,
                separators=(",", ":")).encode("utf-8")).hexdigest(),
            "position_conflicts": directory["position_conflicts"],
            "key_position_conflicts": directory["key_position_conflicts"],
            "invalid_range_row_counts": directory["invalid_range_row_counts"],
            "count_matches_UI_total": total is not None and unique == total,
            "all_entries_observed_at_UI_metadata_level": complete,
            "repeated_row_observations_are_not_extra_copies": directory["repeated_row_observations"],
            "invalid_paging": directory["invalid_paging"], "invalid_rows": directory["invalid_rows"],
            "conflicting_observations": directory["conflicts"]})
        all_entries.update(directory["rows"])

    objects, folders = [], []
    digest_names = defaultdict(list)
    for path, row in sorted(all_entries.items()):
        entry = row["value"]
        if entry["is_folder"]:
            folders.append({**entry, "visited": path in directories})
            continue
        reasons, matches, kept_namespaces, kept_families = protected_reason(path, roots, namespaces, families)
        digest = digest_role(path)
        assessment = {**entry, "observation_indexes": row["observation_indexes"],
            "key_evidence": "UI directory path plus displayed name; raw SDK key not independently certified",
            "classification": reasons[0], "retention_reasons": reasons,
            "local_reference_claim_count": len(matches),
            "local_claimed_digests": sorted({digest for match in matches for digest in match.get("expected_sha256_claims", [])}),
            "local_reference_examples": [example for match in matches for example in match.get("source_examples", [])][:3],
            "matching_local_namespace_claims": sorted(set(kept_namespaces)),
            "matching_code_protected_families": sorted(set(kept_families)),
            "digest_name_analysis": digest,
            "display_nominal_decimal_bytes": display_number(entry["display_size"]),
            "display_amount_is_not_measured_bytes": True, "actual_bytes_verified": False,
            "raw_content_hash_verified": False, "reference_closure_verified": False,
            "reclaimability": "retain_pending_complete_reference_and_byte_evidence",
            "deletion_authorized": False, "confirmed_reclaimable_bytes": 0}
        objects.append(assessment)
        if digest["digest_token"]:
            digest_names[digest["digest_token"]].append(assessment)

    duplicate_candidates = []
    for token, group in sorted(digest_names.items()):
        if len(group) < 2:
            continue
        roles = sorted({item["digest_name_analysis"]["role"] for item in group})
        classification = ("identity_name_repetition_not_content_duplicate" if "identity_digest_name_not_content_hash" in roles
            else "expected_content_digest_name_candidate_unverified" if roles == ["expected_payload_content_digest_name_unverified"]
            else "opaque_digest_name_repetition_unverified")
        duplicate_candidates.append({"displayed_digest_token": token, "paths": [item["path"] for item in group],
            "distinct_UI_physical_paths": len(group), "digest_roles": roles, "classification": classification,
            "actual_byte_equality_verified": False, "confirmed_reclaimable_bytes": 0, "deletion_authorized": False})

    v1_objects = [item["path"] for item in objects if "/historical-snapshots/v1/objects/" in item["path"]]
    v2_intents = []
    for item in objects:
        marker = "/historical-snapshots/v2/intents/"
        if marker not in item["path"] or not item["digest_name_analysis"]["digest_token"]:
            continue
        base = item["path"].split(marker)[0] + "/historical-snapshots/v2"
        token = item["digest_name_analysis"]["digest_token"]
        matching = [other["path"] for other in objects if other["parent"] == base + "/windows"
                    and other["digest_name_analysis"]["digest_token"] == token]
        if not matching:
            v2_intents.append({"intent_path": item["path"], "identity_digest_name": token,
                "matching_window_name_observed": False, "window_directory_fully_observed": base + "/windows" in complete_directories,
                "status": "no_matching_window_name_in_complete_UI_listing" if base + "/windows" in complete_directories
                    else "window_not_observed_listing_incomplete_or_unvisited",
                "potential_partial_batch_pool_prefix": base + "/objects",
                "specific_partial_batch_associations": [], "mtime_used_to_infer_association": False,
                "required_next_evidence": "QC-resident batch header plan/window/batch_index and historical intent/receipt closure",
                "deletion_authorized": False})
    nominal = [Decimal(item["display_nominal_decimal_bytes"]) for item in objects
               if item["display_nominal_decimal_bytes"] is not None]
    unvisited = sorted(item["path"] for item in folders if not item["visited"])
    scope_root = key_path(observation_doc.get("scope_root", ""), root=True)
    return {"schema_version": 1, "kind": "conservative_UI_metadata_inventory_assessment_not_cloud_closure",
        "input_observation_count": len(observations), "scope_root": scope_root,
        "directories_observed": len(directories), "directories": directory_results,
        "unique_UI_leaf_objects": len(objects), "unique_UI_folder_entries": len(folders),
        "folders": folders, "unvisited_child_directories": unvisited,
        "UI_tree_listing_complete_within_declared_scope": scope_root in complete_directories and not unvisited
            and all(item["all_entries_observed_at_UI_metadata_level"] for item in directory_results),
        "global_reference_closure_complete": False, "objects": objects,
        "same_digest_basename_review_groups": duplicate_candidates,
        "v1_raw_objects_require_cloud_reference_and_header_review": v1_objects,
        "v2_intents_without_observed_matching_window_name": v2_intents,
        "display_size_summary": {"unique_leaf_nominal_SI_sum_bytes": str(sum(nominal, Decimal(0))),
            "leaf_display_sizes_recognized": len(nominal), "leaf_display_sizes_unparsed": len(objects) - len(nominal),
            "folder_display_sizes_excluded_to_avoid_double_counting": True,
            "rounded_UI_estimate_only_not_exact_usage_or_reclaimable_bytes": True},
        "confirmed_reclaimable_objects": [], "confirmed_reclaimable_bytes": 0,
        "potential_reclaimable_total_bytes": None,
        "zero_means_no_verified_reclaim_proof_not_no_possible_future_savings": True,
        "boundaries": ["Local roots and SHA fields are claims; matching UI paths does not verify their raw contents.",
            "Unknown/unvisited references, implicit schema edges and other project consumers stay protected.",
            "All history, intents, manifests, receipts and referenced data remain protected regardless of age or task status.",
            "The UI listing is not an atomic cloud snapshot; no timestamp is used as a batch/window association.",
            "Real rows are not input to this analyzer and remain in QuantConnect Cloud."],
        "product_source_changed": False, "cloud_calls": 0, "Research_executions": 0,
        "LEAN_submissions": 0, "Registry_or_budget_changes": 0, "cloud_deletions": 0,
        "independent_acceptance": False, "financial_evidence": False, "final_test_enabled": False}


def packet_path(raw, *, output=False):
    path = Path(raw).resolve()
    allowed = (PACKET,) if output else (PACKET, EVIDENCE_PACKET)
    if not any(path.is_relative_to(parent.resolve()) for parent in allowed):
        raise ValueError("Inventory inputs must stay in 012/013; output must stay in 013")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", default=str(EVIDENCE_PACKET / "ui_observations.json"))
    parser.add_argument("--roots", default=str(EVIDENCE_PACKET / "local_reference_roots.json"))
    parser.add_argument("--rules", default=str(EVIDENCE_PACKET / "reference_rules.json"))
    # Keep the initial actual assessment as historical evidence by default.
    parser.add_argument("--output", default=str(PACKET / "object_assessment.wr31_fixed.json"))
    args = parser.parse_args(argv)
    paths = {key: packet_path(getattr(args, key), output=key == "output")
             for key in ("observations", "roots", "rules", "output")}
    inputs = {key: paths[key].read_bytes() for key in ("observations", "roots", "rules")}
    result = analyze(*(json.loads(inputs[key]) for key in ("observations", "roots", "rules")))
    result["input_sha256"] = {key: sha256(raw).hexdigest() for key, raw in inputs.items()}
    paths["output"].write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"output": paths["output"].relative_to(PACKET).as_posix(),
        "observed_directories": result["directories_observed"], "unique_UI_leaf_objects": result["unique_UI_leaf_objects"],
        "unvisited_child_directories": len(result["unvisited_child_directories"]),
        "confirmed_reclaimable_bytes": 0, "potential_reclaimable_total_bytes": None,
        "cloud_calls": 0, "Registry_or_budget_changes": 0, "final_test_enabled": False}))


if __name__ == "__main__":
    main()
