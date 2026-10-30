import hashlib
import io
import json
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
modules = ["test_engineering_receipts", "test_native_research_failure", "test_research_error_representations",
    "test_wr17_engineering_recovery", "test_native_backtest_rejection", "test_native_runtime_failure",
    "test_wr21_research_dispatch"]
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
(WORK / "compatibility.stderr").write_text(stream.getvalue(), encoding="utf-8")
r = {"modules": modules, "methods": result.testsRun, "failure_records": len(result.failures),
    "error_records": len(result.errors), "skipped": len(result.skipped), "exit_code": 0 if result.wasSuccessful() else 1,
    "purely_synthetic": True, "actual_QC_calls": 0, "authoritative_ledger_writes": 0,
    "production_source_hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
        for p in ["tools/stage2.py", "cloud/qresearch/engineering_receipts.py"]}}
(WORK / "compatibility_execution.json").write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
print(json.dumps(r))
print(stream.getvalue()[-5000:])
raise SystemExit(r["exit_code"])
