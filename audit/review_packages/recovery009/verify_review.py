"""Read-only verification of the recovery009 fixed-source review handoff.

Requires an actual Git checkout. It never opens a Registry or calls a provider.
This verifies identity and recorded invariants, not independent acceptance.
"""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
from stages import source_manifest


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def blob(commit, name):
    return subprocess.check_output(["git", "show", commit + ":" + name], cwd=ROOT)


def check(condition, label):
    if not condition:
        raise ValueError(label)


def main():
    package = read("audit/current_review_package.json")
    check(package["kind"] == "recovery009_fixed_source_software_review", "Wrong review package")
    source = package["source_commit"]
    check(len(source) == 40 and all(c in "0123456789abcdef" for c in source), "Unfixed source")
    manifest = source_manifest(ROOT)
    check(manifest["source_hash"] == package["source_manifest_hash"], "Current source identity differs")
    for name, expected in manifest["source_files"].items():
        # Source-manifest representation is explicitly universal-newline UTF-8;
        # exact Git delivery bytes are separately checked by the packet below.
        text = blob(source, name).decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        check(sha256(text.encode()).hexdigest() == expected, "Fixed source blob differs: " + name)
    report = read(package["test_report"])
    check(report["passed"] is True and report["source_manifest_hash"] == manifest["source_hash"], "Offline report mismatch")
    check(report["new_cloud_calls"] == 0 and report["new_budget_events"] == 0, "Execution policy mismatch")
    protection = read(package["protection_record"])
    for name, evidence in protection["files"].items():
        original = blob(protection["prior_commit"], name)
        current = blob(source, name)
        check(original == current, "Protected Git bytes changed: " + name)
        check(sha256(original).hexdigest() == evidence["prior_git_sha256"], "Protected hash mismatch: " + name)
        local = (ROOT / name).read_bytes()
        if name in {"audit/data_exposure.json", "config/research.json", "config/data.json"}:
            # Existing Windows worktree files have CRLF while Git is LF.
            # These disclosed representations are never called raw equality.
            check(local == current or sha256(local).hexdigest() == evidence["worktree_raw_sha256"], "Unrecorded protected worktree representation")
            check(json.loads(local) == json.loads(current), "Protected facts changed: " + name)
        else:
            check(local == current, "Protected local bytes differ: " + name)
    journal = (ROOT / "audit/runtime/registry/events.jsonl").read_bytes()
    check(len(journal.splitlines()) == 71, "Unexpected journal count")
    budget = read("config/budget.json")
    check(budget["configuration_cycle"]["usage"]["total"] == 3, "Configuration cycle usage changed")
    check(budget["usage"]["configuration_budget_charges"] == 16
          and budget["usage"]["research_execution_attempts"] == 17
          and budget["usage"]["lean_submission_attempts"] == 3, "Budget usage changed")
    packet = read(package["packet_manifest"])
    for name, expected in packet["raw_files"].items():
        check(sha256((ROOT / name).read_bytes()).hexdigest() == expected, "Packet raw bytes differ: " + name)
    for name in packet["raw_files"]:
        check(not name.endswith(".baiduyun.uploading.cfg") and "__pycache__" not in name, "Transient file in packet")
    check(package["historical_runtime_source_commit"] == "b1a4041ce98867047294b8f0830292af5d7ec56e", "Historical runtime identity changed")
    check(package["historical_terminal_materials_commit"] == protection["prior_commit"], "Historical terminal identity changed")
    check(package["independent_review_status"] == "pending"
          and package["stage2_accepted"] is False and package["final_test_enabled"] is False
          and package["financial_evidence"] is False, "Unjustified acceptance")
    print(json.dumps({"source_commit": source, "source_hash": manifest["source_hash"],
        "source_files": len(manifest["source_files"]), "packet_files": len(packet["raw_files"]),
        "protected_git_bytes_unchanged": True, "journal_events": 71,
        "configuration_cycle": "3/13", "lifetime_configurations": 16, "research": "17/20", "lean": "3/16",
        "identity_and_recorded_invariants_passed": True, "independent_acceptance": False,
        "new_cloud_calls": 0, "final_test_enabled": False}))


if __name__ == "__main__":
    main()
