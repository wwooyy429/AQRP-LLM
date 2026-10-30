"""WR29 development support only: synthetic subprocess boundaries, no connector.

All writes, including private synthetic registries, stay below this file's folder.
No repository acceptance test helpers are imported. This is not formal review.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(__file__).resolve().parent
assert OUT == ROOT / ".git" / "repair-work" / "wr29-boundary"
RUN = OUT / datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
RUN.mkdir()
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
from qresearch.artifacts import MemoryArtifactStore, FilesystemArtifactStore, content_hash, decode_events
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.registry import Registry

LIMITS = {kind: dict(total=10, normal=8, reserve=2) for kind in ("configurations", "research", "lean")}
POLICY = dict(schema_version=1, notification_grace_seconds=1800, max_history_pages=3)
RESULT = dict(scope="development_support_only_not_formal_acceptance", run_dir=str(RUN), cases=[], failures=[])
RESULT["validator_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
(RUN / "validator.py").write_bytes(Path(__file__).read_bytes())


def check(condition, label, details=None):
    RESULT["cases"].append(dict(label=label, passed=bool(condition), details=details))
    if not condition:
        RESULT["failures"].append(label)


def seed(label, submitted):
    """Construct accepted submission metadata locally; never dispatch anything."""
    store = MemoryArtifactStore()
    raw = dict(schema_version=1, plan_id="wr29-independent-boundary", scope="engineering", project_id=17,
        source_manifest_hash="a" * 64, deployment_hash="b" * 64, request_mode="symbol_resolution",
        request_template=dict(dataset="US Equities", fields=["close", "volume"],
            start="2018-01-01T00:00:00-05:00", end="2019-01-01T00:00:00-05:00",
            data_version="independent-synthetic-wr29", universe_hash="c" * 64,
            normalization="raw", timezone="America/New_York"),
        symbol_resolution=dict(tickers=["AAPL", "MSFT"], as_of="2019-01-01T00:00:00-05:00",
            method="QuantBook.add_equity/as-of fixed fixture"),
        observation_window=dict(start="2018-01-03T00:00:00-05:00", end_exclusive="2019-01-01T00:00:00-05:00"),
        required_checks=dict(research=["nonempty_history", "second_prefetch_no_history"],
            lean=["data_received", "orders_zero", "corporate_action_received"]),
        max_retries=dict(research=1, lean=1), report_namespace="engineering/wr29-boundary",
        orders_enabled=False, financial_metrics_enabled=False, economic_factor=None, economic_model=None)
    def accepted(payload):
        identity = payload["identity"]
        external = "qc-research:17:" + identity["attempt_id"] if identity["stage"] == "research" else "synthetic-wr29-backtest"
        return dict(identity=identity, identity_kind=payload["external_identity_kind"], external_id=external,
            accepted=True, status="completed", deployment=dict(source_manifest_hash="a" * 64,
                deployment_hash="b" * 64, input_hash="f" * 64),
            raw_receipt=dict(success=True, id=external) if identity["stage"] == "research" else dict(success=True, backtestId=external))
    def completed_research(payload):
        receipt = accepted(payload)
        refs = dict(resolved_registry_ref=dict(key="synthetic/wr29-registry.json", sha256="d" * 64),
            resolved_request_ref=dict(key="synthetic/wr29-request.json", sha256="e" * 64))
        resolution = dict(refs, resolved_registry_hash="d" * 64, resolved_request_hash="e" * 64,
            resolution_artifact_hash=content_hash(refs), tickers=["AAPL", "MSFT"], ticker_count=2,
            permanent_sid_count=2, method="QuantBook.add_equity/as-of fixed fixture")
        report = dict(schema_version=1, identity=payload["identity"], status="completed", terminal=True,
            checks=dict(nonempty_history=True, second_prefetch_no_history=True),
            statistics=dict(record_count=2, history_calls_second=0), resolution=resolution,
            market_values_exported=False, economic_factor_tested=False, final_data_accessed=False,
            full_US200_coverage_certified=False, actual_availability_verified=False)
        return dict(platform=dict(identity=dict(payload["identity"], external_id=receipt["external_id"]),
                status="completed", terminal=True, deployment=receipt["deployment"], raw_receipt=dict(completed=True)),
            cloud_report=report, report_ref=dict(key=payload["report_key"], sha256=content_hash(report)))
    with patch("qresearch.registry.datetime") as clock:
        clock.now.return_value = submitted
        registry = Registry(store, LIMITS)
        bridge = EngineeringTaskBridge(registry, EngineeringTaskPlan.from_dict(raw, discovered_project_ids=(17,)))
        bridge.register()
        research = bridge.claim("research")
        research_payload = bridge.payload(research)
        bridge.record_submission(research, accepted(research_payload))
        bridge.consume_completion(research, completion_source=completed_research)
        lean = bridge.claim("lean")
        bridge.record_submission(lean, accepted(bridge.payload(lean)))
    disk_path = RUN / "stores" / label
    disk = FilesystemArtifactStore(disk_path, data_classification="synthetic")
    for key, data in store._data.items():
        disk.write_once(key, data)
    return disk_path, lean.attempt_id, sha256(disk.read_bytes(Registry.JOURNAL)).hexdigest()


FACTORY = '''from pathlib import Path
from datetime import datetime, timezone
import json, os, sys, traceback
import followup_host as public
from followup_host import FollowupHost, TransportAuthority, ReadGrant
from qresearch.artifacts import FilesystemArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController
LIMITS = {kind:dict(total=10,normal=8,reserve=2) for kind in ("configurations","research","lean")}
def controller():
    return TaskFollowupController(Registry(FilesystemArtifactStore(os.environ["WR29_STORE"],data_classification="synthetic"),LIMITS),dict(schema_version=1,notification_grace_seconds=1800,max_history_pages=3))
def forbidden_clock():
    Path(os.environ["WR29_CLOCK_USED"]).write_text("factory clock executed",encoding="utf-8")
    raise AssertionError("factory clock must be replaced by CLI real UTC")
def build(discovery=True,history=True):
    attempt=os.environ["WR29_ATTEMPT"]
    host=FollowupHost(controller(),authority=TransportAuthority("independent-synthetic",frozenset({attempt}) if discovery else frozenset(),frozenset({attempt}) if history else frozenset()),enabled=True,clock=forbidden_clock)
    meta={"host_module":type(host).__module__,"authority_module":type(host.authority).__module__,"grant_module":ReadGrant.__module__,"host_is_public":type(host) is public.FollowupHost,"file":str(Path(public.__file__).resolve()),"main_module":public.main.__module__,"serve_module":public.serve.__module__,"main_has_host_type":hasattr(sys.modules["__main__"],"FollowupHost")}
    Path(os.environ["WR29_METADATA"]).write_text(json.dumps(meta),encoding="utf-8")
    original=host.command
    def traced(message):
        try: return original(message)
        except Exception:
            Path(os.environ["WR29_EXCEPTION_LOG"]).write_text(traceback.format_exc(),encoding="utf-8")
            raise
    host.command=traced
    return host
def no_discovery(): return build(discovery=False)
def no_history(): return build(history=False)
def disabled(): return FollowupHost()
def bad(): return None
class Duck:
    enabled=True
    def command(self,message): return {"unsafe":True}
def duck(): return Duck()
class Child(FollowupHost): pass
def subclass(): return Child()
def bad_authority(): return FollowupHost(controller(),authority=Duck(),enabled=True)
def bad_controller(): return FollowupHost(Duck(),authority=TransportAuthority("synthetic"),enabled=True)
'''
(OUT / "wr29_boundary_factory.py").write_text(FACTORY, encoding="utf-8")
(OUT / "wr29_malicious.py").write_text('from pathlib import Path\nimport os\nPath(os.environ["WR29_MALICIOUS_USED"]).write_text("imported",encoding="utf-8")\nraise RuntimeError("malicious factory imported")\n', encoding="utf-8")

ENTRIES = {
    "canonical": [sys.executable, "-B", "-c", "import followup_host; raise SystemExit(followup_host.main())"],
    "script": [sys.executable, "-B", str(ROOT / "tools" / "followup_host.py")],
    "module": [sys.executable, "-B", "-m", "followup_host"],
}


def run(entry, label, store=None, attempt="1" * 32, factory="build", messages=(), enabled=True,
        command="serve", factory_spec=None, cwd=None, no_tools_path=False, extra=()):
    metadata = RUN / (label + "-metadata.json")
    clock_used = RUN / (label + "-clock-used.txt")
    malicious_used = RUN / (label + "-malicious-used.txt")
    exception_log = RUN / (label + "-exception.txt")
    env = dict(os.environ)
    env.update(PYTHONPATH=os.pathsep.join([str(OUT)] + ([] if no_tools_path else [str(ROOT / "tools")]) + [str(ROOT / "cloud")]),
        PYTHONDONTWRITEBYTECODE="1", WR29_STORE=str(store or RUN / "unused-store"), WR29_ATTEMPT=attempt,
        WR29_METADATA=str(metadata), WR29_CLOCK_USED=str(clock_used), WR29_MALICIOUS_USED=str(malicious_used), WR29_EXCEPTION_LOG=str(exception_log))
    args = list(ENTRIES[entry]) + [command]
    if command == "plan": args += ["--attempt", attempt]
    if enabled: args += ["--enable-dispatch"]
    if factory is not None: args += ["--host-factory", factory_spec or "wr29_boundary_factory:" + factory]
    args += list(extra)
    start = datetime.now(timezone.utc)
    proc = subprocess.run(args, cwd=cwd or ROOT, env=env,
        input="".join(json.dumps(message) + "\n" for message in messages), text=True, capture_output=True, timeout=30)
    stop = datetime.now(timezone.utc)
    record = dict(label=label, entry=entry, exit=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        before=start.isoformat(), after=stop.isoformat(), clock_used=clock_used.exists(),
        malicious_imported=malicious_used.exists(), exception_trace=exception_log.read_text(encoding="utf-8") if exception_log.exists() else None,
        metadata=json.loads(metadata.read_text(encoding="utf-8")) if metadata.exists() else None)
    RESULT.setdefault("subprocesses", []).append(record)
    return record, [json.loads(line) for line in proc.stdout.splitlines()]


def host_events(path, attempt):
    file = path / "engineering" / "followup-host" / attempt / "events.jsonl"
    return [x["event"] for x in decode_events(file.read_bytes())] if file.exists() else []


def registry_unchanged(path, digest):
    return sha256((path / Registry.JOURNAL).read_bytes()).hexdigest() == digest


def main():
    RESULT["source_sha256"] = {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in ["tools/followup_host.py"]}
    old = datetime(2001, 1, 1, tzinfo=timezone.utc)
    for entry in ENTRIES:
        path, attempt, journal = seed(entry + "-restart", old)
        record, lines = run(entry, entry + "-empty", path, attempt)
        check(record["exit"] == 0 and not lines and not record["stderr"], entry + ": valid factory empty serve", record)
        meta = record["metadata"]
        check(meta and all(meta[key] == "followup_host" for key in ("host_module", "authority_module", "grant_module", "main_module", "serve_module"))
            and meta["host_is_public"] and not meta["main_has_host_type"]
            and Path(meta["file"]) == ROOT / "tools" / "followup_host.py", entry + ": stable public module identity", meta)
        record, lines = run(entry, entry + "-wake", path, attempt, messages=[dict(command="wake", attempt_id=attempt)])
        check(record["exit"] == 0 and len(lines) == 1 and lines[0].get("tool_name") == "mcp__quantconnect__list_projects", entry + ": accepted factory emits discovery")
        events = host_events(path, attempt)
        reserved = [e for e in events if e["kind"] == "reserved"]
        check(len(reserved) == 1 and not record["clock_used"] and datetime.fromisoformat(record["before"]) <= datetime.fromisoformat(reserved[0]["reserved_at"]) <= datetime.fromisoformat(record["after"])
            and reserved[0]["reserved_at"].endswith("+00:00"), entry + ": real UTC replaces factory clock", reserved)
        for restart_entry in ENTRIES:
            restart, outputs = run(restart_entry, entry + "-restart-" + restart_entry, path, attempt,
                messages=[dict(command="status", attempt_id=attempt), dict(command="wake", attempt_id=attempt)])
            check(restart["exit"] == 0 and all(x.get("failure_code") == "reserved_response_unknown" for x in outputs)
                and len(outputs) == 2 and host_events(path, attempt) == events, entry + "->" + restart_entry + ": no replay on restart")
        request = lines[0]
        native = dict(success=True, projects=[dict(projectId=17, name="SYNTHETIC_WR29", language="Py")], page=1, nextPage=None, totalPages=1)
        response = dict(command="response", **{k: request[k] for k in ("attempt_id", "correlation_id", "tool_name", "arguments")},
            result=dict(structuredContent=native, content=[dict(type="text", text=json.dumps(native))], isError=False))
        record, outputs = run("module", entry + "-late-original", path, attempt, messages=[response, dict(command="wake", attempt_id=attempt)])
        check(record["exit"] == 0 and len(outputs) == 2 and outputs[0].get("action") == "projects_observed" and outputs[1].get("tool_name") == "mcp__quantconnect__list_backtests", entry + ": late original response crosses entry boundary")
        check(registry_unchanged(path, journal), entry + ": private registry journal unchanged by followup")

        record, outputs = run(entry, entry + "-default-off", attempt=attempt, factory_spec="wr29_malicious:build", enabled=False,
            messages=[dict(command="wake", attempt_id=attempt)])
        check(record["exit"] == 0 and outputs[0].get("action") == "dispatch_disabled" and not record["malicious_imported"], entry + ": default off does not import malicious factory")
        record, outputs = run(entry, entry + "-default-plan", attempt=attempt, factory_spec="wr29_malicious:build", enabled=False, command="plan")
        check(record["exit"] == 0 and outputs[0].get("action") == "dispatch_disabled" and not record["malicious_imported"], entry + ": default plan does not import malicious factory")
        for bad in ("bad", "disabled", "duck", "subclass", "bad_authority", "bad_controller"):
            record, outputs = run(entry, entry + "-reject-" + bad, path, attempt, factory=bad)
            check(record["exit"] != 0 and not outputs, entry + ": rejects " + bad)
        for spec in ("missingcolon", ":build", "wr29_boundary_factory:bad-name"):
            record, outputs = run(entry, entry + "-invalid-spec-" + str(len(RESULT["cases"])), path, attempt, factory_spec=spec)
            check(record["exit"] == 2 and not outputs, entry + ": rejects malformed factory " + spec)
        record, outputs = run(entry, entry + "-reject-now", path, attempt, extra=("--now", "2099-01-01T00:00:00+00:00"))
        check(record["exit"] == 2 and not outputs, entry + ": CLI rejects supplied clock")

        future_path, future_attempt, journal = seed(entry + "-future", datetime(2099, 1, 1, tzinfo=timezone.utc))
        record, outputs = run(entry, entry + "-future-grace", future_path, future_attempt, messages=[dict(command="wake", attempt_id=future_attempt)])
        check(record["exit"] == 0 and outputs[0].get("failure_code") == "watch_registration_failed"
            and not record["clock_used"] and not any(e["kind"] == "reserved" for e in host_events(future_path, future_attempt)), entry + ": impossible future accepted clock fails closed")
        check(registry_unchanged(future_path, journal), entry + ": future private journal unchanged")

        recent_path, recent_attempt, journal = seed(entry + "-recent", datetime.now(timezone.utc) - timedelta(minutes=5))
        record, outputs = run(entry, entry + "-recent-grace", recent_path, recent_attempt, messages=[dict(command="wake", attempt_id=recent_attempt)])
        check(record["exit"] == 0 and outputs[0].get("action") == "wait_for_delivery" and not record["clock_used"]
            and not host_events(recent_path, recent_attempt), entry + ": real UTC preserves lawful grace interval")
        check(registry_unchanged(recent_path, journal), entry + ": recent private journal unchanged")

        permission_path, permission_attempt, journal = seed(entry + "-permission", old)
        record, outputs = run(entry, entry + "-no-discovery", permission_path, permission_attempt, factory="no_discovery", messages=[dict(command="wake", attempt_id=permission_attempt)])
        check(record["exit"] == 0 and outputs[0].get("failure_code") == "discovery_not_authorized" and not any(e["kind"] == "reserved" for e in host_events(permission_path, permission_attempt)), entry + ": discovery authority remains required")

        history_path, history_attempt, journal = seed(entry + "-history-permission", old)
        record, outputs = run(entry, entry + "-history-discover", history_path, history_attempt, factory="no_history", messages=[dict(command="wake", attempt_id=history_attempt)])
        check(record["exit"] == 0 and len(outputs) == 1 and outputs[0].get("tool_name") == "mcp__quantconnect__list_projects", entry + ": discovery permission alone permits only discovery")
        request = outputs[0]
        response = dict(command="response", **{k: request[k] for k in ("attempt_id", "correlation_id", "tool_name", "arguments")},
            result=dict(structuredContent=native, content=[dict(type="text", text=json.dumps(native))], isError=False))
        record, outputs = run(entry, entry + "-history-denied", history_path, history_attempt, factory="no_history", messages=[response, dict(command="wake", attempt_id=history_attempt)])
        check(record["exit"] == 0 and len(outputs) == 2 and outputs[1].get("failure_code") == "history_not_authorized"
            and sum(e["kind"] == "reserved" for e in host_events(history_path, history_attempt)) == 1, entry + ": history authority remains required")
        check(registry_unchanged(history_path, journal), entry + ": permission denial private journal unchanged")

    outside = RUN / "outside-cwd"
    outside.mkdir(exist_ok=True)
    path, attempt, _ = seed("absolute-script", old)
    record, outputs = run("script", "absolute-script-other-cwd-no-tools-pythonpath", path, attempt, cwd=outside, no_tools_path=True)
    check(record["exit"] == 0 and record["metadata"]["host_is_public"], "absolute script resolves canonical module outside repo without tools PYTHONPATH")
    record, outputs = run("module", "module-from-tools-cwd-no-tools-pythonpath", path, attempt, cwd=ROOT / "tools", no_tools_path=True)
    check(record["exit"] == 0 and record["metadata"]["host_is_public"], "module resolves canonical identity from tools cwd without tools PYTHONPATH")
    RESULT["source_sha256_after"] = {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in RESULT["source_sha256"]}
    check(RESULT["source_sha256"] == RESULT["source_sha256_after"], "source stable during independent test")


try:
    main()
except Exception as exc:
    RESULT["failures"].append("validator_unexpected_exception")
    RESULT["exception"] = repr(exc)
finally:
    (OUT / "results.json").write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN / "results.json").write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(cases=len(RESULT["cases"]), failures=RESULT["failures"], source_sha256=RESULT.get("source_sha256")), ensure_ascii=False))
raise SystemExit(bool(RESULT["failures"]))
