"""Replay original first-round inputs in new private copies, with trace capture."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
initial = out / "run-20261029T120628630572Z"
first = json.loads((initial / "results.json").read_text(encoding="utf-8"))
focus = out / datetime.now(timezone.utc).strftime("focused-%Y%m%dT%H%M%S%fZ")
focus.mkdir()
sys.path.insert(0, str(root / "cloud"))
from qresearch.artifacts import decode_events, MemoryArtifactStore

factory = out / "wr29_boundary_factory.py"
(focus / "traced_factory.py").write_bytes(factory.read_bytes())
records = []
native = dict(success=True, projects=[dict(projectId=17, name="SYNTHETIC_WR29", language="Py")], page=1, nextPage=None, totalPages=1)
for original_entry in ("canonical", "module"):
    request = json.loads(next(x["stdout"] for x in first["subprocesses"] if x["label"] == original_entry + "-wake"))
    response = dict(command="response", **{k: request[k] for k in ("attempt_id", "correlation_id", "tool_name", "arguments")},
        result=dict(structuredContent=native, content=[dict(type="text", text=json.dumps(native))], isError=False))
    text_input = json.dumps(response) + "\n" + json.dumps(dict(command="wake", attempt_id=request["attempt_id"])) + "\n"
    (focus / (original_entry + "-original-input.jsonl")).write_text(text_input, encoding="utf-8", newline="")
    source_store = initial / "stores" / (original_entry + "-restart")
    stream = "engineering/followup-host/" + request["attempt_id"] + "/events.jsonl"
    prior = decode_events((source_store / stream).read_bytes())
    assert [x["event"]["kind"] for x in prior[:2]] == ["bound", "reserved"]
    resealed = MemoryArtifactStore()
    for event in prior[:2]: resealed.append_event(stream, event["event"])
    for repeat in range(5):
        label = original_entry + "-" + str(repeat)
        private = focus / (label + "-store")
        shutil.copytree(source_store, private)
        (private / stream).write_bytes(resealed.read_bytes(stream))
        metadata = focus / (label + "-metadata.json")
        trace = focus / (label + "-exception.txt")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(out), str(root / "tools"), str(root / "cloud"))),
            PYTHONDONTWRITEBYTECODE="1", WR29_STORE=str(private), WR29_ATTEMPT=request["attempt_id"],
            WR29_METADATA=str(metadata), WR29_EXCEPTION_LOG=str(trace), WR29_CLOCK_USED=str(focus / (label + "-clock-used.txt")))
        args = [sys.executable, "-B", "-m", "followup_host", "serve", "--enable-dispatch", "--host-factory", "wr29_boundary_factory:build"]
        proc = subprocess.run(args, cwd=root, env=env, input=text_input, text=True, capture_output=True, timeout=30)
        outputs = [json.loads(line) for line in proc.stdout.splitlines()]
        passed = proc.returncode == 0 and len(outputs) == 2 and outputs[0].get("action") == "projects_observed" and outputs[1].get("tool_name") == "mcp__quantconnect__list_backtests"
        records.append(dict(label=label, passed=passed, exit=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
            stdin=text_input, trace=trace.read_text(encoding="utf-8") if trace.exists() else None))
result = dict(scope="development_support_not_formal_acceptance", host_sha256=sha256((root / "tools/followup_host.py").read_bytes()).hexdigest(),
    factory_sha256=sha256(factory.read_bytes()).hexdigest(), records=records)
(focus / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
(out / "focused-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(focus_dir=str(focus), passed=sum(x["passed"] for x in records), total=len(records), failures=[x for x in records if not x["passed"]]), ensure_ascii=False))
raise SystemExit(not all(x["passed"] for x in records))
