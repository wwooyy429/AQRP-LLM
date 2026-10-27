"""Read-only consistency check for an explicitly pinned offline repair record.

This compares local Git and metadata only. It is not an approval, a market-data
audit, or proof of unobserved external activity. It never changes the ledger.
"""
from pathlib import Path
import argparse
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("cloud", "tests", "tools")
HISTORICAL_FIELDS = ("source_changed_this_round", "source_configuration_budget_changed_scope",
                     "read_or_polled_this_turn_scope")
COUNTERS = ("new_configuration_count", "new_Research_execution_count", "new_LEAN_submission_count",
            "model_API_calls", "completed_result_read_count", "backtest_poll_count")
SOURCE_SCOPE = "Offline software and metadata repair only; zero new market configuration registrations, Research executions or LEAN submissions; budget and journal unchanged."
PLATFORM_SCOPE = "No QuantConnect reads, polling, writes or deployments in this repair; no market-data or model calls."


def validate_current(document, changed_paths, historical_document, *, baseline_commit,
                     budget_unchanged, journal_unchanged):
    if not isinstance(baseline_commit, str) or re.fullmatch(r"[a-f0-9]{40}", baseline_commit) is None:
        raise ValueError("An exact Git baseline commit is required")
    activity = document.get("current_activity")
    if not isinstance(activity, dict) or activity != {
            "kind": "offline_repair", "baseline_commit": baseline_commit,
            "source_roots": list(SOURCE_ROOTS), "source_suffix": ".py",
            "quantconnect_reads": 0, "quantconnect_writes": 0, "new_deployments": 0}:
        raise ValueError("The current offline activity and exact source scope must be declared")
    for key in COUNTERS:
        if type(document.get(key)) is not int or document[key] != 0:
            raise ValueError("Current offline counters must be explicit zero integers")
    if any(type(activity[key]) is not int for key in ("quantconnect_reads", "quantconnect_writes", "new_deployments")):
        raise ValueError("Activity counters must not use boolean aliases")
    if (document.get("source_configuration_budget_changed") is not False
            or document.get("read_or_polled_this_turn") is not False
            or document.get("candidate_cloud_deployed") is not False):
        raise ValueError("Current offline state conflicts with budget or platform flags")
    if (document.get("source_configuration_budget_changed_scope") != SOURCE_SCOPE
            or document.get("read_or_polled_this_turn_scope") != PLATFORM_SCOPE):
        raise ValueError("Current activity text contains a stale or contradictory scope")
    expected = sorted(set(changed_paths))
    if any(not isinstance(path, str) or path.split("/", 1)[0] not in SOURCE_ROOTS or not path.endswith(".py") for path in expected):
        raise ValueError("Changed-source paths are outside the explicitly declared scope")
    if document.get("source_changed_this_round") != expected:
        raise ValueError("Current source list differs from the pinned Git change set")
    history = document.get("historical_activity_descriptions")
    if not isinstance(history, list) or not any(isinstance(item, dict)
            and item.get("recorded_at_commit") == baseline_commit
            and item.get("actual_cloud_source_commit") == "7fc5ef2e9d2379d29f48d05a1f3cc760000884d6"
            and isinstance(item.get("prior_current_fields"), dict)
            and all(key in item["prior_current_fields"] and item["prior_current_fields"][key] == historical_document[key]
                    for key in HISTORICAL_FIELDS) for item in history):
        raise ValueError("Prior activity descriptions must be preserved with their exact source identities")
    if budget_unchanged is not True or journal_unchanged is not True:
        raise ValueError("Offline metadata cannot claim an unchanged budget or journal when bytes differ")
    return {"status": "metadata_consistent", "baseline_commit": baseline_commit,
            "changed_source_files": len(expected), "budget_and_journal_raw_unchanged": True,
            "external_activity_authenticated": False, "independent_acceptance": False,
            "financial_evidence": False}


def check_repository(root):
    root = Path(root).resolve()
    document = json.loads((root / "audit/stage2_current_readiness.json").read_text(encoding="utf-8-sig"))
    baseline = document.get("current_activity", {}).get("baseline_commit")
    if not isinstance(baseline, str) or re.fullmatch(r"[a-f0-9]{40}", baseline) is None:
        raise ValueError("Missing exact baseline; no remote fetching is performed")

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    previous = json.loads(git("show", baseline + ":audit/stage2_current_readiness.json"))
    names = git("diff", "--name-only", "-z", "--no-renames", baseline, "--", *SOURCE_ROOTS)
    names += git("ls-files", "--others", "--exclude-standard", "-z", "--", *SOURCE_ROOTS)
    changed = {name for name in names.decode("utf-8").split("\0") if name and name.endswith(".py")}
    result = validate_current(document, changed, previous, baseline_commit=baseline,
        budget_unchanged=(root / "config/budget.json").read_bytes() == git("show", baseline + ":config/budget.json"),
        journal_unchanged=(root / "audit/runtime/registry/events.jsonl").read_bytes() == git("show", baseline + ":audit/runtime/registry/events.jsonl"))
    from stages import source_manifest
    if document.get("candidate_source_manifest_hash") != source_manifest()["source_hash"]:
        raise ValueError("Current metadata does not identify the actual local source manifest")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(check_repository(args.root), ensure_ascii=True))
