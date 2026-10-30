from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
source = OUT / "fixed_source"
target = OUT / "fixed_mre/alternate_root"
caller = OUT / "fixed_mre/caller"
caller.mkdir(exist_ok=True)
gitdir = subprocess.check_output(["git", "rev-parse", "--absolute-git-dir"], cwd=ROOT, text=True).strip()
actual_index = Path(gitdir) / "index"
before_index = hashlib.sha256(actual_index.read_bytes()).hexdigest()
meta_path = target / "audit/stage2_current_readiness.json"
own_raw = meta_path.read_bytes()
own_meta = json.loads(own_raw)
foreign_hash = json.loads((source / "audit/stage2_current_readiness.json").read_bytes())["candidate_source_manifest_hash"]
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
    OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", GIT_OPTIONAL_LOCKS="0",
    GIT_DIR=gitdir, GIT_WORK_TREE=str(target), GIT_INDEX_FILE=str(OUT / "fixed_mre/fixed_source.index"))
observations = []
for label in ("relative_target_correct", "relative_target_foreign_hash", "default_tool_from_foreign_cwd"):
    try:
        if label == "relative_target_foreign_hash":
            value = dict(own_meta); value["candidate_source_manifest_hash"] = foreign_hash
            meta_path.write_text(json.dumps(value) + "\n", encoding="utf-8", newline="\n")
        args = [sys.executable, "-B", str(source / "tools/review_metadata.py")]
        if label != "default_tool_from_foreign_cwd":
            args += ["--root", os.path.relpath(target, caller)]
        case_env = dict(env, GIT_WORK_TREE=str(source)) if label.startswith("default_") else env
        result = subprocess.run(args, cwd=caller, env=case_env, capture_output=True)
        (OUT / (label + ".stdout")).write_bytes(result.stdout)
        (OUT / (label + ".stderr")).write_bytes(result.stderr)
        observations.append({"case": label, "command": args, "cwd": str(caller), "exit_code": result.returncode,
            "expected_exit": 1 if label == "relative_target_foreign_hash" else 0})
        assert result.returncode == observations[-1]["expected_exit"], label
    finally:
        meta_path.write_bytes(own_raw)
assert hashlib.sha256(actual_index.read_bytes()).hexdigest() == before_index
report = {"kind": "developer_relative_root_actual_CLI_probe", "cases": observations,
    "actual_CLI_processes": len(observations), "actual_repository_index_unchanged": True,
    "isolated_target_metadata_restored": meta_path.read_bytes() == own_raw,
    "new_QC_or_market_calls": 0, "new_authoritative_budget_writes": 0,
    "independent_acceptance": False, "financial_evidence": False}
(OUT / "relative_cli_execution.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
print(json.dumps({"CLI_cases": [(x["case"], x["exit_code"]) for x in observations], "actual_repository_index_unchanged": True}))
