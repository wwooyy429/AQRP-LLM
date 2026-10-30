"""Replay the original response after a captured private-store append refusal."""
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
run = out / "run-20261029T121029989473Z"
results = json.loads((run / "results.json").read_text(encoding="utf-8"))
record = next(x for x in results["subprocesses"] if x["label"] == "module-late-original")
assert "PermissionError" in record["exception_trace"] and 'path.open("ab")' in record["exception_trace"]
request = json.loads(next(x["stdout"] for x in results["subprocesses"] if x["label"] == "module-wake"))
store = run / "stores" / "module-restart"
sys.path.insert(0, str(root / "cloud"))
from qresearch.artifacts import decode_events
stream = store / "engineering" / "followup-host" / request["attempt_id"] / "events.jsonl"
before_events = [x["event"] for x in decode_events(stream.read_bytes())]
assert [x["kind"] for x in before_events] == ["bound", "reserved"]
journal = store / "registry" / "events.jsonl"
before_journal = sha256(journal.read_bytes()).hexdigest()
native = dict(success=True, projects=[dict(projectId=17, name="SYNTHETIC_WR29", language="Py")], page=1, nextPage=None, totalPages=1)
response = dict(command="response", **{k: request[k] for k in ("attempt_id", "correlation_id", "tool_name", "arguments")},
    result=dict(structuredContent=native, content=[dict(type="text", text=json.dumps(native))], isError=False))
commands = dict(
    canonical=[sys.executable, "-B", "-c", "import followup_host; raise SystemExit(followup_host.main())"],
    script=[sys.executable, "-B", str(root / "tools" / "followup_host.py")],
    module=[sys.executable, "-B", "-m", "followup_host"])
records = []
checks = []
for label, entry in commands.items():
    payload = [response, dict(command="wake", attempt_id=request["attempt_id"])] if label == "canonical" else [response, dict(command="wake", attempt_id=request["attempt_id"])]
    stdin = "".join(json.dumps(x) + "\n" for x in payload)
    (out / ("io-recovery-" + label + "-input.jsonl")).write_text(stdin, encoding="utf-8", newline="")
    trace = out / ("io-recovery-" + label + "-exception.txt")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(out), str(root / "tools"), str(root / "cloud"))),
        PYTHONDONTWRITEBYTECODE="1", WR29_STORE=str(store), WR29_ATTEMPT=request["attempt_id"],
        WR29_METADATA=str(out / ("io-recovery-" + label + "-metadata.json")), WR29_EXCEPTION_LOG=str(trace),
        WR29_CLOCK_USED=str(out / ("io-recovery-" + label + "-clock-used.txt")))
    proc = subprocess.run(entry + ["serve", "--enable-dispatch", "--host-factory", "wr29_boundary_factory:build"],
        cwd=root, env=env, input=stdin, text=True, capture_output=True, timeout=30)
    outputs = [json.loads(line) for line in proc.stdout.splitlines()]
    record = dict(entry=label, exit=proc.returncode, stdin=stdin, stdout=proc.stdout, stderr=proc.stderr,
        trace=trace.read_text(encoding="utf-8") if trace.exists() else None)
    records.append(record)
    checks.append(dict(label=label + " original response accepted idempotently", passed=proc.returncode == 0 and len(outputs) == 2 and outputs[0].get("action") == "projects_observed"))
    checks.append(dict(label=label + " next wake dispatches once or refuses unknown replay", passed=(outputs[1].get("tool_name") == "mcp__quantconnect__list_backtests") if label == "canonical" else outputs[1].get("failure_code") == "reserved_response_unknown"))
after_events = [x["event"] for x in decode_events(stream.read_bytes())]
checks.append(dict(label="no discovery redispatch; exactly one history reservation", passed=[x["tool_name"] for x in after_events if x["kind"] == "reserved"] == ["mcp__quantconnect__list_projects", "mcp__quantconnect__list_backtests"]))
checks.append(dict(label="private registry journal unchanged", passed=before_journal == sha256(journal.read_bytes()).hexdigest()))
result = dict(scope="development_support_not_formal_acceptance", host_sha256=sha256((root / "tools/followup_host.py").read_bytes()).hexdigest(),
    before_events=before_events, after_events=after_events, records=records, checks=checks)
(out / "io-refusal-recovery-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(passed=sum(x["passed"] for x in checks), total=len(checks), failures=[x for x in checks if not x["passed"]]), ensure_ascii=False))
raise SystemExit(not all(x["passed"] for x in checks))
