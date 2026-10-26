"""Cloud-only, no-order data reception checks for a registered engineering job.

No row values leave these functions. End times describe modeled LEAN delivery,
not certified historical vendor receipts. This is not a trading strategy.
"""
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import ast
import hashlib
import json
import re
import platform

import pandas as pd
import numpy as np

from .artifacts import canonical_json, content_hash
from .cache import CacheMiss, SharedDataCache
from .contracts import DataRequest, NY, RECORD_COLUMNS, aware
from .coverage import produce_engineering_coverage
from .engineering_tasks import EngineeringTaskPlan, _safe_collection_probe, validate_joint_report
from .quantconnect import ExchangeCalendar, ObjectStoreArtifactStore, QuantConnectHistoryProvider


STORE_PREFIX = "aqrp/engineering/v2"


def _runtime_environment(api):
    return {"python": platform.python_version(), "pandas": pd.__version__,
        "numpy": np.__version__, "lean": str(api.Globals.version)}


def load_task_input(path):
    """Read a generated JSON literal without executing the input as Python."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    if (len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign)
            or len(tree.body[0].targets) != 1 or not isinstance(tree.body[0].targets[0], ast.Name)
            or tree.body[0].targets[0].id != "TASK_INPUT_JSON"
            or not isinstance(tree.body[0].value, ast.Constant)
            or not isinstance(tree.body[0].value.value, str)):
        raise ValueError("Generated task input must be one inert JSON string assignment")
    return json.loads(tree.body[0].value.value)


def _request(raw):
    return DataRequest(raw["dataset"], tuple(raw["fields"]), tuple(raw["sids"]),
        raw["start"], raw["end"], raw["data_version"], raw["universe_hash"],
        raw["normalization"], raw["timezone"])


def _save(store, key, document):
    encoded = canonical_json(document)
    store.write_once(key, encoded)
    return {"key": key, "sha256": hashlib.sha256(encoded).hexdigest()}


def _load(store, reference):
    encoded = store.read_bytes(reference["key"])
    if hashlib.sha256(encoded).hexdigest() != reference["sha256"]:
        raise ValueError("Engineering cloud artifact integrity mismatch")
    return json.loads(encoded)


def verify_deployment(manifest, expected_hash, *, source_root=None):
    """Verify implementation bytes separately from the generated job input.

    The input contains the plan and therefore is explicitly outside the code
    manifest; its own bytes are pinned in the platform submission receipt.
    """
    if not isinstance(manifest, dict) or not manifest or content_hash(manifest) != expected_hash:
        raise ValueError("Missing or changed frozen source manifest")
    root = Path(source_root or Path(__file__).resolve().parents[1]).resolve()
    observed = {}
    for name, expected in sorted(manifest.items()):
        path = root / name
        if (not isinstance(name, str) or not name.endswith(".py") or "\\" in name
                or name.startswith("/") or ".." in name.split("/")
                or not path.resolve().is_relative_to(root)
                or name == "_engineering_task_input.py"):
            raise ValueError("Invalid implementation source path")
        actual = hashlib.sha256(path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()
        if actual != expected:
            raise ValueError("Cloud implementation differs from the frozen deployment")
        observed[name] = actual
    return content_hash(observed)


def _context(payload, stage, *, source_root=None):
    if not isinstance(payload, dict) or payload.get("identity", {}).get("stage") != stage:
        raise ValueError("Wrong engineering execution stage")
    identity = payload["identity"]
    _identity_shape(identity)
    plan = EngineeringTaskPlan.from_dict(payload["plan"], discovered_project_ids=(identity["project_id"],))
    document = plan.to_dict()
    if document["request_mode"] != "symbol_resolution":
        raise ValueError("This fixed producer requires its declared symbol resolver")
    expected = {"plan_hash": plan.hash, "project_id": document["project_id"],
        "source_manifest_hash": document["source_manifest_hash"],
        "deployment_hash": document["deployment_hash"], "data_request_hash": plan.request_hash}
    if any(identity.get(key) != value for key, value in expected.items()):
        raise ValueError("Engineering payload differs from its registered plan")
    if not identity.get("attempt_id") or not identity.get("config_id"):
        raise ValueError("A precharged registered engineering attempt is required")
    if identity["config_id"] != content_hash({"engineering_task_schema_version": 1, "plan": document}):
        raise ValueError("Engineering configuration identity changed")
    report_key = document["report_namespace"] + "/reports/" + plan.hash + "/" + stage + "/" + identity["attempt_id"] + ".json"
    if payload.get("report_key") != report_key:
        raise ValueError("Engineering result destination differs from the admitted attempt")
    verify_deployment(payload.get("deployment_manifest"), document["deployment_hash"], source_root=source_root)
    return plan, document, identity


def _identity_shape(identity):
    if not isinstance(identity, dict) or set(identity) != {"plan_hash", "config_id", "attempt_id", "stage", "project_id", "source_manifest_hash", "deployment_hash", "data_request_hash"}:
        raise ValueError("Unknown engineering identity metadata")
    for name in ("plan_hash", "config_id", "source_manifest_hash", "deployment_hash", "data_request_hash"):
        if not isinstance(identity[name], str) or re.fullmatch("[0-9a-f]{64}", identity[name]) is None:
            raise ValueError("Engineering identities must be canonical hashes")
    if (not isinstance(identity["attempt_id"], str) or re.fullmatch("[0-9a-f]{32}", identity["attempt_id"]) is None
            or type(identity["project_id"]) is not int or identity["project_id"] <= 0
            or identity["stage"] not in {"research", "lean"}):
        raise ValueError("Invalid engineering attempt metadata")


def _safe_evidence(evidence):
    allowed = {"coverage_report_ref", "cache_payload_refs", "coverage_certification_gaps",
        "lean_engine_version", "vendor_revision_known", "received_bar_ref", "corporate_action_ref",
        "unobserved_action_types_are_not_certified", "runtime_environment", "collection_probe"}
    if not isinstance(evidence, dict) or not set(evidence) <= allowed:
        raise ValueError("Unknown engineering evidence metadata")
    for name, value in evidence.items():
        if name == "collection_probe":
            _safe_collection_probe(value)
        elif name.endswith("_ref") or name == "cache_payload_refs":
            refs = value if name == "cache_payload_refs" else [value]
            if not isinstance(refs, list) or len(refs) > 5:
                raise ValueError("Invalid cloud evidence references")
            for ref in refs:
                if (not isinstance(ref, dict) or set(ref) != {"key", "sha256"}
                        or not isinstance(ref["key"], str) or not isinstance(ref["sha256"], str)
                        or re.fullmatch("[0-9a-f]{64}", ref["sha256"]) is None):
                    raise ValueError("Only content-addressed evidence metadata can leave cloud")
        elif name == "coverage_certification_gaps":
            from .coverage import RESEARCH_GAPS
            if value != list(RESEARCH_GAPS):
                raise ValueError("Coverage gaps must be the fixed program observations")
        elif name == "lean_engine_version":
            if not isinstance(value, str) or not value or len(value) > 100 or "\n" in value:
                raise ValueError("Invalid engine version metadata")
        elif name == "runtime_environment":
            if (not isinstance(value, dict) or set(value) != {"python", "pandas", "numpy", "lean"}
                    or any(not isinstance(version, str) or not version or len(version) > 100 or "\n" in version or "\r" in version for version in value.values())):
                raise ValueError("Only runtime version strings can leave cloud")
        elif name == "vendor_revision_known" and value is not False:
            raise ValueError("Vendor revision has not been certified")
        elif name == "unobserved_action_types_are_not_certified" and value is not True:
            raise ValueError("Unobserved corporate actions are not certified")


def _cloud_store(object_store, *, read_only=False):
    return ObjectStoreArtifactStore(object_store, STORE_PREFIX,
        read_only=read_only, single_producer=not read_only)


def _resolution(store, plan, symbols):
    document = plan.to_dict()
    resolver = document["symbol_resolution"]
    if sorted(symbols) != resolver["tickers"]:
        raise ValueError("Resolved tickers differ from the fixed engineering plan")
    entries = [{"ticker": ticker, "sid": str(symbol.id)} for ticker, symbol in sorted(symbols.items())]
    registry = {"schema_version": 1, "method": resolver["method"], "as_of": resolver["as_of"],
        "symbols": entries, "purpose": "fixed_engineering_fixture_not_historical_universe"}
    sids = tuple(entry["sid"] for entry in entries)
    if len(set(sids)) != 2 or any(not sid.strip() for sid in sids):
        raise ValueError("Engineering fixture did not resolve two permanent identities")
    template = document["request_template"]
    request = _request(dict(template, sids=list(sids)))
    namespace = document["report_namespace"] + "/resolutions/" + plan.hash
    registry_ref = _save(store, namespace + "/" + content_hash(registry) + ".json", registry)
    request_ref = _save(store, namespace + "/" + content_hash(request.identity()) + ".json", request.identity())
    references = {"resolved_registry_ref": registry_ref, "resolved_request_ref": request_ref}
    return request, {"resolved_request_hash": request_ref["sha256"],
        "resolved_registry_hash": registry_ref["sha256"], "resolution_artifact_hash": content_hash(references),
        "tickers": sorted(symbols), "ticker_count": 2, "permanent_sid_count": 2,
        "method": resolver["method"], **references}


def _read_resolution(store, plan, resolution):
    references = {key: resolution[key] for key in ("resolved_registry_ref", "resolved_request_ref")}
    if (content_hash(references) != resolution["resolution_artifact_hash"]
            or references["resolved_registry_ref"]["sha256"] != resolution["resolved_registry_hash"]
            or references["resolved_request_ref"]["sha256"] != resolution["resolved_request_hash"]):
        raise ValueError("Engineering resolution metadata changed")
    registry, raw_request = (_load(store, references[name]) for name in ("resolved_registry_ref", "resolved_request_ref"))
    document = plan.to_dict()
    entries = registry["symbols"]
    if (sorted(entry["ticker"] for entry in entries) != document["symbol_resolution"]["tickers"]
            or registry["method"] != document["symbol_resolution"]["method"]
            or registry["as_of"] != document["symbol_resolution"]["as_of"]
            or len(entries) != 2 or len({entry["sid"] for entry in entries}) != 2):
        raise ValueError("Resolved identities differ from the fixed fixture")
    request = _request(raw_request)
    if request.identity() != _request(dict(document["request_template"], sids=[entry["sid"] for entry in entries])).identity():
        raise ValueError("Resolved data request differs from the frozen template")
    return request, {entry["ticker"]: entry["sid"] for entry in entries}


def _finish(store, payload, checks, statistics, resolution, *, evidence=None):
    _identity_shape(payload["identity"])
    allowed = ({"record_count", "history_calls_first", "history_calls_second", "expected_formation_count"}
        if payload["identity"]["stage"] == "research" else
        {"data_event_count", "slice_count", "orders_submitted", "runtime_error_count", "dividend_event_count", "split_event_count", "delisting_event_count", "mapping_event_count"})
    if not isinstance(statistics, dict) or not set(statistics) <= allowed or any(type(value) is not int or value < 0 for value in statistics.values()):
        raise ValueError("Only nonnegative engineering counts can leave cloud")
    _safe_evidence(evidence or {})
    resolution_keys = {"resolved_request_hash", "resolved_registry_hash", "resolution_artifact_hash", "tickers", "ticker_count", "permanent_sid_count", "method", "resolved_registry_ref", "resolved_request_ref"}
    if not isinstance(resolution, dict) or set(resolution) != resolution_keys:
        raise ValueError("Only fixed resolution metadata can leave cloud")
    for name in ("resolved_request_hash", "resolved_registry_hash", "resolution_artifact_hash"):
        if not isinstance(resolution[name], str) or re.fullmatch("[0-9a-f]{64}", resolution[name]) is None:
            raise ValueError("Resolution identities must be canonical hashes")
    if (resolution["tickers"] != ["AAPL", "MSFT"] or type(resolution["ticker_count"]) is not int
            or resolution["ticker_count"] != 2 or type(resolution["permanent_sid_count"]) is not int
            or resolution["permanent_sid_count"] != 2
            or resolution["method"] != "QuantBook.add_equity/as-of fixed fixture"):
        raise ValueError("Resolution differs from the fixed engineering fixture")
    _safe_evidence({"cache_payload_refs": [resolution["resolved_registry_ref"], resolution["resolved_request_ref"]]})
    references = {key: resolution[key] for key in ("resolved_registry_ref", "resolved_request_ref")}
    if (content_hash(references) != resolution["resolution_artifact_hash"]
            or resolution["resolved_registry_ref"]["sha256"] != resolution["resolved_registry_hash"]
            or resolution["resolved_request_ref"]["sha256"] != resolution["resolved_request_hash"]):
        raise ValueError("Resolution reference bundle changed")
    required = payload["plan"]["required_checks"][payload["identity"]["stage"]]
    if not set(required) <= set(checks) or any(type(value) is not bool for value in checks.values()):
        raise ValueError("Fixed engineering observations are missing")
    report = {"schema_version": 1, "identity": payload["identity"],
        "status": "completed" if all(checks.values()) else "failed", "terminal": True,
        "checks": checks, "statistics": statistics, "resolution": resolution,
        "market_values_exported": False, "economic_factor_tested": False,
        "final_data_accessed": False, "full_US200_coverage_certified": False,
        "actual_availability_verified": False, "evidence": evidence or {}}
    validate_joint_report(report, payload["plan"])
    reference = _save(store, payload["report_key"], report)
    return {"cloud_report": report, "report_ref": reference}


def _run_collection_probe(qb, store, plan, payload, *, api):
    """One fixed substep of the precharged parent, never a second task/ledger."""
    from .collection import HistoricalCollectionPlan, HistoricalSnapshotCollector
    from .historical_source import QuantConnectSnapshotSource
    document = plan.to_dict()
    raw = document["collection_probe"]
    child = HistoricalCollectionPlan.from_dict(raw["collection_plan"], field_catalog=raw["field_catalog"])
    key = document["report_namespace"] + "/collection-probes/" + plan.hash + "/" + payload["identity"]["attempt_id"] + ".json"
    reader = HistoricalSnapshotCollector(store, None, child)
    if store.exists(key):
        receipt = json.loads(store.read_bytes(key))
        if (not isinstance(receipt, dict) or set(receipt) != {"identity", "collection_plan_hash", "first", "cache_only_replay"}
                or receipt["identity"] != payload["identity"] or receipt["collection_plan_hash"] != child.hash):
            raise ValueError("Saved joint collection receipt differs from this parent")
        first, second = receipt["first"], receipt["cache_only_replay"]
        observed = reader.collect()
        if (not isinstance(first, dict) or set(first) != set(observed) or second != observed
                or any(first[name] != value for name, value in observed.items() if name not in {"provider_calls", "reused_windows"})):
            raise ValueError("Saved joint collection receipt differs from verified cache")
    else:
        source = QuantConnectSnapshotSource(qb, child.field_catalog, api=api)
        first = HistoricalSnapshotCollector(store, source, child).collect()
        second = reader.collect()
        receipt = {"identity": payload["identity"], "collection_plan_hash": child.hash,
                   "first": first, "cache_only_replay": second}
    reference = _save(store, key, receipt)
    summary = {"schema_version": 1, "plan_hash": child.hash, "receipt_ref": reference,
        "window_count": first["window_count"], "record_count": first["record_count"],
        "source_fetch_calls": first["provider_calls"], "reused_windows": first["reused_windows"],
        "empty_windows": first["empty_windows"], "cache_only_source_fetch_calls": second["provider_calls"],
        "missing_values": first["missing_values"], "full_historical_US200_certified": False,
        "actual_availability_certified": False, "research_certified": False,
        "row_values_exported": False, "financial_vintage_certified": False}
    _safe_collection_probe(summary)
    return summary


def run_research_task(payload, *, api=None, quantbook_factory=None):
    """Execute one admitted Research job, prefetch once, then read only cache."""
    if api is None:
        import AlgorithmImports as api
    if quantbook_factory is None:
        from QuantConnect.Research import QuantBook
        quantbook_factory = QuantBook
    plan, document, identity = _context(payload, "research")
    qb = quantbook_factory()
    qb.set_time_zone("America/New_York")
    frontier = aware(document["symbol_resolution"]["as_of"])
    qb.set_start_date(frontier.year, frontier.month, frontier.day)
    next_day = frontier + pd.Timedelta(days=1)
    qb.set_end_date(next_day.year, next_day.month, next_day.day)
    qb.settings.daily_precise_end_time = True
    securities = {ticker: qb.add_equity(ticker, api.Resolution.DAILY, fill_forward=False,
        data_normalization_mode=api.DataNormalizationMode.RAW) for ticker in document["symbol_resolution"]["tickers"]}
    store = _cloud_store(qb.object_store)
    request, resolution = _resolution(store, plan, {name: security.symbol for name, security in securities.items()})
    provider = QuantConnectHistoryProvider(qb, {str(s.symbol.id): s.symbol for s in securities.values()}, request.data_version, api=api)
    cache = SharedDataCache(store, provider)
    first = cache.prefetch(request)
    first_calls = provider.fetch_call_count
    second = cache.prefetch(request)
    records = cache.read(request, allow_fetch=False)
    second_calls = provider.fetch_call_count - first_calls
    consumer = SharedDataCache(_cloud_store(qb.object_store, read_only=True))
    copied = consumer.read(request, allow_fetch=False)
    cache_miss_rejected = False
    try:
        consumer.read(replace(request, data_version=request.data_version + "-negative-unprefetched"), allow_fetch=False)
    except CacheMiss:
        cache_miss_rejected = True
    readonly_rejected = False
    try:
        consumer.store.write_once("forbidden-readonly-probe.json", b"{}")
    except PermissionError:
        readonly_rejected = True
    final_rejected = False
    try:
        replace(request, end=datetime(2024, 1, 2, tzinfo=NY))
    except ValueError:
        final_rejected = True
    window = document["observation_window"]
    calendar = ExchangeCalendar(next(iter(securities.values())).exchange.hours)
    schedule = calendar.decisions(aware(window["start"]), aware(window["end_exclusive"]))
    expected = dict(zip(schedule.formation_at, schedule.session_close))
    membership = pd.DataFrame(True, index=pd.DatetimeIndex(schedule.formation_at), columns=request.sids)
    source_refs = []
    for part in cache.partitions(request):
        for field in part.fields:
            unit = replace(part, fields=(field,))
            manifest = json.loads(store.read_bytes("feature-cache/v1/manifests/" + unit.key + ".json"))
            source_refs.append({"key": manifest["payload"], "sha256": manifest["sha256"]})
    coverage = produce_engineering_coverage(store, request=request, records=records,
        decisions=tuple(schedule.formation_at), sids=request.sids,
        policies={field: "exact_session" for field in request.fields}, expected_events=expected,
        membership=membership, provenance=provider.provenance, subject_hash=plan.hash,
        source_hash=identity["deployment_hash"], source_refs=source_refs)
    checks = {"source_snapshot_matches": True, "raw_data_received": not records.empty,
        "second_prefetch_no_history": second_calls == 0, "same_partition_ids": first == second,
        "cache_only_consumer": copied.equals(records) and cache_miss_rejected,
        "read_only_write_rejected": readonly_rejected, "final_request_rejected": final_rejected,
        "coverage_observed_complete": coverage["status"] == "passed",
        "development_only": bool((records.event_time.dt.year == 2018).all()),
        "symbol_registry_resolved": resolution["permanent_sid_count"] == 2}
    statistics = {"record_count": len(records), "history_calls_first": first_calls,
        "history_calls_second": second_calls, "expected_formation_count": len(schedule)}
    evidence = {"coverage_report_ref": coverage["report_ref"], "cache_payload_refs": source_refs,
                  "coverage_certification_gaps": coverage["research_certification_gaps"],
                  "lean_engine_version": str(api.Globals.version), "vendor_revision_known": False,
                  "runtime_environment": _runtime_environment(api)}
    if document["schema_version"] == 2:
        summary = _run_collection_probe(qb, store, plan, payload, api=api)
        evidence["collection_probe"] = summary
        checks.update(collection_windows_completed=summary["window_count"] == 40,
                      collection_cache_only_replay=summary["cache_only_source_fetch_calls"] == 0,
                      collection_nonempty=summary["record_count"] > 0)
    return _finish(store, payload, checks, statistics, resolution, evidence=evidence)


def initialize_receiver(algorithm, payload, *, api=None):
    """Initialize a dedicated no-order LEAN data receiver using Research refs."""
    if api is None:
        import AlgorithmImports as api
    plan, document, identity = _context(payload, "lean")
    store = _cloud_store(algorithm.object_store)
    request, registry = _read_resolution(store, plan, payload["research_resolution"])
    window = document["observation_window"]
    start, end = aware(window["start"]), aware(window["end_exclusive"]) - pd.Timedelta(days=1)
    algorithm.set_time_zone("America/New_York")
    algorithm.settings.daily_precise_end_time = True
    algorithm.set_start_date(start.year, start.month, start.day)
    algorithm.set_end_date(end.year, end.month, end.day)
    algorithm.set_cash(100000)  # Engineering cash only; never invested.
    securities = {ticker: algorithm.add_equity(ticker, api.Resolution.DAILY, fill_forward=False,
        data_normalization_mode=api.DataNormalizationMode.RAW) for ticker in sorted(registry)}
    if any(str(security.symbol.id) != registry[ticker] for ticker, security in securities.items()):
        raise ValueError("LEAN and Research resolved different permanent identities")
    algorithm.set_benchmark(securities["AAPL"].symbol)
    algorithm._engineering_state = {"payload": payload, "plan": plan, "request": request,
        "store": store, "securities": securities, "records": [], "bar_keys": [],
        "actions": [], "order_events": 0, "slices": 0, "engine_version": str(api.Globals.version),
        "runtime_environment": _runtime_environment(api)}


def receive_slice(algorithm, data):
    state = algorithm._engineering_state
    state["slices"] += 1
    received = pd.Timestamp(algorithm.time)
    received = received.tz_localize(NY) if received.tzinfo is None else received.tz_convert(NY)
    if received.year != 2018:
        raise ValueError("Engineering receiver left its frozen development year")
    expected_sids = {str(security.symbol.id) for security in state["securities"].values()}
    for collection in ("bars", "dividends", "splits", "delistings", "symbol_changed_events"):
        if {str(symbol.id) for symbol in getattr(data, collection).keys()} - expected_sids:
            raise ValueError("Engineering slice contains an undeclared identity")
    for ticker, security in state["securities"].items():
        symbol, sid = security.symbol, str(security.symbol.id)
        bar = data.bars.get(symbol)
        if bar is not None:
            if str(bar.symbol.id) != sid:
                raise ValueError("Bar identity differs from its declared dictionary key")
            event = pd.Timestamp(bar.end_time)
            event = event.tz_localize(NY) if event.tzinfo is None else event.tz_convert(NY)
            if event != ExchangeCalendar(security.exchange.hours).close_on(event) or event > received:
                raise ValueError("LEAN bar time differs from the completed exchange session")
            state["bar_keys"].append((sid, event.isoformat()))
            for field in state["request"].fields:
                state["records"].append([sid, field, event.isoformat(), received.isoformat(),
                    float(getattr(bar, field)), state["request"].data_version])
        for name in ("dividends", "splits", "delistings", "symbol_changed_events"):
            action = getattr(data, name).get(symbol)
            if action is None:
                continue
            if str(action.symbol.id) != sid:
                raise ValueError("Corporate action identity differs from its dictionary key")
            item = {"kind": name, "sid": sid, "received_at": received.isoformat()}
            for attribute in ("time", "end_time"):
                if hasattr(action, attribute):
                    stamp = pd.Timestamp(getattr(action, attribute))
                    stamp = stamp.tz_localize(NY) if stamp.tzinfo is None else stamp.tz_convert(NY)
                    if pd.isna(stamp) or stamp > received:
                        raise ValueError("Corporate action event follows its modeled receipt")
                    item[attribute] = stamp.isoformat()
            for attribute in ("distribution", "split_factor", "type", "old_symbol", "new_symbol"):
                if hasattr(action, attribute):
                    value = getattr(action, attribute)
                    item[attribute] = float(value) if attribute in {"distribution", "split_factor"} else str(value)
            state["actions"].append(item)


def finish_receiver(algorithm):
    state = algorithm._engineering_state
    payload, request, store = state["payload"], state["request"], state["store"]
    document = state["plan"].to_dict()
    window = document["observation_window"]
    expected = set()
    for security in state["securities"].values():
        calendar = ExchangeCalendar(security.exchange.hours)
        schedule = calendar.decisions(aware(window["start"]), aware(window["end_exclusive"]))
        expected.update((str(security.symbol.id), calendar.close_on(time).isoformat()) for time in schedule.formation_at)
    actual = set(state["bar_keys"])
    rows = {"schema_version": 1, "request_hash": request.key, "columns": list(RECORD_COLUMNS), "rows": state["records"]}
    actions = {"schema_version": 1, "availability_basis": "modeled_LEAN_event_delivery", "events": state["actions"]}
    namespace = document["report_namespace"] + "/received/" + payload["identity"]["attempt_id"]
    raw_ref = _save(store, namespace + "/" + content_hash(rows) + ".json", rows)
    action_ref = _save(store, namespace + "/" + content_hash(actions) + ".json", actions)
    orders = len(list(algorithm.transactions.get_orders()))
    dividend_count = sum(item["kind"] == "dividends" for item in state["actions"])
    checks = {"source_snapshot_matches": True, "raw_data_received": bool(actual),
        "complete_expected_bars": bool(expected) and actual == expected and len(actual) == len(state["bar_keys"]),
        "no_orders": orders == 0 and state["order_events"] == 0,
        "development_only": all(aware(item[2]).year == 2018 for item in state["records"]),
        "symbol_registry_resolved": True, "corporate_action_received": dividend_count > 0}
    statistics = {"data_event_count": len(state["bar_keys"]), "slice_count": state["slices"],
        "orders_submitted": orders, "runtime_error_count": 0, "dividend_event_count": dividend_count,
        "split_event_count": sum(item["kind"] == "splits" for item in state["actions"]),
        "delisting_event_count": sum(item["kind"] == "delistings" for item in state["actions"]),
        "mapping_event_count": sum(item["kind"] == "symbol_changed_events" for item in state["actions"])}
    return _finish(store, payload, checks, statistics, payload["research_resolution"],
        evidence={"received_bar_ref": raw_ref, "corporate_action_ref": action_ref,
                  "unobserved_action_types_are_not_certified": True,
                  "lean_engine_version": state["engine_version"], "vendor_revision_known": False,
                  "runtime_environment": state["runtime_environment"]})
