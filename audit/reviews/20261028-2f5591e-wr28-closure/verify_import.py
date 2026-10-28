"""Read-only compact review seal; never a product test or review approval."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_source_maps(repository, sources):
    """Read immutable Git blobs in one batch; no checkout/eol conversion."""
    tree_maps = {}
    blobs = set()
    for label, source in sources.items():
        output = subprocess.check_output(["git", "ls-tree", "-rz", source["commit"]], cwd=repository)
        mapping = {}
        for entry in output.split(b"\0"):
            if not entry:
                continue
            metadata, name = entry.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            assert kind == b"blob", "Only ordinary Git file objects are supported"
            path, oid = name.decode("utf-8"), oid.decode("ascii")
            assert path not in mapping
            mapping[path] = oid
            blobs.add(oid)
        assert set(mapping) == set(source["files"]), label
        tree_maps[label] = mapping
    ordered = sorted(blobs)
    completed = subprocess.run(["git", "cat-file", "--batch"], cwd=repository,
        input=("\n".join(ordered) + "\n").encode("ascii"), capture_output=True, check=True)
    data, cursor, observed = completed.stdout, 0, {}
    for oid in ordered:
        end = data.index(b"\n", cursor)
        header = data[cursor:end].split()
        assert len(header) == 3 and header[0].decode("ascii") == oid and header[1] == b"blob"
        size = int(header[2])
        start, cursor = end + 1, end + 1 + size
        raw = data[start:cursor]
        assert len(raw) == size and data[cursor:cursor+1] == b"\n"
        cursor += 1
        observed[oid] = digest(raw)
    assert cursor == len(data)
    for label, source in sources.items():
        for name, expected in source["files"].items():
            assert observed[tree_maps[label][name]] == expected, (label, name)
    return {label: len(mapping) for label, mapping in tree_maps.items()}


def verify(*, original_zip=None, git_repository=None):
    root = Path(__file__).resolve().parent
    seal = json.loads((root / "archive_manifest.json").read_bytes())
    assert isinstance(seal, dict) and seal
    for name, expected in seal.items():
        path = (root / name).resolve()
        assert path.is_relative_to(root.resolve()), name
        assert digest(path.read_bytes()) == expected, name
    index = json.loads((root / "import_index.json").read_bytes())
    for name, expected in index["copied_files"].items():
        assert digest((root / name).read_bytes()) == expected, name
    report = json.loads((root / "evidence/formal_report.json").read_bytes())
    assert report["review_id"] == index["review_id"] == "AQRP-20261028-2F5591E-WR28-24"
    assert report["reviewed_source_commit"] == index["reviewed_commit"] == "2f5591e28c0748ac42caeae7bbf3977141d031cb"
    assert report["production_source_commit"] == "4a42c18f0b78bea2068d589bc12f1615712354c6"
    assert report["software_acceptance"]["WR28_audit_delivery_scope"] == "fixed_verified_passed_and_closed_at_2f5591e"
    assert report["software_acceptance"]["phase2_overall"] == "not_accepted"
    assert report["WR28_resolution"]["id"] == "WR-28"
    assert report["WR28_resolution"]["status"] == "fixed_verified_closed"
    assert report["WR28_resolution"]["new_records_verified"] == 122
    assert report["WR28_resolution"]["original_legacy_mismatches_retained"] == 3
    assert report["findings"] == []
    assert report["budget_replay"]["events"] == 48
    assert report["budget_replay"]["usage"] == dict(configurations=12, research=15, lean=2)
    assert report["platform_evidence_level"]["actual_orders"] is None
    assert report["platform_evidence_level"]["actual_successful_LEAN_checks"] is None
    assert report["platform_evidence_level"]["EOF_v2_registered_or_deployed"] is False
    assert report["financial_evidence"] is False
    zip_checked, git_checked, source_counts = False, False, None
    if original_zip is not None:
        assert digest(original_zip.read_bytes()) == index["original_zip_sha256"]
        with zipfile.ZipFile(original_zip) as archive:
            assert archive.testzip() is None
            members = [member for member in archive.infolist() if not member.is_dir()]
            names = [member.filename for member in members]
            assert len(names) == len(set(names)) == index["original_total_files"]
            prefix = index["original_bundle_name"] + "/"
            assert all(name.startswith(prefix) for name in names)
            mapping = {member.filename[len(prefix):]: member for member in members}
            manifest_raw = archive.read(mapping["artifact_manifest.json"])
            assert digest(manifest_raw) == index["original_artifact_manifest_sha256"]
            manifest = json.loads(manifest_raw)
            assert set(mapping) == set(manifest) | {"artifact_manifest.json"}
            for name, expected in manifest.items():
                assert digest(archive.read(mapping[name])) == expected, name
            source_raw = archive.read(mapping["source_git_manifest.json"])
            assert digest(source_raw) == index["original_source_manifest_sha256"]
            sources = json.loads(source_raw)
            for label, source in sources.items():
                assert len(source["files"]) == source["count"]
                assert index["source_trees"][label]["commit"] == source["commit"]
                assert index["source_trees"][label]["count"] == source["count"]
                prefix = source["directory"] + "/"
                exported = {name[len(prefix):]: expected for name, expected in manifest.items() if name.startswith(prefix)}
                assert exported == source["files"], label
            zip_checked = True
        if git_repository is not None:
            source_counts = git_source_maps(git_repository, sources)
            git_checked = True
    else:
        assert git_repository is None, "Git mapping requires the complete original sealed source manifest"
    return {"kind": "developer_readonly_compact_archive_integrity_check",
        "copied_files_verified": len(index["copied_files"]), "compact_files_verified": len(seal),
        "reviewed_commit": index["reviewed_commit"], "original_zip_checked": zip_checked,
        "original_Git_source_maps_checked": git_checked, "source_counts": source_counts,
        "independent_report_preserved": True, "WR28_review_status": "fixed_verified_closed_at_2f5591e_audit_delivery_only",
        "phase2_accepted": False, "new_product_test_runs": 0, "cloud_calls": 0,
        "budget_changed": False, "financial_evidence": False, "final_test_enabled": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-zip", type=Path)
    parser.add_argument("--git-repository", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(original_zip=args.original_zip, git_repository=args.git_repository), ensure_ascii=False))
