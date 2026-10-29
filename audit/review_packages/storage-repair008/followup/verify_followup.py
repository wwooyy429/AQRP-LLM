"""Offline metadata reconciliation only; no platform/provider calls or tests.

The manifest must be pinned externally to the immutable delivery Git commit.
Internal hash consistency is neither a remote signature nor independent review.
Use --seal only after updating the permitted audit packet, then verify normally.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]

from research import open_registry
from collection_task_cli import execution_source_manifest

RUNTIME = "b1a4041ce98867047294b8f0830292af5d7ec56e"
BASE = "40d1b7572214d516075ac5ac06afe311f92f2558"
ATTEMPT = "a03a7c7611fb496aaf5487ca8974b0d2"
BACKTEST = "8a45b6c62d55521033e9cc5b9b9d3950"
USAGE = {"configurations": 16, "research": 17, "lean": 3}


def read(path):
    return json.loads(path.read_bytes())


def git_bytes(revision, name):
    return subprocess.check_output(["git", "show", revision + ":" + name], cwd=ROOT)


def digest(path):
    if path.relative_to(ROOT).as_posix() == "audit/data_exposure.json":
        # Existing original checkout is CRLF, whereas its protected Git blob
        # is LF. This one declared text policy preserves every terminal LF;
        # no fact, JSON token or whitespace other than newline encoding changes.
        return hashlib.sha256(path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required_files():
    files = {path for path in PACKET.rglob("*") if path.is_file()
             and path != HERE / "review_packet_manifest.json" and "__pycache__" not in path.parts
             and not path.name.endswith(".baiduyun.uploading.cfg")}
    for name in ("README.md", "AGENTS.md", "audit/stage2_current_readiness.json",
                 "audit/stage2_storage_repair008_report.json", "audit/data_exposure.json",
                 "config/budget.json", "audit/runtime/registry/baseline.json",
                 "audit/runtime/registry/events.jsonl",
                 "audit/review_packages/storage-repair006/cloud_write_rejection.json",
                 "audit/review_packages/storage-repair007/cloud_write_rejection.json"):
        files.add(ROOT / name)
    for path in files:
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Audit packet path leaves this repository")
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(files)}


def verify(seal=False):
    registry = open_registry()
    snapshot = registry.snapshot()
    usage = {name: value["total"] for name, value in snapshot["usage"].items()}
    assert usage == USAGE, "No new configuration, Research, LEAN charge or refund allowed"
    cycle = registry.configuration_cycle_snapshot()
    assert cycle["usage"]["total"] == 3 and cycle["capacity"]["total"] == 13
    assert cycle["remaining"]["total"] == 10 and cycle["lifetime_usage"]["total"] == 16
    for name in ("config/budget.json", "audit/runtime/registry/baseline.json"):
        assert (ROOT / name).read_bytes() == git_bytes(BASE, name), name
    assert (ROOT / "audit/data_exposure.json").read_text(encoding="utf-8-sig").encode("utf-8") == git_bytes(BASE, "audit/data_exposure.json")
    journal = (ROOT / "audit/runtime/registry/events.jsonl").read_bytes()
    previous = git_bytes(BASE, "audit/runtime/registry/events.jsonl")
    assert journal.startswith(previous), "Original69 events must remain exact"
    record = next(item for item in snapshot["attempts"] if item["attempt_id"] == ATTEMPT)
    assert record["external_id"] == BACKTEST and record["stage"] == "lean"
    readiness = read(ROOT / "audit/stage2_current_readiness.json")
    assert readiness["latest_backtest_id"] == BACKTEST
    assert readiness["current_LEAN_attempt"] == ATTEMPT
    assert readiness["current_LEAN_ledger_status"] == record["status"]
    assert readiness["global_usage"] == USAGE
    assert readiness["new_configuration_capacity_remaining"] == 10
    assert readiness["configuration_reset_authorization"]["current_configuration_usage"] == 3
    assert readiness["configuration_reset_authorization"]["lifetime_configuration_usage"] == 16
    assert readiness["latest_runtime_round_LEAN_submissions"] == 1
    assert readiness["candidate_runtime_source_commit"] == RUNTIME
    assert readiness["managed_cloud_files_verified"] == 43
    assert readiness["candidate_independent_acceptance"] is False
    assert readiness["stage2_accepted"] is False and readiness["financial_evidence"] is False
    assert all(value is False for value in readiness["execution_gates"].values())
    if record["status"] == "pending":
        assert journal == previous, "Pending-only follow-up cannot append settlement events"
        assert readiness["pending_backtest_id"] == BACKTEST
        assert readiness["current_LEAN_platform_status"] == "submitted_terminal_not_delivered"
        assert readiness["cloud_runtime_joint_gate_passed"] is False
    assert (HERE / "previous_readiness.snapshot.json").read_bytes() == git_bytes(BASE, "audit/stage2_current_readiness.json")
    frozen = read(PACKET / "plan_preview.json")
    assert execution_source_manifest()["source_hash"] == frozen["source_manifest_hash"]
    assert readiness["candidate_execution_source_manifest_hash"] == frozen["source_manifest_hash"]
    assert readiness["candidate_deployment_hash"] == frozen["deployment_hash"]
    changes = subprocess.check_output(["git", "diff", "--name-only", RUNTIME, "--",
        "cloud", "tools", "tests", "docs", "templates", "config"], cwd=ROOT).decode().splitlines()
    assert set(changes) <= {"config/budget.json"}, "Frozen implementation cannot change in this follow-up"
    files = required_files()
    manifest_path = HERE / "review_packet_manifest.json"
    manifest = {"schema_version": 1, "runtime_source_commit": RUNTIME,
                "prior_delivery_commit": BASE, "scope": "Readable source references and permitted engineering audit metadata only",
                "trust_boundary": "Pin this manifest externally to the immutable delivery Git commit; not a remote signature or independent acceptance",
                "default_file_hash_policy": "raw-byte SHA256",
                "file_hash_policy_overrides": {"audit/data_exposure.json": "UTF8-sig decode, universal-newline LF, preserving terminal LF count; exact prior Git blob identity. Original physical before/after hash separately recorded."},
                "excluded_transient_metadata": ["__pycache__", "*.baiduyun.uploading.cfg"],
                "files": files}
    if seal:
        manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    assert read(manifest_path) == manifest, "Packet bytes changed; retain old Git record and deliberately reseal new metadata"
    return {"metadata_consistent": True, "runtime_source_commit": RUNTIME,
            "same_attempt_status": record["status"], "usage": usage,
            "journal_events": len(journal.splitlines()), "packet_files": len(files),
            "remote_calls": 0, "new_executions": 0, "independent_acceptance": False,
            "financial_evidence": False, "final_test_enabled": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal", action="store_true")
    print(json.dumps(verify(parser.parse_args().seal), ensure_ascii=False))
