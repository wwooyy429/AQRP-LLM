from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
source = Path("B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ccad61d-20261027/minimal_wr25_wr26.py")
script = OUT / source.name
if not script.exists():
    shutil.copyfile(source, script)
assert script.read_bytes() == source.read_bytes()
label = sys.argv[1]
args = [sys.executable, "-B", str(script), "--source", str(ROOT), "--output", str(OUT / (label + "_result.json"))]
start = time.monotonic()
completed = subprocess.run(args, cwd=ROOT, env=dict(os.environ, PYTHONIOENCODING="utf-8",
    OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"), capture_output=True)
(OUT / (label + ".stdout")).write_bytes(completed.stdout)
(OUT / (label + ".stderr")).write_bytes(completed.stderr)
record = {"command": args, "exit_code": completed.returncode, "seconds": round(time.monotonic() - start, 3),
    "script_unchanged": True, "script_raw_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
    "production_raw_sha256": hashlib.sha256((ROOT / "cloud/qresearch/data_certification.py").read_bytes()).hexdigest(),
    "provider_calls": 0, "authoritative_budget_writes": 0, "independent_acceptance": False}
if (OUT / (label + "_result.json")).exists():
    result = json.loads((OUT / (label + "_result.json")).read_bytes())
    record["expected"] = result["expected"]
    record["actual"] = result["actual"]
(OUT / (label + "_execution.json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record))
