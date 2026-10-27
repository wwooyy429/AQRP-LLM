"""Offline, metadata-only reproduction of round 002 certification limits.

No QC client is imported. Native packets are read, never executed. Unknown
Research totals remain null even when a failing fetch has bounded counters.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
PROGRAM = Path(__file__).resolve().relative_to(ROOT).as_posix()
FIRST = "4de020ffad5a4e82a26c5374f7715685"
OLD = "f5d05f5b964b4a1d924e4b70cd207386"
PREFIX = "Historical source iteration failed; unfinished intent retained"
MAX_BYTES = 10 * 1024 * 1024
HASH = re.compile(r"[0-9a-f]{64}\Z")
ATTEMPT = re.compile(r"([0-9a-f]{32})-research\.json\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def read(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Evidence must remain inside the repository")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("Evidence packet exceeds the bounded limit")
    return parse(raw.decode("utf-8-sig")), {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(raw)}


def whitelist():
    source = ROOT / "cloud/qresearch/collection.py"
    assignments = {}
    for node in ast.parse(source.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"_SOURCE_DIAGNOSTIC_ENUMS", "_SOURCE_DIAGNOSTIC_COUNTS"}:
                assignments[node.targets[0].id] = ast.literal_eval(node.value)
    enums = assignments["_SOURCE_DIAGNOSTIC_ENUMS"]
    counts = assignments["_SOURCE_DIAGNOSTIC_COUNTS"]
    if type(enums) is not dict or type(counts) is not set:
        raise ValueError("Fixed diagnostic declarations are unavailable")
    return enums, counts, {"path": source.relative_to(ROOT).as_posix(), "sha256": digest(source.read_bytes())}


def safe_diagnostic(raw, enums, counts):
    if type(raw) is not dict or set(raw) != {"schema_version", *enums, *counts}:
        raise ValueError("Diagnostic keys differ from the closed whitelist")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("Invalid diagnostic schema")
    for key, allowed in enums.items():
        if type(raw[key]) is not str or raw[key] not in allowed:
            raise ValueError("Unknown diagnostic token")
    for key in counts:
        if raw[key] is not None and (type(raw[key]) is not int or not 0 <= raw[key] <= 1000000000):
            raise ValueError("Invalid diagnostic counter")
    return dict(raw)


def native_errors(packet):
    if (type(packet) is not dict or packet.get("tool_name") != "mcp__quantconnect__jupyter_execute_cell"
            or type(packet.get("arguments")) is not dict
            or type(packet["arguments"].get("projectId")) is not int
            or type(packet["arguments"].get("index")) is not int):
        raise ValueError("Expected archived native Research execution packet")
    result = packet.get("result")
    if type(result) is not dict or type(result.get("content")) is not list:
        raise ValueError("Expected native content carriers")
    unique = {}
    representations = 0
    for block in result["content"]:
        if type(block) is not dict or block.get("type") != "text" or type(block.get("text")) is not str:
            raise ValueError("Unsupported native carrier")
        node = parse(block["text"])
        if type(node) is not dict or node.get("output_type") != "error":
            # A successful envelope must be settled by the trusted engineering
            # receipt parser. This limited diagnostic program never approves it.
            continue
        if (set(node) != {"output_type", "ename", "evalue", "traceback"}
                or type(node["ename"]) is not str or type(node["evalue"]) is not str
                or type(node["traceback"]) is not list
                or any(type(line) is not str for line in node["traceback"])):
            raise ValueError("Invalid direct nbformat error")
        representations += 1
        unique.setdefault(digest(canonical(node)), node)
    return list(unique.items()), representations, result.get("isError")


def one_observation(path, enums, counts):
    match = ATTEMPT.fullmatch(Path(path).name)
    if match is None:
        raise ValueError("Native observation filename must bind one attempt")
    attempt = match[1]
    packet, packet_ref = read(path)
    errors, representations, transport_error = native_errors(packet)
    admitted, admitted_ref = read(ROOT / "audit/runtime/engineering/admitted-inputs" / (attempt + ".json"))
    payload = admitted["payload"]
    identity = payload["identity"]
    if identity.get("attempt_id") != attempt or identity.get("project_id") != packet["arguments"]["projectId"]:
        raise ValueError("Native packet and admitted task identity differ")
    for key in ("source_manifest_hash", "deployment_hash", "plan_hash", "data_request_hash", "config_id"):
        if type(identity.get(key)) is not str or HASH.fullmatch(identity[key]) is None:
            raise ValueError("Malformed admitted task identity")
    plan = payload["plan"]
    if (plan.get("scope") != "engineering" or plan.get("orders_enabled") is not False
            or plan.get("financial_metrics_enabled") is not False):
        raise ValueError("Expected a disabled-finance engineering plan")
    probe = plan["collection_probe"]
    selected = probe["collection_plan"]["fields"]
    catalog = probe["field_catalog"]
    if type(selected) is not list or len(set(selected)) != len(selected) or set(catalog) != set(selected):
        raise ValueError("Probe field list and frozen catalog differ")
    normalized = []
    for hash_value, node in errors:
        message = node["evalue"]
        marker = PREFIX + "; diagnostic="
        diagnostic = safe_diagnostic(parse(message[len(marker):]), enums, counts) if message.startswith(marker) else None
        normalized.append({
            "native_error_sha256": hash_value,
            "error_kind": "CollectionError" if node["ename"] == "CollectionError" else "other",
            "fixed_iteration_failure_message": message == PREFIX or message.startswith(marker),
            "diagnostic": diagnostic,
            "diagnostic_whitelist_validated": diagnostic is not None,
            "cause_classification": ("empty_dataframe_rejected_by_response_contract"
                if diagnostic and diagnostic["stage"] == "response_contract"
                and diagnostic["failure_code"] == "source_contract"
                and diagnostic["response_kind"] == "dataframe" and diagnostic["response_rows"] == 0
                else "unknown"),
            "supplier_or_platform_underlying_cause": None,
        })
    start = datetime.fromisoformat(probe["collection_plan"]["start"])
    first_end = start + timedelta(days=probe["collection_plan"]["calendar_days_per_request"])
    return {
        "attempt_id": attempt, "identity": identity,
        "native_packet": packet_ref, "admitted_input": admitted_ref,
        "native_transport_isError": transport_error,
        "direct_error_representations": representations,
        "deduplicated_native_error_count": len(errors),
        "native_execution_status": "runtime_error" if errors else "not_decided_by_this_diagnostic_program",
        "native_errors": normalized,
        "frozen_first_window": {"start": start.isoformat(), "end_exclusive": first_end.isoformat(),
            "basis": "frozen_collection_plan_not_an_endpoint_field_in_the_native_diagnostic"},
        "diagnostic_counter_scope": "single_failing_source_fetch_only; not entire Research execution",
        "entire_Research_totals": {"history_API_calls": None, "received_rows": None,
            "completed_collection_windows": None, "cache_only_replay_source_calls": None,
            "order_count": None, "financial_statistics": None},
        "probe_catalog": {"field_count": len(selected), "fields": sorted(selected),
            "financial_value_field_count": sum(spec.get("role") == "as_reported_financial_value" for spec in catalog.values())},
        "declared_fixed_price_scope": {"symbols": plan["symbol_resolution"]["tickers"],
            "start": plan["request_template"]["start"], "end_exclusive": plan["request_template"]["end"],
            "normalization": plan["request_template"]["normalization"],
            "complete_native_success_report_obtained": False},
        "financial_evidence": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-observation", action="append", default=[])
    args = parser.parse_args()
    observations = args.research_observation or ["audit/tool_observations/" + FIRST + "-research.json"]
    if len(observations) > 2 or len(set(observations)) != len(observations):
        raise ValueError("At most two distinct round Research observations are permitted")
    enums, counts, validator_ref = whitelist()
    current = [one_observation(ROOT / path, enums, counts) for path in observations]
    if len({item["attempt_id"] for item in current}) != len(current):
        raise ValueError("Duplicate round Research attempt")
    legacy = one_observation(ROOT / "audit/tool_observations" / (OLD + "-research.json"), enums, counts)
    if any(error["diagnostic"] is not None for error in legacy["native_errors"]):
        raise ValueError("Original failure evidence unexpectedly changed")
    source_catalog, source_ref = read(ROOT / "config/source_catalog.json")
    caps, caps_ref = read(ROOT / "audit/stage2_completion_data_capabilities.json")
    research, research_ref = read(ROOT / "config/research.json")
    final = research["final_evaluation"]
    if final["execution_enabled"] is not False or final["contamination"]["whole_window_is_untouched_independent_holdout"] is not False:
        raise ValueError("Final-test closure or prior exposure was changed")
    fields = source_catalog["fields"]
    financial_fields = sum(spec.get("role") == "as_reported_financial_value" for spec in fields.values())
    if caps["result"]["observed_source_field_count"] != len(fields) or caps["result"]["declared_financial_value_field_count"] != financial_fields:
        raise ValueError("Archived capability counts no longer match the source catalog")
    gaps = sorted(set(caps["result"]["gap_codes"]))
    report = {
        "schema_version": 1, "kind": "stage2_round002_metadata_only_data_certification",
        "status": "insufficient_evidence", "round_id": "stage2-cloud-round-002",
        "reproduction": {"program": PROGRAM,
            "program_sha256": digest(Path(__file__).read_bytes()),
            "command": ["python", "-B", PROGRAM]
                + [token for path in observations for token in ("--research-observation", path)],
            "provider_calls_performed": 0, "Research_executions_performed": 0, "LEAN_submissions_performed": 0},
        "input_refs": [source_ref, caps_ref, research_ref, validator_ref],
        "round_observations": current,
        "original_failure_preserved": {"attempt_id": OLD, "native_packet": legacy["native_packet"],
            "direct_error_representations": legacy["direct_error_representations"],
            "deduplicated_native_error_count": legacy["deduplicated_native_error_count"],
            "diagnostic_available": False, "underlying_cause": None,
            "same_cause_as_round002_established": False,
            "entire_Research_totals": legacy["entire_Research_totals"]},
        "field_capabilities": {"source_catalog_field_count": len(fields),
            "source_catalog_financial_value_field_count": financial_fields,
            "four_probe_fields_are_metadata_or_liquidity_only": all(item["probe_catalog"]["financial_value_field_count"] == 0 for item in current)},
        "coverage_assessment": {
            "historical_US200_2010_2023": {"certified": False,
                "missing": ["authoritative historical all-market inventory", "complete permanent-SID listing and classification histories",
                    "20 actual expected sessions for each formation", "complete frozen US200 membership and raw price/action coverage",
                    "authenticated historical availability and revision evidence"]},
            "two_symbol_2018_engineering": {"certified": False,
                "scope": "AAPL/MSFT 2018 engineering only", "complete_joint_native_success_established_by_this_report": False,
                "missing": ["completed same-version Research and LEAN receiver reports", "independent exact-version acceptance"],
                "not_full_historical_US200_evidence": True},
            "financial_vintages": {"certified": False,
                "missing": ["declared financial numerical value fields", "as-reported values and supplier revisions",
                    "actual public timestamps or documented date-only release gates", "actual vendor delivery and historical ingestion receipts"]},
        },
        "gap_codes": gaps,
        "clock_boundary": {"universe_selection_time": "modeled clock, not vendor receipt",
            "native_Time_EndTime": "source observations, not delivery or ingestion proof",
            "exchange_calendar": "expected sessions, not historical availability proof",
            "current_collection_time": "not historical vendor delivery or ingestion"},
        "external_risk": {"Morningstar_migration": {
            "classification": "external compatibility/reproducibility risk only; not diagnosed cause of either attempt",
            "official_documentation_dates_consistent": False,
            "migration_effective_date_for_this_project": None,
            "sources": ["https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/morningstar/us-fundamental-data",
                "https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/morningstar-migration"]}},
        "final_evaluation": {"execution_enabled": False, "independent_executor_configured": final["independent_executor_configured"],
            "reserved_start": final["start"], "reserved_end": final["end"],
            "previously_exposed_start": final["contamination"]["start"], "previously_exposed_end": final["contamination"]["end"],
            "whole_window_is_untouched_independent_holdout": False, "year2026_independence_certified": False},
        "full_historical_US200_certified": False, "actual_availability_certified": False,
        "financial_vintage_certified": False, "research_certified": False,
        "stage2_acceptance_issued": False, "row_values_exported": False,
        "financial_evidence": False, "IC_or_returns_computed": False,
    }
    output = ROOT / "audit/stage2_round002_data_certification.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": output.relative_to(ROOT).as_posix(), "sha256": digest(output.read_bytes()),
        "status": report["status"], "round_observation_count": len(current), "financial_evidence": False}, sort_keys=True))


if __name__ == "__main__":
    main()
