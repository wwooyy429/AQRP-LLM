"""Research-only QC universe snapshots, with no implied PIT certification.

The universe-history index is the modeled selection clock, not a vendor receipt.
Missing fundamentals never remove an otherwise returned security. Licensed rows
must be consumed by HistoricalSnapshotCollector in QC Cloud, never printed.
"""
from collections.abc import Mapping
from datetime import date, datetime
import json
import math
from numbers import Integral, Real

import numpy as np
import pandas as pd

from .artifacts import canonical_json, content_hash
from .collection import SourceDiagnosticError, _catalog
from .contracts import DEVELOPMENT_END, NY, aware


class HistoricalSourceError(SourceDiagnosticError):
    """A native history response cannot satisfy the declared projection."""


# These owned, literal errors select a closed diagnostic token. Never derive
# a code from a native SID, exception message, field value or type name.
_NATIVE_FAILURE_CODES = {
    "Native source property access failed": "native_property_failed",
    "Missing native permanent SID": "native_sid_missing",
    "Empty native permanent SID": "native_sid_empty",
    "Noncanonical native permanent SID": "native_sid_noncanonical",
    "Duplicate native permanent SID": "native_sid_duplicate",
}


def _clock(value, *, native=False):
    try:
        stamp = pd.Timestamp(value)
        if native and stamp.tzinfo is None:
            stamp = stamp.tz_localize(NY)
        result = aware(stamp)
        if pd.isna(result):
            raise ValueError
        return result
    except (ValueError, TypeError, OverflowError):
        raise HistoricalSourceError("An explicit valid development clock is required") from None


def _attribute(obj, path):
    current = obj
    try:
        for name in path.split("."):
            if isinstance(current, Mapping):
                current = current.get(name)
            else:
                current = getattr(current, name, None)
            if current is None:
                return None
        if callable(current):
            raise HistoricalSourceError("Source paths cannot invoke methods")
        return current
    except HistoricalSourceError:
        raise
    except Exception:
        # A retired supplier property may throw. Do not log a native object or
        # convert an API/property failure into an apparently valid missing row.
        raise HistoricalSourceError("Native source property access failed") from None


def _scalar(value, kind):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (Real, np.floating)) and not isinstance(value, (bool, np.bool_)):
        try:
            if math.isnan(value):
                return None
        except (TypeError, OverflowError):
            pass
    if kind == "number":
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (Integral, Real)):
            raise HistoricalSourceError("A declared numeric source field has an invalid type")
        result = int(value) if isinstance(value, Integral) else float(value)
        try:
            if not math.isfinite(result):
                raise ValueError
        except (ValueError, OverflowError):
            raise HistoricalSourceError("A declared numeric source field is not finite") from None
        return result
    if kind == "boolean":
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, Integral) and value in (0, 1):
            return bool(value)
        raise HistoricalSourceError("A declared source flag must be boolean or explicit 0/1")
    if kind == "date":
        if isinstance(value, (date, datetime, pd.Timestamp)):
            result = value.date() if isinstance(value, (datetime, pd.Timestamp)) else value
            # LEAN MultiPeriodField<DateTime>.NoValue is default(DateTime).
            # Inspect the resolved Value, not default-period HasValue: Value can
            # legitimately select a populated alternate period.
            return None if result == date.min else result.isoformat()
        if isinstance(value, str):
            try:
                result = date.fromisoformat(value)
                if result.isoformat() == value:
                    return None if result == date.min else value
            except ValueError:
                pass
        raise HistoricalSourceError("A source date cannot be promoted into an intraday timestamp")
    if kind == "text":
        # Native Time/EndTime retain their original precision and zone, including
        # a naive clock. They are observations, never availability evidence.
        if isinstance(value, (date, datetime, pd.Timestamp)):
            value = value.isoformat()
        if not isinstance(value, str) or len(value) > 4096:
            raise HistoricalSourceError("A declared text source field has an invalid type")
        return value if value else None
    raise HistoricalSourceError("Unsupported source field kind")


def _universe_identity(symbol):
    native_id = None if isinstance(symbol, str) else _attribute(symbol, "id")
    if not isinstance(symbol, str) and native_id is None:
        raise HistoricalSourceError("Native response lacks a universe identity")
    identity = str(native_id) if native_id is not None else symbol
    if not identity or identity.strip() != identity:
        raise HistoricalSourceError("Native response lacks a valid universe identity")
    return ("sid" if native_id is not None else "text", identity)


def _history_endpoint(value):
    """Map the exclusive logical end to LEAN's inclusive EndTime limit.

    The verified daily Fundamental path and Python datetime use microseconds;
    this is not a promise about arbitrary custom 100ns .NET tick histories.
    Subtract on the absolute timeline, then express in the notebook's NY zone.
    """
    return (value.tz_convert("UTC") - pd.Timedelta(microseconds=1)).tz_convert(NY).tz_localize(None).to_pydatetime()


def _history_start(value):
    """Include the whole prior NY source date, not its closed final microsecond.

    Fundamental source-date d carries a modeled EndTime on d+1. LEAN first
    enumerates source files using the remaining exchange-hours interval, so
    shifting the left boundary back only one microsecond can skip the required
    file entirely. A calendar offset preserves local midnight through DST.
    Logical-window cropping below keeps this wider retrieval from changing
    feature clocks or filling missing observations.
    """
    return (value.tz_convert(NY) - pd.DateOffset(days=1)).tz_localize(None).to_pydatetime()


class QuantConnectSnapshotSource:
    """Bulk historical universe feed; no per-symbol History or financial filter.

    The caller operates a dedicated Research notebook with an explicit NY
    frontier and passes only frozen catalog fields. SDK import is lazy so all
    local tests remain synthetic. This is not a trading-universe selector.
    """
    def __init__(self, quantbook, field_catalog, *, api=None, max_records_per_snapshot=20000,
                 observation_policy="unique_sid"):
        if type(max_records_per_snapshot) is not int or not 1 <= max_records_per_snapshot <= 100000:
            raise HistoricalSourceError("A bounded snapshot size is required")
        if (type(observation_policy) is not str
                or observation_policy not in {"unique_sid", "retain_source_occurrences"}):
            raise HistoricalSourceError("A closed native observation policy is required")
        self.qb, self.api = quantbook, api
        self._catalog_bytes = canonical_json(_catalog(field_catalog))
        self.limit = max_records_per_snapshot
        self.observation_policy = observation_policy
        self.universe = None
        self._response_universe = None
        self.history_call_count = 0

    @staticmethod
    def _all_symbols(fundamentals):
        # Do not screen HasFundamentalData, today's members, price or market cap.
        return [item.symbol for item in fundamentals]

    def fetch(self, start, end, selected_field_catalog):
        # Diagnostics are closed metadata, never a native exception message or
        # observation. Reset per fetch, including cache-independent counters.
        diagnostic = dict(schema_version=1, stage="request_validation", failure_code="unexpected_exception",
            exception_kind="other", response_kind="not_observed", index_kind="not_observed",
            index_names="not_observed", snapshot_kind="not_observed", projection_kind="not_observed",
            native_calls=0, response_rows=None, index_levels=None, snapshots_seen=0, rows_emitted=0,
            projection_position=None)
        try:
            yield from self._fetch(start, end, selected_field_catalog, diagnostic)
        except Exception as error:
            kinds = {TypeError: "type_error", ValueError: "value_error", RuntimeError: "runtime_error",
                AttributeError: "attribute_error", KeyError: "key_error", IndexError: "index_error",
                OverflowError: "overflow_error", MemoryError: "memory_error", ImportError: "import_error",
                ModuleNotFoundError: "import_error", HistoricalSourceError: "source_contract"}
            diagnostic["exception_kind"] = kinds.get(type(error), "other")
            if type(error) is HistoricalSourceError:
                message = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
                diagnostic["failure_code"] = _NATIVE_FAILURE_CODES.get(message, "source_contract")
            raise HistoricalSourceError("Historical source failed; unfinished intent retained",
                diagnostic=diagnostic) from None

    def _fetch(self, start, end, selected_field_catalog, diagnostic):
        start, end = _clock(start), _clock(end)
        if (start != start.normalize() or end != end.normalize()
                or not start < end <= DEVELOPMENT_END
                or end > start + pd.DateOffset(days=7)):
            raise HistoricalSourceError("Use bounded development-only NY midnight history intervals")
        selected = _catalog(selected_field_catalog)
        trusted = json.loads(self._catalog_bytes)
        if any(path not in trusted or trusted[path] != definition for path, definition in selected.items()):
            raise HistoricalSourceError("Projection must match the frozen trusted catalog")
        native_start, native_end = _history_start(start), _history_endpoint(end)
        native_start_clock, native_end_clock = _clock(native_start, native=True), _clock(native_end, native=True)
        # QC exposes a naive Time in the notebook's configured zone. That clock
        # interpretation is explicit here and is not vendor delivery evidence.
        diagnostic["stage"] = "notebook_timezone"
        self.qb.set_time_zone("America/New_York")
        diagnostic["stage"] = "notebook_frontier"
        frontier = _clock(self.qb.time, native=True)
        if not end <= frontier <= DEVELOPMENT_END:
            raise HistoricalSourceError("Notebook frontier cannot precede the request or enter final dates")
        if self.universe is None:
            if self.api is None:
                diagnostic["stage"] = "sdk_import"
                import AlgorithmImports as api
                self.api = api
            diagnostic["stage"] = "universe_setup"
            self.qb.universe_settings.resolution = self.api.Resolution.DAILY
            self.universe = self.qb.add_universe(self._all_symbols)
        diagnostic["stage"] = "history_request"
        self.history_call_count += 1
        diagnostic["native_calls"] = 1
        response = self.qb.universe_history(self.universe,
            native_start, native_end, flatten=False)
        diagnostic["stage"] = "response_contract"
        diagnostic["response_kind"] = "series" if isinstance(response, pd.Series) else "dataframe" if isinstance(response, pd.DataFrame) else "other"
        if isinstance(response, (pd.Series, pd.DataFrame)):
            diagnostic["response_rows"] = min(len(response), 1000000000)
            diagnostic["index_kind"] = "multiindex" if isinstance(response.index, pd.MultiIndex) else "other"
            diagnostic["index_levels"] = min(response.index.nlevels, 1000000000)
            diagnostic["index_names"] = "expected" if list(response.index.names) == ["symbol", "time"] else "other"
        # An observed zero-row, zero-column ordinary frame has no constituent
        # payload to project. Normalize only this narrow SDK empty sentinel.
        # The collector records an empty window; this does not prove that an
        # exchange session was absent, that data were complete, or PIT coverage.
        if (type(response) is pd.DataFrame and response.shape == (0, 0)
                and type(response.index) in (pd.Index, pd.RangeIndex)
                and response.index.nlevels == 1 and response.index.name is None
                and type(response.columns) in (pd.Index, pd.RangeIndex)
                and response.columns.nlevels == 1 and response.columns.name is None):
            diagnostic["stage"] = "completed"
            return
        if (not isinstance(response, pd.Series) or not isinstance(response.index, pd.MultiIndex)
                or response.index.nlevels != 2 or list(response.index.names) != ["symbol", "time"]):
            raise HistoricalSourceError("Expected documented symbol/time universe-history Series")
        seen_snapshots = set()
        diagnostic["stage"] = "response_identity"
        expected_universe = _attribute(self.universe, "symbol")
        expected_key = _universe_identity(expected_universe) if expected_universe is not None else None
        diagnostic["stage"] = "response_iteration"
        for (native_universe, native_time), objects in response.items():
            diagnostic["stage"] = "snapshot_identity"
            universe_key = _universe_identity(native_universe)
            expected_mismatch = (expected_key is not None and
                (universe_key != expected_key if universe_key[0] == expected_key[0]
                 else universe_key[0] != "text" or native_universe != str(expected_universe)))
            if (expected_mismatch
                    or (self._response_universe is not None and universe_key != self._response_universe)):
                raise HistoricalSourceError("Native response mixes or replaces the requested universe")
            self._response_universe = universe_key
            diagnostic["stage"] = "snapshot_clock"
            stamp = _clock(native_time, native=True)
            if (not native_start_clock < stamp <= native_end_clock
                    or stamp >= DEVELOPMENT_END or stamp > frontier or stamp in seen_snapshots):
                raise HistoricalSourceError("Duplicate or outside-request native universe snapshot")
            seen_snapshots.add(stamp)
            diagnostic["snapshots_seen"] += 1
            # Validate identity, native request clock and duplicate snapshots
            # before cropping; never inspect SID/field values outside the
            # declared logical interval. A missing day stays missing.
            if not start <= stamp < end:
                continue
            diagnostic["stage"] = "snapshot_container"
            diagnostic["snapshot_kind"] = "list" if isinstance(objects, list) else "tuple" if isinstance(objects, tuple) else "other"
            if not isinstance(objects, (list, tuple)) or len(objects) > self.limit:
                raise HistoricalSourceError("Native snapshot is not a bounded list of fundamentals")
            seen_sids = set()
            diagnostic["stage"] = "snapshot_iteration"
            for source_record_index, item in enumerate(objects):
                diagnostic["stage"] = "row_identity"
                symbol = _attribute(item, "symbol")
                native_sid = _attribute(symbol, "id") if symbol is not None else None
                if native_sid is None:
                    raise HistoricalSourceError("Missing native permanent SID")
                sid = str(native_sid)
                if sid == " 0":
                    # LEAN's exact SecurityIdentifier.Empty string; never trim
                    # or accept this SDK sentinel as a security identity.
                    raise HistoricalSourceError("Empty native permanent SID")
                if not sid or sid.strip() != sid or len(sid) > 256:
                    raise HistoricalSourceError("Noncanonical native permanent SID")
                if self.observation_policy == "unique_sid" and sid in seen_sids:
                    raise HistoricalSourceError("Duplicate native permanent SID")
                seen_sids.add(sid)
                diagnostic["stage"] = "field_projection"
                values = {}
                for position, (path, definition) in enumerate(selected.items(), 1):
                    diagnostic["projection_position"] = position
                    diagnostic["projection_kind"] = definition["kind"]
                    values[path] = _scalar(_attribute(item, path), definition["kind"])
                diagnostic["rows_emitted"] += 1
                row = {"sid": sid, "snapshot_at": stamp.isoformat(), "values": values}
                if self.observation_policy == "retain_source_occurrences":
                    # Explicit v2 collection only: preserve native order and
                    # every projected occurrence for cloud-side quarantine.
                    row["source_record_index"] = source_record_index
                yield row
                diagnostic["stage"] = "snapshot_iteration"
            diagnostic["stage"] = "response_iteration"
        diagnostic["stage"] = "completed"

    def provenance(self):
        result = {"source": "quantconnect_fundamental_universe", "history_api_calls": self.history_call_count,
                "snapshot_clock": "modeled_universe_selection_time_in_America_New_York",
                "vendor_revision_certified": False, "actual_availability_certified": False,
                "full_historical_US200_certified": False, "financial_field_coverage_certified": False}
        if self.observation_policy == "retain_source_occurrences":
            result["observation_policy"] = self.observation_policy
        return result


def observed_liquidity_record(snapshot, *, session_close):
    """Bridge observed metadata into ingestion while preserving unknown receipts.

    session_close MUST come from an independently checked exchange/source-date
    mapping. No calendar date is inferred from the selection clock. The content
    fingerprint below identifies this observation, not a supplier revision.
    """
    if (not isinstance(snapshot, Mapping) or set(snapshot) != {"sid", "snapshot_at", "values"}
            or not isinstance(snapshot["sid"], str) or not snapshot["sid"].strip()
            or not isinstance(snapshot["values"], Mapping)):
        raise HistoricalSourceError("A verified projected snapshot is required")
    stamp, close = _clock(snapshot["snapshot_at"]), _clock(session_close)
    if not close < stamp < DEVELOPMENT_END:
        raise HistoricalSourceError("An independently mapped prior exchange close is required")
    values = snapshot["values"]
    security_type = values.get("security_reference.security_type")
    subtype = values.get("security_reference.common_share_sub_type")
    instrument = {"ST00000001": "common_stock", "ST00000002": "preferred_stock", "ST000000A1": "unit"}.get(security_type)
    if instrument == "common_stock":
        if subtype == "Closed-End Fund":
            instrument = "closed_end_fund"
        elif subtype not in (None, ""):
            instrument = None  # No guessed classification of unfamiliar subtypes.
        elif values.get("security_reference.is_depositary_receipt") is True:
            instrument = "adr"
        elif values.get("company_reference.is_reit") is True:
            instrument = "reit_common"
    status = values.get("security_reference.share_class_status")
    listed = True if status in ("A", "I") else False if status in ("D", "O") else None
    volume = _scalar(values.get("dollar_volume"), "number")
    if volume is not None and volume < 0:
        raise HistoricalSourceError("Supplied DollarVolume cannot be negative")
    return {"sid": snapshot["sid"], "session": close.isoformat(), "dollar_volume": volume,
            "dollar_volume_field": "dollar_volume", "instrument_type": instrument, "listed": listed,
            "source_revision": "observed_snapshot:" + content_hash(dict(snapshot)),
            "vendor_available_at": None, "historical_ingested_at": None, "availability_basis": "unknown",
            "classification_effective_at": None, "classification_available_at": None,
            "listing_effective_at": None, "listing_available_at": None}
