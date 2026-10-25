"""Small SDK-independent contracts shared by Research and LEAN."""
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo
import hashlib
import json
import pandas as pd

NY = ZoneInfo("America/New_York")
DEVELOPMENT_END = datetime(2024, 1, 1, tzinfo=NY)
RECORD_COLUMNS = ("sid", "field", "event_time", "available_time", "value", "revision")


def aware(value):
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise ValueError("Explicit time zone required")
    return result.tz_convert(NY)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class DataRequest:
    dataset: str
    fields: tuple[str, ...]
    sids: tuple[str, ...]
    start: datetime
    end: datetime
    data_version: str
    universe_hash: str
    normalization: str = "raw"
    timezone: str = "America/New_York"

    def __post_init__(self):
        object.__setattr__(self, "start", aware(self.start).to_pydatetime())
        object.__setattr__(self, "end", aware(self.end).to_pydatetime())
        object.__setattr__(self, "fields", tuple(sorted(set(self.fields))))
        object.__setattr__(self, "sids", tuple(sorted(set(self.sids))))
        if self.start >= self.end or self.end > DEVELOPMENT_END:
            raise ValueError("Development requests must end at or before 2024-01-01")
        if self.timezone != "America/New_York" or not self.fields or not self.sids:
            raise ValueError("NY zone, nonempty fields and permanent SIDs required")
        if not self.data_version or not self.universe_hash:
            raise ValueError("Pinned data version and universe identity required")
        if any(x.lower().startswith(("label", "target", "future_", "forward_")) for x in (self.dataset,) + self.fields):
            raise ValueError("Labels cannot enter feature data requests")

    def identity(self):
        return {"dataset": self.dataset, "fields": list(self.fields), "sids": list(self.sids),
                "start": self.start.isoformat(), "end": self.end.isoformat(),
                "data_version": self.data_version, "universe_hash": self.universe_hash,
                "normalization": self.normalization, "timezone": self.timezone}

    @property
    def key(self):
        return digest(self.identity())


@dataclass(frozen=True)
class PITWindow:
    """Causal formation rows and optional historical universe membership.

    Raw series retain histories of entrants. Membership restricts historical
    cross-sectional operations and the final output, not raw rolling history.
    A missing membership matrix represents a caller-declared fixed SID pool.
    """
    as_of: datetime
    matrices: Mapping[str, pd.DataFrame]
    sids: tuple[str, ...]
    universe_membership: pd.DataFrame = None

    def __post_init__(self):
        stamp = aware(self.as_of)
        if stamp >= DEVELOPMENT_END:
            raise ValueError("Independent final executor is not configured")
        sids = tuple(self.sids)
        if len(set(sids)) != len(sids):
            raise ValueError("Duplicate SIDs in feature window")
        copied, common_index = {}, None
        for field, frame in self.matrices.items():
            if not isinstance(frame, pd.DataFrame):
                raise ValueError("Feature matrices must be DataFrames")
            index = pd.DatetimeIndex(frame.index)
            if index.tz is None or not index.is_unique or not index.is_monotonic_increasing:
                raise ValueError("Formation index must be unique, sorted and timezone aware")
            if len(index) and index.max() > stamp:
                raise ValueError("Future formation rows are prohibited")
            if not frame.columns.is_unique or set(frame.columns) != set(sids):
                raise ValueError("Every feature matrix must match the declared SIDs")
            if common_index is not None and not index.equals(common_index):
                raise ValueError("Feature matrices must share one formation index")
            common_index = index
            if field.lower().startswith(("label", "target", "future_", "forward_")):
                raise ValueError("Labels must remain separate")
            copied[field] = frame.reindex(columns=sids).copy(deep=True)
        membership = self.universe_membership
        if membership is not None:
            if not isinstance(membership, pd.DataFrame) or not isinstance(membership.index, pd.DatetimeIndex):
                raise ValueError("Universe membership must be a time-indexed DataFrame")
            if (membership.index.tz is None or not membership.index.is_unique
                    or not membership.index.is_monotonic_increasing
                    or (len(membership) and membership.index.max() > stamp)):
                raise ValueError("Universe membership times must be causal, aware, unique and sorted")
            if (not membership.columns.is_unique or set(membership.columns) != set(sids)
                    or (common_index is not None and not membership.index.equals(common_index))):
                raise ValueError("Universe membership must match the feature index and SIDs")
            if membership.isna().any().any() or not all(pd.api.types.is_bool_dtype(x) for x in membership.dtypes):
                raise ValueError("Universe membership requires nonmissing boolean values")
            membership = membership.reindex(columns=sids).astype(bool).copy(deep=True)
        object.__setattr__(self, "as_of", stamp.to_pydatetime())
        object.__setattr__(self, "sids", sids)
        object.__setattr__(self, "matrices", MappingProxyType(copied))
        object.__setattr__(self, "universe_membership", membership)


def validate_records(frame, request=None):
    missing = set(RECORD_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError("Missing feature record columns: " + str(sorted(missing)))
    data = frame.loc[:, RECORD_COLUMNS].copy()
    for column in ("event_time", "available_time"):
        # Reject naive timestamps instead of silently interpreting UTC.
        data[column] = (pd.DatetimeIndex([aware(x) for x in data[column]]) if len(data)
                        else pd.DatetimeIndex([], tz=NY))
    if len(data) and (data.event_time > data.available_time).any():
        raise ValueError("Event time cannot follow availability")
    if data.duplicated(["sid", "field", "event_time", "available_time", "revision"]).any():
        raise ValueError("Duplicate observation/vintage identity")
    if data.duplicated(["sid", "field", "event_time", "available_time"]).any():
        raise ValueError("Ambiguous simultaneous vintages: revision identifiers do not establish chronology")
    if len(data) and (data.available_time >= DEVELOPMENT_END).any():
        raise ValueError("Final data cannot enter development cache")
    if request is not None:
        if not set(data.sid) <= set(request.sids) or not set(data.field) <= set(request.fields):
            raise ValueError("Provider returned undeclared symbols/fields")
        if len(data) and ((data.event_time < request.start) | (data.event_time >= request.end)).any():
            raise ValueError("Provider returned events outside request")
    data["value"] = pd.to_numeric(data["value"], errors="raise")
    return data.sort_values(["sid", "field", "event_time", "available_time", "revision"]).reset_index(drop=True)
