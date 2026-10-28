"""QuantConnect-only I/O adapters; imports never request or export market data.

Object Store writes require an explicitly operated single cloud producer. The
SDK offers no cross-node compare-and-swap; the process locks below cannot make
multiple producer nodes safe. Parallel factor workers should use read_only=True.
"""
from contextlib import contextmanager
from datetime import datetime, time
import hashlib
import threading

import pandas as pd

from .artifacts import (ArtifactConflict, StoreBusy, canonical_json,
                        decode_events, validate_key)
from .contracts import (DEVELOPMENT_END, NY, RECORD_COLUMNS, aware,
                        validate_records)
from .storage_capacity import (StorageOperationError, StorageVerificationError,
                               preflight_object_store)


class ObjectStoreArtifactStore:
    """Immutable payloads and chained events inside QC Cloud only.

    Explicit single_producer=True is an operational assertion, not a distributed
    locking claim. A disconnected/uncertain producer must be reconciled before
    another process writes to this prefix.
    """
    _locks = {}
    _guard = threading.Lock()
    cloud_resident = True
    residency = "quantconnect_cloud"

    def __init__(self, object_store, prefix, *, read_only=True,
                 single_producer=False, lock_timeout=30):
        self.object_store = object_store
        self.prefix = validate_key(prefix).rstrip("/")
        self.read_only = read_only
        self.single_producer = single_producer
        self.lock_timeout = lock_timeout
        if not read_only and not single_producer:
            raise ValueError("Object Store writers require an explicit single producer")

    def _key(self, key):
        return self.prefix + "/" + validate_key(key)

    def _writable(self):
        if self.read_only or not self.single_producer:
            raise PermissionError("Read-only cloud cache cannot create or update objects")

    def exists(self, key):
        return bool(self.object_store.contains_key(self._key(key)))

    def read_bytes(self, key):
        full_key = self._key(key)
        if not self.object_store.contains_key(full_key):
            raise FileNotFoundError(key)
        return bytes(self.object_store.read_bytes(full_key))

    @contextmanager
    def locked(self, key):
        # Shared among all adapter instances in this Python process.
        full_key = self._key("locks/" + validate_key(key))
        with self._guard:
            lock = self._locks.setdefault(full_key, threading.RLock())
        acquired = lock.acquire(timeout=self.lock_timeout)
        if not acquired:
            raise StoreBusy("Cloud producer process lock is busy")
        try:
            yield
        finally:
            lock.release()

    def _save(self, key, data):
        try:
            saved = self.object_store.save_bytes(self._key(key), bytes(data))
        except Exception:
            raise StorageOperationError("save_exception") from None
        if saved is not True:
            raise StorageOperationError("save_rejected")

    def preflight_capacity(self, required_bytes, required_files, *,
                           reserve_bytes=0, reserve_files=0):
        """Inspect complete store metadata before a caller's bounded write task.

        It makes no explicit save/delete or market-payload read; the SDK's
        get_file_path may flush its existing dirty cache internally. Read-only
        cache consumers do not need to reserve a duplicate of completed data.
        """
        self._writable()
        return preflight_object_store(self.object_store, required_bytes, required_files,
                                      reserve_bytes=reserve_bytes, reserve_files=reserve_files)

    def write_once(self, key, data):
        self._writable()
        data = bytes(data)
        with self.locked("immutable/" + validate_key(key)):
            if self.exists(key):
                if self.read_bytes(key) != data:
                    raise ArtifactConflict("Immutable cloud artifact identity conflict")
                return False
            self._save(key, data)
            try:
                verified = self.read_bytes(key) == data
            except Exception:
                raise StorageVerificationError("verification_exception") from None
            if not verified:
                raise StorageVerificationError("verification_failed")
            return True

    def append_event(self, stream, event):
        self._writable()
        with self.locked("stream/" + validate_key(stream)):
            old = self.read_bytes(stream) if self.exists(stream) else b""
            events = decode_events(old)
            body = {"sequence": len(events) + 1,
                    "previous_hash": events[-1]["hash"] if events else None,
                    "event": event}
            envelope = dict(body, hash=hashlib.sha256(canonical_json(body)).hexdigest())
            self._save(stream, old + canonical_json(envelope) + b"\n")
            return envelope


class ExchangeCalendar:
    """Exchange-provided sessions and actual (including early) close times."""
    def __init__(self, exchange_hours):
        self.hours = exchange_hours

    @staticmethod
    def _local_day(value):
        stamp = aware(value)
        return datetime(stamp.year, stamp.month, stamp.day)

    @staticmethod
    def _from_exchange(value):
        stamp = pd.Timestamp(value)
        return (stamp.tz_localize(NY) if stamp.tzinfo is None
                else stamp.tz_convert(NY))

    def close_on(self, day):
        naive_day = self._local_day(day)
        if not self.hours.is_date_open(naive_day):
            raise ValueError("Requested date is not an exchange session")
        close = self._from_exchange(self.hours.get_next_market_close(naive_day, False))
        if close.date() != naive_day.date():
            raise ValueError("Exchange returned a close from another session")
        return close

    def decisions(self, start, end, decision_time=time(9, 0)):
        start, end = aware(start), aware(end)
        if start >= end or end > DEVELOPMENT_END:
            raise ValueError("Calendar access is development-only")
        day = self._local_day(start)
        if not self.hours.is_date_open(day):
            day = self.hours.get_next_trading_day(day)
        result = []
        while self._from_exchange(day) < end:
            decision = pd.Timestamp(datetime.combine(pd.Timestamp(day).date(),
                                                    decision_time), tz=NY)
            if start <= decision < end:
                previous = self.hours.get_previous_trading_day(day)
                previous_day = self._from_exchange(previous)
                close = self.close_on(previous_day)
                if close >= decision:
                    raise ValueError("Completed session must precede formation")
                result.append({"formation_at": decision, "session_close": close})
            day = self.hours.get_next_trading_day(day)
        return pd.DataFrame(result, columns=["formation_at", "session_close"])


class QuantConnectHistoryProvider:
    """One batched daily History call per cache partition, never per factor.

    Only RAW OHLCV is enabled. Actual historical vendor/ingestion timestamps
    are unavailable from this API. available_time is the modeled LEAN daily
    delivery frontier, not a certified vendor receipt timestamp. Production
    research must pass its separate coverage/timing audit before evaluation.
    """
    cloud_resident = True
    residency = "quantconnect_cloud"
    SUPPORTED_FIELDS = frozenset({"open", "high", "low", "close", "volume"})
    SUPPORTED_DATASETS = frozenset({"US Equities", "us_equity_daily"})

    def __init__(self, qb, symbols_by_sid, data_version, api=None):
        if api is None:
            import AlgorithmImports as api
        self.api = api
        self.qb = qb
        self.symbols = dict(symbols_by_sid)
        self.data_version = data_version
        self.fetch_call_count = 0
        if not data_version:
            raise ValueError("Data/feed revision must be pinned")
        for sid, symbol in self.symbols.items():
            if not hasattr(symbol, "id") or str(symbol.id) != sid:
                raise ValueError("Symbol registry keys must be permanent SecurityIdentifiers")
        self.qb.set_time_zone("America/New_York")
        self.qb.settings.daily_precise_end_time = True
        self.provenance = {
            "provider": "QuantConnect History", "data_version": data_version,
            "normalization": "raw", "fill_forward": False,
            "extended_market_hours": False, "daily_precise_end_time": True,
            "availability": "modeled LEAN end_time; not actual historical vendor receipt",
            "historical_vendor_available_at": None, "historical_ingested_at": None,
            "coverage_status": "not_certified", "financial_fields_enabled": False,
            "source_version_assertion": "Caller supplied feed/engine pin; verify against deployment manifest"
        }

    def _index_sid(self, value):
        if hasattr(value, "id"):
            sid = str(value.id)
            if sid in self.symbols:
                return sid
        # QC DataFrame Symbol index can be represented as a string. Match only
        # this explicit historical registry and reject ambiguous ticker aliases.
        candidates = [sid for sid, symbol in self.symbols.items()
                      if str(value) in (sid, str(symbol), str(symbol.value))]
        if len(candidates) != 1:
            raise ValueError("History returned an unknown or ambiguous Symbol identity")
        return candidates[0]

    def fetch(self, request):
        if request.end > DEVELOPMENT_END:
            raise ValueError("Final data requests are disabled")
        if request.dataset not in self.SUPPORTED_DATASETS:
            raise ValueError("Dataset needs a separately approved point-in-time adapter")
        if not set(request.fields) <= self.SUPPORTED_FIELDS:
            raise ValueError("Only declared raw OHLCV fields are currently enabled")
        if request.normalization != "raw" or request.data_version != self.data_version:
            raise ValueError("Normalization or data/feed revision mismatch")
        if not set(request.sids) <= set(self.symbols):
            raise ValueError("Request SID is absent from historical symbol registry")
        # QuantBook's start date is its History frontier, not the first date to
        # fetch. A later end date does not move this frontier. Fail before a
        # clipped empty/partial response can be published as a complete cache.
        frontier = pd.Timestamp(self.qb.time)
        frontier = (frontier.tz_localize(NY) if frontier.tzinfo is None
                    else frontier.tz_convert(NY))
        if frontier > DEVELOPMENT_END:
            raise ValueError("Development History frontier must not extend past 2024-01-01")
        if frontier < request.end:
            raise ValueError("History frontier precedes request end; set QuantBook start date at the request end or later")
        selected = [self.symbols[sid] for sid in request.sids]
        self.fetch_call_count += 1
        history = self.qb.history(
            selected, request.start.replace(tzinfo=None), request.end.replace(tzinfo=None),
            self.api.Resolution.DAILY, fill_forward=False, extended_market_hours=False,
            data_normalization_mode=self.api.DataNormalizationMode.RAW)
        if history.empty:
            return validate_records(pd.DataFrame(columns=RECORD_COLUMNS), request)
        if not isinstance(history.index, pd.MultiIndex) or history.index.nlevels != 2:
            raise ValueError("Expected a two-level Symbol/end_time history index")
        if not set(request.fields) <= set(history.columns):
            raise ValueError("History omitted requested fields")
        result = []
        for (symbol_key, end_time), values in history.iterrows():
            sid = self._index_sid(symbol_key)
            stamp = pd.Timestamp(end_time)
            stamp = stamp.tz_localize(NY) if stamp.tzinfo is None else stamp.tz_convert(NY)
            if not (request.start <= stamp < request.end):
                continue
            hours = self.qb.securities[self.symbols[sid]].exchange.hours
            expected_close = ExchangeCalendar(hours).close_on(stamp)
            if stamp != expected_close:
                raise ValueError("Daily History end_time does not equal the actual regular-session close")
            for field in request.fields:
                result.append({"sid": sid, "field": field, "event_time": stamp,
                               "available_time": stamp, "value": values[field],
                               "revision": request.data_version})
        return validate_records(pd.DataFrame(result, columns=RECORD_COLUMNS), request)
