"""Declared historical source batches, not a claim of PIT source certification.

Only projected source fields are recorded. Missing vendor receipt, publication,
classification and listing evidence remains missing. Collection time and LEAN
end_time never become substitutes for historical availability. Real row values
stay in the cloud; public ingest receipts contain counts, hashes and gaps only.
"""
from collections.abc import Mapping
from datetime import date
import json
import math
from numbers import Integral, Real
import re

import pandas as pd

from .artifacts import ArtifactConflict, canonical_json, content_hash, decode_events, validate_key
from .contracts import DEVELOPMENT_END, RECORD_COLUMNS, aware, validate_records


class IngestionError(ValueError):
    """A source batch violates its declared historical contract."""


class MissingPITEvidence(IngestionError):
    """Unknown source evidence cannot be promoted to a causal feature view."""


_PATH = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_COMMON = {"sid", "source_revision", "vendor_available_at", "historical_ingested_at", "availability_basis"}
_LIQUIDITY = _COMMON | {"session", "dollar_volume", "dollar_volume_field", "instrument_type", "listed",
    "classification_effective_at", "classification_available_at", "listing_effective_at", "listing_available_at"}
_FINANCIAL = _COMMON | {"field_path", "unit", "period_accessor", "report_period_end", "value",
    "public_at", "public_date", "public_precision"}
_ACTUAL = "actual_historical_receipt"
_CLASSIFICATIONS = {"common_stock", "adr", "reit_common", "etf", "etn", "closed_end_fund",
                    "preferred_stock", "unit", "warrant", "otc"}


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise IngestionError("Nonempty source identity required: " + name)
    return value


def _timestamp(value, name, optional=True):
    if value is None and optional:
        return None
    try:
        stamp = aware(value)
    except (ValueError, TypeError) as exc:
        raise IngestionError("Explicit historical timezone required: " + name) from exc
    if pd.isna(stamp) or stamp >= DEVELOPMENT_END:
        raise IngestionError("Missing/final-period timestamp prohibited: " + name)
    return stamp.isoformat()


def _number(value, name, nonnegative=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (Integral, Real)):
        raise IngestionError("Source numeric value must be a JSON-compatible real: " + name)
    number = int(value) if isinstance(value, Integral) else float(value)
    try:
        finite = math.isfinite(number)
    except OverflowError as exc:
        raise IngestionError("Source numeric value exceeds supported arithmetic: " + name) from exc
    if not finite or (nonnegative and number < 0):
        raise IngestionError("Invalid source numeric value: " + name)
    return number


def _source_path(value, name):
    if not isinstance(value, str) or not _PATH.fullmatch(value):
        raise IngestionError("Explicit attribute path required: " + name)
    return value


def _dollar_volume_path(value):
    path = _source_path(value, "dollar_volume_field")
    if path.split(".")[-1].replace("_", "").lower() != "dollarvolume":
        raise IngestionError("Liquidity requires the supplied DollarVolume field; close-times-volume is prohibited")
    return path


def _get_path(obj, path):
    current = obj
    for part in _source_path(path, "source mapping").split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return None
            current = current[part]
        else:
            try:
                current = getattr(current, part)
            except AttributeError:
                return None
        if current is None:
            return None
    if callable(current):
        raise IngestionError("Source mapping cannot invoke methods or calculated callbacks")
    return current


def extract_qc_records(objects, *, kind, field_map, constants=None, symbol_path="symbol"):
    """Project historical QC objects with explicit paths and Symbol.id identity.

    There is no ticker-to-current-Symbol registry. Missing mapped properties are
    None. The caller supplies a *historical* batch, not today's constituent list.
    This mapping verifies attribute provenance shape, not upstream data coverage.
    """
    allowed = _LIQUIDITY if kind == "liquidity" else _FINANCIAL if kind == "financial" else None
    if allowed is None or not isinstance(field_map, Mapping):
        raise IngestionError("Known batch kind and explicit field mapping required")
    constants = dict(constants or {})
    if (set(field_map) & set(constants) or "sid" in set(field_map) | set(constants)
            or not (set(field_map) | set(constants)) <= allowed - {"sid"}):
        raise IngestionError("Mapped fields/constants conflict or attempt to replace permanent SID")
    for path in field_map.values():
        _source_path(path, "source mapping")
    if kind == "liquidity":
        path = _dollar_volume_path(field_map.get("dollar_volume"))
        if "dollar_volume_field" in set(field_map) | set(constants):
            raise IngestionError("DollarVolume provenance is derived from the exact mapped source path")
    elif field_map.get("value") != constants.get("field_path"):
        raise IngestionError("Financial value path must exactly match its declared field_path")
    for obj in objects:
        symbol = _get_path(obj, symbol_path)
        if symbol is None or not hasattr(symbol, "id"):
            raise IngestionError("Historical QC Symbol with permanent id required; ticker strings are insufficient")
        row = dict(constants)
        row.update({name: _get_path(obj, path) for name, path in field_map.items()})
        if symbol.id is None:
            raise IngestionError("Historical QC Symbol has no permanent id")
        row["sid"] = _text(str(symbol.id), "permanent SID")
        if kind == "liquidity":
            row["dollar_volume_field"] = path
        yield row


def resolve_historical_sid(ticker, at, mappings):
    """Resolve only then-effective, then-known mappings; ambiguity is an error."""
    _text(ticker, "ticker")
    moment = aware(_timestamp(at, "mapping decision", optional=False))
    matches = set()
    for row in mappings:
        if row.get("ticker") != ticker:
            continue
        begin = aware(_timestamp(row.get("effective_from"), "mapping effective_from", optional=False))
        receipt = aware(_timestamp(row.get("available_at"), "mapping available_at", optional=False))
        end = _timestamp(row.get("effective_to"), "mapping effective_to")
        if end is not None and aware(end) <= begin:
            raise IngestionError("Mapping interval is empty")
        if begin <= moment and receipt <= moment and (end is None or moment < aware(end)):
            matches.add(_text(row.get("sid"), "mapping permanent SID"))
    if len(matches) != 1:
        raise IngestionError("Historical ticker mapping is missing or ambiguous")
    return matches.pop()


class HistoricalBatchIngestor:
    """Content-addressed projected batches plus a bounded-partition hash index.

    One explicitly operated cloud producer is required by the store. This class
    does not add distributed locking. Partition keys must be the preregistered
    source/year/SID-chunk plan; streaming callers should not put all years into
    one index. Native SID and timestamp assertions still need source audits.
    """
    def __init__(self, store, *, source, data_version, origin, financial_catalog=None,
                 synthetic=False, max_batch_records=10000):
        if not synthetic and getattr(store, "residency", None) != "quantconnect_cloud":
            raise IngestionError("Real historical row values may only enter authorized QuantConnect cloud storage")
        if origin not in {"historical_all_market", "historical_declared_fixture"}:
            raise IngestionError("Current constituents cannot supply historical coverage")
        if type(max_batch_records) is not int or max_batch_records < 1:
            raise IngestionError("A positive bounded source batch size is required")
        self.store, self.synthetic = store, synthetic
        self.source, self.data_version = _text(source, "source"), _text(data_version, "data_version")
        self.origin, self.limit = origin, max_batch_records
        self.financial_catalog = json.loads(canonical_json(dict(financial_catalog or {})))
        for path, spec in self.financial_catalog.items():
            _source_path(path, "financial catalog path")
            if not isinstance(spec, Mapping) or set(spec) != {"unit", "period_accessor"}:
                raise IngestionError("Financial catalog must pin units and period accessor")
            _text(spec["unit"], "financial unit")
            _text(spec["period_accessor"], "period accessor")
        self.source_binding = {"source": source, "data_version": data_version,
            "origin": origin, "synthetic": synthetic, "financial_catalog": self.financial_catalog}
        self.namespace = content_hash(self.source_binding)

    def _normalize(self, kind, raw):
        allowed = _LIQUIDITY if kind == "liquidity" else _FINANCIAL if kind == "financial" else None
        if allowed is None or not isinstance(raw, Mapping) or not set(raw) <= allowed:
            raise IngestionError("Unknown source kind, fields, or non-mapping source record")
        row = {name: raw.get(name) for name in sorted(allowed)}
        for name in ("sid", "source_revision"):
            row[name] = _text(row[name], name)
        if row["availability_basis"] not in {_ACTUAL, "modeled_lean_frontier", "unknown", None}:
            raise IngestionError("Unknown source availability basis")
        for name in ("vendor_available_at", "historical_ingested_at"):
            row[name] = _timestamp(row[name], name)
        if (row["vendor_available_at"] is not None and row["historical_ingested_at"] is not None
                and aware(row["historical_ingested_at"]) < aware(row["vendor_available_at"])):
            raise IngestionError("Historical ingestion cannot precede vendor receipt")
        if kind == "liquidity":
            row["session"] = _timestamp(row["session"], "session", optional=False)
            row["dollar_volume_field"] = _dollar_volume_path(row["dollar_volume_field"])
            row["dollar_volume"] = _number(row["dollar_volume"], "DollarVolume", nonnegative=True)
            if row["listed"] is not None and type(row["listed"]) is not bool:
                raise IngestionError("Historical listed state must be explicit boolean or unknown")
            if row["instrument_type"] is not None and row["instrument_type"] not in _CLASSIFICATIONS:
                raise IngestionError("Unmapped historical classification must remain unknown")
            for name in ("classification_effective_at", "classification_available_at", "listing_effective_at", "listing_available_at"):
                row[name] = _timestamp(row[name], name)
            if row["vendor_available_at"] is not None and aware(row["vendor_available_at"]) < aware(row["session"]):
                raise IngestionError("Completed-session liquidity cannot arrive before session close")
        else:
            path = _source_path(row["field_path"], "field_path")
            binding = self.financial_catalog.get(path)
            if binding is None or any(row[name] != binding[name] for name in ("unit", "period_accessor")):
                raise IngestionError("Financial field/unit/accessor not in the pinned catalog")
            row["report_period_end"] = _timestamp(row["report_period_end"], "report_period_end", optional=False)
            row["value"] = _number(row["value"], "financial value")
            row["public_at"] = _timestamp(row["public_at"], "public_at")
            if row["public_precision"] not in {"timestamp", "date", "unknown", None}:
                raise IngestionError("Publication precision must be explicit")
            if row["public_date"] is not None:
                try:
                    public_date = date.fromisoformat(row["public_date"])
                except (ValueError, TypeError) as exc:
                    raise IngestionError("Publication date must be an ISO calendar date") from exc
                if public_date >= DEVELOPMENT_END.date() or public_date < aware(row["report_period_end"]).date():
                    raise IngestionError("Publication date is final-period or precedes report period")
                row["public_date"] = public_date.isoformat()
                if row["vendor_available_at"] is not None and aware(row["vendor_available_at"]).date() < public_date:
                    raise IngestionError("Vendor receipt precedes publication date")
            if row["public_precision"] == "timestamp" and row["public_at"] is None:
                raise IngestionError("Timestamp publication precision needs its actual timestamp")
            if row["public_precision"] == "date" and (row["public_date"] is None or row["public_at"] is not None):
                raise IngestionError("Date-only publication must not manufacture an intraday timestamp")
            if row["public_at"] is not None:
                if aware(row["public_at"]) < aware(row["report_period_end"]):
                    raise IngestionError("Publication precedes report period")
                if row["vendor_available_at"] is not None and aware(row["vendor_available_at"]) < aware(row["public_at"]):
                    raise IngestionError("Vendor receipt precedes actual publication")
        return row

    @staticmethod
    def _gaps(kind, rows):
        counts = {}
        required = ["vendor_available_at", "historical_ingested_at"]
        required += (["dollar_volume", "instrument_type", "listed", "classification_effective_at",
                      "classification_available_at", "listing_effective_at", "listing_available_at"]
                     if kind == "liquidity" else ["value"])
        for name in required:
            missing = sum(row[name] is None for row in rows)
            if missing:
                counts[name + "_missing"] = missing
        unverified = sum(row["availability_basis"] != _ACTUAL for row in rows)
        if unverified:
            counts["actual_availability_unverified"] = unverified
        if kind == "financial":
            missing = sum(row["public_precision"] not in {"date", "timestamp"} for row in rows)
            if missing:
                counts["publication_missing"] = missing
            dates = sum(row["public_precision"] == "date" for row in rows)
            if dates:
                counts["date_only_requires_exchange_release_gate"] = dates
        return counts

    def ingest(self, kind, records, *, partition):
        """Record one bounded historical batch; return metadata only."""
        partition = validate_key(partition)
        rows = []
        for raw in records:
            if len(rows) >= self.limit:
                raise IngestionError("Batch limit exceeded; stream preregistered partitions")
            rows.append(self._normalize(kind, raw))
        if not rows:
            raise IngestionError("Empty historical batches cannot supply coverage evidence")
        identities = {}
        for row in rows:
            logical = ([row["sid"], row["session"], row["source_revision"]] if kind == "liquidity" else
                [row["sid"], row["field_path"], row["period_accessor"], row["report_period_end"], row["source_revision"]])
            identity = content_hash(logical)
            if identity in identities:
                raise IngestionError("Duplicate vintage identity inside source batch")
            identities[identity] = content_hash(row)
        rows.sort(key=canonical_json)
        if content_hash(self.source_binding) != self.namespace:
            raise IngestionError("Pinned ingestion source binding was mutated")
        envelope = {"schema_version": 1, "kind": kind, "namespace": self.namespace, "source_binding": self.source_binding,
                    "partition": partition, "records": rows}
        sha = content_hash(envelope)
        key = "ingestion/v1/batches/" + sha + ".json"
        index = "ingestion/v1/index/" + self.namespace + "/" + kind + "/" + partition + ".jsonl"
        with self.store.locked("ingestion/" + content_hash(index)):
            events = decode_events(self.store.read_bytes(index)) if self.store.exists(index) else []
            known, reused = {}, False
            for event in events:
                payload = event["event"]
                known.update(payload["vintages"])
                reused |= payload["batch_hash"] == sha
            for identity, digest in identities.items():
                if identity in known and known[identity] != digest:
                    raise ArtifactConflict("A historical vintage changed without a new source revision")
            self.store.write_once(key, canonical_json(envelope))
            if not reused:
                self.store.append_event(index, {"batch_hash": sha, "batch_key": key, "vintages": identities})
        return {"schema_version": 1, "kind": kind, "batch_ref": {"key": key, "sha256": sha},
            "index_ref": index, "rows": len(rows), "new_vintages": sum(identity not in known for identity in identities),
            "reused_batch": reused, "gaps": self._gaps(kind, rows), "row_values_exported": False,
            "synthetic": self.synthetic, "origin": self.origin, "full_historical_universe_certified": False,
            "actual_source_timing_certified": False}

    def ingest_stream(self, kind, batches, *, partition):
        for records in batches:
            yield self.ingest(kind, records, partition=partition)

    def _records(self, reference, kind):
        if (not isinstance(reference, Mapping) or set(reference) != {"key", "sha256"}
                or not isinstance(reference["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"])
                or reference["key"] != "ingestion/v1/batches/" + reference["sha256"] + ".json"):
            raise IngestionError("Content-bound ingestion batch reference required")
        envelope = json.loads(self.store.read_bytes(reference["key"]))
        if (not isinstance(envelope, dict) or content_hash(envelope) != reference["sha256"]
                or envelope.get("schema_version") != 1 or envelope.get("namespace") != self.namespace
                or envelope.get("source_binding") != self.source_binding
                or content_hash(envelope.get("source_binding")) != self.namespace or envelope.get("kind") != kind):
            raise IngestionError("Batch bytes, source namespace or batch kind changed")
        partition = validate_key(envelope["partition"])
        index = "ingestion/v1/index/" + self.namespace + "/" + kind + "/" + partition + ".jsonl"
        if not self.store.exists(index) or not any(event["event"].get("batch_hash") == reference["sha256"]
                and event["event"].get("batch_key") == reference["key"]
                for event in decode_events(self.store.read_bytes(index))):
            raise IngestionError("Batch has no completed ingestion index event")
        rows = [self._normalize(kind, row) for row in envelope["records"]]
        if rows != envelope["records"]:
            raise IngestionError("Stored source projection is not canonical")
        return rows

    def _combined_records(self, references, kind):
        references = [references] if isinstance(references, Mapping) else references
        if not isinstance(references, (list, tuple)) or not references:
            raise IngestionError("One or more completed source batch references required")
        combined, seen_vintages = {}, {}
        for reference in references:
            for row in self._records(reference, kind):
                digest = content_hash(row)
                identity = content_hash([row["sid"], row["session"], row["source_revision"]] if kind == "liquidity" else
                    [row["sid"], row["field_path"], row["period_accessor"], row["report_period_end"], row["source_revision"]])
                if identity in seen_vintages and seen_vintages[identity] != digest:
                    raise ArtifactConflict("Overlapping source partitions disagree on a historical vintage")
                seen_vintages[identity] = digest
                combined[digest] = row
        return list(combined.values())

    def liquidity_rows_asof(self, reference, formation_at, expected_sessions):
        """Cloud-only rank input; unknown evidence fails, never filters a name.

        This constructs the existing rank kernel's shape from declared actual
        timestamps. It does not certify those declarations or all-market scope.
        """
        formation = aware(_timestamp(formation_at, "formation", optional=False))
        sessions = {aware(_timestamp(x, "expected session", optional=False)) for x in expected_sessions}
        if not sessions or max(sessions) >= formation:
            raise IngestionError("Completed expected exchange sessions are required")
        selected = [row for row in self._combined_records(reference, "liquidity") if aware(row["session"]) in sessions]
        if self._gaps("liquidity", selected):
            raise MissingPITEvidence("Historical liquidity/classification or actual timing evidence is incomplete")
        result = []
        for row in selected:
            available = max(aware(row[name]) for name in ("vendor_available_at", "historical_ingested_at",
                "classification_effective_at", "classification_available_at", "listing_effective_at", "listing_available_at"))
            if available <= formation:
                result.append({"sid": row["sid"], "session": aware(row["session"]), "available_at": available,
                    "dollar_volume": row["dollar_volume"], "instrument_type": row["instrument_type"], "listed": row["listed"]})
        frame = pd.DataFrame(result, columns=["sid", "session", "available_at", "dollar_volume", "instrument_type", "listed"])
        if frame.duplicated(["sid", "session", "available_at"]).any():
            raise IngestionError("Simultaneous liquidity revisions are ambiguous")
        return frame.sort_values("available_at").drop_duplicates(["sid", "session"], keep="last")

    def financial_records_asof(self, reference, formation_at, *, date_release_gates=None):
        """Cloud-only vintage records for causal_window; missing value stays NaN.

        Date-only gates must come from an independently checked exchange calendar
        and be the next session close after publication. This checks shape and
        causal ordering only; calendar/source certification is a separate audit.
        """
        formation = aware(_timestamp(formation_at, "formation", optional=False))
        gates = date_release_gates or {}
        output = []
        for row in self._combined_records(reference, "financial"):
            if aware(row["report_period_end"]) > formation:
                continue
            if (row["availability_basis"] != _ACTUAL or row["vendor_available_at"] is None
                    or row["historical_ingested_at"] is None):
                raise MissingPITEvidence("Actual historical financial receipt and ingestion evidence is missing")
            if row["public_precision"] == "timestamp":
                release = aware(row["public_at"])
            elif row["public_precision"] == "date" and row["public_date"] in gates:
                release = aware(_timestamp(gates[row["public_date"]], "exchange publication gate", optional=False))
                if release.date() <= date.fromisoformat(row["public_date"]):
                    raise IngestionError("Date-only reports must wait through a later exchange-session close")
            else:
                raise MissingPITEvidence("Publication timing or checked date-only exchange gate is missing")
            available = max(release, aware(row["vendor_available_at"]), aware(row["historical_ingested_at"]))
            if available <= formation:
                output.append({"sid": row["sid"], "field": row["field_path"], "event_time": aware(row["report_period_end"]),
                    "available_time": available, "value": row["value"], "revision": row["source_revision"]})
        return validate_records(pd.DataFrame(output, columns=RECORD_COLUMNS))
