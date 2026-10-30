"""Trusted operator: append a user-authorized engineering round to the registry.

No market data, Research execution, backtest submission, budget increase or final
test access occurs here. Check the actual human instruction before authorizing;
a content hash is not proof that the instruction came from a human.
"""
import argparse
import json
from pathlib import Path

from research import open_registry, read_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    authorize = sub.add_parser("authorize")
    authorize.add_argument("--grant-file", type=Path, required=True)
    authorize.add_argument("--authorization-file", type=Path, required=True)
    authorize.add_argument("--package-file", type=Path, action="append", required=True)
    bind = sub.add_parser("bind")
    bind.add_argument("--round-id", required=True)
    bind.add_argument("--package-file", type=Path, required=True)
    close = sub.add_parser("close")
    close.add_argument("--round-id", required=True)
    close.add_argument("--reason", required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    registry = open_registry()
    if args.command == "authorize":
        result = registry.authorize_engineering_round(read_json(args.grant_file),
            [read_json(path) for path in args.package_file], read_json(args.authorization_file))
    elif args.command == "bind":
        result = {"configuration_id": registry.bind_engineering_configuration(
            args.round_id, read_json(args.package_file))}
    elif args.command == "close":
        result = registry.close_engineering_round(args.round_id, args.reason)
    else:
        result = {"engineering_rounds": registry.engineering_rounds_snapshot(),
                  "registry": registry.snapshot()}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
