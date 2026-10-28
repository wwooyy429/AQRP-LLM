"""Write the fixed-commit raw-blob audit manifest; no Registry or cloud access."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from git_protection import build_manifest, ProtectionError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    try:
        value = build_manifest(args.repository, (package / "protected_before.json").read_bytes())
        encoded = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        # The root agent chooses the sole authoritative output path. Existing
        # files must be byte-identical; this helper never overwrites evidence.
        if args.output.exists():
            if args.output.read_bytes() != encoded:
                raise ProtectionError("Git raw-byte protection output conflicts")
        else:
            with args.output.open("xb") as handle:
                handle.write(encoded)
    except (OSError, ProtectionError):
        raise SystemExit("Git raw-byte protection manifest build failed") from None
    print(json.dumps({"kind": value["kind"], "protected_file_count": value["protected_file_count"],
                      "cloud_calls": 0, "registry_writes": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
