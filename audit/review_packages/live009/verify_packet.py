"""Offline evidence integrity only; no provider, dispatch or acceptance."""
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
            raise ValueError("Packet source or evidence differs")
    journal = (ROOT / "audit/runtime/registry/events.jsonl").read_bytes()
    prefix = b"\n".join(journal.splitlines()[:71]) + b"\n"
    if sha256(prefix).hexdigest() != "cea800e0fe5a0facc5f2aed238d105a6f3d1c80db40c1dc4b674efd3026cd48a":
        raise ValueError("Prior registry prefix differs")
    result = {"packet_hashes_verified": len(manifest["files"]), "original_71_events_preserved": True,
              "cloud_calls": 0, "execution_debits": 0, "independent_acceptance": False,
              "stage2_accepted": False, "financial_evidence": False, "final_test_enabled": False}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
