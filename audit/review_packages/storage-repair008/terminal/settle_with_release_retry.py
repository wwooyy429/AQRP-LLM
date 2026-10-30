"""One local metadata settlement with bounded Win32 lock-release backoff.

This operator wrapper invokes the existing fixed stage2.py unchanged. It adds
retry only to Path.unlink for this exact Registry transaction lock, only for
WinError32, and only while its complete owner bytes remain identical. No parser,
metric, plan, source identity, budget check or completion value is overridden.
No cloud/provider call, task claim, submission or source/configuration write is
performed. Reconcile any already-orphaned lock owner before invoking this file.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LOCK = (ROOT / "audit/runtime/.locks/7a92016ed6ba0dd4adfb44d68c28ab65ae446049076f24d5260d2a27b1111ab6.lock").resolve()
ORIGINAL_UNLINK = Path.unlink
OBSERVATIONS = []
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
from collection_task_cli import execution_source_manifest
from qresearch.artifacts import canonical_json

EXPECTED_SOURCE = "60a42c12d0d195d7dc924e4520710c00ad960a92c606042e236d157be806c338"


def release_with_backoff(path, missing_ok=False):
    if path.resolve() != LOCK:
        return ORIGINAL_UNLINK(path, missing_ok=missing_ok)
    owner_bytes = path.read_bytes() if path.exists() else None
    if owner_bytes is None:
        raise RuntimeError("Registry lock owner is unavailable during release")
    owner = json.loads(owner_bytes)
    if (type(owner) is not dict or set(owner) != {"owner_token", "process_id", "key"}
            or type(owner["process_id"]) is not int or owner["process_id"] != os.getpid()
            or owner["key"] != "registry/transaction"
            or type(owner["owner_token"]) is not str
            or re.fullmatch("[0-9a-f]{32}", owner["owner_token"]) is None
            or canonical_json(owner) != owner_bytes):
        raise RuntimeError("Registry lock is not owned by this settling process")
    for number in range(121):
        if not path.exists() or path.read_bytes() != owner_bytes:
            raise RuntimeError("Registry lock ownership changed during release backoff")
        try:
            return ORIGINAL_UNLINK(path, missing_ok=missing_ok)
        except PermissionError as exc:
            if sys.platform != "win32" or exc.winerror != 32 or number == 120:
                raise
            OBSERVATIONS.append({"operation": "release_registry_transaction_lock",
                "winerror": 32, "retry_number": number + 1,
                "owner_bytes_sha256": hashlib.sha256(owner_bytes).hexdigest()})
            time.sleep(0.05)


if __name__ == "__main__":
    operation = sys.argv[1] if len(sys.argv) == 2 else "settle"
    if operation not in {"settle", "close-round"}:
        raise ValueError("Only this existing attempt's settlement or round closure is allowed")
    assert execution_source_manifest()["source_hash"] == EXPECTED_SOURCE
    budget_before = (ROOT / "config/budget.json").read_bytes()
    journal_before = (ROOT / "audit/runtime/registry/events.jsonl").read_bytes()
    Path.unlink = release_with_backoff
    original_argv = sys.argv
    if operation == "settle":
        entry = ROOT / "tools/stage2.py"
        sys.argv = [str(entry), "backtest-result", "--attempt",
            "a03a7c7611fb496aaf5487ca8974b0d2", "--tool-file",
            str(HERE / "backtest_terminal_observation.json"), "--logs-file",
            str(HERE / "backtest_logs_observations.json")]
    else:
        entry = ROOT / "tools/engineering_round.py"
        sys.argv = [str(entry), "close", "--round-id", "stage2-storage-repair-round-008",
            "--reason", "Same-plan native Research13/13 and LEAN7/7 completed with zero orders; historical terminal reconciled, bounded1/1/1 round complete with no retries or new submissions."]
    outcome = "failed"
    try:
        runpy.run_path(str(entry), run_name="__main__")
        outcome = "returned_successfully"
    finally:
        Path.unlink = ORIGINAL_UNLINK
        sys.argv = original_argv
        source_unchanged = execution_source_manifest()["source_hash"] == EXPECTED_SOURCE
        budget_unchanged = (ROOT / "config/budget.json").read_bytes() == budget_before
        journal_after = (ROOT / "audit/runtime/registry/events.jsonl").read_bytes()
        report = {"kind": "local_metadata_lock_release_backoff_observation",
            "fixed_entry": "tools/stage2.py backtest-result" if operation == "settle" else "tools/engineering_round.py close",
            "same_attempt": "a03a7c7611fb496aaf5487ca8974b0d2",
            "outcome": outcome, "backoff_observations": OBSERVATIONS,
            "parser_or_budget_checks_overridden": False,
            "product_source_modified": not source_unchanged,
            "budget_raw_bytes_unchanged": budget_unchanged,
            "journal_original_prefix_preserved": journal_after.startswith(journal_before),
            "journal_events_before": len(journal_before.splitlines()),
            "journal_events_after": len(journal_after.splitlines()), "cloud_calls": 0,
            "new_executions": 0, "final_test_enabled": False}
        report_name = "local_release_backoff.json" if operation == "settle" else "local_release_backoff_close.json"
        (HERE / report_name).write_bytes(
            (json.dumps(report, indent=2) + "\n").encode("utf-8"))
        assert source_unchanged and budget_unchanged and journal_after.startswith(journal_before)
