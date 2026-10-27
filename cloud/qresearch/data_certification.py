"""Bounded cloud evidence diagnostics, never an approval of vendor provenance.

This module reuses completed ingestion batches and the shared US200 ranker.
It verifies declared rows against an explicit calendar and frozen scope. None
of those declarations authenticates a historical vendor receipt. Reports are
metadata-only; no result here opens ResearchEngine or the final-test gate.
"""
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re

import pandas as pd

from .artifacts import canonical_json, content_hash
from .contracts import DEVELOPMENT_END, aware
from .ingestion import HistoricalBatchIngestor, IngestionError, resolve_historical_sid
from .quantconnect import ExchangeCalendar
from .universe import INCLUDED, select_liquid_universe


class DataCertificationError(ValueError):
    """Evidence is malformed or inconsistent; messages contain no row values."""


_HASH = re.compile(r"[a-f0-9]{64}")
_PATH = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*")
_TEXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,159}")
_PLAN_KEYS = {"schema_version", "plan_id", "start", "end_exclusive", "warmup_start",
              "timezone", "source_manifest_hash", "data_version", "ingestion_namespace",
              "financial_catalog", "universe_size", "liquidity_lookback_sessions"}
_TABLES = {"membership", "prices", "security_master", "corporate_actions"}
_INPUT = "data-certification/v1/inputs/"
_REPORT = "data-certification/v1/reports/"
_CONTEXT = "data-certification/v1/contexts/"
_LIMIT = 250000
_GAPS = (
    "authoritative_all_market_inventory_receipt_not_supported",
    "authenticated_vendor_revision_receipt_not_supported",
    "authenticated_historical_delivery_and_ingestion_receipt_not_supported",
    "authoritative_security_master_and_action_coverage_receipt_not_supported",
)
_COLUMNS = {
    "membership": {"formation_at", "sids"},
    "prices": {"sid", "session", "available_at", "open", "high", "low", "close", "volume", "normalization", "source_revision"},
    "security_master": {"sid", "ticker", "effective_from", "effective_to", "available_at", "instrument_type", "listed", "exchange"},
    "corporate_actions": {"sid", "event_time", "available_at", "kind", "source_revision"},
}
_KINDS = ("dividend", "split", "mapping", "delisting", "ipo")
_COUNTS = ("formation_count", "expected_member_cells", "observed_member_cells", "liquidity_record_count",
    "financial_record_count", "security_master_record_count", "price_record_count", "corporate_action_record_count",
    "financial_expected_cells", "financial_available_cells", "financial_missing_cells", "missing_actual_timing_rows",
    "incomplete_warmup_formations", "unavailable_liquidity_formations", "membership_mismatch_formations",
    "missing_or_ambiguous_security_master_cells", "ambiguous_mapping_cells", "inconsistent_classification_cells",
    "price_expected_cells", "price_observed_cells", "price_missing_cells", "unavailable_financial_formations",
    "ambiguous_financial_cells", "known_eligible_candidate_expected_cells", "missing_candidate_session_cells",
    "incomplete_candidate_histories") + tuple(kind + "_event_count" for kind in _KINDS)
_CHECKS = {"all_required_input_components_present", "complete_calendar_formations", "complete_twenty_session_warmup",
    "ranked_membership_matches", "historical_classification_and_mapping_consistent", "raw_price_scope_complete",
    "financial_fields_declared", "financial_scope_coverage_complete", "declared_actual_timing_complete",
    "historical_all_market_origin_declared", "corporate_action_sids_known", "all_known_eligible_candidate_histories_complete"}
_FALSE_FLAGS = {"vendor_provenance_authenticated", "full_historical_US200_certified", "actual_availability_certified",
                "financial_vintage_certified", "research_certified", "row_values_exported", "financial_evidence"}
_REPORT_KEYS = {"schema_version", "kind", "plan_hash", "source_manifest_hash", "ingestion_namespace", "data_version_hash",
    "financial_catalog_hash", "scope_start", "scope_end_exclusive", "warmup_start", "universe_size", "liquidity_lookback_sessions",
    "status", "checks", "counts", "evidence_refs", "calendar_hash", "ranked_membership_hash", "gap_codes", "synthetic", "context_ref"} | _FALSE_FLAGS


def _fail(message):
    raise DataCertificationError(message) from None


def _digest(value):
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _clock(value, *, endpoint=False):
    try:
        stamp = aware(value)
        if pd.isna(stamp) or (stamp > DEVELOPMENT_END if endpoint else stamp >= DEVELOPMENT_END):
            raise ValueError
        return stamp
    except (ValueError, TypeError, OverflowError):
        _fail("Explicit finite development timestamps are required")


def _identity(value):
    if (not isinstance(value, str) or not value or len(value) > 256 or value.strip() != value
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        _fail("A bounded nonempty source identity is required")
    return value


def _boundary(store, synthetic):
    if type(synthetic) is not bool:
        _fail("Explicit synthetic classification is required")
    if not synthetic and getattr(store, "residency", None) != "quantconnect_cloud":
        _fail("Real certification inputs must remain in QuantConnect Cloud")


@dataclass(frozen=True, init=False)
class DataCertificationPlan:
    """Exact scope and input identities; no tunable ranking or approval flags."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use DataCertificationPlan.from_dict")

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict) or set(raw) != _PLAN_KEYS:
            _fail("A complete certification plan without overrides is required")
        try:
            value = json.loads(canonical_json(raw))
        except (ValueError, TypeError, UnicodeError):
            _fail("Certification plans require finite JSON values")
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["timezone"] != "America/New_York"
                or type(value["universe_size"]) is not int or value["universe_size"] != 200
                or type(value["liquidity_lookback_sessions"]) is not int or value["liquidity_lookback_sessions"] != 20):
            _fail("Only the fixed NY US200 and 20-session rule is supported")
        for name in ("plan_id", "data_version"):
            if not isinstance(value[name], str) or _TEXT.fullmatch(value[name]) is None:
                _fail("Bounded explicit plan and source versions are required")
        if not all(_digest(value[name]) for name in ("source_manifest_hash", "ingestion_namespace")):
            _fail("Pin implementation and ingestion identities with SHA-256")
        start, end, warm = (_clock(value["start"]), _clock(value["end_exclusive"], endpoint=True),
                            _clock(value["warmup_start"]))
        if not warm < start < end or any(x != x.normalize() for x in (warm, start, end)):
            _fail("Explicit NY-midnight warmup and nonempty development scope are required")
        value.update(start=start.isoformat(), end_exclusive=end.isoformat(), warmup_start=warm.isoformat())
        catalog = value["financial_catalog"]
        if not isinstance(catalog, dict) or len(catalog) > 64:
            _fail("A bounded frozen financial field catalog is required")
        for path, spec in catalog.items():
            if (not isinstance(path, str) or len(path) > 256 or _PATH.fullmatch(path) is None
                    or path.lower().startswith(("label", "target", "future_", "forward_"))
                    or not isinstance(spec, dict) or set(spec) != {"unit", "period_accessor"}
                    or any(not isinstance(spec[key], str) or _TEXT.fullmatch(spec[key]) is None for key in spec)):
                _fail("Pin exact financial paths, units and period accessors")
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json(value))
        return result

    def to_dict(self):
        return json.loads(self._encoded)

    @property
    def hash(self):
        return sha256(self._encoded).hexdigest()


def store_certification_table(store, plan, component, rows, *, synthetic=False):
    """Store audit input in cloud, or an explicitly synthetic fixture store."""
    _boundary(store, synthetic)
    if not isinstance(plan, DataCertificationPlan) or component not in _TABLES:
        _fail("A frozen plan and registered evidence component are required")
    if not isinstance(rows, list) or len(rows) > _LIMIT:
        _fail("Stream bounded certification partitions; do not truncate rows")
    try:
        raw = canonical_json({"schema_version": 1, "component": component,
                              "plan_hash": plan.hash, "rows": rows})
    except (ValueError, TypeError, UnicodeError):
        _fail("Certification input rows require finite JSON values")
    digest = sha256(raw).hexdigest()
    key = _INPUT + digest + ".json"
    store.write_once(key, raw)
    return {"key": key, "sha256": digest}


def _references(references):
    if not isinstance(references, (list, tuple)) or len(references) > 10000:
        _fail("A bounded list of immutable references is required")
    seen = set()
    result = []
    for item in references:
        if (not isinstance(item, dict) or set(item) != {"key", "sha256"}
                or not _digest(item["sha256"]) or not isinstance(item["key"], str)
                or item["key"] in seen):
            _fail("References must be unique immutable key/hash objects")
        seen.add(item["key"])
        result.append(dict(item))
    return sorted(result, key=lambda x: x["key"])


def _tables(store, plan, refs, component):
    result = []
    for ref in refs:
        if ref["key"] != _INPUT + ref["sha256"] + ".json":
            _fail("Certification tables require their exact content-addressed key")
        try:
            raw = store.read_bytes(ref["key"])
            envelope = json.loads(raw)
        except (OSError, ValueError, TypeError, KeyError):
            _fail("Referenced certification table is unavailable or invalid")
        if (sha256(raw).hexdigest() != ref["sha256"]
                or not isinstance(envelope, dict) or set(envelope) != {"schema_version", "component", "plan_hash", "rows"}
                or type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1
                or envelope["component"] != component or envelope["plan_hash"] != plan.hash
                or not isinstance(envelope["rows"], list)):
            _fail("Certification table identity or bytes changed")
        try:
            if canonical_json(envelope) != raw:
                raise ValueError
        except (ValueError, TypeError, UnicodeError):
            _fail("Certification tables require finite canonical JSON")
        result.extend(envelope["rows"])
        if len(result) > _LIMIT:
            _fail("Certification scope exceeds the bounded row limit; use explicit partitions")
    if any(not isinstance(row, dict) or set(row) != _COLUMNS[component] for row in result):
        _fail("Evidence rows must match the exact registered component schema")
    return result


def _source_rows(ingestor, references, kind):
    if not references:
        return []
    try:
        rows = ingestor._combined_records(references, kind)
    except (ValueError, TypeError, OSError, KeyError):
        _fail("Completed ingestion evidence is inconsistent or unavailable")
    if len(rows) > _LIMIT:
        _fail("Certification scope exceeds the bounded row limit; use explicit partitions")
    return rows


class _VerifiedBatchView:
    """One verified read per source; use the original ingestion calculations."""
    liquidity_rows_asof = HistoricalBatchIngestor.liquidity_rows_asof
    financial_records_asof = HistoricalBatchIngestor.financial_records_asof
    _gaps = staticmethod(HistoricalBatchIngestor._gaps)

    def __init__(self, liquid, financial):
        # A source's then-known listing clock is a lower bound for its session
        # observations, not merely for the later formation clock. Keep unknown
        # listing evidence in the view so the shared gap check still rejects it.
        # Session stamps denote completed exchange-session closes; equality is
        # included, while a listing after that close starts with a later close.
        # Original batches, references and input counts remain unchanged.
        post_listing = [row for row in liquid if row["listing_effective_at"] is None
            or _clock(row["listing_effective_at"]) <= _clock(row["session"])]
        self._rows = {"liquidity": post_listing, "financial": financial}

    def _combined_records(self, references, kind):
        return self._rows[kind]


def _rows(plan, tables):
    """Normalize private rows; never return row values to the caller."""
    value = plan.to_dict()
    start, end, warm = _clock(value["start"]), _clock(value["end_exclusive"], endpoint=True), _clock(value["warmup_start"])
    members, prices, masters, actions = {}, {}, [], []
    for row in tables["membership"]:
        formation = _clock(row["formation_at"])
        sids = row["sids"]
        if (not start <= formation < end or formation in members or not isinstance(sids, list)
                or len(sids) != 200 or len(set(_identity(x) for x in sids)) != 200):
            _fail("Membership must contain exactly 200 unique permanent identities per formation")
        members[formation] = tuple(sids)
    for row in tables["prices"]:
        sid, session, available = _identity(row["sid"]), _clock(row["session"]), _clock(row["available_at"])
        if (not warm <= session < end or not session <= available or row["normalization"] != "raw"
                or (sid, session) in prices):
            _fail("Raw price sessions and vintages must be unique, causal and inside the declared scope")
        _identity(row["source_revision"])
        values = [row[name] for name in ("open", "high", "low", "close", "volume")]
        try:
            valid_numbers = all(not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in values)
        except (OverflowError, ValueError, TypeError):
            valid_numbers = False
        if not valid_numbers:
            _fail("Raw price observations require finite nonnegative real values")
        if min(values[:4]) <= 0 or row["high"] < max(row["open"], row["low"], row["close"]) or row["low"] > min(row["open"], row["close"]):
            _fail("Raw OHLC relationships are inconsistent")
        prices[(sid, session)] = available
    seen = set()
    for row in tables["security_master"]:
        item = dict(row)
        item["sid"], item["ticker"] = _identity(row["sid"]), _identity(row["ticker"])
        item["effective_from"], item["available_at"] = _clock(row["effective_from"]), _clock(row["available_at"])
        item["effective_to"] = _clock(row["effective_to"]) if row["effective_to"] is not None else None
        if (item["effective_to"] is not None and item["effective_to"] <= item["effective_from"]
                or row["listed"] is not None and type(row["listed"]) is not bool):
            _fail("Historical security intervals or listed state are invalid")
        if row["instrument_type"] is not None:
            _identity(row["instrument_type"])
        if row["exchange"] is not None:
            _identity(row["exchange"])
        identity = (item["sid"], item["ticker"], item["effective_from"], item["available_at"])
        if identity in seen:
            _fail("Duplicate historical security identity")
        seen.add(identity)
        masters.append(item)
    seen = set()
    for row in tables["corporate_actions"]:
        sid, event, receipt = _identity(row["sid"]), _clock(row["event_time"]), _clock(row["available_at"])
        _identity(row["source_revision"])
        if not isinstance(row["kind"], str) or row["kind"] not in _KINDS:
            _fail("Corporate-action kind is unsupported")
        identity = (sid, event, row["kind"], receipt)
        if (not warm <= event < end or event > receipt or identity in seen):
            _fail("Corporate-action identities or event ordering are invalid")
        seen.add(identity)
        actions.append((sid, event, receipt, row["kind"]))
    return members, prices, masters, actions


def audit_data_certification(store, plan, *, calendar, ingestor=None, liquidity_refs=(), financial_refs=(),
        membership_refs=(), price_refs=(), security_master_refs=(), corporate_action_refs=(), synthetic=False):
    """Compute bounded observed conformance and permanent certification gaps.

    Calendar is the exchange adapter, not caller-provided counts. An actual
    authenticated inventory/revision/delivery protocol is not available in the
    current source adapter, so even complete declared evidence is NOT certified.
    Missing financials never change the ranked membership or select rank201.
    """
    _boundary(store, synthetic)
    if not isinstance(plan, DataCertificationPlan) or not synthetic and not isinstance(calendar, ExchangeCalendar):
        _fail("A frozen plan and real exchange calendar adapter are required")
    v = plan.to_dict()
    refs = {"liquidity": _references(liquidity_refs), "financial": _references(financial_refs),
            "membership": _references(membership_refs), "prices": _references(price_refs),
            "security_master": _references(security_master_refs), "corporate_actions": _references(corporate_action_refs)}
    keys = [item["key"] for items in refs.values() for item in items]
    if len(keys) != len(set(keys)):
        _fail("One input reference cannot serve multiple evidence components")
    if ingestor is not None and (not isinstance(ingestor, HistoricalBatchIngestor) or ingestor.store is not store
            or ingestor.synthetic != synthetic or ingestor.namespace != v["ingestion_namespace"]
            or ingestor.data_version != v["data_version"] or ingestor.financial_catalog != v["financial_catalog"]):
        _fail("Ingestion source, store, catalog or synthetic identity differs from the frozen plan")
    if ingestor is None and (refs["liquidity"] or refs["financial"]):
        _fail("Source batch references require their exact ingestion namespace")
    try:
        schedule = calendar.decisions(_clock(v["warmup_start"]), _clock(v["end_exclusive"], endpoint=True))
        if not isinstance(schedule, pd.DataFrame) or set(schedule.columns) != {"formation_at", "session_close"}:
            raise ValueError
        pairs = [(_clock(row.formation_at), _clock(row.session_close)) for row in schedule.itertuples(index=False)]
        if (len(pairs) > 10000 or any(close >= formation or (formation.hour, formation.minute, formation.second, formation.microsecond) != (9, 0, 0, 0)
                for formation, close in pairs)):
            raise ValueError
        if (len({x[0] for x in pairs}) != len(pairs) or pairs != sorted(pairs)
                or any(pairs[index][1] >= pairs[index + 1][1] for index in range(len(pairs) - 1))):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        _fail("An explicit unique complete exchange-calendar schedule is required")
    starts, end = _clock(v["start"]), _clock(v["end_exclusive"], endpoint=True)
    if any(not _clock(v["warmup_start"]) <= formation < end for formation, _ in pairs):
        _fail("Exchange schedule exceeds the frozen calendar scope")
    scored = [(formation, close) for formation, close in pairs if starts <= formation < end]
    sessions = sorted({close for _, close in pairs})
    tables = {component: _tables(store, plan, refs[component], component) for component in _TABLES}
    members, prices, masters, actions = _rows(plan, tables)
    liquid = _source_rows(ingestor, refs["liquidity"], "liquidity") if ingestor else []
    financial = _source_rows(ingestor, refs["financial"], "financial") if ingestor else []
    verified = _VerifiedBatchView(liquid, financial)
    if any(not _clock(v["warmup_start"]) <= _clock(row["session"]) < end for row in liquid):
        _fail("Liquidity batches exceed the frozen warmup and scope")
    if any(_clock(row["report_period_end"]) >= end for row in financial):
        _fail("Financial batches exceed the declared development scope")
    counts = Counter({name: 0 for name in _COUNTS})
    counts.update(formation_count=len(scored), expected_member_cells=200 * len(scored),
        liquidity_record_count=len(liquid), financial_record_count=len(financial),
        security_master_record_count=len(masters), price_record_count=len(prices),
        corporate_action_record_count=len(actions), financial_expected_cells=200 * len(scored) * len(v["financial_catalog"]))
    for kind in _KINDS:
        counts[kind + "_event_count"] = sum(item[3] == kind for item in actions)
    if ingestor:
        counts["missing_actual_timing_rows"] = sum(row["availability_basis"] != "actual_historical_receipt"
            or row["vendor_available_at"] is None or row["historical_ingested_at"] is None for row in liquid + financial)
    ranked_private = []
    for formation, close in scored:
        trailing = [session for session in sessions if session <= close][-20:]
        if len(trailing) != 20:
            counts["incomplete_warmup_formations"] += 1
            continue
        if not ingestor or not liquid:
            counts["unavailable_liquidity_formations"] += 1
            continue
        try:
            rank_input = verified.liquidity_rows_asof(refs["liquidity"], formation, trailing)
            active = [row for row in masters if row["effective_from"] <= formation and row["available_at"] <= formation
                      and (row["effective_to"] is None or formation < row["effective_to"])]
            known_old_listings = {row["sid"] for row in liquid if row["listing_effective_at"] is not None
                and _clock(row["listing_effective_at"]) <= trailing[0]
                and row["listing_available_at"] is not None and _clock(row["listing_available_at"]) <= formation
                and row["vendor_available_at"] is not None and _clock(row["vendor_available_at"]) <= formation}
            expected_candidates = {row["sid"] for row in active if row["listed"] is True
                and row["instrument_type"] in INCLUDED
                and (row["effective_from"] <= trailing[0] or row["sid"] in known_old_listings)}
            counts["known_eligible_candidate_expected_cells"] += 20 * len(expected_candidates)
            observed_sessions = {sid: set(group.session) for sid, group in rank_input.groupby("sid")}
            for sid in expected_candidates:
                missing = len(set(trailing) - observed_sessions.get(sid, set()))
                counts["missing_candidate_session_cells"] += missing
                counts["incomplete_candidate_histories"] += bool(missing)
            ranked = select_liquid_universe(rank_input, formation, trailing, size=200, lookback=20)
        except (IngestionError, ValueError, TypeError):
            counts["unavailable_liquidity_formations"] += 1
            continue
        ranked_private.append([formation.isoformat(), list(ranked)])
        if members.get(formation) is None or tuple(members[formation]) != ranked:
            counts["membership_mismatch_formations"] += 1
        else:
            counts["observed_member_cells"] += 200
        by_sid = {sid: [row for row in active if row["sid"] == sid] for sid in ranked}
        latest = rank_input[rank_input.session == close].set_index("sid")
        for sid in ranked:
            rows = by_sid[sid]
            if len(rows) != 1:
                counts["missing_or_ambiguous_security_master_cells"] += 1
            else:
                row = rows[0]
                try:
                    mapping = resolve_historical_sid(row["ticker"], formation, active)
                    if mapping != sid:
                        raise ValueError
                except (ValueError, TypeError):
                    counts["ambiguous_mapping_cells"] += 1
                if (row["listed"] is not True or row["instrument_type"] is None or row["exchange"] is None
                        or row["instrument_type"] != latest.at[sid, "instrument_type"]):
                    counts["inconsistent_classification_cells"] += 1
            counts["price_expected_cells"] += 1
            if (sid, close) in prices and prices[(sid, close)] <= formation:
                counts["price_observed_cells"] += 1
        if financial:
            gates = {row["public_date"]: next((session for session in sessions if session.date() > pd.Timestamp(row["public_date"]).date()), None)
                     for row in financial if row["public_precision"] == "date"}
            gates = {date: stamp for date, stamp in gates.items() if stamp is not None}
            try:
                frame = verified.financial_records_asof(refs["financial"], formation, date_release_gates=gates)
                for sid in ranked:
                    for field in v["financial_catalog"]:
                        visible = frame[(frame.sid == sid) & (frame.field == field)]
                        if not visible.empty:
                            if visible.duplicated(["event_time", "available_time"]).any():
                                counts["ambiguous_financial_cells"] += 1
                                continue
                            latest_value = visible.sort_values(["event_time", "available_time", "revision"]).iloc[-1].value
                            if pd.notna(latest_value):
                                counts["financial_available_cells"] += 1
            except (IngestionError, ValueError, TypeError):
                counts["unavailable_financial_formations"] += 1
    counts["price_missing_cells"] = max(0, counts["expected_member_cells"] - counts["price_observed_cells"])
    counts["financial_missing_cells"] = max(0, counts["financial_expected_cells"] - counts["financial_available_cells"])
    checks = {
        "all_required_input_components_present": all(bool(items) for items in refs.values()),
        "complete_calendar_formations": bool(scored) and set(members) == {formation for formation, _ in scored},
        "complete_twenty_session_warmup": bool(scored) and not counts["incomplete_warmup_formations"],
        "all_known_eligible_candidate_histories_complete": counts["known_eligible_candidate_expected_cells"] > 0
            and not counts["incomplete_candidate_histories"],
        "ranked_membership_matches": counts["observed_member_cells"] == counts["expected_member_cells"] > 0,
        "historical_classification_and_mapping_consistent": bool(masters) and len(ranked_private) == len(scored) > 0 and not any(counts[name] for name in
            ("missing_or_ambiguous_security_master_cells", "ambiguous_mapping_cells", "inconsistent_classification_cells")),
        "raw_price_scope_complete": counts["price_observed_cells"] == counts["expected_member_cells"] > 0,
        "financial_fields_declared": bool(v["financial_catalog"]),
        "financial_scope_coverage_complete": counts["financial_available_cells"] == counts["financial_expected_cells"] > 0,
        "declared_actual_timing_complete": bool(liquid) and bool(financial) and not counts["missing_actual_timing_rows"],
        "historical_all_market_origin_declared": ingestor is not None and ingestor.origin == "historical_all_market",
        "corporate_action_sids_known": bool(refs["corporate_actions"]) and all(sid in {row["sid"] for row in masters} for sid, _, _, _ in actions),
    }
    context = {"schema_version": 1, "plan": plan.to_dict(), "source_binding": ingestor.source_binding if ingestor else None}
    context_hash = content_hash(context)
    context_ref = {"key": _CONTEXT + context_hash + ".json", "sha256": context_hash}
    store.write_once(context_ref["key"], canonical_json(context))
    report = {"schema_version": 1, "kind": "data_certification_observed_scope", "plan_hash": plan.hash,
        "source_manifest_hash": v["source_manifest_hash"], "ingestion_namespace": v["ingestion_namespace"],
        "data_version_hash": content_hash(v["data_version"]), "financial_catalog_hash": content_hash(v["financial_catalog"]),
        "scope_start": v["start"], "scope_end_exclusive": v["end_exclusive"], "warmup_start": v["warmup_start"],
        "universe_size": 200, "liquidity_lookback_sessions": 20,
        "status": "observations_passed" if all(checks.values()) else "insufficient_evidence",
        "checks": checks, "counts": dict(sorted(counts.items())), "evidence_refs": refs, "context_ref": context_ref,
        "calendar_hash": content_hash([[a.isoformat(), b.isoformat()] for a, b in pairs]),
        "ranked_membership_hash": content_hash(ranked_private),
        "gap_codes": sorted(list(_GAPS) + ["observed_" + name + "_failed" for name, passed in checks.items() if not passed]),
        "vendor_provenance_authenticated": False, "full_historical_US200_certified": False,
        "actual_availability_certified": False, "financial_vintage_certified": False,
        "research_certified": False, "row_values_exported": False, "financial_evidence": False,
        "synthetic": synthetic}
    digest = content_hash(report)
    reference = {"key": _REPORT + digest + ".json", "sha256": digest}
    store.write_once(reference["key"], canonical_json(report))
    return dict(report, report_ref=reference)


def summarize_certification_scope(store, scope_manifest, expected_hash, *, calendar, synthetic=False):
    """Recompute frozen partition reports before aggregating their metadata.

    Each partition pins a computed report hash, or explicitly records a missing
    report. Small engineering scopes can never stand in for the full interval.
    Summed counts include repeated warmup rows and are not unique observations.
    Hashes establish internal integrity, not issuer or vendor authentication.
    """
    _boundary(store, synthetic)
    if not synthetic and not isinstance(calendar, ExchangeCalendar):
        _fail("An actual exchange calendar adapter is required for partition revalidation")
    required = {"schema_version", "start", "end_exclusive", "source_manifest_hash", "ingestion_namespace",
                "data_version_hash", "financial_catalog_hash", "partitions"}
    if not isinstance(scope_manifest, dict) or set(scope_manifest) != required or not _digest(expected_hash):
        _fail("A complete frozen scope manifest and SHA-256 are required")
    try:
        if content_hash(scope_manifest) != expected_hash:
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        _fail("Frozen scope manifest bytes or identity are invalid")
    m = scope_manifest
    identities = ("source_manifest_hash", "ingestion_namespace", "data_version_hash", "financial_catalog_hash")
    if (type(m["schema_version"]) is not int or m["schema_version"] != 1
            or not all(_digest(m[name]) for name in identities)
            or not isinstance(m["partitions"], list) or not m["partitions"] or len(m["partitions"]) > 10000):
        _fail("Only bounded exact versioned partition identities are supported")
    start, end = _clock(m["start"]), _clock(m["end_exclusive"], endpoint=True)
    if not start < end or start != start.normalize() or end != end.normalize():
        _fail("Scope endpoints must be explicit development NY midnights")
    spans, seen, reports, references = [], set(), [], []
    for partition in m["partitions"]:
        if (not isinstance(partition, dict) or set(partition) != {"plan_hash", "start", "end_exclusive", "report_ref"}
                or not _digest(partition["plan_hash"]) or partition["plan_hash"] in seen):
            _fail("Partition plans must be unique and exact")
        seen.add(partition["plan_hash"])
        begin, finish = _clock(partition["start"]), _clock(partition["end_exclusive"], endpoint=True)
        if (not start <= begin < finish <= end or begin != begin.normalize() or finish != finish.normalize()):
            _fail("Partition dates exceed their frozen scope")
        spans.append((begin, finish))
        if partition["report_ref"] is None:
            continue
        ref = _references([partition["report_ref"]])[0]
        if ref["key"] != _REPORT + ref["sha256"] + ".json" or ref in references:
            _fail("Only unique exact partition report references are supported")
        references.append(ref)
        try:
            raw = store.read_bytes(ref["key"])
            report = json.loads(raw)
            canonical = canonical_json(report)
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            _fail("Partition report is unavailable or malformed")
        if (sha256(raw).hexdigest() != ref["sha256"] or canonical != raw
                or not isinstance(report, dict) or set(report) != _REPORT_KEYS
                or type(report["schema_version"]) is not int or report["schema_version"] != 1
                or report["kind"] != "data_certification_observed_scope" or report["plan_hash"] != partition["plan_hash"]
                or report["scope_start"] != begin.isoformat() or report["scope_end_exclusive"] != finish.isoformat()
                or any(report[name] != m[name] for name in identities)
                or any(report[name] is not False for name in _FALSE_FLAGS) or report["synthetic"] is not synthetic
                or type(report["universe_size"]) is not int or report["universe_size"] != 200
                or type(report["liquidity_lookback_sessions"]) is not int or report["liquidity_lookback_sessions"] != 20
                or not isinstance(report["checks"], dict) or set(report["checks"]) != _CHECKS
                or any(type(value) is not bool for value in report["checks"].values())
                or not isinstance(report["counts"], dict) or set(report["counts"]) != set(_COUNTS)
                or any(type(value) is not int or not 0 <= value <= 10 ** 12 for value in report["counts"].values())
                or report["status"] != ("observations_passed" if all(report["checks"].values()) else "insufficient_evidence")
                or not _digest(report["calendar_hash"]) or not _digest(report["ranked_membership_hash"])):
            _fail("Partition report does not match the frozen scope and supported observation contract")
        if not _clock(report["warmup_start"]) < begin:
            _fail("Partition warmup does not precede its declared scope")
        expected_gaps = sorted(list(_GAPS) + ["observed_" + name + "_failed" for name, passed in report["checks"].items() if not passed])
        if report["gap_codes"] != expected_gaps or not isinstance(report["evidence_refs"], dict) or set(report["evidence_refs"]) != {"liquidity", "financial"} | _TABLES:
            _fail("Partition evidence metadata contains unknown fields or approval claims")
        for kind, refs in report["evidence_refs"].items():
            checked = _references(refs)
            prefix = "ingestion/v1/batches/" if kind in {"liquidity", "financial"} else _INPUT
            if any(item["key"] != prefix + item["sha256"] + ".json" for item in checked):
                _fail("Partition source references are not bounded content-addressed metadata")
        counts = report["counts"]
        if (counts["expected_member_cells"] != 200 * counts["formation_count"]
                or counts["observed_member_cells"] > counts["expected_member_cells"]
                or counts["price_missing_cells"] != counts["expected_member_cells"] - counts["price_observed_cells"]
                or counts["financial_missing_cells"] != counts["financial_expected_cells"] - counts["financial_available_cells"]):
            _fail("Partition metadata counts are inconsistent")
        context_ref = _references([report["context_ref"]])[0]
        if context_ref["key"] != _CONTEXT + context_ref["sha256"] + ".json":
            _fail("Partition context must be exactly content-addressed")
        try:
            raw_context = store.read_bytes(context_ref["key"])
            context = json.loads(raw_context)
            if (sha256(raw_context).hexdigest() != context_ref["sha256"] or canonical_json(context) != raw_context
                    or not isinstance(context, dict) or set(context) != {"schema_version", "plan", "source_binding"}
                    or type(context["schema_version"]) is not int or context["schema_version"] != 1):
                raise ValueError
            plan = DataCertificationPlan.from_dict(context["plan"])
            if plan.hash != partition["plan_hash"]:
                raise ValueError
            binding = context["source_binding"]
            if binding is None:
                ingestor = None
            else:
                if (not isinstance(binding, dict) or set(binding) != {"source", "data_version", "origin", "synthetic", "financial_catalog"}
                        or binding["synthetic"] is not synthetic):
                    raise ValueError
                ingestor = HistoricalBatchIngestor(store, source=binding["source"], data_version=binding["data_version"],
                    origin=binding["origin"], financial_catalog=binding["financial_catalog"], synthetic=synthetic)
            replayed = audit_data_certification(store, plan, calendar=calendar, ingestor=ingestor, synthetic=synthetic,
                liquidity_refs=report["evidence_refs"]["liquidity"], financial_refs=report["evidence_refs"]["financial"],
                membership_refs=report["evidence_refs"]["membership"], price_refs=report["evidence_refs"]["prices"],
                security_master_refs=report["evidence_refs"]["security_master"], corporate_action_refs=report["evidence_refs"]["corporate_actions"])
            if replayed["report_ref"] != ref:
                raise ValueError
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            _fail("Partition observation claims differ from revalidated private inputs")
        reports.append(report)
    spans.sort()
    if any(spans[index][1] > spans[index + 1][0] for index in range(len(spans) - 1)):
        _fail("Overlapping certification partitions cannot inflate coverage")
    interval_complete = spans[0][0] == start and spans[-1][1] == end and all(
        spans[index][1] == spans[index + 1][0] for index in range(len(spans) - 1))
    all_present = len(reports) == len(spans)
    observations_passed = all_present and all(report["status"] == "observations_passed" for report in reports)
    counts = {name: sum(report["counts"][name] for report in reports) for name in _COUNTS}
    result = {"schema_version": 1, "kind": "data_certification_partition_summary", "scope_manifest_hash": expected_hash,
        "scope_start": start.isoformat(), "scope_end_exclusive": end.isoformat(), "partition_count": len(spans),
        "report_count": len(reports), "missing_report_count": len(spans) - len(reports),
        "partition_intervals_cover_target": interval_complete, "all_partition_observations_passed": observations_passed,
        "status": "observations_passed" if interval_complete and observations_passed else "insufficient_evidence",
        "counts": counts, "counts_are_partition_sums_not_unique_rows": True, "report_refs": sorted(references, key=lambda x: x["key"]),
        "gap_codes": sorted(list(_GAPS) + ([] if interval_complete else ["partition_intervals_do_not_cover_target"])
                            + ([] if all_present else ["partition_reports_missing"])
                            + ([] if observations_passed else ["partition_observations_incomplete"])),
        "raw_rows_recomputed_here": True, "source_manifest_hash": m["source_manifest_hash"],
        "declared_full_development_interval": start == _clock("2010-01-01T00:00:00-05:00") and end == DEVELOPMENT_END,
        **{name: False for name in _FALSE_FLAGS}, "synthetic": synthetic}
    digest = content_hash(result)
    key = "data-certification/v1/scope-reports/" + digest + ".json"
    store.write_once(key, canonical_json(result))
    return dict(result, report_ref={"key": key, "sha256": digest})


def certification_capabilities(field_catalog):
    """Safe source-capability metadata, with no market-data access or approval."""
    if not isinstance(field_catalog, dict):
        _fail("An explicit source field catalog is required")
    catalog = json.loads(canonical_json(field_catalog))
    financial = sum(isinstance(spec, dict) and spec.get("role") == "as_reported_financial_value" for spec in catalog.values())
    return {"schema_version": 1, "kind": "data_certification_capabilities", "catalog_hash": content_hash(catalog),
        "observed_source_field_count": len(catalog), "declared_financial_value_field_count": financial,
        "required_components": ["exchange_calendar", "historical_inventory_and_security_master", "liquidity_20_session_US200",
                                "frozen_membership", "raw_prices", "corporate_actions", "financial_vintages_and_publication", "actual_delivery_and_ingestion"],
        "gap_codes": list(_GAPS) + ([] if financial else ["financial_value_catalog_not_available"]),
        "full_historical_US200_certified": False, "actual_availability_certified": False,
        "financial_vintage_certified": False, "research_certified": False,
        "ready_to_dispatch": False, "budget_admission_performed": False, "financial_evidence": False}
