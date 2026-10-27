"""Archived comparison only; no cloud/network/provider access."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
mode = sys.argv[1] if len(sys.argv) > 1 else "before"
reviewed = "81fbe5294055423e88ee5aeae48ca6223e7971da"

def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))

def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

summary_path = "audit/stage2_current_readiness.json"
if mode == "before":
    summary_raw = subprocess.check_output(["git", "show", reviewed + ":" + summary_path], cwd=ROOT)
    readiness = json.loads(summary_raw)
else:
    summary_raw = (ROOT / summary_path).read_bytes()
    readiness = json.loads(summary_raw)
summary = readiness["platform_comparison_from_independent_review"]

archive = "audit/reviews/20261027-ae2b898-windows"
manifest_path = archive + "/source_git_manifest.json"
comparison_path = archive + "/cloud_comparison.json"
manifest = read(manifest_path)["candidate"]
comparison = read(comparison_path)
assert summary["candidate_commit"] == manifest["commit"] == comparison["reviewed_source_commit"]
candidate = {k[len("cloud/"):]: v for k, v in manifest["files"].items()
             if k.startswith("cloud/") and k.endswith(".py")}
reference = {item["path"]: item["cloud_utf8_sha256"] for item in comparison["files"]
             if item["path"] != "_engineering_task_input.py"}
different = sorted(k for k in candidate.keys() & reference.keys() if candidate[k] != reference[k])
outside = sorted(candidate.keys() - reference.keys())
equal = sorted(k for k in candidate.keys() & reference.keys() if candidate[k] == reference[k])
computed = len(different) + len(outside)

historical_archive = "audit/reviews/20261027-dc49f0f-windows"
historical_manifest = read(historical_archive + "/source_git_manifest.json")["candidate"]
historical_report = read(historical_archive + "/formal_report.json")
historical_candidate = {k[len("cloud/"):]: v for k, v in historical_manifest["files"].items()
                        if k.startswith("cloud/") and k.endswith(".py")}
historical_different = sorted(k for k in historical_candidate.keys() & reference.keys()
                              if historical_candidate[k] != reference[k])
historical_outside = sorted(historical_candidate.keys() - reference.keys())
historical_computed = len(historical_different) + len(historical_outside)
assert historical_report["platform_state"]["current_cloud_source_commit"] == comparison["old_cloud_source_commit"]
assert historical_computed == historical_report["platform_state"]["candidate_differing_paths"] == 12

post_fix_metadata_checks = None
if mode == "after":
    assert summary["candidate_known_reference_different_paths"] == len(different) == 9
    assert summary["candidate_paths_not_in_reference"] == len(outside) == 4
    assert summary["candidate_manifest_files"] == len(candidate) == 29
    assert summary["known_reference_files"] == len(reference) == 25
    assert summary["differing_known_reference_paths"] == different
    assert summary["paths_not_in_known_reference"] == outside
    assert summary["runtime_source_commit"] == comparison["old_cloud_source_commit"]
    assert summary["candidate_manifest_ref"] == {"path": manifest_path, "raw_sha256": sha(manifest_path)}
    assert summary["archived_platform_comparison_ref"] == {"path": comparison_path, "raw_sha256": sha(comparison_path)}
    original_raw = subprocess.check_output(["git", "show", reviewed + ":" + summary_path], cwd=ROOT)
    correction = readiness["WR19_comparison_correction"]
    assert (ROOT / correction["original_Git_record"]).read_bytes() == original_raw
    assert correction["original_claim"] == json.loads(original_raw)["platform_comparison_from_independent_review"]
    assert correction["original_claim"]["candidate_different_or_missing_paths"] == 12
    assert correction["corrected_count"] == computed == 13
    historical_paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", reviewed, "--", historical_archive], cwd=ROOT).decode("utf-8").splitlines()
    assert historical_paths
    for path in historical_paths:
        old_bytes = subprocess.check_output(["git", "show", reviewed + ":" + path], cwd=ROOT)
        assert (ROOT / path).read_bytes() == old_bytes, "Historical archive changed: " + path
    post_fix_metadata_checks = {
        "declared_components_and_lists_match_recomputation": True,
        "source_ids_and_raw_hash_references_match": True,
        "original_Git_record_preserved_byte_exact": True,
        "original_Git_record_raw_sha256": hashlib.sha256(original_raw).hexdigest(),
        "original_claim_12_retained_and_corrected_13_explicit": True,
        "historical_dc49_archive_files_checked_byte_exact": len(historical_paths),
        "historical_dc49_archive_unchanged_vs_fixed81f": True,
    }

result = {
    "kind": "read_only_archived_comparison_recomputation_not_platform_evidence",
    "mode": mode,
    "fixed_reported_commit": reviewed,
    "summary_raw_sha256": hashlib.sha256(summary_raw).hexdigest(),
    "candidate_commit": manifest["commit"],
    "reference_source_commit": comparison["old_cloud_source_commit"],
    "candidate_file_count": len(candidate), "known_reference_file_count": len(reference),
    "equal_paths": equal, "different_paths": different,
    "outside_known_reference_paths": outside,
    "different_count": len(different), "outside_known_reference_count": len(outside),
    "computed_total": computed,
    "declared_total": summary["candidate_different_or_missing_paths"],
    "declaration_matches": summary["candidate_different_or_missing_paths"] == computed,
    "references": {
        "candidate_manifest": {"path": manifest_path, "raw_sha256": sha(manifest_path)},
        "comparison": {"path": comparison_path, "raw_sha256": sha(comparison_path)}
    },
    "historical_dc49": {
        "candidate_commit": historical_manifest["commit"],
        "candidate_file_count": len(historical_candidate),
        "different_paths": historical_different, "outside_known_reference_paths": historical_outside,
        "computed_total": historical_computed, "declared_total": 12,
        "reference_source_same_old75": True,
        "historical_declaration_is_consistent_and_must_not_be_rewritten": True
    },
    "current_cloud_missing_files_proven": False,
    "current_cloud_inventory_certified": False,
    "actual_cloud_or_market_or_model_calls": 0
}
if post_fix_metadata_checks is not None:
    result["post_fix_metadata_checks"] = post_fix_metadata_checks
OUT.mkdir(parents=True, exist_ok=True)
(OUT / ("pre_fix_comparison_audit.json" if mode == "before" else "post_fix_comparison_audit.json")).write_bytes(
    (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(json.dumps(result, ensure_ascii=True, indent=2))
assert result["declaration_matches"], "WR-19: archived comparison count mismatch"
