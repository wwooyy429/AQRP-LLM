"""Read-only fixed packet integrity; no acceptance or provider execution."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKET = Path(__file__).resolve().parent


def identity_digest(raw, policy):
    if policy == "utf8_sig_universal_newlines":
        raw = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    elif policy != "raw_bytes":
        raise ValueError("Unknown fixed identity policy")
    return sha256(raw).hexdigest()


def main():
    manifest = json.loads((PACKET / "packet_manifest.json").read_bytes())
    sources = json.loads((PACKET / "full_offline_validation_v3/source_overlay_identity.json").read_bytes())["source_files"]
    for item in manifest["files"]:
        path = (ROOT / item["path"]).resolve()
        expected_policy = "utf8_sig_universal_newlines" if item["path"] in sources else "raw_bytes"
        if item["identity_policy"] != expected_policy or item["path"] in sources and item["sha256"] != sources[item["path"]]:
            raise ValueError("Source and original-evidence identity policies differ")
        if not path.is_relative_to(ROOT) or identity_digest(path.read_bytes(), item["identity_policy"]) != item["sha256"]:
            raise ValueError("Fixed packet identity differs")
    journal = (ROOT / "audit/runtime/registry/events.jsonl").read_bytes()
    if sha256(journal).hexdigest() != "5fa2c6fb5b94b7c76cb6b7458be3daec01c444057af0426a4aea9d2051f33e87" or len(journal.splitlines()) != 78:
        raise ValueError("Authoritative Registry changed")
    result = {"packet_files_verified": len(manifest["files"]), "registry_events": 78,
              "budget_mutations": 0, "cloud_calls": 0, "independent_acceptance": False,
              "stage2_accepted": False, "financial_evidence": False, "final_test_enabled": False}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
