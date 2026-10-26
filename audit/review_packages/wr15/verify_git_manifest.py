"""Read-byte verification for an exported AQRP Git tree; no provider access."""
import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    folder = Path(root).resolve() / "audit/review_packages/wr14"
    report = json.loads((folder / "developer_verification.json").read_text(encoding="utf-8-sig"))
    raw = (folder / "developer_outputs_manifest.json").read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != report["developer_outputs_manifest_raw_sha256"]:
        raise ValueError("Declared manifest hash differs from exported Git bytes")
    manifest = json.loads(raw.decode("utf-8-sig"))
    for item in manifest["files"]:
        path = (folder / item["archive_path"]).resolve()
        if folder not in path.parents:
            raise ValueError("Output path escapes the evidence package")
        output = path.read_bytes()
        if len(output) != item["bytes"] or hashlib.sha256(output).hexdigest() != item["raw_sha256"]:
            raise ValueError("Original output hash/length differs: " + item["archive_path"])
    if len(manifest["files"]) != manifest["file_count"]:
        raise ValueError("Original output count differs")
    return {"manifest_raw_sha256": actual, "original_outputs_verified": len(manifest["files"]),
            "market_or_model_calls": 0, "financial_evidence": False}


if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1])))
