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

from .artifacts import ArtifactConflict, canonical_json, content_hash
from .contracts import DEVELOPMENT_END, aware


class CollectionError(ValueError):
    """A collection request or projected record is invalid."""


class CollectionMiss(CollectionError):
    """A cache-only consumer cannot request missing source data."""


class CollectionInterrupted(CollectionError):
    """An unfinished intent requires explicit reconciliation, never auto-retry."""


class CollectionIntegrityError(CollectionError):
    """A reference, completed manifest or payload is inconsistent."""


_COLLECTION_DIAGNOSTIC_STAGES = {
    "capacity_preflight", "intent_persist", "row_projection", "row_observation",
    "batch_serialize", "batch_persist", "batch_verify", "manifest_serialize",
    "manifest_persist", "manifest_verify", "completed_cache_verify", "cache_read",
}
_COLLECTION_FAILURE_CODES = {
    "unexpected_exception", "artifact_conflict", "capacity_unavailable",
    "byte_capacity_insufficient", "file_capacity_insufficient", "invalid_capacity_request",
    "save_rejected", "save_exception", "verification_failed", "verification_exception",
}
_COLLECTION_EXCEPTION_KINDS = {
    "io_error", "artifact_conflict", "type_error", "value_error", "runtime_error",
    "attribute_error", "key_error", "index_error", "overflow_error", "memory_error", "other",
}


def safe_collection_diagnostic(raw):
    """Revalidate closed tokens only; no native messages, types, keys or rows."""
    if (type(raw) is not dict or any(type(key) is not str for key in raw)
            or set(raw) != {"schema_version", "stage", "failure_code", "exception_kind"}
            or type(raw["schema_version"]) is not int or raw["schema_version"] != 1):
        return None
    for name, allowed in (("stage", _COLLECTION_DIAGNOSTIC_STAGES),
                          ("failure_code", _COLLECTION_FAILURE_CODES),
                          ("exception_kind", _COLLECTION_EXCEPTION_KINDS)):
        if type(raw[name]) is not str or raw[name] not in allowed:
            return None
    return dict(raw)


class InternalCollectionDiagnosticError(CollectionError):
    """Opt-in value-free internal failure; old collector messages are unchanged."""

    def __init__(self, diagnostic):
        self.diagnostic = safe_collection_diagnostic(diagnostic)
        if self.diagnostic is None:
            raise ValueError("Invalid closed collection diagnostic")
        super().__init__("Historical collection operation failed; collection_diagnostic="
                         + canonical_json(self.diagnostic).decode("utf-8"))


def internal_collection_failure(stage, error):
    """Classify owned persistence errors without stringifying any exception."""
    kind = "other"
    for cls, token in ((ArtifactConflict, "artifact_conflict"), (OSError, "io_error"),
                       (TypeError, "type_error"), (ValueError, "value_error"),
                       (AttributeError, "attribute_error"), (KeyError, "key_error"),
                       (IndexError, "index_error"), (OverflowError, "overflow_error"),
                       (MemoryError, "memory_error"), (RuntimeError, "runtime_error")):
        if isinstance(error, cls):
            kind = token
            break
    code = "artifact_conflict" if isinstance(error, ArtifactConflict) else "unexpected_exception"
    # Only our owned classes may contribute their fixed vocabulary. SDK and
    # source exceptions are never introspected or converted to text.
    try:
        from .storage_capacity import StorageCapacityError, StorageOperationError, StorageVerificationError
        if type(error) in (StorageCapacityError, StorageOperationError, StorageVerificationError):
            raw = error.safe_diagnostic()
            if (type(raw) is dict and set(raw) == {"schema_version", "failure_code"}
                    and type(raw["schema_version"]) is int and raw["schema_version"] == 1
                    and type(raw["failure_code"]) is str and raw["failure_code"] in _COLLECTION_FAILURE_CODES):
                code = raw["failure_code"]
            if isinstance(error, StorageVerificationError):
                stage = {"batch_persist": "batch_verify", "manifest_persist": "manifest_verify"}.get(stage, stage)
    except Exception:
        pass
    diagnostic = {"schema_version": 1, "stage": stage, "failure_code": code, "exception_kind": kind}
    if safe_collection_diagnostic(diagnostic) is None:
        raise ValueError("Invalid closed collection diagnostic stage")
    return InternalCollectionDiagnosticError(diagnostic)


_SOURCE_DIAGNOSTIC_ENUMS = {
    "stage": {"request_validation", "notebook_timezone", "notebook_frontier", "sdk_import",
              "universe_setup", "history_request", "response_contract", "response_identity",
              "response_iteration", "snapshot_identity", "snapshot_clock", "snapshot_container",
              "snapshot_iteration", "row_identity", "field_projection", "completed"},
    "failure_code": {"unexpected_exception", "source_contract", "native_property_failed",
                     "native_sid_missing", "native_sid_empty", "native_sid_noncanonical", "native_sid_duplicate"},
    "exception_kind": {"source_contract", "type_error", "value_error", "runtime_error",
                       "attribute_error", "key_error", "index_error", "overflow_error",
                       "memory_error", "import_error", "other"},
    "response_kind": {"not_observed", "series", "dataframe", "other"},
    "index_kind": {"not_observed", "multiindex", "other"},
    "index_names": {"not_observed", "expected", "other"},
    "snapshot_kind": {"not_observed", "list", "tuple", "other"},
    "projection_kind": {"not_observed", "number", "boolean", "date", "text"},
}
_SOURCE_DIAGNOSTIC_COUNTS = {"native_calls", "response_rows", "index_levels", "snapshots_seen", "rows_emitted", "projection_position"}


def _safe_source_diagnostic(raw):
    """Only fixed structural tokens and bounded counts can leave QC Cloud.

    Never stringify an exception, a native type name, an index name, an object,
    a field path or a row. Revalidate even an owned exception's mutable payload.
    """
    if (type(raw) is not dict or any(type(key) is not str for key in raw)
            or set(raw) != {"schema_version", *_SOURCE_DIAGNOSTIC_ENUMS, *_SOURCE_DIAGNOSTIC_COUNTS}):
        return None
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        return None
    for key, allowed in _SOURCE_DIAGNOSTIC_ENUMS.items():
        if type(raw[key]) is not str or raw[key] not in allowed:
            return None
    for key in _SOURCE_DIAGNOSTIC_COUNTS:
        if raw[key] is not None and (type(raw[key]) is not int or not 0 <= raw[key] <= 1000000000):
            return None
    return dict(raw)


class SourceDiagnosticError(CollectionError):
    """An owned adapter failure may attach closed, value-free diagnostics."""

    def __init__(self, message, *, diagnostic=None):
        super().__init__(message)
        self.diagnostic = _safe_source_diagnostic(diagnostic)


def _source_failure_message(prefix, error):
    try:
        diagnostic = _safe_source_diagnostic(error.diagnostic) if isinstance(error, SourceDiagnosticError) else None
    except Exception:
        diagnostic = None
    return prefix if diagnostic is None else prefix + "; diagnostic=" + canonical_json(diagnostic).decode("utf-8")


_HASH = re.compile(r"[0-9a-f]{64}")
_PATH = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*")
_FIELDS = {"schema_version", "plan_id", "scope", "source", "data_version", "start",
           "end_exclusive", "timezone", "fields", "calendar_days_per_request",
           "max_batch_records", "max_records_per_window", "source_manifest_hash"}
_ROOT = "historical-snapshots/v1/"
_OCCURRENCE_ROOT = "historical-snapshots/v2/"
_OBSERVATION_POLICY = "retain_source_occurrences"
_OCCURRENCE_COUNTS = {"duplicate_projection_records", "conflicting_projection_records"}
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
        if not isinstance(raw, Mapping):
            raise CollectionError("A complete collection plan with no unknown overrides is required")
        expected = _FIELDS | {"observation_policy"} if type(raw.get("schema_version")) is int and raw["schema_version"] == 2 else _FIELDS
        if set(raw) != expected:
            raise CollectionError("A complete collection plan with no unknown overrides is required")
        try:
            value = json.loads(canonical_json(dict(raw)))
        except (TypeError, ValueError):
            raise CollectionError("Collection plans require finite JSON configuration values") from None
        if (type(value["schema_version"]) is not int or value["schema_version"] not in (1, 2)
                or value["scope"] != "engineering"
                or value["source"] != "quantconnect_fundamental_universe"
                or value["timezone"] != "America/New_York"):
            raise CollectionError("Only the versioned NY engineering snapshot source is supported")
        if value["schema_version"] == 2 and value["observation_policy"] != _OBSERVATION_POLICY:
            raise CollectionError("Version 2 engineering collection must retain all source occurrences")
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
    sid, snapshot_at and values. Version 2 additionally requires the zero-based
    source_record_index within each snapshot and retains every occurrence.
    A missing value is None, never an invented zero.
    source=None enables completed-cache reads but no fetching or new writes.
    """
    def __init__(self, store, source, plan, *, synthetic=False, internal_diagnostics=False, before_fetch=None):
        if (not isinstance(plan, HistoricalCollectionPlan) or type(synthetic) is not bool
                or type(internal_diagnostics) is not bool or (before_fetch is not None and not callable(before_fetch))):
            raise CollectionError("A frozen plan and explicit synthetic classification are required")
        if not synthetic and getattr(store, "residency", None) != "quantconnect_cloud":
            raise CollectionError("Real snapshots must remain inside QuantConnect cloud storage")
        if source is not None and not callable(getattr(source, "fetch", None)):
            raise CollectionError("The source must implement the bounded fetch contract")
        self.store, self.source, self.plan, self.synthetic = store, source, plan, synthetic
        self.internal_diagnostics, self.before_fetch = internal_diagnostics, before_fetch
        self._schema_version = plan.to_dict()["schema_version"]
        self._occurrences = self._schema_version == 2
        self._root = _OCCURRENCE_ROOT if self._occurrences else _ROOT

    def _internal_call(self, stage, operation, *args):
        try:
            return operation(*args)
        except CollectionError:
            raise
        except Exception as error:
            if self.internal_diagnostics:
                raise internal_collection_failure(stage, error) from None
            raise

    def _window(self, start, end):
        return {"start": start.isoformat(), "end_exclusive": end.isoformat()}

    def _identity(self, window):
        return {"plan_hash": self.plan.hash, "synthetic": self.synthetic, "window": window}

    def _key(self, window):
        return self._root + "windows/" + content_hash(self._identity(window)) + ".json"

    def _row(self, raw, start, end):
        required = {"sid", "snapshot_at", "values"} | ({"source_record_index"} if self._occurrences else set())
        if not isinstance(raw, Mapping) or set(raw) != required:
            raise CollectionError("Projected snapshots require exactly the declared source columns")
        sid, stamp = _text(raw["sid"]), _time(raw["snapshot_at"])
        if len(sid) > 256 or not start <= stamp < end or stamp >= DEVELOPMENT_END:
            raise CollectionError("Snapshot identity or time is outside the frozen window")
        if self._occurrences and (type(raw["source_record_index"]) is not int
                or not 0 <= raw["source_record_index"] < self.plan.to_dict()["max_records_per_window"]):
            raise CollectionError("Source occurrence index must be a bounded native nonnegative integer")
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
                            parsed = date.fromisoformat(value)
                            if parsed.isoformat() != value or parsed == date.min:
                                raise ValueError
                        except ValueError:
                            raise CollectionError("Date fields require an ISO date; SDK missing-date sentinels must be null") from None
            values[path] = value
        row = {"sid": sid, "snapshot_at": stamp.isoformat(), "values": values}
        if self._occurrences:
            row["source_record_index"] = raw["source_record_index"]
        return row

    def _projection_state(self):
        return {"record_count": 0, "identities": set(), "snapshots": set(), "sids": set(),
                "missing_values": {path: 0 for path in self.plan.field_catalog},
                "next_indices": {}, "first_projections": {},
                "duplicate_projection_records": 0, "conflicting_projection_records": 0}

    def _observe(self, row, state):
        """Verify source sequence and count every row on ingestion and replay.

        A repeated SID/snapshot is an observation in v2, never a preferred
        replacement. Conflicts compare each occurrence with the first projected
        values of that SID/snapshot, including repeats across batch boundaries.
        """
        sid_stamp = (row["sid"], row["snapshot_at"])
        if self._occurrences:
            stamp = row["snapshot_at"]
            if row["source_record_index"] != state["next_indices"].get(stamp, 0):
                raise CollectionError("Source occurrence indices must start at zero and be continuous per snapshot")
            state["next_indices"][stamp] = row["source_record_index"] + 1
            identity = (stamp, row["source_record_index"])
            projected = content_hash(row["values"])
            if sid_stamp in state["first_projections"]:
                state["duplicate_projection_records"] += 1
                state["conflicting_projection_records"] += projected != state["first_projections"][sid_stamp]
            else:
                state["first_projections"][sid_stamp] = projected
        else:
            identity = sid_stamp
        if identity in state["identities"]:
            raise CollectionError("Duplicate snapshot identity inside the source window")
        state["identities"].add(identity)
        state["record_count"] += 1
        if state["record_count"] > self.plan.to_dict()["max_records_per_window"]:
            raise CollectionError("Source exceeded the frozen window record bound")
        state["snapshots"].add(row["snapshot_at"])
        state["sids"].add(row["sid"])
        for path, value in row["values"].items():
            state["missing_values"][path] += value is None

    def _counts(self, state):
        return {"record_count": state["record_count"], "snapshot_count": len(state["snapshots"]),
                "unique_sid_count": len(state["sids"])}

    def _occurrence_metadata(self, state):
        if not self._occurrences:
            return {}
        return {"observation_policy": _OBSERVATION_POLICY,
                **{key: state[key] for key in _OCCURRENCE_COUNTS}}

    def _write_batch(self, window, index, rows):
        payload = {"schema_version": self._schema_version, **self._identity(window), "batch_index": index, "records": rows}
        digest = self._internal_call("batch_serialize", content_hash, payload)
        key = self._root + "objects/" + digest + ".json"
        self._internal_call("batch_persist", self.store.write_once, key,
                            self._internal_call("batch_serialize", canonical_json, payload))
        return {"key": key, "sha256": digest}

    def _document(self, reference, prefix):
        if (not isinstance(reference, Mapping) or set(reference) != {"key", "sha256"}
                or not isinstance(reference["sha256"], str) or _HASH.fullmatch(reference["sha256"]) is None
                or not isinstance(reference["key"], str) or not reference["key"].startswith(self._root + prefix)
                or _HASH.fullmatch(reference["key"][len(self._root + prefix):-5]) is None
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
        if self._occurrences:
            required |= {"observation_policy", *_OCCURRENCE_COUNTS}
        if (not isinstance(manifest, dict) or set(manifest) != required
                or type(manifest["schema_version"]) is not int or manifest["schema_version"] != self._schema_version
                or manifest["status"] != "completed"
                or manifest["plan_hash"] != self.plan.hash or type(manifest["synthetic"]) is not bool
                or manifest["synthetic"] != self.synthetic or manifest["plan_identity"] != self.plan.identity()
                or any(manifest[key] is not value for key, value in _FLAGS.items())
                or (self._occurrences and manifest["observation_policy"] != _OBSERVATION_POLICY)):
            raise CollectionIntegrityError("Only completed results of this exact source plan may be consumed")
        window = manifest["window"]
        if window not in [self._window(*pair) for pair in self.plan.windows()] or reference["key"] != self._key(window):
            raise CollectionIntegrityError("Collection reference belongs to another interval or source plan")
        if (not isinstance(manifest["batches"], list) or type(manifest["provider_calls"]) is not int
                or manifest["provider_calls"] != 1):
            raise CollectionIntegrityError("Completed window metadata is invalid")
        raw_plan = self.plan.to_dict()
        start, end = _time(window["start"]), _time(window["end_exclusive"])
        rows, state = [], self._projection_state()
        for index, ref in enumerate(manifest["batches"]):
            payload = self._document(ref, "objects/")
            if (not isinstance(payload, dict) or set(payload) != {"schema_version", "plan_hash", "synthetic", "window", "batch_index", "records"}
                    or type(payload["schema_version"]) is not int or payload["schema_version"] != self._schema_version
                    or type(payload["batch_index"]) is not int or payload["batch_index"] != index
                    or type(payload["synthetic"]) is not bool
                    or any(payload[key] != value for key, value in self._identity(window).items())
                    or ref["key"] != self._root + "objects/" + ref["sha256"] + ".json"
                    or not isinstance(payload["records"], list) or not 1 <= len(payload["records"]) <= raw_plan["max_batch_records"]):
                raise CollectionIntegrityError("Collection batch identity, sequence or bound is invalid")
            for raw in payload["records"]:
                try:
                    row = self._row(raw, start, end)
                    if row != raw:
                        raise CollectionError("Noncanonical source projection")
                    self._observe(row, state)
                except CollectionError:
                    raise CollectionIntegrityError("Stored source rows violate the frozen projection") from None
                rows.append(row)
        counts = self._counts(state)
        if self._occurrences:
            counts.update({key: state[key] for key in _OCCURRENCE_COUNTS})
        if (any(type(manifest[key]) is not int or manifest[key] != value for key, value in counts.items())
                or not isinstance(manifest["missing_values"], dict)
                or any(type(value) is not int for value in manifest["missing_values"].values())
                or manifest["missing_values"] != state["missing_values"]):
            raise CollectionIntegrityError("Completed counts and gaps do not match source payloads")
        return manifest, rows

    def read_window(self, window_ref):
        """Return rows only after the entire completed window has been verified."""
        return self._load_window(window_ref)[1]

    def _source_rows(self, start, end):
        """Do not let provider exception messages disclose licensed row values."""
        try:
            source_rows = iter(self.source.fetch(start, end, self.plan.field_catalog))
        except Exception as error:
            raise CollectionError(_source_failure_message(
                "Historical source fetch failed; unfinished intent retained", error)) from None
        while True:
            try:
                row = next(source_rows)
            except StopIteration:
                return
            except Exception as error:
                raise CollectionError(_source_failure_message(
                    "Historical source iteration failed; unfinished intent retained", error)) from None
            yield row

    def _collect_window(self, start, end):
        window = self._window(start, end)
        key = self._key(window)
        with self.store.locked(self._root + "window-locks/" + content_hash(self._identity(window))):
            if self.store.exists(key):
                reference = {"key": key, "sha256": sha256(self.store.read_bytes(key)).hexdigest()}
                return reference, self._internal_call("completed_cache_verify", self._load_window, reference)[0], False
            intent = self._root + "intents/" + content_hash(self._identity(window)) + ".json"
            if self.store.exists(intent):
                raise CollectionInterrupted("Unfinished collection intent requires reconciliation or a new frozen source plan")
            if self.source is None:
                raise CollectionMiss("Cache-only collection cannot call a source; prefetch the frozen plan first")
            if self.before_fetch is not None:
                self._internal_call("capacity_preflight", self.before_fetch, self.plan, start, end)
            self._internal_call("intent_persist", self.store.write_once, intent,
                                canonical_json({"schema_version": self._schema_version, **self._identity(window)}))
            plan = self.plan.to_dict()
            refs, batch, state = [], [], self._projection_state()
            try:
                for raw in self._source_rows(start, end):
                    row = self._internal_call("row_projection", self._row, raw, start, end)
                    self._internal_call("row_observation", self._observe, row, state)
                    batch.append(row)
                    if len(batch) == plan["max_batch_records"]:
                        refs.append(self._write_batch(window, len(refs), batch))
                        batch = []
                if batch:
                    refs.append(self._write_batch(window, len(refs), batch))
                manifest = {"schema_version": self._schema_version, **self._identity(window), "status": "completed",
                    "plan_identity": self.plan.identity(), "batches": refs, **self._counts(state),
                    "missing_values": state["missing_values"], "provider_calls": 1,
                    **self._occurrence_metadata(state), **_FLAGS}
                encoded = self._internal_call("manifest_serialize", canonical_json, manifest)
                self._internal_call("manifest_persist", self.store.write_once, key, encoded)
            except CollectionError:
                raise
            except Exception:
                # Source exceptions may interpolate licensed data. Preserve the
                # intent and fail, but never echo provider exception contents.
                raise CollectionError("Historical source collection failed; unfinished intent retained") from None
            reference = {"key": key, "sha256": content_hash(manifest)}
            return reference, self._internal_call("completed_cache_verify", self._load_window, reference)[0], True

    def collect(self):
        """Prepare all windows and return exportable counts, references and gaps."""
        windows, calls, reused, records, empty = [], 0, 0, 0, 0
        missing = {path: 0 for path in self.plan.field_catalog}
        occurrences = {key: 0 for key in _OCCURRENCE_COUNTS}
        for start, end in self.plan.windows():
            reference, manifest, fetched = self._collect_window(start, end)
            windows.append(reference)
            calls += int(fetched); reused += int(not fetched)
            records += manifest["record_count"]; empty += int(manifest["record_count"] == 0)
            for path, count in manifest["missing_values"].items():
                missing[path] += count
            if self._occurrences:
                for key in _OCCURRENCE_COUNTS:
                    occurrences[key] += manifest[key]
        return {"schema_version": self._schema_version, "plan_hash": self.plan.hash, "synthetic": self.synthetic,
                "window_refs": windows, "window_count": len(windows), "record_count": records,
                "provider_calls": calls, "reused_windows": reused, "empty_windows": empty,
                "missing_values": missing, **self._occurrence_metadata(occurrences), **_FLAGS}
