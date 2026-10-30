"""Run the unmodified sealed MRE against fresh current-source copies only."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parent
SEALED = REPO.parent / "LLM审核" / "review-deb85d9-20261027" / "entry_agent"
sys.path[:0] = [str(REPO / "cloud"), str(REPO / "tools"), str(SEALED)]
# Import the changed controller before historical helpers add their sealed
# source location. Imports do not run a provider, CLI or actual ledger command.
import stage2
import minimal_new_success_without_dispatch as mre

original_files = [SEALED / name for name in (
    "minimal_new_success_without_dispatch.py", "independent_cli_gates.py",
    "independent_wr16_boundaries.py", "quick_joint_probes.py")]
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in original_files}
builds = []
original_case = mre.f.case
mre.f.SOURCE = REPO
mre.f.RUN = WORK / "independent_cases"
mre.ROOT = WORK


def fresh_case(version, tag):
    dest = original_case(version, tag)
    command = [sys.executable, "-B", str(dest / "tools/research.py"), "build"]
    result = subprocess.run(command, cwd=dest, capture_output=True,
        encoding="utf-8", text=True, env=dict(os.environ, PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1"))
    builds.append({"command": command, "cwd": str(dest), "exit_code": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise AssertionError("Isolated current-source build failed: " + result.stderr)
    return dest


mre.f.case = fresh_case
out = io.StringIO()
exit_code = 0
error = None
try:
    with contextlib.redirect_stdout(out):
        mre.main()
except BaseException as exc:
    exit_code, error = 1, repr(exc)
after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in original_files}
assert before == after, "Sealed scripts changed"
(WORK / "independent_mre.stdout").write_text(out.getvalue(), encoding="utf-8")
(WORK / "independent_isolated_builds.json").write_text(json.dumps(builds, indent=2) + "\n", encoding="utf-8")
report = {"exit_code": exit_code, "error": error, "original_MRE_scripts_raw_sha256": before,
    "reviewer_originals_unchanged": True, "source_root": str(REPO),
    "actual_synthetic_CLI_commands": len(mre.f.COMMANDS), "isolated_builds": len(builds),
    "fixture_adaptations": ["SOURCE points to the current working source", "fresh case builds deployment before freeze",
        "outputs and synthetic ledger copies redirected under .git/repair-work"],
    "actual_authoritative_ledger_writes": 0, "actual_QC_calls": 0, "independent_acceptance": False}
(WORK / "independent_mre_execution.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))
raise SystemExit(exit_code)
