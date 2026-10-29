from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
original = root.parent / "LLM审核" / "review-2d1d306-20261029" / "minimal_wr29.py"
env = dict(os.environ, TMP=str(out), TEMP=str(out), PYTHONDONTWRITEBYTECODE="1")
run = subprocess.run([sys.executable, "-B", str(original), str(root)], cwd=root, env=env,
    text=True, capture_output=True, timeout=60)
result = dict(original_sha256=sha256(original.read_bytes()).hexdigest(),
    host_sha256=sha256((root / "tools/followup_host.py").read_bytes()).hexdigest(),
    exit=run.returncode, stdout=run.stdout, stderr=run.stderr)
(out / "original-minimal-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(run.returncode)
