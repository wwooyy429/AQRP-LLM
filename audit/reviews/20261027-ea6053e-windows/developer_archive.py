"""Verify a sealed review and preserve selected originals without executing it.

This developer archival check does not grant software or financial approval.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import io
import json
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
TARGET = Path(__file__).resolve().parent
ORIGINAL = Path("B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ea6053e-20261027")
PASTED = Path("C:/Users/11638/.codex/attachments/60b0706d-1634-4d98-818c-0554c8bbcd25/已粘贴的文本.txt")
EXPECTED_ZIP = "3eb0d548f2667c83c24e62f88495ae02fa2c8942440ce0c4aa665bb06b054753"
INVENTORIES = {"artifact_manifest.json", "source_git_manifest.json"}
ROOT_REDUNDANT = {"change.diff", "PR_complete_patch.stdout", "PR_complete_name_status.stdout"}
COMPLETE = {"cert_agent", "entry_additional", "entry_agent", "wr22_confirmation", "wr23_confirmation"}
NONCOMMAND = {"dispatch_agent", "recovery_agent"}
EXTERNAL_NON_UTF8 = {"archive_agent/first.stdout", "dispatch_agent/legacy_original/crash_addendum/first.stdout"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def omitted_reason(relative):
    parts = Path(relative).parts
    if parts[0] in {"source", "baselines"}:
        return "fixed_Git_source_snapshot_reconstructible_from_verified_commit"
    if relative in INVENTORIES:
        return "complete_original_inventory_retained_in_original_hash_verified_package"
    if relative in ROOT_REDUNDANT:
        return "redundant_full_patch_or_PR_name_list_retained_in_original_package"
    if relative in EXTERNAL_NON_UTF8:
        return "non_UTF8_original_stdout_retained_without_transcoding_in_original_package"
    if parts[0] == "archive_agent" and (parts[-1].endswith("_git_archive.stdout") or parts[-1].endswith("full_patch.stdout")):
        return "redundant_binary_Git_tar_or_full_patch_retained_in_original_package"
    if len(parts) == 1 or parts[0] in COMPLETE or parts[0] == "archive_agent":
        return None
    if parts[0] in NONCOMMAND and "commands" not in parts:
        return None
    return "historical_replay_or_individual_command_output_retained_in_original_package"


def main():
    zip_path = ORIGINAL.with_suffix(".zip")
    assert digest(zip_path.read_bytes()) == EXPECTED_ZIP
    manifest = read(ORIGINAL / "artifact_manifest.json")
    actual = {p.relative_to(ORIGINAL).as_posix(): p for p in ORIGINAL.rglob("*") if p.is_file()}
    assert set(actual) == set(manifest) | {"artifact_manifest.json"}
    for name, expected in manifest.items():
        assert (ORIGINAL / name).resolve().is_relative_to(ORIGINAL.resolve())
        assert digest(actual[name].read_bytes()) == expected, name
    with zipfile.ZipFile(zip_path) as archive:
        entries = archive.infolist()
        assert all(not item.is_dir() for item in entries)
        assert len({item.filename for item in entries}) == len(entries)
        prefix = ORIGINAL.name + "/"
        assert {item.filename for item in entries} == {prefix + name for name in actual}
        for info in entries:
            name = info.filename[len(prefix):]
            assert digest(archive.read(info)) == manifest.get(name, digest(actual[name].read_bytes())), name
    print(json.dumps({"complete_package_manifest_and_ZIP_verified": True,
                      "manifest_files": len(manifest), "zip_files": len(actual)}), flush=True)

    git_checks = {}
    for label, snapshot in read(ORIGINAL / "source_git_manifest.json").items():
        files = snapshot["files"]
        assert len(files) == snapshot["count"]
        requests = "".join(snapshot["commit"] + ":" + name + "\n" for name in files).encode("utf-8")
        stream = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=requests, cwd=ROOT))
        for name, expected in files.items():
            header = stream.readline().decode("ascii").strip().split()
            assert len(header) == 3 and header[1] == "blob", (label, name)
            raw = stream.read(int(header[2]))
            assert stream.read(1) == b"\n"
            assert digest(raw) == expected, (label, name)
        assert stream.read() == b""
        git_checks[label] = {"commit": snapshot["commit"], "raw_git_blobs_verified": len(files),
                             "all_equal_original_manifest": True}
    print(json.dumps({"fixed_Git_snapshots_verified": git_checks}), flush=True)

    selected = []
    omitted_groups = defaultdict(lambda: {"files": 0, "bytes": 0})
    omitted_count = 0
    for name, source in sorted(actual.items()):
        reason = omitted_reason(name)
        if reason:
            omitted_count += 1
            omitted_groups[reason]["files"] += 1
            omitted_groups[reason]["bytes"] += source.stat().st_size
            continue
        raw = source.read_bytes()
        raw.decode("utf-8")  # Only readable source/audit metadata enters Git.
        target = TARGET / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == raw, name
        else:
            shutil.copyfile(source, target)
        assert target.read_bytes() == raw
        selected.append({"path": name, "raw_sha256": digest(raw), "bytes": len(raw)})

    pasted_raw = PASTED.read_bytes()
    pasted_target = TARGET / "user_pasted_report.txt"
    if pasted_target.exists():
        assert pasted_target.read_bytes() == pasted_raw
    else:
        shutil.copyfile(PASTED, pasted_target)
    selection = {
        "kind": "developer_selective_archival_metadata_not_new_review",
        "original_directory": str(ORIGINAL), "original_zip": str(zip_path),
        "original_zip_sha256": EXPECTED_ZIP, "original_zip_bytes": zip_path.stat().st_size,
        "original_package_files": len(actual), "manifest_registered_files": len(manifest),
        "manifest_excludes_itself": True,
        "selected_originals": selected, "omitted_original_count": omitted_count,
        "omitted_groups": omitted_groups,
        "exact_selection_rule": {
            "omit_all_subtrees": ["source", "baselines"],
            "omit_root_files": sorted(INVENTORIES | ROOT_REDUNDANT),
            "retain_non_UTF8_originals_externally_without_transcoding": sorted(EXTERNAL_NON_UTF8),
            "retain_complete_subtrees": sorted(COMPLETE),
            "retain_noncommand_subtrees": sorted(NONCOMMAND),
            "omit_any_commands_directory_within_noncommand_subtrees": True,
            "retain_archive_agent_except_git_tar_and_full_patch_stdout": True,
            "retain_other_root_files": True, "omit_other_subtrees": True,
            "exact_omitted_names_and_hashes_reconstructible_from_external_original_manifest": True,
        },
        "verified_external_inventory_refs": {
            name: {"original_path": str(ORIGINAL / name), "raw_sha256": digest((ORIGINAL / name).read_bytes()),
                   "bytes": (ORIGINAL / name).stat().st_size} for name in sorted(INVENTORIES)},
        "verified_external_non_UTF8_refs": {
            name: {"original_path": str(ORIGINAL / name), "raw_sha256": digest((ORIGINAL / name).read_bytes()),
                   "bytes": (ORIGINAL / name).stat().st_size} for name in sorted(EXTERNAL_NON_UTF8)},
        "pasted_report": {"source_path": str(PASTED), "path": pasted_target.name,
                          "raw_sha256": digest(pasted_raw), "bytes": len(pasted_raw)},
        "original_complete_manifest_is_not_selected_archive_manifest": True,
        "all_selected_originals_copied_without_byte_changes": True, "original_package_not_modified": True,
    }
    write(TARGET / "developer_archive_selection.json", selection)
    review = read(ORIGINAL / "formal_report.json")
    check = {
        "kind": "metadata_archival_verification_only_not_software_retest",
        "reviewed_source_commit": review["reviewed_source_commit"],
        "review_formal_json_raw_sha256": digest((ORIGINAL / "formal_report.json").read_bytes()),
        "review_formal_txt_raw_sha256": digest((ORIGINAL / "formal_report.txt").read_bytes()),
        "original_zip_sha256": EXPECTED_ZIP, "original_package_files": len(actual),
        "original_manifest_registered_files": len(manifest), "manifest_excludes_itself": True,
        "original_package_manifest_and_ZIP_verified": True,
        "archived_original_count": len(selected), "archived_original_raw_bytes": sum(x["bytes"] for x in selected),
        "archived_original_raw_hashes_match": True, "selective_archive_not_complete_original_package": True,
        "omitted_original_count": omitted_count,
        "archive_selection_ref": {"path": (TARGET / "developer_archive_selection.json").relative_to(ROOT).as_posix(),
                                  "raw_sha256": digest((TARGET / "developer_archive_selection.json").read_bytes())},
        "git_source_snapshots_verified": git_checks,
        "source_manifest_hash": review["source_manifest_hash"],
        "execution_source_manifest_hash": review["execution_source_manifest_hash"],
        "software_acceptance": review["software_acceptance"],
        "original_WR20_WR21_trigger_scope": "independently_passed_after_fix_on_ea6053e_only",
        "new_open_findings": [{"id": "WR-23", "priority": "P1", "blocking": True},
                              {"id": "WR-22", "priority": "P2", "blocking": True},
                              {"id": "WR-24", "priority": "P3", "blocking": False}],
        "remaining_acceptance_gates": {
            "G1": "Actual Research failed; no new qualifying Research/collection/cache/LEAN success chain",
            "G2": "Old failed worker bytes/source difference remain unproven",
            "G3": "WR21 original trigger passed; new prepare/admission crash identity WR23 blocks full entry protocol",
            "G4": "WR20 original IPO trigger passed; WR22 missing history audit blocks module; full data provenance remains insufficient"},
        "stage2_whole_accepted": False, "real_registry_event_count": 17,
        "global_usage": {"configurations": 7, "research": 10, "lean": 1},
        "engineering_round_usage": {"configurations": 2, "research": 2, "lean": 1},
        "engineering_round_stopped": True,
        "archival_QC_calls": 0, "archival_Research_executions": 0, "archival_LEAN_submissions": 0,
        "archival_model_calls": 0, "archival_deployments": 0, "archival_software_test_executions": 0,
        "review_original_tests_not_reexecuted_by_this_archival_check": True,
        "production_or_config_files_changed_by_archival_agent": False,
        "archive_helper_attempts_ref": "audit/reviews/20261027-ea6053e-windows/developer_archive_attempts.json",
        "report_counts_are_overlapping": True, "final_test_enabled": False, "financial_evidence": False,
    }
    write(ROOT / "audit/ea6053e_review_archive_check.json", check)
    expected_paths = {item["path"] for item in selected} | {
        "user_pasted_report.txt", "developer_archive_selection.json", "developer_archive.py", ".gitattributes", "DEVELOPER_ARCHIVE_README.md",
        "developer_archive_initial.py", "developer_archive_attempts.json"}
    actual_paths = {p.relative_to(TARGET).as_posix() for p in TARGET.rglob("*") if p.is_file()}
    assert actual_paths == expected_paths, (actual_paths - expected_paths, expected_paths - actual_paths)
    assert sum(item["files"] for item in omitted_groups.values()) + len(selected) == len(actual)
    print(json.dumps({k: check[k] for k in ("original_package_files", "original_manifest_registered_files",
        "archived_original_count", "archived_original_raw_bytes", "omitted_original_count",
        "original_package_manifest_and_ZIP_verified", "git_source_snapshots_verified")}), flush=True)


if __name__ == "__main__":
    main()
