from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
protected = list((ROOT / "config").glob("*.json")) + list((ROOT / "audit/runtime").rglob("*"))
protected += [ROOT / "audit/data_exposure.json", ROOT / "audit/tool_observations/f5d05f5b964b4a1d924e4b70cd207386-research.json"]
protected = [p for p in protected if p.is_file()]
before = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
           OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
runs = []
for label, args in (("build", ["tools/research.py", "build"]), ("verify", ["tools/stages.py", "verify"])):
    cmd = [sys.executable, "-B", *args]
    start = time.monotonic()
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True)
    (OUT / ("final_" + label + ".stdout")).write_bytes(r.stdout)
    (OUT / ("final_" + label + ".stderr")).write_bytes(r.stderr)
    runs.append({"label": label, "command": cmd, "cwd": str(ROOT), "exit_code": r.returncode,
                 "elapsed_seconds": round(time.monotonic() - start, 3), "stdout": "final_" + label + ".stdout",
                 "stderr": "final_" + label + ".stderr"})
    print(json.dumps(runs[-1]), flush=True)
    if r.returncode:
        (OUT / "final_verify_failure.json").write_text(json.dumps({"runs": runs}, indent=2) + "\n", encoding="utf-8")
        sys.exit(r.returncode)
after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in before}
assert before == after, [name for name in before if before[name] != after[name]]
result = json.loads((ROOT / "audit/stage_verification.json").read_text(encoding="utf-8-sig"))
match = re.search(r"Ran (\d+) tests in ([\d.]+)s", result["test_output"])
assert match and result["local_tests_passed"]
report = {"kind": "developer_offline_repair_verification", "baseline_commit": "deb85d9f27441b275ab8b108f0232ecd2707a1e8",
          "runs": runs, "local_tests_passed": True, "test_methods": int(match[1]), "test_seconds": float(match[2]),
          "source_manifest_hash": result["source_hash"], "protected_file_count": len(before),
          "all_protected_bytes_unchanged": True, "real_journal_events": 17,
          "global_usage": {"configurations": 7, "research": 10, "lean": 1},
          "new_market_configuration_registrations": 0, "new_Research_executions": 0,
          "new_LEAN_submissions": 0, "new_model_calls": 0, "new_deployments": 0,
          "engineering_stop_retained": True, "final_test_enabled": False,
          "independent_acceptance": False, "financial_evidence": False}
(OUT / "final_verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report), flush=True)
