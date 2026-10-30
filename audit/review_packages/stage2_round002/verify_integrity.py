"""Read-only, metadata-only reconciliation of engineering round 002.

Run with python -B; stdout is the report. This program never creates a Registry
lock, updates a budget, writes evidence, contacts QuantConnect or executes the
archived notebook input. Hashes bind local archives, not independent provenance.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import canonical_json, content_hash, decode_events, validate_key
from qresearch.engineering_receipts import research_dispatch_binding, research_entry_protocol, research_observation
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import Registry

BASELINE = "65b8025b8618021eddd50520fe87c764b60af377"
ROUND = "stage2-cloud-round-002"
ATTEMPTS = ("4de020ffad5a4e82a26c5374f7715685", "d45af7fcfdc849c888694aaa6dd7c0ae")
EXPECTED_CONFIGS = ("d080612c40090d33c262a9769eb46f008942119ee06a6f7c1252497ea73da0a5",
                    "7e2613dea0b41747a8562c5e4fff1852ca391867c518078a2dd8610120ee08f7")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


class ReadOnlyStore:
    """No mutating store methods; cached bytes detect concurrent evidence edits."""
    def __init__(self, root):
        self.root, self.observed = Path(root).resolve(), {}

    def read_bytes(self, key):
        path = (self.root / validate_key(key)).resolve()
        require(path.is_relative_to(self.root), "Evidence path leaves the metadata root")
        raw = path.read_bytes()
        require(len(raw) <= 16 * 1024 * 1024, "Evidence exceeds the metadata size bound")
        if key in self.observed:
            require(self.observed[key] == raw, "Evidence changed during read: " + key)
        self.observed[key] = raw
        return raw

    def exists(self, key):
        path = (self.root / validate_key(key)).resolve()
        require(path.is_relative_to(self.root), "Evidence path leaves the metadata root")
        return path.is_file()

    def locked(self, key):
        validate_key(key)
        return nullcontext()

    def unchanged(self):
        for key, original in self.observed.items():
            require((self.root / key).read_bytes() == original, "Evidence changed during verification: " + key)


def git_bytes(repository, path):
    return subprocess.run(["git", "-C", str(repository), "show", BASELINE + ":" + path],
                          check=True, capture_output=True).stdout


def flags(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            name = prefix + "." + key if prefix else key
            if key.endswith("_enabled"):
                result[name] = child
            result.update(flags(child, name))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(flags(child, prefix + "[" + str(index) + "]"))
    return result


def verify(root=ROOT, reference_repository=ROOT):
    root = Path(root).resolve()
    files = ReadOnlyStore(root)
    runtime = ReadOnlyStore(root / "audit/runtime")
    checks = {}

    # The fixed commit records the TURN START (7/10/1), not the much older
    # immutable initialization baseline (5/6/0). Both remain separate evidence.
    old_journal = git_bytes(reference_repository, "audit/runtime/registry/events.jsonl")
    journal = runtime.read_bytes(Registry.JOURNAL)
    old_events, events = decode_events(old_journal), decode_events(journal)
    require(len(old_events) == 17 and journal.startswith(old_journal), "Original 17-event byte prefix changed")
    require(len(events) == 28, "Round 002 journal event count differs")
    baseline_raw = runtime.read_bytes("registry/baseline.json")
    require(baseline_raw == git_bytes(reference_repository, "audit/runtime/registry/baseline.json"), "Immutable initialization baseline changed")
    baseline = parse(baseline_raw)
    registry = Registry(runtime, baseline)
    snapshot, rounds = registry.snapshot(), registry.engineering_rounds_snapshot()
    old_budget = parse(git_bytes(reference_repository, "config/budget.json"))
    budget = parse(files.read_bytes("config/budget.json"))
    require({k: v for k, v in budget.items() if k != "usage"} ==
            {k: v for k, v in old_budget.items() if k != "usage"}, "Budget policy, totals or allocations changed")
    require(old_budget["usage"]["configuration_budget_charges"] == 7 and
            old_budget["usage"]["research_execution_attempts"] == 10 and
            old_budget["usage"]["lean_submission_attempts"] == 1, "Incorrect turn-start usage")
    usage = snapshot["usage"]
    require(usage == {"configurations": {"normal": 6, "reserve": 3, "total": 9},
                      "research": {"normal": 6, "reserve": 6, "total": 12},
                      "lean": {"normal": 1, "reserve": 0, "total": 1}}, "Authoritative actual usage differs")
    keys = {"configurations": ("configuration_budget_charges", "configuration_normal_used", "configuration_reserve_used"),
            "research": ("research_execution_attempts", "research_normal_used", "research_reserve_used"),
            "lean": ("lean_submission_attempts", "lean_normal_used", "lean_reserve_used")}
    for kind, names in keys.items():
        for key, part in zip(names, ("total", "normal", "reserve")):
            require(budget["usage"][key] == usage[kind][part], "Budget projection differs from ledger: " + key)
    require({kind: count["total"] for kind, count in snapshot["limits"].items()} ==
            {"configurations": 12, "research": 20, "lean": 16}, "Global totals changed")
    checks["original_17_events_and_initialization_preserved"] = True
    checks["turn_start_and_current_usage_reconciled_without_refunds"] = True
    checks["global_limits_allocations_and_nonusage_policy_unchanged"] = True

    exposure = files.read_bytes("audit/data_exposure.json")
    require(parse(exposure) == parse(git_bytes(reference_repository, "audit/data_exposure.json")), "Prior data exposure facts changed")
    exposure_doc = parse(exposure)
    require(exposure_doc["whole_window_uncontaminated"] is False and any(
        item.get("start") == "2024-01-01" and item.get("end") == "2025-12-31"
        and item.get("independent_test_eligible") is False for item in exposure_doc["records"]), "Prior 2024-2025 exposure is missing")
    checks["prior_data_exposure_preserved"] = True

    require(set(rounds) == {ROUND}, "Unexpected engineering grant exists")
    current_round = rounds[ROUND]
    require(current_round["status"] == "closed" and current_round["grant"]["limits"] ==
            {"configurations": 2, "research": 2, "lean": 1} and current_round["usage"] ==
            {"configurations": 2, "research": 2, "lean": 0}, "Round limits, actual usage or closed state differs")
    require(current_round["config_ids"] == list(EXPECTED_CONFIGS), "Round configuration binding differs")
    require(current_round["grant"] == parse(files.read_bytes("config/engineering_round002.json")), "Grant source differs from immutable ledger")
    authority = parse(files.read_bytes("config/engineering_round002_authorization.json"))
    require(canonical_json(authority) == runtime.read_bytes(current_round["grant"]["authorization_ref"]["key"]), "Authorization source differs from receipt")
    records = [item for item in snapshot["attempts"] if item["config_id"] in EXPECTED_CONFIGS]
    require({item["attempt_id"] for item in records} == set(ATTEMPTS) and len(records) == 2,
            "Unexpected new execution exists")
    require(all(item["status"] == "failed" and item["stage"] == "research" and item["allocation"] == "reserve"
                for item in records), "New tasks are unresolved, uncharged or another resource")
    require(all(item["status"] not in {"started", "pending", "ambiguous"} for item in records), "New work remains unresolved")
    suffix = [item["event"] for item in events[len(old_events):]]
    require(sum(item["kind"] == "config_registered" for item in suffix) == 2 and
            sum(item["kind"] == "attempt_started" for item in suffix) == 2 and
            not any(item["kind"] == "attempt_started" and item["stage"] == "lean" for item in suffix),
            "Round debits differ or unused LEAN quota was consumed")
    require(suffix[-1]["kind"] == "engineering_round_closed", "Round was not finally closed")
    checks["closed_round_actual_2_2_0_and_unused_lean_reservation_only_released"] = True
    checks["no_unresolved_new_tasks_or_new_lean_submission"] = True

    per_attempt = []
    for attempt_id, config_id in zip(ATTEMPTS, EXPECTED_CONFIGS):
        record = next(item for item in records if item["attempt_id"] == attempt_id)
        package_raw = runtime.read_bytes("configurations/" + config_id + ".json")
        package = parse(package_raw)
        require(sha(package_raw) == config_id and canonical_json(package) == package_raw, "Configuration identity changed")
        plan = EngineeringTaskPlan.from_dict(package["plan"], discovered_project_ids=[current_round["grant"]["project_id"]])
        task = EngineeringTaskBridge(registry, plan)
        require(task.config_id == config_id, "Frozen full configuration differs")
        admission = parse(runtime.read_bytes("engineering/admitted-inputs/" + attempt_id + ".json"))
        payload, deployment = admission["payload"], admission["deployment"]
        require(payload == dict(task.payload(attempt_id), deployment_manifest=payload["deployment_manifest"]), "Admitted payload identity differs")
        require(content_hash(payload["deployment_manifest"]) == deployment["deployment_hash"] == plan.to_dict()["deployment_hash"], "Deployment manifest differs")
        input_path = "audit/task_inputs/" + attempt_id + ".py"
        input_bytes = files.read_bytes(input_path)
        require(admission["input_path"] == input_path and admission["cloud_input_path"] == "_engineering_task_input.py"
                and sha(input_bytes) == deployment["input_hash"], "Admitted inert input bytes differ")
        tree = ast.parse(input_bytes.decode("utf-8-sig"))
        require(len(tree.body) == 1 and isinstance(tree.body[0], ast.Assign)
            and len(tree.body[0].targets) == 1 and isinstance(tree.body[0].targets[0], ast.Name)
            and tree.body[0].targets[0].id == "TASK_INPUT_JSON", "Input is not one inert assignment")
        require(json.loads(ast.literal_eval(tree.body[0].value)) == payload, "Input literal differs from admission")
        entry = parse(runtime.read_bytes("engineering/research-entry-protocol/" + attempt_id + ".json"))
        require(entry == admission["research_entry_protocol"] == research_entry_protocol(payload, deployment), "Original entry protocol differs")
        native_read = parse(files.read_bytes("audit/tool_observations/" + attempt_id + "-read-cell.json"))
        dispatch = parse(runtime.read_bytes("engineering/research-dispatch/" + attempt_id + ".json"))
        require(dispatch == research_dispatch_binding(payload, deployment, native_read), "Native cell read and pre-dispatch binding differ")
        native = parse(files.read_bytes("audit/tool_observations/" + attempt_id + "-research.json"))
        observed = research_observation(payload, deployment, native, dispatch_binding=dispatch, dispatch_required=True)
        submission = task._recorded_submission(task.payload(attempt_id))
        require(parse(runtime.read_bytes(submission["receipt_ref"]["key"])) == observed["submission"],
                "Native submission does not reproduce archived receipt")
        completion_ref = record["error"]["evidence_ref"]
        completion_raw = runtime.read_bytes(completion_ref["key"])
        require(sha(completion_raw) == completion_ref["sha256"] and canonical_json(observed["completion"]) == completion_raw,
                "Native completion does not reproduce failed settlement evidence")
        status, passed = task._completion_contract(task.payload(attempt_id), submission, observed["completion"])
        require(passed is False and observed["completion"]["platform"]["terminal"] is True,
                "Failed settlement is not justified by terminal native evidence")
        attempt_events = [item for item in events if item["event"].get("attempt_id") == attempt_id]
        require([item["event"]["kind"] for item in attempt_events] == ["attempt_started", "pending", "failed"],
                "Debit/submission/failure event order differs")
        require(record["reconciliation"] == completion_ref["sha256"], "Failure reconciliation differs")
        require(plan.to_dict()["orders_enabled"] is False and plan.to_dict()["financial_metrics_enabled"] is False,
                "Engineering plan enables financial execution")
        per_attempt.append({"attempt_id": attempt_id, "configuration_id": config_id, "ledger_status": "failed",
            "platform_status": status, "terminal": True, "required_checks_passed": passed,
            "debit_sequence": attempt_events[0]["sequence"], "failed_sequence": attempt_events[-1]["sequence"],
            "completion_ref": completion_ref, "native_packet_sha256": sha(files.observed["audit/tool_observations/" + attempt_id + "-research.json"]),
            "dispatch_binding_sha256": content_hash(dispatch), "input_sha256": sha(input_bytes)})
    require(per_attempt[0]["platform_status"] == "runtime_error" and per_attempt[1]["platform_status"] == "completed",
            "Platform terminal status unexpectedly changed")
    checks["two_configuration_admission_dispatch_native_receipt_and_failure_bindings_reproduced"] = True
    checks["debits_precede_recorded_submission_and_failures_are_not_refunded"] = True

    execution_flags = {}
    config_paths = sorted((root / "config").glob("*.json"))
    for path in config_paths:
        key = path.relative_to(root).as_posix()
        execution_flags.update({key + ":" + name: value for name, value in flags(parse(files.read_bytes(key))).items()})
    generated = ast.parse(files.read_bytes("cloud/research_config.py").decode("utf-8-sig"))
    configurations = [ast.literal_eval(node.value) for node in generated.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CONFIGURATION" for target in node.targets)]
    require(len(configurations) == 1, "Generated configuration is missing or ambiguous")
    execution_flags.update({"cloud/research_config.py:" + name: value for name, value in flags(configurations[0]).items()})
    require(bool(execution_flags) and all(value is False for value in execution_flags.values()), "Execution switch was enabled")
    checks["all_source_and_generated_execution_flags_false"] = True
    runtime.unchanged(); files.unchanged()
    require(sorted(path.relative_to(root).as_posix() for path in (root / "config").glob("*.json")) ==
            sorted(path.relative_to(root).as_posix() for path in config_paths), "Configuration inventory changed during verification")
    checks["all_read_evidence_unchanged_during_verification"] = True
    evidence = {"audit/runtime/" + key: sha(raw) for key, raw in runtime.observed.items()}
    evidence.update({key: sha(raw) for key, raw in files.observed.items()})
    return {"schema_version": 1, "status": "pass", "scope": "local_archived_metadata_integrity_only",
        "program": "audit/review_packages/stage2_round002/verify_integrity.py",
        "program_sha256": sha(Path(__file__).read_bytes()), "baseline_commit": BASELINE,
        "baseline_event_count": len(old_events), "baseline_journal_sha256": sha(old_journal),
        "current_event_count": len(events), "current_journal_sha256": sha(journal),
        "turn_start_usage": {"configurations": 7, "research": 10, "lean": 1},
        "current_usage": usage, "global_limits": snapshot["limits"],
        "round": {"round_id": ROUND, "status": "closed", "limits": current_round["grant"]["limits"],
                  "actual_usage": current_round["usage"], "allocation": "reserve", "unused_lean_reservation_released": 1,
                  "charged_attempts_refunded": 0},
        "checks": checks, "attempts": per_attempt, "execution_flags": execution_flags,
        "evidence_sha256": dict(sorted(evidence.items())),
        "independent_software_acceptance": False, "stage2_accepted": False,
        "market_data_coverage_certified": False, "financial_evidence": False,
        "final_test_executed": False,
        "limitations": ["Archive hashes do not independently authenticate a remote tool or human instruction.",
            "Event order proves debit before recorded submission, not an independently timestamped remote dispatch.",
            "The first native execution terminated with runtime_error; the second native cell completed but required collection_nonempty failed.",
            "Existing 2024-2025 research exposure remains; no independent final financial test is claimed."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--reference-repository", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.reference_repository), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
