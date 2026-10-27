"""Read-only verification and selected byte-preserving archival of a sealed review.

This is developer archival metadata, not another independent software review.
It never executes review/product scripts or changes the authoritative ledger.
"""
from pathlib import Path
import hashlib
import io
import json
import collections
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
TARGET = Path(__file__).resolve().parent
ORIGINAL = Path("B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-deb85d9-20261027")
PASTED = Path("C:/Users/11638/.codex/attachments/f21bf5c9-7d10-4589-a457-e2ca8c3b011f/已粘贴的文本.txt")
EXPECTED_ZIP = "19d2614008caf209c18b79e16220826de0394ee9a86f585f32ccce5a9bfd6b49"
OMIT_PATCHES = {"change.diff", "PR_complete_patch.stdout"}
EXTERNAL_INVENTORIES = {"artifact_manifest.json", "source_git_manifest.json"}
COMPLETE_SUBTREES = {"cert_agent", "entry_agent", "entry_additional", "wr20_confirmation", "wr21_confirmation"}
NATIVE_NONCOMMAND_SUBTREE = "native_agent"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def document(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_document(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    assert ORIGINAL.is_dir()
    zip_path = ORIGINAL.with_suffix(".zip")
    zip_raw_hash = digest(zip_path.read_bytes())
    assert zip_raw_hash == EXPECTED_ZIP
    manifest = document(ORIGINAL / "artifact_manifest.json")
    actual = {p.relative_to(ORIGINAL).as_posix(): p for p in ORIGINAL.rglob("*") if p.is_file()}
    assert set(actual) == set(manifest) | {"artifact_manifest.json"}
    for relative, expected in manifest.items():
        assert (ORIGINAL / relative).resolve().is_relative_to(ORIGINAL.resolve())
        assert digest(actual[relative].read_bytes()) == expected, relative
    with zipfile.ZipFile(zip_path) as archive:
        entries = archive.infolist()
        assert all(not info.is_dir() for info in entries)
        assert len({info.filename for info in entries}) == len(entries)
        prefix = ORIGINAL.name + "/"
        assert {info.filename for info in entries} == {prefix + rel for rel in actual}
        for info in entries:
            relative = info.filename[len(prefix):]
            expected = manifest.get(relative) or digest(actual[relative].read_bytes())
            assert digest(archive.read(info)) == expected, info.filename

    source_manifests = document(ORIGINAL / "source_git_manifest.json")
    git_checks = {}
    for name, source in source_manifests.items():
        files = source["files"]
        assert len(files) == source["count"]
        lines = b"".join((source["commit"] + ":" + rel + "\n").encode("utf-8") for rel in files)
        result = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, input=lines, capture_output=True, check=True)
        stream = io.BytesIO(result.stdout)
        for relative, expected in files.items():
            head = stream.readline().decode("ascii").strip().split()
            assert len(head) == 3 and head[1] == "blob", (name, relative, head)
            body = stream.read(int(head[2]))
            assert stream.read(1) == b"\n"
            assert digest(body) == expected, (name, relative)
        assert stream.read() == b""
        git_checks[name] = {"commit": source["commit"], "raw_git_blobs_verified": len(files), "all_equal_original_manifest": True}

    selected = []
    omitted = []
    for relative, path in sorted(actual.items()):
        parts = Path(relative).parts
        reason = ("fixed_Git_source_snapshot_reconstructible_from_verified_commit" if parts[0] in {"source", "baselines"}
                  else "complete_original_inventory_retained_in_original_hash_verified_package" if relative in EXTERNAL_INVENTORIES
                  else "redundant_full_patch_retained_in_original_hash_verified_package" if relative in OMIT_PATCHES
                  else "historical_replay_or_individual_native_command_output_retained_in_original_hash_verified_package"
                  if len(parts) > 1 and parts[0] not in COMPLETE_SUBTREES
                  and not (parts[0] == NATIVE_NONCOMMAND_SUBTREE and "commands" not in parts)
                  else None)
        raw = path.read_bytes()
        if reason:
            omitted.append({"path": relative, "raw_sha256": digest(raw), "bytes": len(raw), "reason": reason})
            continue
        target = TARGET / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == raw, relative
        else:
            shutil.copyfile(path, target)
        assert target.read_bytes() == raw
        selected.append({"path": relative, "raw_sha256": digest(raw), "bytes": len(raw)})
    pasted_raw = PASTED.read_bytes()
    pasted_target = TARGET / "user_pasted_report.txt"
    if pasted_target.exists():
        assert pasted_target.read_bytes() == pasted_raw
    else:
        shutil.copyfile(PASTED, pasted_target)
    omitted_groups = collections.defaultdict(lambda: {"files": 0, "bytes": 0})
    for item in omitted:
        group = omitted_groups[item["reason"]]
        group["files"] += 1
        group["bytes"] += item["bytes"]
    write_document(TARGET / "developer_archive_selection.json", {
        "kind": "developer_selective_archival_metadata_not_new_review",
        "original_directory": str(ORIGINAL), "original_zip": str(zip_path),
        "original_zip_sha256": zip_raw_hash, "original_zip_bytes": zip_path.stat().st_size,
        "selected_originals": selected,
        "omitted_original_count": len(omitted),
        "omitted_groups": omitted_groups,
        "exact_selection_rule": {
            "omit_all_subtrees": ["source", "baselines"],
            "omit_root_files": sorted(OMIT_PATCHES | EXTERNAL_INVENTORIES),
            "retain_complete_subtrees": sorted(COMPLETE_SUBTREES),
            "retain_native_subtree_except_any_commands_directory": NATIVE_NONCOMMAND_SUBTREE,
            "retain_other_root_files": True,
            "omit_other_subtrees": True,
            "reconstruct_omitted_names_and_hashes_from_external_original_manifest": True,
        },
        "verified_external_inventory_refs": {name: {"original_path": str(ORIGINAL / name),
            "raw_sha256": digest((ORIGINAL / name).read_bytes()), "bytes": (ORIGINAL / name).stat().st_size}
            for name in sorted(EXTERNAL_INVENTORIES)},
        "pasted_report": {"source_path": str(PASTED), "path": pasted_target.name,
                          "raw_sha256": digest(pasted_raw), "bytes": len(pasted_raw)},
        "original_complete_manifest_is_not_selected_archive_manifest": True,
        "all_selected_originals_copied_without_byte_changes": True,
        "original_package_not_modified": True,
    })
    review = document(ORIGINAL / "formal_report.json")
    check = {
        "kind": "metadata_archival_verification_only_not_software_retest",
        "reviewed_source_commit": review["reviewed_source_commit"],
        "review_formal_json_raw_sha256": digest((ORIGINAL / "formal_report.json").read_bytes()),
        "review_formal_txt_raw_sha256": digest((ORIGINAL / "formal_report.txt").read_bytes()),
        "original_zip_sha256": zip_raw_hash,
        "original_package_files": len(actual), "original_manifest_registered_files": len(manifest),
        "manifest_excludes_itself": True,
        "original_package_manifest_and_ZIP_verified": True,
        "archived_original_count": len(selected),
        "archived_original_raw_bytes": sum(item["bytes"] for item in selected),
        "archived_original_raw_hashes_match": True,
        "selective_archive_not_complete_original_package": True,
        "omitted_original_count": len(omitted),
        "archive_selection_ref": {"path": (TARGET / "developer_archive_selection.json").relative_to(ROOT).as_posix(),
                                  "raw_sha256": digest((TARGET / "developer_archive_selection.json").read_bytes())},
        "git_source_snapshots_verified": git_checks,
        "source_manifest_hash": review["source_manifest_hash"],
        "execution_source_manifest_hash": review["execution_source_manifest_hash"],
        "software_acceptance": review["software_acceptance"],
        "new_open_findings": [{"id": "WR-21", "priority": "P1"}, {"id": "WR-20", "priority": "P2"}],
        "remaining_acceptance_gates": review["acceptance_gates"],
        "stage2_whole_accepted": False,
        "real_registry_event_count": 17,
        "global_usage": {"configurations": 7, "research": 10, "lean": 1},
        "engineering_round_usage": {"configurations": 2, "research": 2, "lean": 1},
        "engineering_round_stopped": True,
        "archival_QC_calls": 0, "archival_Research_executions": 0,
        "archival_LEAN_submissions": 0, "archival_model_calls": 0,
        "archival_deployments": 0, "archival_software_test_executions": 0,
        "review_original_tests_not_reexecuted_by_this_archival_check": True,
        "archive_helper_attempts": [
            {"attempt": 1, "status": "completed_full_verification_initial_selection", "selected_originals": 218,
             "selected_raw_bytes": 7279327, "note": "Initial selection included both large original inventories; developer selection metadata listed every omitted file."},
            {"attempt": 2, "status": "completed_compact_selection", "note": "Retain original inventories externally with exact raw hashes and selection rules; avoid copying duplicate source inventories or listing every omitted Git source file again."},
        ],
        "production_or_config_files_changed_by_archival_agent": False,
        "report_counts_are_overlapping": True,
        "final_test_enabled": False, "financial_evidence": False,
    }
    write_document(ROOT / "audit/deb85d9_review_archive_check.json", check)
    print(json.dumps({k: check[k] for k in ["original_package_files", "original_manifest_registered_files", "archived_original_count", "archived_original_raw_bytes", "omitted_original_count", "original_package_manifest_and_ZIP_verified", "git_source_snapshots_verified"]}))


if __name__ == "__main__":
    main()
