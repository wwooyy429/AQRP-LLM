"""Read-only fixed packet integrity; no acceptance or provider execution."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKET = Path(__file__).resolve().parent


def main():
    manifest = json.loads((PACKET / "packet_manifest.json").read_bytes())
    for item in manifest["files"]:
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or sha256(path.read_bytes()).hexdigest() != item["sha256"]:
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
