"""Prove received rows equal a verified cached subset without copying rows.

All row comparison and hashing occur in the cloud. The returned document stores
only the frozen request, observation interval, aggregate count, matching hashes
and original cache references. It never grants access to final-test dates.
"""
from datetime import datetime
from hashlib import sha256
import math
import re

import pandas as pd

from .artifacts import canonical_json
from .cache import _encode as _cached_payload
from .contracts import DataRequest, DEVELOPMENT_END, RECORD_COLUMNS, NY, aware, validate_records


_HASH = re.compile(r"[0-9a-f]{64}")
_FIELDS = {"open", "high", "low", "close", "volume"}
_MAX_RECORDS = 100000


def _fail():
    raise ValueError("Received rows do not exactly match the frozen verified cache") from None


def _clock(value, *, received=False):
    if received:
        if type(value) is not str or len(value) > 128:
            _fail()
    elif not isinstance(value, (pd.Timestamp, datetime)):
        _fail()
    try:
        result = aware(value)
        if pd.isna(result):
            _fail()
        return result
    except (ValueError, TypeError, OverflowError):
        _fail()


def _native_text(value):
    if type(value) is not str or not value or value != value.strip() or len(value) > 512:
        _fail()
    return value


def _row(raw, request, *, received):
    if type(raw) not in (tuple, list) or len(raw) != len(RECORD_COLUMNS):
        _fail()
    sid, field, event, available, value, revision = raw
    sid, field, revision = _native_text(sid), _native_text(field), _native_text(revision)
    if sid not in request.sids or field not in request.fields or revision != request.data_version:
        _fail()
    event, available = _clock(event, received=received), _clock(available, received=received)
    if not request.start <= event < request.end or not event <= available < DEVELOPMENT_END:
        _fail()
    if type(value) not in (int, float):
        _fail()
    try:
        number = float(value)
    except (ValueError, OverflowError):
        _fail()
    if not math.isfinite(number) or number != value:
        _fail()
    return [sid, field, event.isoformat(), available.isoformat(), number, revision]


def _sort_unique(rows):
    rows.sort(key=lambda r: (r[0], r[1], aware(r[2]), aware(r[3]), r[5]))
    keys = [(r[0], r[1], r[2], r[3], r[5]) for r in rows]
    clocks = [(r[0], r[1], r[2], r[3]) for r in rows]
    if len(set(keys)) != len(keys) or len(set(clocks)) != len(clocks):
        _fail()
    return rows


def _references(source_refs):
    if type(source_refs) is not list or len(source_refs) != 5:
        _fail()
    copied = []
    for ref in source_refs:
        if (type(ref) is not dict or set(ref) != {"key", "sha256"}
                or type(ref["sha256"]) is not str or _HASH.fullmatch(ref["sha256"]) is None
                or type(ref["key"]) is not str
                or ref["key"] != "feature-cache/v1/objects/" + ref["sha256"] + ".json"):
            _fail()
        copied.append({"key": ref["key"], "sha256": ref["sha256"]})
    if len({ref["key"] for ref in copied}) != 5:
        _fail()
    return sorted(copied, key=lambda ref: ref["key"])


def build_received_manifest(records, cached, request, window, source_refs):
    """Return metadata only after exact received/cache equality is established.

    ``cached`` must be the frame returned by a verified, cache-only
    SharedDataCache read. Original content-addressed references are provided by
    that same verified read. This function performs no source or store I/O.
    """
    if (not isinstance(request, DataRequest) or request.dataset != "US Equities"
            or request.normalization != "raw" or request.timezone != "America/New_York"
            or set(request.fields) != _FIELDS or not 1 <= len(request.sids) <= 64
            or any(type(value) is not str for value in request.sids + request.fields)
            or type(request.data_version) is not str
            or type(request.universe_hash) is not str):
        _fail()
    _native_text(request.data_version); _native_text(request.universe_hash)
    if (request.start != datetime(request.start.year, 1, 1, tzinfo=NY)
            or request.end != datetime(request.start.year + 1, 1, 1, tzinfo=NY)):
        _fail()
    if (type(window) is not dict or set(window) != {"start", "end_exclusive"}
            or type(window["start"]) is not str or type(window["end_exclusive"]) is not str):
        _fail()
    start = _clock(window["start"], received=True)
    end = _clock(window["end_exclusive"], received=True)
    if not request.start <= start < end <= request.end <= DEVELOPMENT_END:
        _fail()
    references = _references(source_refs)
    if (type(records) is not list or not 1 <= len(records) <= _MAX_RECORDS
            or not isinstance(cached, pd.DataFrame) or not cached.columns.is_unique
            or set(cached.columns) != set(RECORD_COLUMNS) or not 1 <= len(cached) <= _MAX_RECORDS):
        _fail()
    actual = [_row(row, request, received=True) for row in records]
    if any(not start <= aware(row[2]) < end for row in actual):
        _fail()
    expected_all = [_row(list(row), request, received=False)
                    for row in cached.loc[:, RECORD_COLUMNS].itertuples(index=False, name=None)]
    # Validate uniqueness in the whole request, including rows outside the
    # observation interval, before selecting the exact comparison subset.
    _sort_unique(expected_all)
    # This engineering protocol has one full calendar-year SID chunk and five
    # field objects. Rebuild each original cache payload hash in cloud so an
    # unrelated but well-formed reference cannot be attached to matching rows.
    try:
        normalized = validate_records(cached, request)
        expected_refs = []
        for field in request.fields:
            digest = sha256(_cached_payload(normalized[normalized.field == field])).hexdigest()
            expected_refs.append({"key": "feature-cache/v1/objects/" + digest + ".json", "sha256": digest})
        if references != _references(expected_refs):
            _fail()
    except Exception:
        _fail()
    expected = [row for row in expected_all if start <= aware(row[2]) < end]
    actual, expected = _sort_unique(actual), _sort_unique(expected)
    if not expected:
        _fail()
    actual_bytes, cached_bytes = canonical_json(actual), canonical_json(expected)
    if actual_bytes != cached_bytes:
        _fail()
    actual_hash = sha256(actual_bytes).hexdigest()
    cached_hash = sha256(cached_bytes).hexdigest()
    manifest = {"schema_version": 1, "encoding": "cached_row_reference_v1",
                "request": request.identity(), "request_hash": request.key,
                "observation_window": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
                "columns": list(RECORD_COLUMNS), "record_count": len(actual),
                "actual_rowset_sha256": actual_hash, "cached_rowset_sha256": cached_hash,
                "source_refs": references, "row_values_stored": False}
    metadata = {"schema_version": 1, "encoding": "cached_row_reference_v1", "record_count": len(actual),
                "rowset_sha256": actual_hash, "manifest_sha256": sha256(canonical_json(manifest)).hexdigest(),
                "cache_reference_count": len(references), "new_row_objects": False}
    return manifest, metadata
