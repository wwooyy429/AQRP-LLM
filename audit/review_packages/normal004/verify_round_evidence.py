"""Read-only reconciliation of normal round004; no cloud or market-data IO.

Run with ``python -B audit/review_packages/normal004/verify_round_evidence.py``.
Prints metadata only. It never opens the writable local Registry: all ledger
replay occurs in MemoryArtifactStore. Pending/missing delivered packets remain
pending. It neither polls tasks nor settles the authoritative ledger.

Optional LEAN packet overrides (repeat for retries):
  --lean-packet ATTEMPT_ID=audit/tool_observations/PACKET.json
  --lean-logs ATTEMPT_ID=audit/tool_observations/LOGS.json
Default packet names are ATTEMPT_ID-backtest-result.json / -backtest.json /
-lean.json and ATTEMPT_ID-backtest-logs.json / -logs.json. A delivered successful
LEAN result requires actual native log envelopes and immutable ledger evidence.
This developer helper is not independent GPT Work acceptance.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
from functools import lru_cache
import hashlib
import json
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash, decode_events
from qresearch.collection import _safe_source_diagnostic
from qresearch.engineering_receipts import backtest_observation, backtest_submission, research_observation
from qresearch.registry import Registry
from stage2 import admitted_input, bridge_for_attempt, _read_research_dispatch, settle_research_result

BASELINE = "eaf6b70aca485a292b4575fc99df312dc9560510"
BASELINE_JOURNAL_SHA256 = "520ab8b0584a0b2d58d5ebb99eb043031c887b6fcac6b065c62d50f08c8b846f"
SOURCE_COMMITS = {
    "9e8e49615584f6416c44eb6c9f6b61c58d8341aa1dbc1c83a9f9aeac02445f0c": "42b45c830aac691fe0763bfc6363997947625bc1",
    "4785e506c51dca4bee4716ed26cc2d1749068124b77fd48f2eaab5a3b0f41f6c": "662ccd876b67ca0949f921a53c4c33df37cfbbf1",
}
ROUND = "stage2-normal-repair-round-004"
FIRST = "b9f952c1de3a44f9b06e5c552f7d1af3"
SECOND = "2d1095df62dc4222bffd8000c0737d38"
CAPS = {"configurations": 2, "research": 4, "lean": 2}
INITIAL = {
    "configurations": {"normal": 6, "reserve": 4, "total": 10},
    "research": {"normal": 6, "reserve": 7, "total": 13},
    "lean": {"normal": 1, "reserve": 0, "total": 1},
}
LIMITS = {
    "configurations": {"normal": 8, "reserve": 4, "total": 12},
    "research": {"normal": 12, "reserve": 8, "total": 20},
    "lean": {"normal": 8, "reserve": 8, "total": 16},
}
ACCEPTED_OFFLINE = "44676db609b3b7c2175fa7fa4f19c8ccf8165458"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(value).hexdigest()


@lru_cache(maxsize=None)
def git_bytes(commit, path):
    return subprocess.check_output(["git", "show", commit + ":" + path], cwd=ROOT, stderr=subprocess.PIPE)


def lf(raw):
    return raw.replace(b"\r\n", b"\n")


class Reads:
    def __init__(self):
        self.originals = {}

    def bytes(self, path):
        path = Path(path)
        raw = path.read_bytes()
        if path in self.originals:
            require(raw == self.originals[path], "Input changed during verification")
        self.originals[path] = raw
        return raw

    def json(self, path):
        return json.loads(self.bytes(path).decode("utf-8-sig"))

    def unchanged(self):
        return all(path.read_bytes() == raw for path, raw in self.originals.items())


def _safe_override(value):
    attempt, path = value.split("=", 1)
    require(re.fullmatch(r"[0-9a-f]{32}", attempt) is not None, "Canonical existing attempt required")
    resolved = (ROOT / path).resolve()
    require(resolved.is_relative_to(ROOT / "audit" / "tool_observations"), "Use archived tool observation metadata")
    return attempt, resolved


def _packet_path(attempt, suffixes, override=None):
    if override is not None:
        return override
    candidates = [ROOT / "audit/tool_observations" / (attempt + suffix) for suffix in suffixes]
    existing = [path for path in candidates if path.exists()]
    require(len(existing) <= 1, "Multiple candidate packets require an explicit override")
    return existing[0] if existing else None


def _context(reads, registry, record):
    bridge = bridge_for_attempt(record["attempt_id"], registry=registry)
    admission = admitted_input(bridge, record["attempt_id"])
    input_path = ROOT / admission["input_path"]
    if input_path.exists():
        reads.bytes(input_path)
    payload, deployment = admission["payload"], admission["deployment"]
    commit = SOURCE_COMMITS[record["config_id"]]
    manifest = payload["deployment_manifest"]
    require(len(manifest) == 32, "Complete fixed source set must have32 managed files")
    for path, expected in manifest.items():
        actual = git_bytes(commit, "cloud/" + path).decode("utf-8-sig")
        require(digest(actual.replace("\r\n", "\n").encode("utf-8")) == expected,
                "Admitted source differs from its fixed Git commit")
    price_request = payload["plan"]["request_template"]
    require(price_request["normalization"] == "raw" and price_request["data_version"] == "qc-engineering-2018-raw-snapshot-v1",
            "Fixed engineering price-cache identity changed")
    return bridge, admission, {
        "attempt_id": record["attempt_id"], "stage": record["stage"], "config_id": record["config_id"],
        "ledger_status": record["status"], "source_commit": commit,
        "frozen_identity": payload["identity"], "frozen_deployment": deployment,
        "managed_source_file_count": len(manifest),
        "price_request_template_sha256": content_hash(price_request),
        "price_row_values_exported": False,
    }


def _strict_terminal(bridge, record, payload, observed):
    submission = bridge._recorded_submission(payload)
    platform_status, passed = bridge._completion_contract(payload, submission, observed)
    ref = {"key": "engineering/evidence/" + record["attempt_id"] + "/completion/" + content_hash(observed) + ".json",
           "sha256": content_hash(observed)}
    require(bridge.store.exists(ref["key"]) and bridge.store.read_bytes(ref["key"]) == canonical_json(observed),
            "Terminal packet is not the immutable original completion evidence")
    if record["status"] == "failed":
        require(isinstance(record.get("error"), dict) and record["error"].get("evidence_ref") == ref,
                "Failed ledger record does not bind this terminal evidence")
        require(platform_status != "completed" or passed is False, "Failed ledger contradicts terminal result")
    else:
        require(record["status"] == "completed" and platform_status == "completed" and passed is True,
                "Completed ledger requires actual passed terminal result")
        result = bridge.registry.read_result(record["attempt_id"])
        require(result["platform_evidence_ref"] == ref and result["cloud_report"] == observed["cloud_report"]
                and result["report_ref"] == observed["report_ref"], "Completed result differs from original terminal evidence")
    return platform_status, passed, ref


def _report_metadata(observed):
    report = observed.get("cloud_report")
    if report is None:
        return {"cloud_report_present": False}
    evidence = report.get("evidence", {})
    # Every field was validated by the shared fixed receipt parser. Only
    # counts/checks/hashes/references are returned, never native price rows.
    return {"cloud_report_present": True, "report_ref": observed["report_ref"],
        "cloud_checks": report["checks"], "cloud_statistics": report["statistics"],
        "price_cache_payload_refs": evidence.get("cache_payload_refs", []),
        "collection_probe": evidence.get("collection_probe"),
        "report_financial_evidence": report.get("financial_evidence", False)}


def _research(reads, registry, record):
    bridge, admission, result = _context(reads, registry, record)
    payload, deployment = admission["payload"], admission["deployment"]
    binding = _read_research_dispatch(bridge, payload, deployment, require_dispatch=True)
    result["dispatch_binding_sha256"] = content_hash(binding)
    path = ROOT / "audit/tool_observations" / (record["attempt_id"] + "-research.json")
    if not path.exists():
        require(record["status"] not in {"failed", "completed"}, "Terminal Research has no native packet archive")
        return result | {"native_packet_present": False, "terminal_evidence_verified": False,
                         "verification_state": "awaiting_delivered_native_packet"}
    packet = reads.json(path)
    observed = research_observation(payload, deployment, packet, dispatch_binding=binding, dispatch_required=True)
    result.update(native_packet_present=True, native_packet_sha256=digest(reads.bytes(path)),
                  platform_status=observed["completion"]["platform"]["status"])
    if record["status"] not in {"failed", "completed"}:
        return result | {"terminal_evidence_verified": False, "verification_state": "awaiting_ledger_reconciliation"}
    status, passed, ref = _strict_terminal(bridge, record, payload, observed["completion"])
    saved = dict(registry.store._data)
    replay = settle_research_result(bridge, record["attempt_id"], packet)
    require(replay.status == record["status"] and registry.store._data == saved,
            "Original Research receipt replay changed metadata")
    result.update(terminal_evidence_verified=True, verification_state="original_terminal_evidence_verified",
                  original_receipt_replay_unchanged=True, terminal_evidence_ref=ref,
                  engineering_checks_passed=bool(status == "completed" and passed),
                  **_report_metadata(observed["completion"]))
    if record["attempt_id"] == FIRST:
        native_blocks = {block["text"] for block in packet["result"]["content"] if block.get("type") == "text"}
        require(len(native_blocks) == 1, "Original diagnostic native error representations differ")
        native = json.loads(next(iter(native_blocks)))
        diagnostic = _safe_source_diagnostic(json.loads(native["evalue"].split("; diagnostic=", 1)[1]))
        require(diagnostic is not None and diagnostic["failure_code"] == "native_sid_duplicate"
                and diagnostic["stage"] == "row_identity" and diagnostic["rows_emitted"] == 5124,
                "Original observed SID failure subtype/count changed")
        require(record["status"] == "failed" and status == "runtime_error", "Diagnostic attempt must retain its actual failure")
        result.update(diagnostic=diagnostic, diagnostic_count_scope="one failing fetch, not completed window/full Research totals")
    return result


def _lean(reads, registry, record, packets, logs):
    bridge, admission, result = _context(reads, registry, record)
    payload, deployment = admission["payload"], admission["deployment"]
    submission_path = ROOT / "audit/tool_observations" / (record["attempt_id"] + "-submission.json")
    result["native_submission_packet_present"] = submission_path.exists()
    if submission_path.exists():
        submitted = backtest_submission(payload, deployment, reads.json(submission_path))
        original = bridge._recorded_submission(payload)
        submission_ref = original["receipt_ref"]
        require(original["external_id"] == record["external_id"] == submitted["external_id"]
                and submission_ref["sha256"] == content_hash(submitted)
                and bridge.store.read_bytes(submission_ref["key"]) == canonical_json(submitted),
                "Native LEAN submission differs from immutable accepted identity")
        result.update(native_submission_verified=True, external_backtest_id=submitted["external_id"],
                      native_submission_packet_sha256=digest(reads.bytes(submission_path)),
                      submission_evidence_ref=submission_ref)
    packet_path = _packet_path(record["attempt_id"], ("-backtest-result.json", "-backtest.json", "-lean.json"), packets.get(record["attempt_id"]))
    if packet_path is None:
        require(record["status"] not in {"failed", "completed"}, "Terminal LEAN needs explicit actual native packet metadata")
        return result | {"native_packet_present": False, "terminal_evidence_verified": False,
                         "verification_state": "awaiting_delivered_native_packet"}
    log_path = _packet_path(record["attempt_id"], ("-backtest-logs.json", "-logs.json"), logs.get(record["attempt_id"]))
    packet, native_logs = reads.json(packet_path), reads.json(log_path) if log_path else []
    observed = backtest_observation(payload, deployment, record["external_id"], packet, native_logs)
    result.update(native_packet_present=True, native_packet_sha256=digest(reads.bytes(packet_path)),
                  platform_status=observed["platform"]["status"])
    if record["status"] not in {"failed", "completed"}:
        return result | {"terminal_evidence_verified": False, "verification_state": "awaiting_ledger_reconciliation"}
    status, passed, ref = _strict_terminal(bridge, record, payload, observed)
    result.update(terminal_evidence_verified=True, verification_state="original_terminal_evidence_verified",
                  terminal_evidence_ref=ref, engineering_checks_passed=bool(status == "completed" and passed),
                  **_report_metadata(observed))
    return result


def verify(*, lean_packets=None, lean_logs=None):
    reads = Reads()
    journal_path = ROOT / "audit/runtime/registry/events.jsonl"
    journal = reads.bytes(journal_path)
    old = git_bytes(BASELINE, "audit/runtime/registry/events.jsonl")
    require(len(old.splitlines()) == 34 and digest(old) == BASELINE_JOURNAL_SHA256 and journal.startswith(old),
            "Original34-event baseline prefix changed")
    baseline_note = reads.json(ROOT / "audit/stage2_normal004_baseline.json")
    require(baseline_note["baseline_commit"] == BASELINE and baseline_note["events"] == 34
            and baseline_note["journal_sha256"] == BASELINE_JOURNAL_SHA256
            and baseline_note["global_usage"] == INITIAL and baseline_note["global_limits"] == LIMITS,
            "Round baseline metadata changed")
    store = MemoryArtifactStore()
    runtime = ROOT / "audit/runtime"
    for path in sorted(runtime.rglob("*")):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".py"}:
            store.write_once(path.relative_to(runtime).as_posix(), reads.bytes(path))
    require(store.read_bytes("registry/events.jsonl") == journal, "Journal changed while capturing read-only snapshot")
    registry = Registry(store, json.loads(store.read_bytes("registry/baseline.json")))
    require(store.read_bytes("registry/baseline.json") == git_bytes(BASELINE, "audit/runtime/registry/baseline.json"),
            "Original authoritative budget baseline bytes changed")
    snapshot = registry.snapshot()
    latest_input = json.loads(store.read_bytes("engineering/admitted-inputs/" + SECOND + ".json"))
    latest_commit = SOURCE_COMMITS[latest_input["payload"]["identity"]["config_id"]]
    for name, expected in latest_input["payload"]["deployment_manifest"].items():
        current = reads.bytes(ROOT / "cloud" / name).decode("utf-8-sig")
        require(digest(current.replace("\r\n", "\n").encode("utf-8")) == expected,
                "Current imported calculation/parser source differs from frozen repair")
    require(lf(reads.bytes(ROOT / "tools/stage2.py")) == lf(git_bytes(latest_commit, "tools/stage2.py")),
            "Current settlement helper differs from fixed repair source")
    require(registry.limits == LIMITS and registry.ENGINEERING_STOP_LIMIT == 2, "Global/legacy limits changed")
    round_record = registry.engineering_rounds_snapshot()[ROUND]
    grant = round_record["grant"]
    require(grant["allocation"] == "normal" and grant["limits"] == CAPS and grant["final_test_enabled"] is False
            and grant["extra_spend_usd"] == 0, "Round allocation or caps changed")
    auth = json.loads(store.read_bytes(grant["authorization_ref"]["key"]))
    require(auth["scope"] == "stage2_normal_allocation_exception"
            and auth["normal_allocation_approval"]["answer"] == "允许", "Explicit normal exception missing")
    require(set(round_record["config_ids"]) == set(SOURCE_COMMITS), "Round must bind only its two frozen configurations")
    require(round_record["usage"]["configurations"] == 2 and 2 <= round_record["usage"]["research"] <= 4
            and 0 <= round_record["usage"]["lean"] <= 2, "Observed round usage exceeds or lacks its admitted work")
    for resource in CAPS:
        require(snapshot["usage"][resource]["reserve"] == INITIAL[resource]["reserve"], "Normal round consumed reserve")
        for lane in ("normal", "total"):
            require(snapshot["usage"][resource][lane] == INITIAL[resource][lane] + round_record["usage"][resource],
                    "Round charges do not explain global usage")
    current_budget = reads.json(ROOT / "config/budget.json")
    baseline_budget = json.loads(git_bytes(BASELINE, "config/budget.json"))
    counters = {
        "configurations": ("configuration_budget_charges", "configuration_normal_used", "configuration_reserve_used"),
        "research": ("research_execution_attempts", "research_normal_used", "research_reserve_used"),
        "lean": ("lean_submission_attempts", "lean_normal_used", "lean_reserve_used"),
    }
    for resource, fields in counters.items():
        for field, lane in zip(fields, ("total", "normal", "reserve")):
            require(current_budget["usage"].get(field, 0) == snapshot["usage"][resource][lane],
                    "Generated budget usage projection differs from authoritative ledger")
    current_budget.pop("usage"); baseline_budget.pop("usage")
    require(current_budget == baseline_budget, "Budget policy/resources/allocations changed")
    exposure = reads.bytes(ROOT / "audit/data_exposure.json")
    old_exposure = git_bytes(BASELINE, "audit/data_exposure.json")
    require(lf(exposure) == lf(old_exposure) and json.loads(exposure) == json.loads(old_exposure), "Prior data-exposure facts changed")
    execution = reads.json(ROOT / "config/development.json")["execution"]
    require(all(execution[name] is False for name in ("market_research_enabled", "llm_runtime_enabled", "final_test_enabled", "live_trading_enabled")),
            "Disabled research/final/live gates changed")
    readiness = reads.json(ROOT / "audit/stage2_current_readiness.json")
    old_readiness = json.loads(git_bytes(BASELINE, "audit/stage2_current_readiness.json"))
    require(readiness["accepted_offline_source_commit"] == ACCEPTED_OFFLINE
            and readiness["accepted_offline_scope"] == old_readiness["accepted_offline_scope"]
            and readiness["independent_offline_accepted_stages"] == [0, 1], "Historical independent acceptance scope changed")
    require(readiness["accepted_offline_scope"]["full_phase2"] is False, "Scoped prior acceptance became full Phase2 acceptance")
    records = [record for record in snapshot["attempts"] if record["config_id"] in SOURCE_COMMITS]
    require(any(r["attempt_id"] == FIRST and r["status"] == "failed" for r in records)
            and any(r["attempt_id"] == SECOND for r in records), "Expected charged Research attempts missing")
    require(all(r["allocation"] == "normal" for r in records), "Unexpected attempt allocation")
    lean_ids = {r["attempt_id"] for r in records if r["stage"] == "lean"}
    require(set(lean_packets or {}) <= lean_ids and set(lean_logs or {}) <= lean_ids,
            "Evidence override must name an existing charged LEAN attempt in this round")
    evidence = [_research(reads, registry, r) if r["stage"] == "research" else
                _lean(reads, registry, r, lean_packets or {}, lean_logs or {}) for r in records]
    pending = [r["attempt_id"] for r in evidence if r["terminal_evidence_verified"] is False]
    require(reads.unchanged(), "Inputs changed during verification; rerun after coordinator finishes reconciliation")
    return {"schema_version": 1, "kind": "auxiliary_developer_read_only_normal004_evidence_verification",
        "verification": "passed_existing_evidence_with_pending_runtime" if pending else "passed_existing_evidence",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
        "original34_event_prefix_preserved": True, "current_event_count": len(decode_events(journal)),
        "journal_sha256": digest(journal), "global_limits": registry.limits, "global_usage": snapshot["usage"],
        "budget_policy_resources_allocations_unchanged": True, "legacy_stop_preserved": True,
        "data_exposure_unchanged_under_LF_policy": True, "data_exposure_normalized_sha256": digest(lf(exposure)),
        "round_id": ROUND, "round_status": round_record["status"], "round_caps": grant["limits"],
        "round_usage": round_record["usage"], "authorization_ref": grant["authorization_ref"],
        "human_authorization_trust": "Trusted operator transcription; hashes do not authenticate human provenance",
        "attempts": evidence, "pending_or_unreconciled_attempts": pending,
        "same_plan_LEAN_completed": any(r["stage"] == "lean" and r.get("engineering_checks_passed") is True for r in evidence),
        "historical_independent_accepted_commit": ACCEPTED_OFFLINE, "historical_full_phase2_accepted": False,
        "all_input_bytes_unchanged_during_check": True, "real_registry_opened_for_writing": False,
        "current_shared_parsers_match_frozen_repair_source": True,
        "real_source_calls": 0, "real_backtest_submissions": 0, "raw_market_rows_exported": False,
        "failure_refunds": 0, "independent_GPT_Work_acceptance": False, "full_stage2_accepted": False,
        "full_historical_US200_certified": False, "actual_availability_certified": False,
        "financial_vintage_certified": False, "financial_evidence": False, "final_test_enabled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-packet", action="append", default=[])
    parser.add_argument("--lean-logs", action="append", default=[])
    args = parser.parse_args()
    try:
        result = verify(lean_packets=dict(_safe_override(v) for v in args.lean_packet),
                        lean_logs=dict(_safe_override(v) for v in args.lean_logs))
    except Exception as error:
        # Native exception strings can contain source values. Only the closed
        # failure classification leaves this wrapper; no traceback is printed.
        print(json.dumps({"schema_version": 1, "kind": "auxiliary_read_only_evidence_verification",
            "verification": "failed", "error_kind": type(error).__name__,
            "independent_GPT_Work_acceptance": False, "financial_evidence": False, "final_test_enabled": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
