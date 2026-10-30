"""Collaborator's read-only cross-check of saved actual UI metadata only."""
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import base64
import json
import re
import zlib


P = Path(__file__).resolve().parent
ui_raw = (P / "ui_observations.json").read_bytes()
assert sha256(ui_raw).hexdigest() == "4808a3cfcddf81b3f837b0a40cf1636217a3c67fb7dc4b0aeb76c146dcb0962f"
ui = json.loads(ui_raw)
assessment_raw = (P / "object_assessment.pagination_fixed.json").read_bytes()
assessment = json.loads(assessment_raw)
index = json.loads((P / "raw_UI_metadata_index.json").read_bytes())
encoded = (P / index["path"]).read_bytes()
decoded = zlib.decompress(base64.b64decode(encoded))
assert sha256(decoded).hexdigest() == index["decoded_sha256"]
assert sha256(encoded).hexdigest() == index["encoded_sha256"]
blocks = json.loads(decoded)
assert len(blocks["blocks"]) == 40 and len(blocks["capacity_blocks"]) == 2
by_call = {(row["call_id"], row["output_block"]): row for row in blocks["blocks"]}
formats = Counter()
for observation in ui["observations"]:
    source = observation["provenance"]
    block = by_call[source["call_id"], source["output_block"]]
    text = block["text"]
    assert sha256(text.encode("utf-8")).hexdigest() == source["actual_output_sha256"]
    start, end = source["record_character_span"]
    marker, value = text[start:end].split(" ", 1)
    actual = json.loads(value)
    if marker == "AQRP_STORAGE_INVENTORY_UI":
        rows = actual["rows"]
    else:
        assert marker == "AQRP_STORAGE_INVENTORY_TUPLES"
        assert actual["columns"] == ["name", "type", "display_size", "last_modified"]
        assert actual["exact_bytes_available"] is False
        rows = [dict(zip(actual["columns"], row), exact_bytes=None) for row in actual["rows"]]
    formats[marker] += 1
    assert actual["path"] == observation["path"]
    assert rows == observation["rows"] and actual["paging"] == observation["paging"]

entries = {}
observed_rows = 0
positions = defaultdict(dict)
totals = defaultdict(set)
for number, observation in enumerate(ui["observations"]):
    match = re.search(r"(\d+)\s*to\s*(\d+)\s*of\s*(\d+)", " ".join(observation["paging"]), re.I)
    assert match
    low, high, total = map(int, match.groups())
    totals[observation["path"]].add(total)
    assert len(observation["rows"]) == (0 if total == 0 else high - low + 1)
    for position, row in zip(range(low, high + 1), observation["rows"]):
        path = "/".join(filter(None, [observation["path"], row["name"]]))
        old = positions[observation["path"]].get(position)
        assert old is None or old == path
        positions[observation["path"]][position] = path
    for row in observation["rows"]:
        observed_rows += 1
        path = "/".join(filter(None, [observation["path"], row["name"]]))
        assert path not in entries or entries[path] == row
        entries[path] = row
leaves = {key: value for key, value in entries.items() if value["type"] != "Folder"}
folders = {key: value for key, value in entries.items() if value["type"] == "Folder"}
assert len(leaves) == 456 and len(folders) == 40 and observed_rows == 529
assert set(leaves) == {row["path"] for row in assessment["objects"]}
assert len(totals) == 31 and all(len(values) == 1 for values in totals.values())
for path, values in totals.items():
    total = next(iter(values))
    assert sorted(positions[path]) == list(range(1, total + 1))
    result = next(row for row in assessment["directories"] if row["path"] == path)
    assert result["all_entries_observed_at_UI_metadata_level"]
    assert result["range_position_coverage_complete"] and result["position_to_key_consistent"]
assert all(row["exact_bytes"] is None for row in leaves.values())
unvisited = assessment["unvisited_child_directories"]
assert len(unvisited) == 10 and all(path.startswith("aqrp/engineering/v2/engineering/") for path in unvisited)
groups = assessment["same_digest_basename_review_groups"]
assert len(groups) == 96 and all(row["classification"] == "identity_name_repetition_not_content_duplicate" for row in groups)
gaps = {}
for version in ("v1", "v2"):
    prefix = "aqrp/engineering/v2/historical-snapshots/" + version
    intents = {key.rsplit("/", 1)[-1]: key for key in leaves if key.startswith(prefix + "/intents/")}
    windows = {key.rsplit("/", 1)[-1] for key in leaves if key.startswith(prefix + "/windows/")}
    gaps[version] = [intents[name] for name in sorted(intents.keys() - windows)]
assert len(gaps["v1"]) == 4 and len(gaps["v2"]) == 1
assert gaps["v2"][0].endswith("/7d192eebb9e271c7d420d00e7e11cc9f98d6482e4c62fd68e6bb9dc7d365deb5.json")
assert assessment["v2_intents_without_observed_matching_window_name"][0]["window_directory_fully_observed"] is True
assert assessment["confirmed_reclaimable_bytes"] == 0 and assessment["potential_reclaimable_total_bytes"] is None
assert assessment["UI_tree_listing_complete_within_declared_scope"] is False

review = {
    "schema_version": 1,
    "kind": "developer_collaborator_actual_metadata_review_not_independent_acceptance",
    "inputs": {"UI_sha256": sha256(ui_raw).hexdigest(), "fixed_assessment_sha256": sha256(assessment_raw).hexdigest(),
               "analyzer_sha256": sha256((P / "analyze_inventory.py").read_bytes()).hexdigest()},
    "actual_checks": {"original_block_archive_hashes_match": True, "table_blocks": 40, "capacity_blocks": 2,
        "all63_observations_match_original_block_hash_character_span_and_explicit_column_mapping": True,
        "raw_marker_formats": dict(formats), "visible_row_observations": 529, "unique_UI_entries": 496,
        "unique_UI_leaf_objects": 456, "unique_UI_folders": 40, "repeated_observations_not_extra_objects": 33,
        "directories_observed": 31, "all31_range_ordered_positions_and_unique_keys_match_totals": True,
        "metadata_conflicts": 0, "exact_byte_sizes_obtained": 0, "whole_organization_tree_complete": False},
    "pagination_fix": {"initial_actual_assessment_preserved": "object_assessment.json",
        "initial_extended19_tests_failed": 4, "final20_known_answers_passed": True,
        "known_answer_evidence": "pagination_fix/final_known_answers.json", "v2_window_page_total_labels": [3, 4],
        "v2_window_unique_keys_and_positions": 43, "v2_window_repeated_rows": 30,
        "Factor_Validator_empty_0_of_0_supported": True, "nonempty_0_of_0_rejected": True},
    "reviewer_probe_correction": {"initial_probe_exit": 1,
        "reason": "Review probe initially assumed only the UI object marker; saved actual tool output also uses TUPLES with four explicit columns",
        "correction": "Decode each recorded marker format with its actual declared columns; do not change the UI source observations",
        "this_was_an_audit_probe_assumption_not_an_additional_product_defect": True},
    "hash_name_review": {"same_digest_name_groups": 96, "all_are_identity_names_not_content_duplicate_proof": True,
        "payload_digest_duplicate_name_groups_observed": 0, "actual_content_duplicates_verified": 0},
    "unmatched_intents_by_UI_name_only": gaps,
    "unmatched_interpretation": "Absent names in complete respective window listings; preserve intent and any partial-write forensic evidence. No specific batch association follows from a name or timestamp.",
    "v1_raw_payload_objects_requiring_cloud_header_and_reference_review": assessment["v1_raw_objects_require_cloud_reference_and_header_review"],
    "unvisited_child_directories": unvisited,
    "unvisited_disposition": "All ten are within historical engineering namespaces. Retain each entire subtree; descendant counts and all reference edges were not enumerated.",
    "release": {"every_leaf_retained": True, "unknown_generic_raw_objects_retained": 3,
        "confirmed_reclaimable_bytes": 0, "potential_total_bytes": None, "reference_closure_complete": False,
        "rounded_UI_sizes_are_not_release_bytes": True},
    "remaining_boundaries": ["Raw SDK keys and exact bytes are not authenticated",
        "Cloud metadata bodies and transitive references remain unresolved",
        "Other project consumers or unseen implicit references remain possible",
        "No payload bytes or row values were exported or compared",
        "Saved UI tool text consistency is not server authentication or an atomic cloud snapshot"],
    "product_source_changed": False, "cloud_calls": 0, "Research_executions": 0, "LEAN_submissions": 0,
    "Registry_or_budget_changes": 0, "cloud_deletions": 0, "independent_acceptance": False,
    "financial_evidence": False, "final_test_enabled": False}
assert ui_raw == (P / "ui_observations.json").read_bytes()
(P / "actual_assessment_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"actual_review_saved": True, "original_UI_observations_verified": 63,
    "visited_directories_with_complete_range_position_evidence": 31, "UI_leaf_objects": 456,
    "unmatched_v1_intents": 4, "unmatched_v2_intents": 1, "unvisited_historical_subtrees": 10,
    "confirmed_reclaimable_bytes": 0, "potential_total_bytes": None,
    "review_sha256": sha256((P / "actual_assessment_review.json").read_bytes()).hexdigest()}))
