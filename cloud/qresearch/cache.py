"""Partitioned, immutable cloud feature cache. Factors never receive this object."""
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import pandas as pd
from .contracts import DataRequest, NY, RECORD_COLUMNS, digest, validate_records


class CacheMiss(RuntimeError):
    pass


def _encode(data):
    rows = []
    for row in data.itertuples(index=False):
        rows.append([str(row.sid), str(row.field), row.event_time.isoformat(),
                     row.available_time.isoformat(), None if pd.isna(row.value) else float(row.value),
                     str(row.revision)])
    return json.dumps(rows, separators=(",", ":"), allow_nan=False).encode()


def _decode(raw):
    return validate_records(pd.DataFrame(json.loads(raw), columns=RECORD_COLUMNS))


class SharedDataCache:
    """One producer, many cache-only readers. No implied distributed CAS lock.

    A whole calendar year and fixed SID chunks are cache units. Merge all factor
    field requirements before prefetch. Historical vintages must have a pinned
    source version; a refresh requires a new version instead of overwriting.
    """
    def __init__(self, store, provider=None, sid_chunk_size=64):
        if sid_chunk_size < 1:
            raise ValueError("Positive SID chunk size required")
        self.store, self.provider = store, provider
        self.sid_chunk_size = sid_chunk_size

    def partitions(self, request):
        for year in range(request.start.year, request.end.year + 1):
            start, end = datetime(year, 1, 1, tzinfo=NY), datetime(year + 1, 1, 1, tzinfo=NY)
            if start >= request.end or end <= request.start:
                continue
            for offset in range(0, len(request.sids), self.sid_chunk_size):
                yield replace(request, start=start, end=end,
                              sids=request.sids[offset:offset + self.sid_chunk_size])

    def _load(self, part, allow_fetch):
        # Store each field independently, but fetch all missing fields in one
        # batch. Adding a factor field does not download cached fields again.
        field_parts = [replace(part, fields=(field,)) for field in part.fields]
        lock_identity = part.identity() | {"fields": []}
        with self.store.locked("feature-cache/" + digest(lock_identity)):
            missing = [unit for unit in field_parts if not self.store.exists(
                "feature-cache/v1/manifests/" + unit.key + ".json")]
            if missing:
                fetch_request = replace(part, fields=tuple(unit.fields[0] for unit in missing))
                if not allow_fetch or self.provider is None:
                    raise CacheMiss("Cache-only access: prefetch the union plan first")
                intent_keys = ["feature-cache/v1/intents/" + unit.key + ".json" for unit in missing]
                if any(self.store.exists(key) for key in intent_keys):
                    raise RuntimeError("Unresolved/failed fetch requires explicit reconciliation and a new data version")
                for unit, intent_key in zip(missing, intent_keys):
                    self.store.write_once(intent_key, json.dumps(unit.identity(), sort_keys=True).encode())
                try:
                    data = validate_records(self.provider.fetch(fetch_request), fetch_request)
                    provenance = dict(getattr(self.provider, "provenance", {}))
                    for unit in missing:
                        subset = data[data.field == unit.fields[0]]
                        payload = _encode(subset)
                        content_hash = hashlib.sha256(payload).hexdigest()
                        object_key = "feature-cache/v1/objects/" + content_hash + ".json"
                        self.store.write_once(object_key, payload)
                        manifest = {"request": unit.identity(), "payload": object_key,
                                    "sha256": content_hash, "rows": len(subset),
                                    "provenance": provenance, "status": "complete"}
                        self.store.write_once("feature-cache/v1/manifests/" + unit.key + ".json",
                                              json.dumps(manifest, sort_keys=True).encode())
                    self.store.append_event("cache", {"event": "fetched", "request_hash": fetch_request.key,
                                                       "row_count": len(data)})
                except Exception as exc:
                    self.store.append_event("cache", {"event": "fetch_failed", "request_hash": part.key,
                                                       "error_type": type(exc).__name__})
                    raise
            frames = []
            for unit in field_parts:
                manifest = json.loads(self.store.read_bytes("feature-cache/v1/manifests/" + unit.key + ".json"))
                payload = self.store.read_bytes(manifest["payload"])
                if manifest["request"] != unit.identity() or hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
                    raise ValueError("Cache identity or content integrity violation")
                frames.append(_decode(payload))
            return pd.concat(frames, ignore_index=True)

    def read(self, request, allow_fetch=False):
        frames = [self._load(part, allow_fetch) for part in self.partitions(request)]
        data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=RECORD_COLUMNS)
        return data[(data.event_time >= request.start) & (data.event_time < request.end)].reset_index(drop=True)

    def prefetch(self, request):
        # Do not materialize the complete multi-year panel just to warm a cache.
        keys = []
        for part in self.partitions(request):
            self._load(part, True)
            keys.append(part.key)
        return tuple(keys)


def merge_requests(requests):
    """One declared union per compatible source/version before factor evaluation."""
    grouped = {}
    for request in requests:
        key = (request.dataset, request.data_version, request.universe_hash,
               request.normalization, request.timezone)
        grouped.setdefault(key, []).append(request)
    merged = []
    for group in grouped.values():
        first = group[0]
        merged.append(replace(first, fields=tuple({x for r in group for x in r.fields}),
                              sids=tuple({x for r in group for x in r.sids}),
                              start=min(r.start for r in group), end=max(r.end for r in group)))
    return tuple(sorted(merged, key=lambda r: r.key))
