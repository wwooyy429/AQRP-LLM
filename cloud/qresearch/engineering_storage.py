"""Fixed storage policy and metadata validation, including retired v3 records.

New jobs use readable cache-reference manifests. Legacy encoding metadata is
parseable only to preserve immutable history; this module has no binary codec.
"""

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


def validate_storage_policy(raw, child, *, plan_version=4, historical_decode=False):
    if type(historical_decode) is not bool:
        raise ValueError("Historical storage decoding requires an explicit boolean") from None
    if (type(raw) is not dict or set(raw) != {"schema_version", "price_cache_mode", "capacity",
            "collection_cache", "lean_record_encoding"} or type(raw["schema_version"]) is not int
            or raw["schema_version"] != 1 or raw["price_cache_mode"] != "cache_only"
            or raw["lean_record_encoding"] != ({3: "zlib_json_v1", 4: "cached_row_reference_v1"}.get(plan_version))):
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
    if historical_decode:
        from .collection_storage import validate_storage_policy_structure
        validate_storage_policy_structure(raw["collection_cache"], child)
    else:
        from .collection_storage import StableCollectionCache
        # Only new/current paths require today's source compatibility. An old
        # admitted receipt is decoded separately, never read as a current cache.
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


def validate_encoding_metadata(raw):
    if type(raw) is dict and raw.get("encoding") == "cached_row_reference_v1":
        return validate_reference_metadata(raw)
    if (type(raw) is not dict or set(raw) != {"schema_version", "encoding", "uncompressed_bytes",
            "stored_bytes", "raw_sha256", "stored_sha256"} or type(raw["schema_version"]) is not int
            or raw["schema_version"] != 1 or raw["encoding"] != "zlib_json_v1"
            or any(type(raw[k]) is not int or not 1 <= raw[k] <= 2 * 1024 * 1024
                   for k in ("uncompressed_bytes", "stored_bytes"))
            or not _hash(raw["raw_sha256"]) or not _hash(raw["stored_sha256"])):
        raise ValueError("Invalid cloud compression metadata") from None
    return raw


def validate_reference_metadata(raw):
    if (type(raw) is not dict or set(raw) != {"schema_version", "encoding", "record_count",
            "rowset_sha256", "manifest_sha256", "cache_reference_count", "new_row_objects"}
            or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or raw["encoding"] != "cached_row_reference_v1"
            or type(raw["record_count"]) is not int or not 1 <= raw["record_count"] <= 100000
            or type(raw["cache_reference_count"]) is not int or raw["cache_reference_count"] != 5
            or not _hash(raw["rowset_sha256"]) or not _hash(raw["manifest_sha256"])
            or raw["new_row_objects"] is not False):
        raise ValueError("Invalid bounded receiver reference metadata") from None
    return raw
