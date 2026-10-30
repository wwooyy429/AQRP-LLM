from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "wr24"
out = OUT / "archive_agent"
out.mkdir(parents=True, exist_ok=True)
original = Path("B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ea6053e-20261027/archive_agent/minimal_wr24_metadata.py")
script = out / original.name
shutil.copyfile(original, script)
baseline = "ea6053e3e9ef4be17db246daf18a4cf9b2e5be58"
for name in ("audit/stage2_current_readiness.json", "audit/runtime/registry/events.jsonl"):
    path = OUT / "source" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(subprocess.check_output(["git", "show", baseline + ":" + name], cwd=ROOT))
r = subprocess.run([sys.executable, "-B", str(script)], cwd=ROOT,
    env=dict(os.environ, PYTHONIOENCODING="utf-8"), capture_output=True)
(OUT / "baseline.stdout").write_bytes(r.stdout)
(OUT / "baseline.stderr").write_bytes(r.stderr)
report = {"command": [sys.executable, "-B", str(script)], "exit_code": r.returncode,
    "original_script_raw_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
    "original_script_unchanged": script.read_bytes() == original.read_bytes(),
    "source_commit": baseline, "source_copy": "only two immutable metadata files required by this MRE",
    "old_review_Git_path_is_used_read_only": True, "new_platform_calls": 0,
    "real_ledger_or_budget_writes": 0, "independent_acceptance": False}
if r.stdout:
    try:
        result = json.loads(r.stdout)
        report["observed_checks"] = result["checks"]
    except (ValueError, KeyError):
        report["output_parse_failed"] = True
(OUT / "baseline_execution.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))
assert r.returncode == 1 and report.get("observed_checks") == {
    "current_new_config_and_Research_scope": False,
    "current_source_changed_this_round_matches_pinned_diff": False}
