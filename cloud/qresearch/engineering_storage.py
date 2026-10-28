"""Fixed engineering storage policy and bounded compressed cloud artifacts.

Only aggregate capacity metadata and hashes may leave the worker. Compression
does not authorize deleting or exporting a historical observation.
"""
from hashlib import sha256
import json
import zlib

from .artifacts import canonical_json, validate_key


CAPACITY_KEYS = {"required_bytes", "required_files", "reserve_bytes", "reserve_files"}
CAPACITY_OBSERVATION_KEYS = {"schema_version", "status", "max_size_bytes", "max_files",
    "used_size_bytes", "used_files", "required_bytes", "required_files", "reserve_bytes", "reserve_files",
    "remaining_bytes_after_reservation", "remaining_files_after_reservation", "usage_method"}
COLLECTION_EVIDENCE_KEYS = {"schema_version", "mode", "data_identity_hash", "requested_plan_hash",
    "storage_plan_hash", "origin_receipt_ref", "verified_window_count", "provider_calls", "reused_windows",
    "new_row_objects", "full_historical_US200_certified", "actual_availability_certified"}


def _hash(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_storage_policy(raw, child):
    if (type(raw) is not dict or set(raw) != {"schema_version", "price_cache_mode", "capacity",
            "collection_cache", "lean_record_encoding"} or type(raw["schema_version"]) is not int
            or raw["schema_version"] != 1 or raw["price_cache_mode"] != "cache_only"
            or raw["lean_record_encoding"] != "zlib_json_v1"):
        raise ValueError("Invalid fixed engineering storage policy") from None
    capacity = raw["capacity"]
    if type(capacity) is not dict or set(capacity) != {"research", "lean"}:
        raise ValueError("Both storage stages require bounded reservations") from None
    for counts in capacity.values():
        if (type(counts) is not dict or set(counts) != CAPACITY_KEYS
                or any(type(v) is not int or v < 0 for v in counts.values())
                or not 16384 <= counts["required_bytes"] <= 1048576
                or not 1 <= counts["required_files"] <= 32
                or not 4096 <= counts["reserve_bytes"] <= 1048576
                or not 1 <= counts["reserve_files"] <= 32):
            raise ValueError("Storage reservations exceed the fixed engineering bounds") from None
    from .collection_storage import StableCollectionCache
    # Constructor validates the complete frozen cache policy without reading I/O.
    class NoIO:
        residency = "quantconnect_cloud"
    StableCollectionCache(NoIO(), child, raw["collection_cache"])
    if raw["collection_cache"]["mode"] != "reuse_verified_legacy_only":
        raise ValueError("This engineering repair is verified legacy-cache-only") from None
    return raw


def validate_capacity_observation(raw):
    if (type(raw) is not dict or set(raw) != CAPACITY_OBSERVATION_KEYS
            or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or raw["status"] != "sufficient" or raw["usage_method"] != "keys_file_stat"):
        raise ValueError("Only fixed capacity observations may leave cloud") from None
    for key in CAPACITY_OBSERVATION_KEYS - {"schema_version", "status", "usage_method"}:
        if type(raw[key]) is not int or not 0 <= raw[key] <= 10**15:
            raise ValueError("Invalid bounded storage capacity counter") from None
    if (raw["remaining_bytes_after_reservation"] != raw["max_size_bytes"] - raw["used_size_bytes"]
            - raw["required_bytes"] - raw["reserve_bytes"]
            or raw["remaining_files_after_reservation"] != raw["max_files"] - raw["used_files"]
            - raw["required_files"] - raw["reserve_files"]):
        raise ValueError("Storage reservation arithmetic differs") from None
    return raw


def validate_collection_evidence(raw):
    if (type(raw) is not dict or set(raw) != COLLECTION_EVIDENCE_KEYS
            or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or raw["mode"] not in {"verified_legacy", "stable_cache", "stable_prefetch"}
            or any(not _hash(raw[k]) for k in ("data_identity_hash", "requested_plan_hash", "storage_plan_hash"))
            or raw["full_historical_US200_certified"] is not False
            or raw["actual_availability_certified"] is not False or type(raw["new_row_objects"]) is not bool):
        raise ValueError("Invalid bounded cache reuse evidence") from None
    for key in ("verified_window_count", "provider_calls", "reused_windows"):
        if type(raw[key]) is not int or not 0 <= raw[key] <= 40:
            raise ValueError("Invalid bounded cache reuse count") from None
    ref = raw["origin_receipt_ref"]
    if ref is not None:
        if type(ref) is not dict or set(ref) != {"key", "sha256"} or not _hash(ref["sha256"]):
            raise ValueError("Invalid legacy provenance reference") from None
        validate_key(ref["key"])
    if raw["mode"] == "verified_legacy" and (ref is None or raw["new_row_objects"]
            or raw["provider_calls"] != 0 or raw["reused_windows"] != raw["verified_window_count"]):
        raise ValueError("Legacy reuse must preserve provenance without fetching or copying rows") from None
    return raw


def encode_compressed_json(document, *, max_raw_bytes=2 * 1024 * 1024):
    raw = canonical_json(document)
    if len(raw) > max_raw_bytes:
        raise ValueError("Engineering cloud artifact exceeds its bounded encoding") from None
    stored = zlib.compress(raw, 9)
    metadata = {"schema_version": 1, "encoding": "zlib_json_v1", "uncompressed_bytes": len(raw),
                "stored_bytes": len(stored), "raw_sha256": sha256(raw).hexdigest(),
                "stored_sha256": sha256(stored).hexdigest()}
    return stored, metadata


def decode_compressed_json(stored, metadata, *, max_raw_bytes=2 * 1024 * 1024):
    validate_encoding_metadata(metadata)
    if (metadata["uncompressed_bytes"] > max_raw_bytes or len(stored) != metadata["stored_bytes"]
            or sha256(stored).hexdigest() != metadata["stored_sha256"]):
        raise ValueError("Compressed cloud artifact identity differs") from None
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(stored, max_raw_bytes + 1)
        if len(raw) > max_raw_bytes or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
            raise ValueError
        if len(raw) != metadata["uncompressed_bytes"] or sha256(raw).hexdigest() != metadata["raw_sha256"]:
            raise ValueError
        value = json.loads(raw)
        if canonical_json(value) != raw:
            raise ValueError
    except (ValueError, TypeError, UnicodeError, zlib.error):
        raise ValueError("Compressed cloud artifact verification failed") from None
    return value


def validate_encoding_metadata(raw):
    if (type(raw) is not dict or set(raw) != {"schema_version", "encoding", "uncompressed_bytes",
            "stored_bytes", "raw_sha256", "stored_sha256"} or type(raw["schema_version"]) is not int
            or raw["schema_version"] != 1 or raw["encoding"] != "zlib_json_v1"
            or any(type(raw[k]) is not int or not 1 <= raw[k] <= 2 * 1024 * 1024
                   for k in ("uncompressed_bytes", "stored_bytes"))
            or not _hash(raw["raw_sha256"]) or not _hash(raw["stored_sha256"])):
        raise ValueError("Invalid cloud compression metadata") from None
    return raw
