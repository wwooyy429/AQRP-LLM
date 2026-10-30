"""Recompute an archived source comparison; no platform or market access."""
import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    root = Path(root).resolve()
    ready = json.loads((root / "audit/stage2_current_readiness.json").read_text(encoding="utf-8-sig"))
    summary = ready["platform_comparison_from_independent_review"]
    documents = []
    for name in ("candidate_manifest_ref", "archived_platform_comparison_ref"):
        ref = summary[name]
        path = (root / ref["path"]).resolve()
        if root not in path.parents:
            raise ValueError("Comparison reference escapes the exported tree")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref["raw_sha256"]:
            raise ValueError("Archived reference raw bytes differ")
        documents.append(json.loads(raw.decode("utf-8-sig")))
    manifest, comparison = documents[0]["candidate"], documents[1]
    if summary["candidate_commit"] != manifest["commit"] or manifest["commit"] != comparison["reviewed_source_commit"]:
        raise ValueError("Comparison source identities differ")
    candidate = {k[len("cloud/"):]: v for k, v in manifest["files"].items()
                 if k.startswith("cloud/") and k.endswith(".py")}
    items = [item for item in comparison["files"] if item["path"] != "_engineering_task_input.py"]
    reference = {item["path"]: item["cloud_utf8_sha256"] for item in items}
    if len(reference) != len(items):
        raise ValueError("Archived known-reference paths are duplicated")
    different = sorted(k for k in candidate.keys() & reference.keys() if candidate[k] != reference[k])
    outside = sorted(candidate.keys() - reference.keys())
    expected = {"candidate_different_or_missing_paths": len(different) + len(outside),
                "candidate_known_reference_different_paths": len(different),
                "candidate_paths_not_in_reference": len(outside),
                "candidate_manifest_files": len(candidate), "known_reference_files": len(reference),
                "differing_known_reference_paths": different, "paths_not_in_known_reference": outside}
    if any(summary.get(name) != value for name, value in expected.items()):
        raise ValueError("WR-19: declared archived comparison differs from its referenced hashes")
    return {"candidate_commit": manifest["commit"], **expected,
            "scope": "Archived references only; no current cloud missing-file or inventory assertion",
            "actual_provider_or_model_calls": 0, "financial_evidence": False}


if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1])))
