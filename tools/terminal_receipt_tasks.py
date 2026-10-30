"""Default-off JSON-lines transport for the fixed native receipt collector.

Only a trusted installed Python factory may inject delivery authority, a cloud
receipt source and an already admitted bridge. stdin cannot choose those inputs.
No Registry is opened, source changed, budget granted or backtest submitted here.
"""
if __name__ == "__main__":
    from terminal_receipt_tasks import main as _canonical_main
    raise SystemExit(_canonical_main())

import argparse
import importlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.terminal_receipt_tasks import TerminalReceiptCollector
from qresearch.engineering_receipts import _json

MAX_LINE = 2 * 1024 * 1024


def main(argv=None, *, input_stream=None, output_stream=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "status"))
    parser.add_argument("--enable-dispatch", action="store_true")
    parser.add_argument("--host-factory")
    args = parser.parse_args(argv)
    collector = TerminalReceiptCollector()
    if args.enable_dispatch:
        if not args.host_factory:
            parser.error("dispatch requires an installed trusted --host-factory")
        module, separator, name = args.host_factory.partition(":")
        if not separator or not module or not name.isidentifier():
            parser.error("factory must be module:function")
        collector = getattr(importlib.import_module(module), name)()
        if type(collector) is not TerminalReceiptCollector or not collector.enabled:
            parser.error("factory must return the exact explicitly enabled collector")
    elif args.host_factory:
        parser.error("factory loading requires --enable-dispatch")
    source = sys.stdin if input_stream is None else input_stream
    output = sys.stdout if output_stream is None else output_stream
    if args.command == "status":
        output.write(json.dumps(collector.status()) + "\n")
        output.flush()
        return 0
    while True:
        line = source.readline(MAX_LINE + 1)
        if not line:
            return 0
        try:
            if not line.endswith("\n") or len(line.encode("utf-8")) > MAX_LINE:
                raise ValueError("invalid frame")
            value = collector.command(_json(line))
        except Exception:
            value = {"schema_version": 1, "type": "status", "action": "attention_required",
                     "failure_code": "invalid_message_or_receipt_state", "should_execute": False}
        output.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        output.flush()
        if len(line) > MAX_LINE:
            return 0

