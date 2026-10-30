"""Developer archival verification, not an independent product test."""
from collections import Counter
from io import BytesIO
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import subprocess
import zipfile

ROOT = Path.cwd().resolve()
SOURCE = Path("B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-44676db-20261027")
ZIP = SOURCE.with_suffix(".zip")
PASTED = Path("C:/Users/11638/.codex/attachments/af222930-c4a9-4fad-a50a-fa17fee17442/已粘贴的文本.txt")
TARGET = ROOT / "audit/reviews/20261027-44676db-windows"
CHECK = ROOT / "audit/44676db_review_archive_check.json"
EXPECTED_ZIP = "a7af4c6669228f65012e8d3d4d1fcdf18605663e700b70a90a6f631b225cc4da"
COMMIT = "44676db609b3b7c2175fa7fa4f19c8ccf8165458"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


protected = {str(path.relative_to(ROOT)): digest(path) for path in
    [ROOT / "config/budget.json", ROOT / "audit/runtime/registry/events.jsonl", ROOT / "audit/data_exposure.json"]}
assert digest(ZIP) == EXPECTED_ZIP
manifest_path = SOURCE / "artifact_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
assert len(manifest) == 15969
all_files = {path.relative_to(SOURCE).as_posix(): path for path in SOURCE.rglob("*") if path.is_file()}
assert set(all_files) == set(manifest) | {"artifact_manifest.json"}
for name, expected in manifest.items():
    pure = PurePosixPath(name)
    assert not pure.is_absolute() and ".." not in pure.parts and "\\" not in name
    assert digest(all_files[name]) == expected, name
with zipfile.ZipFile(ZIP) as archive:
    prefix = SOURCE.name + "/"
    members = {item.filename[len(prefix):]: item for item in archive.infolist() if not item.is_dir()
               and item.filename.startswith(prefix)}
    assert len(members) == len(archive.infolist()) == len(all_files)
    assert set(members) == set(all_files)
    for name, item in members.items():
        expected = manifest[name] if name in manifest else digest(manifest_path)
        value = hashlib.sha256()
        with archive.open(item) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(block)
        assert value.hexdigest() == expected, name

source_manifest_path = SOURCE / "source_git_manifest.json"
snapshots = json.loads(source_manifest_path.read_text(encoding="utf-8-sig"))
git_results = {}
for label, snapshot in snapshots.items():
    files = snapshot["files"]
    assert len(files) == snapshot["count"]
    requests = "".join(snapshot["commit"] + ":" + name + "\n" for name in files).encode("utf-8")
    response = subprocess.check_output(["git", "cat-file", "--batch"], input=requests, cwd=ROOT)
    stream = BytesIO(response)
    for name, expected in files.items():
        header = stream.readline().decode("ascii").split()
        assert len(header) == 3 and header[1] == "blob", (label, name)
        data = stream.read(int(header[2])); assert stream.read(1) == b"\n"
        assert hashlib.sha256(data).hexdigest() == expected, (label, name)
        assert manifest[snapshot["directory"] + "/" + name] == expected
    assert not stream.read()
    git_results[label] = {"commit": snapshot["commit"], "raw_git_blobs_verified": len(files),
                          "all_equal_original_manifest": True}

def selection_reason(name):
    parts = PurePosixPath(name).parts
    base = parts[-1]
    if parts[0] in {"source", "baselines"}:
        return "omitted_duplicate_fixed_Git_snapshot"
    if base.endswith(".index"):
        return "omitted_reconstructible_Git_index"
    if name in {"artifact_manifest.json", "source_git_manifest.json", "archive_agent/source_raw_git_manifest.json"}:
        return "omitted_complete_large_manifest_retained_in_ZIP"
    if name in {"change.diff", "PR_complete_patch.stdout", "archive_agent/baseline_to_candidate_full_patch.stdout"}:
        return "omitted_large_full_patch_retained_in_ZIP"
    if base in {"current_complete_name_status.stdout", "PR_complete_name_status.stdout", "change.names"}:
        return "omitted_redundant_full_name_list"
    if name == "archive_agent/old_cloud_source_rows.json":
        return "omitted_existing_archived_cloud_reference_copy"
    if len(parts) == 1:
        return "selected_root_report_provenance_or_reproduction"
    if parts[0] in {"cert_agent", "root_repair_confirmation", "root_wr27_confirmation", "archive_agent"}:
        return "selected_new_findings_original_material"
    if parts[0] == "protocol_agent":
        if len(parts) == 2 or parts[1] in {"legacy_adapted_scripts", "recovery_adapted_scripts", "wr23_original", "wr21_explicit_legacy"}:
            return "selected_protocol_scripts_or_original_mre"
        if parts[1] in {"boundaries", "research_failure"}:
            if len(parts) == 3 and base != "command_log.json" or parts[1] == "boundaries" and parts[2] == "parallel":
                return "selected_protocol_first_results_or_concurrent_controls"
        if base in {"results.json", "test_results.json", "execution.json", "execution_records.json", "summary.json"}:
            return "selected_protocol_summary"
    if name == "runs/execution_records.json":
        return "selected_root_execution_index"
    if parts[0] in {"admission_agent", "control_replay", "recovery_agent"} and len(parts) == 2:
        if base.endswith(".py") or base in {"report.json", "report.txt", "execution_records.json", "new_first_results.json", "new_contract_corrected_results.json", "script_bindings.json", "worker_identity_first_results.json", "pure_corrected_results.json", "cli_first_results.json", "preflight_cli_first_results.json"}:
            return "selected_existing_regression_summary_and_scripts"
    return "omitted_historical_replay_detail_retained_in_ZIP"

selected, omitted, non_utf = [], Counter(), []
for name, path in sorted(all_files.items()):
    reason = selection_reason(name)
    if reason.startswith("selected"):
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            non_utf.append({"path": name, "raw_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                            "reason": "Original non-UTF8 retained in complete ZIP without transcoding"})
            omitted["omitted_non_UTF8_original_retained_in_ZIP"] += 1
            continue
        selected.append({"path": name, "raw_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    else:
        omitted[reason] += 1

assert not TARGET.exists(), "Archive must be created once; do not overwrite a frozen archive"
TARGET.mkdir(parents=True)
for item in selected:
    dest = TARGET / item["path"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / item["path"], dest)
    assert digest(dest) == item["raw_sha256"]
pasted_name = "user_pasted_report_original.txt"
shutil.copyfile(PASTED, TARGET / pasted_name)
pasted = {"path": pasted_name, "source": str(PASTED), "raw_sha256": digest(PASTED), "bytes": PASTED.stat().st_size}
(TARGET / ".gitattributes").write_text("* -text\n", encoding="ascii", newline="\n")
selection = {"kind": "developer_selective_archival_metadata_not_new_review", "original_directory": str(SOURCE),
    "original_zip": str(ZIP), "original_zip_sha256": EXPECTED_ZIP, "original_zip_bytes": ZIP.stat().st_size,
    "original_package_files": len(all_files), "manifest_registered_files": len(manifest), "manifest_excludes_itself": True,
    "selected_originals": selected, "omitted_original_count": len(all_files) - len(selected), "omitted_groups": dict(omitted),
    "exact_selection_rule": "developer_archive_helper.py: selection_reason, then UTF-8-decodable selected originals only",
    "verified_external_inventory_refs": [{"path": "artifact_manifest.json", "raw_sha256": digest(manifest_path), "bytes": manifest_path.stat().st_size},
        {"path": "source_git_manifest.json", "raw_sha256": digest(source_manifest_path), "bytes": source_manifest_path.stat().st_size},
        {"path": "archive_agent/source_raw_git_manifest.json", "raw_sha256": digest(SOURCE / "archive_agent/source_raw_git_manifest.json"), "bytes": (SOURCE / "archive_agent/source_raw_git_manifest.json").stat().st_size}],
    "verified_external_non_UTF8_refs": non_utf, "pasted_report": pasted,
    "original_complete_manifest_is_not_selected_archive_manifest": True,
    "all_selected_originals_copied_without_byte_changes": True, "original_package_not_modified": True}
write(TARGET / "developer_archive_selection.json", selection)
helper = Path(__file__).read_bytes()
(TARGET / "developer_archive_helper.py").write_bytes(helper)
validation = {"kind": "developer_archive_integrity_not_product_validation", "original_zip_sha256_verified": True,
    "original_manifest_files_verified": len(manifest), "original_directory_and_ZIP_files_verified": len(all_files),
    "git_source_snapshots_verified": git_results, "selected_raw_hashes_verified": len(selected),
    "original_pasted_raw_hash_verified": True, "non_UTF8_originals_omitted_without_transcoding": non_utf,
    "archival_helper_attempts": [{"attempt": 1, "status": "passed", "product_tests_executed": 0}],
    "original_review_conclusion": "WR25/26/27 independently passed in tested offline scope; no new reproduced software findings; phase2 still pending actual runtime and data certification",
    "no_current_QC_or_product_test_calls": True, "no_authoritative_registry_or_budget_writes": True}
write(TARGET / "developer_archive_validation.json", validation)
(TARGET / "ARCHIVE_SCOPE.md").write_text("# Selective original review archive\n\n"
    "The fixed independent review is 44676db609b3b7c2175fa7fa4f19c8ccf8165458. WR-25/26/27 passed in the independently tested offline scope, with no newly reproduced software findings. Phase 2 as a whole still awaits real runtime and data certification.\n\n"
    "This directory is a selective raw-byte copy, not the complete sealed review package. The external ZIP, exact original paths, SHA-256 values, selection rule and omitted categories are in developer_archive_selection.json. The complete manifest and fixed Git snapshots were verified against all originals and ZIP members; large manifests, patches, repeated source, reconstructible Git indexes and historical command details remain in the original ZIP. Any non-UTF8 originals were kept there without conversion.\n\n"
    "developer_archive_* files, this scope file and .gitattributes are developer archival metadata, not independent review findings. user_pasted_report_original.txt is a separately labeled raw user attachment. The original review files keep their original bytes and labels. Reproductions require an isolated source tree and the indicated helpers; do not write outputs into this archive.\n\n"
    "No product tests, cloud reads, Research, LEAN submissions, model calls, deployment, trading or authoritative ledger writes were performed by this archival check. Budget remains configuration 7/12, Research 10/20, LEAN 1/16; journal 17 events, engineering stop gate active, final evaluation disabled, financial_evidence=false.\n", encoding="utf-8", newline="\n")
inventory = [{"path": path.relative_to(TARGET).as_posix(), "raw_sha256": digest(path), "bytes": path.stat().st_size}
             for path in sorted(TARGET.rglob("*")) if path.is_file()]
write(TARGET / "developer_archive_inventory.json", {"kind": "local_archive_files_except_this_manifest", "files": inventory,
    "manifest_excludes_itself": True, "selected_review_original_count": len(selected), "pasted_original_count": 1,
    "developer_metadata_count_including_this_manifest": 6})
expected_paths = {item["path"] for item in inventory} | {"developer_archive_inventory.json"}
assert expected_paths == {path.relative_to(TARGET).as_posix() for path in TARGET.rglob("*") if path.is_file()}
for name, expected in protected.items():
    assert digest(ROOT / name) == expected, name
report = json.loads((SOURCE / "formal_report.json").read_text(encoding="utf-8-sig"))
check = {"kind": "metadata_archival_verification_only_not_software_retest", "reviewed_source_commit": COMMIT,
    "review_formal_json_raw_sha256": digest(TARGET / "formal_report.json"), "review_formal_txt_raw_sha256": digest(TARGET / "formal_report.txt"),
    "original_zip_sha256": EXPECTED_ZIP, "original_package_files": len(all_files), "original_manifest_registered_files": len(manifest),
    "manifest_excludes_itself": True, "original_package_manifest_and_ZIP_verified": True,
    "archived_original_count": len(selected), "archived_original_raw_bytes": sum(item["bytes"] for item in selected),
    "archived_original_raw_hashes_match": True, "selective_archive_not_complete_original_package": True,
    "omitted_original_count": len(all_files) - len(selected), "archive_selection_ref": {"path": (TARGET / "developer_archive_selection.json").relative_to(ROOT).as_posix(), "raw_sha256": digest(TARGET / "developer_archive_selection.json")},
    "git_source_snapshots_verified": git_results, "source_manifest_hash": report["source_manifest_hash"],
    "execution_source_manifest_hash": report["execution_source_manifest_hash"], "software_acceptance": report["software_acceptance"],
    "original_WR25_WR26_WR27_repair_scope": "independently_passed_after_fix_on44676db_tested_offline_scope_only",
    "new_open_findings": [],
    "stage2_whole_accepted": False, "runtime_and_data_acceptance": "pending_insufficient_evidence", "real_registry_event_count": 17,
    "global_usage": {"configurations": 7, "research": 10, "lean": 1}, "engineering_round_usage": {"configurations": 2, "research": 2, "lean": 1}, "engineering_round_stopped": True,
    "archival_QC_calls": 0, "archival_Research_executions": 0, "archival_LEAN_submissions": 0, "archival_model_calls": 0, "archival_deployments": 0, "archival_software_test_executions": 0,
    "review_original_tests_not_reexecuted_by_this_archival_check": True, "production_or_config_files_changed_by_archival_agent": False,
    "report_counts_are_overlapping": True, "final_test_enabled": False, "financial_evidence": False}
write(CHECK, check)
for item in selected:
    assert digest(TARGET / item["path"]) == manifest[item["path"]]
assert digest(PASTED) == digest(TARGET / pasted_name)
assert digest(ZIP) == EXPECTED_ZIP
print(json.dumps({"archive": str(TARGET.relative_to(ROOT)), "selected_originals": len(selected),
    "selected_original_bytes": sum(item["bytes"] for item in selected), "archive_files": len(expected_paths),
    "archive_bytes": sum(path.stat().st_size for path in TARGET.rglob("*") if path.is_file()),
    "original_manifest_files": len(manifest), "original_package_files": len(all_files),
    "non_UTF8_omitted": non_utf, "all_checks_passed": True}))
