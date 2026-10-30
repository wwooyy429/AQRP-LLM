from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6"
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "cloud")]
from review_metadata import SOURCE_ROOTS, SOURCE_SCOPE, PLATFORM_SCOPE, COUNTERS
from stages import source_manifest

raw = subprocess.check_output(["git", "show", BASELINE + ":audit/stage2_current_readiness.json"], cwd=ROOT)
previous = json.loads(raw)
path = ROOT / "audit/stage2_current_readiness.json"
current = json.loads(path.read_text(encoding="utf-8-sig"))
historical_names = ("source_changed_this_round", "source_configuration_budget_changed_scope",
    "read_or_polled_this_turn_scope", "completed_result_read_count", "terminal_read_scope",
    "consolidated_run_preparation", "market_calls_scope", "candidate_additions",
    "new_candidate_acceptance_scope", "latest_independent_platform_observation")
history = current.setdefault("historical_activity_descriptions", [])
if not any(item.get("recorded_at_commit") == BASELINE for item in history):
    history.append({"recorded_at_commit": BASELINE,
        "baseline_source_manifest_hash": "0467707062f8f37d4a827e10fede9dd71a24ae7fc21980be93020d06bf3e7327",
        "actual_cloud_source_commit": "7fc5ef2e9d2379d29f48d05a1f3cc760000884d6",
        "scope": "Prior current-field descriptions copied verbatim from pinned baseline; not this repair activity",
        "prior_current_fields": {key: previous[key] for key in historical_names if key in previous}})
current.pop("consolidated_run_preparation", None)
current["source_configuration_budget_changed_scope"] = SOURCE_SCOPE
current["read_or_polled_this_turn_scope"] = PLATFORM_SCOPE
current["current_activity"] = {"kind": "offline_repair", "baseline_commit": BASELINE,
    "source_roots": list(SOURCE_ROOTS), "source_suffix": ".py",
    "quantconnect_reads": 0, "quantconnect_writes": 0, "new_deployments": 0}
for key in COUNTERS:
    current[key] = 0
for key in ("source_configuration_budget_changed", "read_or_polled_this_turn", "candidate_cloud_deployed"):
    current[key] = False
current["market_calls"] = 0
current["market_calls_scope"] = "No market-data provider calls in this offline repair; prior failed-cell call counts remain unknown in their historical report."
current["terminal_read_scope"] = "No terminal result or platform read in this repair; prior reads are in the pinned historical activity object."
current["current_candidate_change_scope"] = "offline_WR25_WR26_eligibility_and_WR27_root_manifest_repair"
current["new_candidate_acceptance_scope"] = "WR25/26/27 development candidate requires independent fixed-commit review; prior WR22/23/24 scope passed only on ccad61d."
current["candidate_additions"] = ["WR25_closed_classification_semantics", "WR26_current_qualification_coverage", "WR27_same_root_manifest_binding"]
names = subprocess.check_output(["git", "diff", "--name-only", "-z", "--no-renames", BASELINE, "--", *SOURCE_ROOTS], cwd=ROOT)
names += subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z", "--", *SOURCE_ROOTS], cwd=ROOT)
current["source_changed_this_round"] = sorted({name for name in names.decode("utf-8").split("\0") if name and name.endswith(".py")})
current["candidate_source_manifest_hash"] = source_manifest()["source_hash"]
path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"metadata_current_baseline": BASELINE, "source_changed_this_round": current["source_changed_this_round"],
    "historical_records": len(history), "budget_or_ledger_written": False}))
