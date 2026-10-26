"""Bounded historical snapshot collection; rows stay in the cloud.

Collection is preparation, not factor evaluation or PIT certification. An outer
trusted dispatcher must debit any real Research execution before dispatch; this
module never submits a remote job and has no independent budget counter.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
import math
from numbers import Integral, Real
import re

import pandas as pd

from .artifacts import canonical_json, content_hash
from .contracts import DEVELOPMENT_END, aware


class CollectionError(ValueError):
    """A collection request or projected record is invalid."""


class CollectionMiss(CollectionError):
    """A cache-only consumer cannot request missing source data."""


class CollectionInterrupted(CollectionError):
    """An unfinished intent requires explicit reconciliation, never auto-retry."""


class CollectionIntegrityError(CollectionError):
    """A reference, completed manifest or payload is inconsistent."""


_HASH = re.compile(r"[0-9a-f]{64}")
_PATH = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*")
_FIELDS = {"schema_version", "plan_id", "scope", "source", "data_version", "start",
           "end_exclusive", "timezone", "fields", "calendar_days_per_request",
           "max_batch_records", "max_records_per_window", "source_manifest_hash"}
_ROOT = "historical-snapshots/v1/"
_FLAGS = {"full_historical_US200_certified": False, "actual_availability_certified": False,
          "research_certified": False, "row_values_exported": False}


def _text(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise CollectionError("A nonempty explicit source string is required")
    return value


def _time(value):
    try:
        result = aware(value)
    except (TypeError, ValueError, OverflowError):
        raise CollectionError("An explicit valid timezone-aware source time is required") from None
    if pd.isna(result):
        raise CollectionError("Missing source time is prohibited")
    return result


def _catalog(raw):
    if not isinstance(raw, Mapping) or not raw:
        raise CollectionError("An explicit trusted field catalog is required")
    result = {}
    for path, definition in raw.items():
        if not isinstance(path, str) or _PATH.fullmatch(path) is None:
            raise CollectionError("Only explicit attribute paths are permitted")
        if (not isinstance(definition, Mapping)
                or set(definition) != {"kind", "role", "unit", "period_accessor"}
                or not isinstance(definition["kind"], str)
                or definition["kind"] not in {"number", "text", "boolean", "date"}):
            raise CollectionError("Complete supported field definitions are required")
        for name in ("role", "unit"):
            _text(definition[name])
        if definition["period_accessor"] is not None:
            _text(definition["period_accessor"])
        result[path] = dict(definition)
    return result


@dataclass(frozen=True, init=False)
class HistoricalCollectionPlan:
    """Immutable plan; identity() also binds the selected catalog definitions."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use HistoricalCollectionPlan.from_dict with a trusted field catalog")

    @classmethod
    def from_dict(cls, raw, *, field_catalog):
        if not isinstance(raw, Mapping) or set(raw) != _FIELDS:
            raise CollectionError("A complete collection plan with no unknown overrides is required")
        try:
            value = json.loads(canonical_json(dict(raw)))
        except (TypeError, ValueError):
            raise CollectionError("Collection plans require finite JSON configuration values") from None
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["scope"] != "engineering"
                or value["source"] != "quantconnect_fundamental_universe"
                or value["timezone"] != "America/New_York"):
            raise CollectionError("Only the versioned NY engineering snapshot source is supported")
        for name in ("plan_id", "data_version"):
            _text(value[name])
        if not isinstance(value["source_manifest_hash"], str) or _HASH.fullmatch(value["source_manifest_hash"]) is None:
            raise CollectionError("Pin the source implementation SHA-256")
        fields = value["fields"]
        catalog = _catalog(field_catalog)
        if (not isinstance(fields, list) or not fields
                or any(not isinstance(path, str) for path in fields)
                or len(fields) != len(set(fields)) or not set(fields) <= set(catalog)):
            raise CollectionError("Use unique nonempty fields from the trusted catalog only")
        value["fields"] = sorted(fields)
        for name, maximum in (("calendar_days_per_request", 7),
                              ("max_batch_records", 10000), ("max_records_per_window", 200000)):
            if type(value[name]) is not int or not 1 <= value[name] <= maximum:
                raise CollectionError("Collection bounds must be explicit supported positive integers")
        if value["max_batch_records"] > value["max_records_per_window"]:
            raise CollectionError("A batch cannot exceed the window record bound")
        start, end = _time(value["start"]), _time(value["end_exclusive"])
        if start != start.normalize() or end != end.normalize():
            raise CollectionError("Daily collection endpoints must be NY midnights")
        if not start < end <= DEVELOPMENT_END:
            raise CollectionError("Only nonempty development intervals ending by 2024-01-01 are permitted")
        value.update(start=start.isoformat(), end_exclusive=end.isoformat())
        result = object.__new__(cls)
        identity = {"plan": value, "field_catalog": {path: catalog[path] for path in value["fields"]}}
        object.__setattr__(result, "_encoded", canonical_json(identity))
        return result

    def identity(self):
        return json.loads(self._encoded)

    def to_dict(self):
        return self.identity()["plan"]

    @property
    def field_catalog(self):
        return self.identity()["field_catalog"]

    @property
    def hash(self):
        return sha256(self._encoded).hexdigest()

    def windows(self):
        """Calendar chunks, not a replacement trading-session calendar."""
        raw = self.to_dict()
        current, end = _time(raw["start"]), _time(raw["end_exclusive"])
        output = []
        while current < end:
            following = min(end, current + pd.DateOffset(days=raw["calendar_days_per_request"]))
            output.append((current, following))
            current = following
        return tuple(output)


class HistoricalSnapshotCollector:
    """One explicit producer, bounded windows and immutable completed results.

    Source.fetch(start, end, selected_field_catalog) yields dictionaries with
    sid, snapshot_at and values. A missing value is None, never an invented zero.
    source=None enables completed-cache reads but no fetching or new writes.
    """
    def __init__(self, store, source, plan, *, synthetic=False):
        if not isinstance(plan, HistoricalCollectionPlan) or type(synthetic) is not bool:
            raise CollectionError("A frozen plan and explicit synthetic classification are required")
        if not synthetic and getattr(store, "residency", None) != "quantconnect_cloud":
            raise CollectionError("Real snapshots must remain inside QuantConnect cloud storage")
        if source is not None and not callable(getattr(source, "fetch", None)):
            raise CollectionError("The source must implement the bounded fetch contract")
        self.store, self.source, self.plan, self.synthetic = store, source, plan, synthetic

    def _window(self, start, end):
        return {"start": start.isoformat(), "end_exclusive": end.isoformat()}

    def _identity(self, window):
        return {"plan_hash": self.plan.hash, "synthetic": self.synthetic, "window": window}

    def _key(self, window):
        return _ROOT + "windows/" + content_hash(self._identity(window)) + ".json"

    def _row(self, raw, start, end):
        if not isinstance(raw, Mapping) or set(raw) != {"sid", "snapshot_at", "values"}:
            raise CollectionError("Projected snapshots require exactly the declared source columns")
        sid, stamp = _text(raw["sid"]), _time(raw["snapshot_at"])
        if len(sid) > 256 or not start <= stamp < end or stamp >= DEVELOPMENT_END:
            raise CollectionError("Snapshot identity or time is outside the frozen window")
        definitions = self.plan.field_catalog
        if not isinstance(raw["values"], Mapping) or set(raw["values"]) != set(definitions):
            raise CollectionError("Snapshot values must exactly match the frozen field projection")
        values = {}
        for path, definition in definitions.items():
            value, kind = raw["values"][path], definition["kind"]
            if value is not None:
                if kind == "number":
                    if isinstance(value, bool) or not isinstance(value, (Integral, Real)):
                        raise CollectionError("A finite real scalar or explicit missing value is required")
                    value = int(value) if isinstance(value, Integral) else float(value)
                    try:
                        finite = math.isfinite(value)
                    except OverflowError:
                        finite = False
                    if not finite:
                        raise CollectionError("A finite real scalar or explicit missing value is required")
                elif kind == "boolean" and type(value) is not bool:
                    raise CollectionError("An explicit boolean or missing value is required")
                elif kind in {"text", "date"}:
                    if not isinstance(value, str) or len(value) > 4096:
                        raise CollectionError("A bounded string or missing value is required")
                    if kind == "date":
                        try:
                            if date.fromisoformat(value).isoformat() != value:
                                raise ValueError
                        except ValueError:
                            raise CollectionError("Date fields require an explicit ISO date without a made-up time") from None
            values[path] = value
        return {"sid": sid, "snapshot_at": stamp.isoformat(), "values": values}

    def _write_batch(self, window, index, rows):
        payload = {"schema_version": 1, **self._identity(window), "batch_index": index, "records": rows}
        digest = content_hash(payload)
        key = _ROOT + "objects/" + digest + ".json"
        self.store.write_once(key, canonical_json(payload))
        return {"key": key, "sha256": digest}

    def _document(self, reference, prefix):
        if (not isinstance(reference, Mapping) or set(reference) != {"key", "sha256"}
                or not isinstance(reference["sha256"], str) or _HASH.fullmatch(reference["sha256"]) is None
                or not isinstance(reference["key"], str) or not reference["key"].startswith(_ROOT + prefix)
                or _HASH.fullmatch(reference["key"][len(_ROOT + prefix):-5]) is None
                or not reference["key"].endswith(".json")):
            raise CollectionIntegrityError("A canonical source-bound collection reference is required")
        try:
            raw = self.store.read_bytes(reference["key"])
        except FileNotFoundError:
            raise CollectionIntegrityError("A referenced collection artifact is missing") from None
        try:
            value = json.loads(raw)
            if sha256(raw).hexdigest() != reference["sha256"] or canonical_json(value) != raw:
                raise ValueError
        except (ValueError, TypeError, UnicodeDecodeError):
            raise CollectionIntegrityError("Collection artifact bytes or hash are invalid") from None
        return value

    def _load_window(self, reference):
        manifest = self._document(reference, "windows/")
        required = {"schema_version", "plan_hash", "synthetic", "window", "status", "plan_identity",
                    "batches", "record_count", "snapshot_count", "unique_sid_count", "missing_values", "provider_calls", *_FLAGS}
        if (not isinstance(manifest, dict) or set(manifest) != required
                or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
                or manifest["status"] != "completed"
                or manifest["plan_hash"] != self.plan.hash or type(manifest["synthetic"]) is not bool
                or manifest["synthetic"] != self.synthetic or manifest["plan_identity"] != self.plan.identity()
                or any(manifest[key] is not value for key, value in _FLAGS.items())):
            raise CollectionIntegrityError("Only completed results of this exact source plan may be consumed")
        window = manifest["window"]
        if window not in [self._window(*pair) for pair in self.plan.windows()] or reference["key"] != self._key(window):
            raise CollectionIntegrityError("Collection reference belongs to another interval or source plan")
        if (not isinstance(manifest["batches"], list) or type(manifest["provider_calls"]) is not int
                or manifest["provider_calls"] != 1):
            raise CollectionIntegrityError("Completed window metadata is invalid")
        raw_plan = self.plan.to_dict()
        start, end = _time(window["start"]), _time(window["end_exclusive"])
        rows, identities, snapshots, sids = [], set(), set(), set()
        missing = {path: 0 for path in self.plan.field_catalog}
        for index, ref in enumerate(manifest["batches"]):
            payload = self._document(ref, "objects/")
            if (not isinstance(payload, dict) or set(payload) != {"schema_version", "plan_hash", "synthetic", "window", "batch_index", "records"}
                    or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
                    or type(payload["batch_index"]) is not int or payload["batch_index"] != index
                    or type(payload["synthetic"]) is not bool
                    or any(payload[key] != value for key, value in self._identity(window).items())
                    or ref["key"] != _ROOT + "objects/" + ref["sha256"] + ".json"
                    or not isinstance(payload["records"], list) or not 1 <= len(payload["records"]) <= raw_plan["max_batch_records"]):
                raise CollectionIntegrityError("Collection batch identity, sequence or bound is invalid")
            for raw in payload["records"]:
                try:
                    row = self._row(raw, start, end)
                except CollectionError:
                    raise CollectionIntegrityError("Stored source rows violate the frozen projection") from None
                identity = (row["sid"], row["snapshot_at"])
                if row != raw or identity in identities:
                    raise CollectionIntegrityError("Collection contains duplicate or noncanonical projected records")
                identities.add(identity); snapshots.add(row["snapshot_at"]); sids.add(row["sid"])
                for path, value in row["values"].items():
                    missing[path] += value is None
                rows.append(row)
                if len(rows) > raw_plan["max_records_per_window"]:
                    raise CollectionIntegrityError("Completed window exceeds its frozen record bound")
        counts = {"record_count": len(rows), "snapshot_count": len(snapshots), "unique_sid_count": len(sids)}
        if (any(type(manifest[key]) is not int or manifest[key] != value for key, value in counts.items())
                or not isinstance(manifest["missing_values"], dict)
                or any(type(value) is not int for value in manifest["missing_values"].values())
                or manifest["missing_values"] != missing):
            raise CollectionIntegrityError("Completed counts and gaps do not match source payloads")
        return manifest, rows

    def read_window(self, window_ref):
        """Return rows only after the entire completed window has been verified."""
        return self._load_window(window_ref)[1]

    def _source_rows(self, start, end):
        """Do not let provider exception messages disclose licensed row values."""
        try:
            source_rows = iter(self.source.fetch(start, end, self.plan.field_catalog))
        except Exception:
            raise CollectionError("Historical source fetch failed; unfinished intent retained") from None
        while True:
            try:
                row = next(source_rows)
            except StopIteration:
                return
            except Exception:
                raise CollectionError("Historical source iteration failed; unfinished intent retained") from None
            yield row

    def _collect_window(self, start, end):
        window = self._window(start, end)
        key = self._key(window)
        with self.store.locked(_ROOT + "window-locks/" + content_hash(self._identity(window))):
            if self.store.exists(key):
                reference = {"key": key, "sha256": sha256(self.store.read_bytes(key)).hexdigest()}
                return reference, self._load_window(reference)[0], False
            intent = _ROOT + "intents/" + content_hash(self._identity(window)) + ".json"
            if self.store.exists(intent):
                raise CollectionInterrupted("Unfinished collection intent requires reconciliation or a new frozen source plan")
            if self.source is None:
                raise CollectionMiss("Cache-only collection cannot call a source; prefetch the frozen plan first")
            self.store.write_once(intent, canonical_json({"schema_version": 1, **self._identity(window)}))
            plan = self.plan.to_dict()
            refs, batch, identities, snapshots, sids = [], [], set(), set(), set()
            missing = {path: 0 for path in self.plan.field_catalog}
            try:
                for raw in self._source_rows(start, end):
                    row = self._row(raw, start, end)
                    identity = (row["sid"], row["snapshot_at"])
                    if identity in identities:
                        raise CollectionError("Duplicate snapshot identity inside the source window")
                    identities.add(identity)
                    if len(identities) > plan["max_records_per_window"]:
                        raise CollectionError("Source exceeded the frozen window record bound")
                    snapshots.add(row["snapshot_at"]); sids.add(row["sid"])
                    for path, value in row["values"].items():
                        missing[path] += value is None
                    batch.append(row)
                    if len(batch) == plan["max_batch_records"]:
                        refs.append(self._write_batch(window, len(refs), batch))
                        batch = []
                if batch:
                    refs.append(self._write_batch(window, len(refs), batch))
                manifest = {"schema_version": 1, **self._identity(window), "status": "completed",
                    "plan_identity": self.plan.identity(), "batches": refs, "record_count": len(identities),
                    "snapshot_count": len(snapshots), "unique_sid_count": len(sids), "missing_values": missing,
                    "provider_calls": 1, **_FLAGS}
                self.store.write_once(key, canonical_json(manifest))
            except CollectionError:
                raise
            except Exception:
                # Source exceptions may interpolate licensed data. Preserve the
                # intent and fail, but never echo provider exception contents.
                raise CollectionError("Historical source collection failed; unfinished intent retained") from None
            reference = {"key": key, "sha256": content_hash(manifest)}
            return reference, self._load_window(reference)[0], True

    def collect(self):
        """Prepare all windows and return exportable counts, references and gaps."""
        windows, calls, reused, records, empty = [], 0, 0, 0, 0
        missing = {path: 0 for path in self.plan.field_catalog}
        for start, end in self.plan.windows():
            reference, manifest, fetched = self._collect_window(start, end)
            windows.append(reference)
            calls += int(fetched); reused += int(not fetched)
            records += manifest["record_count"]; empty += int(manifest["record_count"] == 0)
            for path, count in manifest["missing_values"].items():
                missing[path] += count
        return {"schema_version": 1, "plan_hash": self.plan.hash, "synthetic": self.synthetic,
                "window_refs": windows, "window_count": len(windows), "record_count": records,
                "provider_calls": calls, "reused_windows": reused, "empty_windows": empty,
                "missing_values": missing, **_FLAGS}
