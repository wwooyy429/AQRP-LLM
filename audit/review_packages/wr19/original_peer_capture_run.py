from pathlib import Path
import json
import os
import subprocess
import sys
import time

folder = Path(__file__).resolve().parent
mode = sys.argv[1]
command = [sys.executable, "-B", str(folder / "check_comparison.py"), mode]
start = time.monotonic()
result = subprocess.run(command, cwd=folder.parents[2],
                        env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1"),
                        capture_output=True)
(folder / (mode + ".stdout")).write_bytes(result.stdout)
(folder / (mode + ".stderr")).write_bytes(result.stderr)
record = {"command": command, "cwd": str(folder.parents[2]), "exit_code": result.returncode,
          "seconds": time.monotonic() - start,
          "expected_exit_code": 1 if mode == "before" else 0,
          "actual_provider_or_model_calls": 0,
          "raw_outputs_captured": True}
(folder / (mode + "_execution.json")).write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
print(json.dumps(record))
sys.exit(result.returncode)
