"""Bounded Object Store metadata audit; explicit writes and market APIs absent.

This standard-library worker is separately frozen by the trusted task bridge.
Known development-window metadata may authorize one cloud-only payload hash;
unknown schemas, namespaces, dates and consumers remain retained. A successful
execution is not a complete reference closure or permission to delete anything.
The SDK's get_file_path may flush an already dirty SDK cache internally. Two
matching metadata passes are observations, not an atomic snapshot or a lock.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
import re
import stat
import time


LIMITS = {"max_keys": 1000, "max_total_read_bytes": 64 * 1024 * 1024,
          "max_object_read_bytes": 2 * 1024 * 1024, "max_edges": 20000,
          "max_json_depth": 64, "max_seconds": 180, "max_report_bytes": 524288}
PREFIX = "aqrp/engineering/v2/"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ATTEMPT = re.compile(r"[0-9a-f]{32}\Z")
_HIST = re.compile(r"aqrp/engineering/v2/historical-snapshots/v([12])/(windows|intents|objects)/([0-9a-f]{64})\.json\Z")
_FEATURE = re.compile(r"aqrp/engineering/v2/feature-cache/v1/(manifests|intents|objects)/([0-9a-f]{64})\.json\Z")
_RECEIPT = re.compile(r"aqrp/engineering/v2/engineering/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/(?:reports|resolutions|collection-probes)/[A-Za-z0-9_./-]+\.json\Z")
_FAILURES = {"metadata_unavailable", "duplicate_or_invalid_key", "key_limit", "sdk_error",
             "metadata_changed", "time_limit", "read_limit", "edge_limit", "report_limit",
             "worker_error", "reference_hash_mismatch", "metadata_integrity_error"}
_ROLES = {"historical_window", "historical_intent", "historical_payload", "feature_manifest",
          "feature_intent", "feature_payload", "engineering_receipt", "other_unread"}
_CONTENT = {"not_read", "metadata_verified", "payload_hash_verified", "retained_unknown_schema",
            "retained_reserved_or_unknown_dates", "rejected_metadata"}
_EDGE_KINDS = {"historical_window_batch", "feature_manifest_payload"}
_LIMITATIONS = ["observed_metadata_consistency_is_not_an_atomic_snapshot",
               "get_file_path_may_flush_existing_SDK_dirty_cache",
               "unknown_dynamic_and_external_consumers_are_not_certified",
               "all_history_intents_receipts_and_unknown_objects_remain_retained",
               "real_rows_are_not_exported_and_remain_in_QuantConnect_Cloud",
               "byte_envelope_comparison_is_not_a_storage_reservation",
               "final_test_and_safe_deletion_are_disabled"]
_RETENTION = {"all_objects_retained": True, "global_reference_closure": False,
              "confirmed_reclaimable_bytes": 0, "potential_reclaimable_bytes": None,
              "safe_deletion_authorized": False, "final_test_enabled": False}
_REPORT_FIELDS = {"schema_version", "kind", "identity", "policy_sha256", "status", "failure_codes",
                  "capacity_before", "capacity_after", "metadata_observation_stable", "details_complete",
                  "objects", "references", "read_summary", "retention", "limitations"}
_SUMMARY = {"metadata_passes", "metadata_read_calls", "payload_read_calls", "total_read_bytes",
            "objects_hashed", "metadata_keys_requested", "metadata_keys_found", "missing_metadata_keys",
            "unrecognized_metadata_objects", "unread_objects"}


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _digest(value):
    return sha256(_encoded(value)).hexdigest()


def _key(value):
    if (type(value) is not str or not value or len(value) > 1024 or value != value.strip()
            or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ValueError("Invalid inventory key metadata")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("Invalid inventory key metadata") from None
    return value


def _hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


def _integer(value, *, maximum=None):
    return type(value) is int and value >= 0 and (maximum is None or value <= maximum)


def _role(key):
    historical = _HIST.fullmatch(key)
    if historical:
        return {"windows": "historical_window", "intents": "historical_intent",
                "objects": "historical_payload"}[historical[2]]
    feature = _FEATURE.fullmatch(key)
    if feature:
        return {"manifests": "feature_manifest", "intents": "feature_intent",
                "objects": "feature_payload"}[feature[1]]
    return "engineering_receipt" if _RECEIPT.fullmatch(key) else "other_unread"


def validate_policy(policy):
    """Freeze exact read-only bounds; no field can enable writes or final data."""
    if type(policy) is not dict or set(policy) != {"schema_version", "metadata_keys", *LIMITS}:
        raise ValueError("Invalid inventory policy schema")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise ValueError("Invalid inventory policy version")
    for name, cap in LIMITS.items():
        if type(policy[name]) is not int or not 1 <= policy[name] <= cap:
            raise ValueError("Invalid inventory policy bound")
    if policy["max_report_bytes"] < 4096:
        raise ValueError("Inventory failure report requires at least4096 bytes")
    keys = policy["metadata_keys"]
    if type(keys) is not list or len(keys) > policy["max_keys"]:
        raise ValueError("Invalid inventory metadata allowlist")
    for key in keys:
        _key(key)
        if _role(key) not in {"historical_window", "historical_intent", "feature_manifest",
                              "feature_intent", "engineering_receipt"}:
            raise ValueError("Only known metadata-key families can be read")
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate metadata allowlist key")
    result = dict(policy)
    result["metadata_keys"] = sorted(keys)
    return result


def _identity(identity):
    fields = {"project_id", "attempt_id", "config_id", "plan_hash", "stage", "worker_sha256"}
    if (type(identity) is not dict or set(identity) != fields or type(identity["project_id"]) is not int
            or identity["project_id"] <= 0 or identity["stage"] != "research"
            or type(identity["attempt_id"]) is not str or _ATTEMPT.fullmatch(identity["attempt_id"]) is None
            or any(not _hash(identity[name]) for name in ("config_id", "plan_hash", "worker_sha256"))):
        raise ValueError("Invalid inventory attempt identity")
    return dict(identity)


def _capacity(value, policy):
    fields = {"max_size_bytes", "max_files", "used_size_bytes", "used_files", "key_size_sha256",
              "free_size_bytes", "lean_required_bytes", "lean_byte_envelope_sufficient"}
    if value is None:
        return
    if (type(value) is not dict or set(value) != fields
            or any(not _integer(value[name]) for name in ("max_size_bytes", "max_files", "used_size_bytes", "used_files"))
            or value["used_files"] > policy["max_keys"] or not _hash(value["key_size_sha256"])
            or type(value["free_size_bytes"]) is not int
            or value["free_size_bytes"] != value["max_size_bytes"] - value["used_size_bytes"]
            or type(value["lean_required_bytes"]) is not int or value["lean_required_bytes"] != 73728
            or type(value["lean_byte_envelope_sufficient"]) is not bool
            or value["lean_byte_envelope_sufficient"] != (value["free_size_bytes"] >= 73728)):
        raise ValueError("Invalid exact capacity observation")


def validate_report(report, policy, identity):
    """Reject unknown output, licensed rows and unbound task/capacity claims."""
    policy, identity = validate_policy(policy), _identity(identity)
    if (type(report) is not dict or set(report) != _REPORT_FIELDS
            or type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["kind"] != "object_store_inventory_v1" or report["identity"] != identity
            or report["policy_sha256"] != _digest(policy)
            or report["status"] not in {"completed", "failed"}
            or type(report["failure_codes"]) is not list or any(type(x) is not str or x not in _FAILURES for x in report["failure_codes"])
            or report["failure_codes"] != sorted(set(report["failure_codes"]))
            or type(report["metadata_observation_stable"]) is not bool
            or type(report["details_complete"]) is not bool
            or report["retention"] != _RETENTION or report["limitations"] != _LIMITATIONS):
        raise ValueError("Invalid inventory report schema or fixed limitations")
    # Python equality must not permit bool to impersonate integer limitations.
    if _encoded(report["retention"]) != _encoded(_RETENTION):
        raise ValueError("Invalid inventory retention types")
    if _encoded(report["identity"]) != _encoded(identity):
        raise ValueError("Inventory identity types changed")
    for name in ("capacity_before", "capacity_after"):
        _capacity(report[name], policy)
    objects, references, summary = report["objects"], report["references"], report["read_summary"]
    if (type(objects) is not list or len(objects) > policy["max_keys"] or type(references) is not list
            or len(references) > policy["max_edges"] or type(summary) is not dict or set(summary) != _SUMMARY
            or any(not _integer(value) for value in summary.values())
            or summary["metadata_passes"] > 2 or summary["metadata_keys_requested"] != len(policy["metadata_keys"])
            or summary["metadata_keys_found"] + summary["missing_metadata_keys"] != len(policy["metadata_keys"])
            or summary["metadata_read_calls"] > len(policy["metadata_keys"])
            or summary["metadata_read_calls"] + summary["payload_read_calls"] > policy["max_keys"]
            or summary["objects_hashed"] > policy["max_keys"] or summary["unread_objects"] > policy["max_keys"]
            or summary["unrecognized_metadata_objects"] > summary["metadata_read_calls"]
            or summary["total_read_bytes"] > policy["max_total_read_bytes"]):
        raise ValueError("Invalid inventory report counts")
    by_key = {}
    for item in objects:
        if (type(item) is not dict or set(item) != {"key", "size_bytes", "role", "content_sha256", "content_status", "deletion_authorized"}
                or not _integer(item["size_bytes"]) or item["role"] not in _ROLES
                or item["content_status"] not in _CONTENT or item["deletion_authorized"] is not False
                or (item["content_sha256"] is not None and not _hash(item["content_sha256"]))):
            raise ValueError("Invalid inventory object metadata")
        key = _key(item["key"])
        if key in by_key or item["role"] != _role(key):
            raise ValueError("Inventory objects must have unique exact physical keys")
        if item["content_status"] == "not_read" and item["content_sha256"] is not None:
            raise ValueError("Unread inventory objects cannot have content hashes")
        if item["content_status"] != "not_read" and item["content_sha256"] is None:
            raise ValueError("Read inventory content needs its actual raw hash")
        if item["content_status"] == "metadata_verified" and key not in policy["metadata_keys"]:
            raise ValueError("Verified metadata was not allowlisted")
        by_key[key] = item
    if objects != sorted(objects, key=lambda item: item["key"]):
        raise ValueError("Inventory objects must be canonically ordered")
    if not report["details_complete"]:
        if "report_limit" not in report["failure_codes"] or objects or references or report["capacity_before"] is not None or report["capacity_after"] is not None:
            raise ValueError("Only explicit report-limit failure may omit detail")
    else:
        before = report["capacity_before"]
        if before is not None and (before["used_files"] != len(objects)
                or before["used_size_bytes"] != sum(item["size_bytes"] for item in objects)
                or before["key_size_sha256"] != _digest([[key, by_key[key]["size_bytes"]] for key in sorted(by_key)])):
            raise ValueError("Capacity must sum unique exact object metadata once")
        hashed = [item for item in objects if item["content_sha256"] is not None]
        if (summary["objects_hashed"] != len(hashed)
                or summary["metadata_keys_found"] != len(set(policy["metadata_keys"]) & set(by_key))
                or summary["metadata_read_calls"] > summary["metadata_keys_found"]
                or summary["metadata_read_calls"] < sum(item["key"] in policy["metadata_keys"] for item in hashed)
                or summary["payload_read_calls"] < sum(item["key"] not in policy["metadata_keys"] for item in hashed)
                or summary["total_read_bytes"] != sum(item["size_bytes"] for item in hashed)
                or summary["metadata_read_calls"] + summary["payload_read_calls"] > len(objects)
                or summary["objects_hashed"] > summary["metadata_read_calls"] + summary["payload_read_calls"]
                or summary["unread_objects"] != len(objects) - len(hashed)):
            raise ValueError("Inventory read counters disagree with retained objects")
    seen = set()
    for edge in references:
        fields = {"source_key", "target_key", "kind", "expected_sha256", "target_exists", "actual_sha256", "content_hash_verified"}
        if (type(edge) is not dict or set(edge) != fields or edge["kind"] not in _EDGE_KINDS
                or not _hash(edge["expected_sha256"]) or type(edge["target_exists"]) is not bool
                or type(edge["content_hash_verified"]) is not bool
                or (edge["actual_sha256"] is not None and not _hash(edge["actual_sha256"]))):
            raise ValueError("Invalid typed inventory reference")
        source, target = _key(edge["source_key"]), _key(edge["target_key"])
        if source not in by_key or not target.startswith(PREFIX) or edge["target_exists"] != (target in by_key):
            raise ValueError("Inventory reference endpoints disagree with the observed keys")
        if edge["kind"] == "historical_window_batch":
            match = _HIST.fullmatch(source)
            family = PREFIX + "historical-snapshots/v" + match[1] + "/objects/" if match else ""
            source_role = "historical_window"
        else:
            family = PREFIX + "feature-cache/v1/objects/"
            source_role = "feature_manifest"
        if (not family or by_key[source]["role"] != source_role
                or by_key[source]["content_status"] != "metadata_verified"
                or target != family + edge["expected_sha256"] + ".json"):
            raise ValueError("Typed reference crosses its hash or namespace domain")
        marker = (source, target, edge["kind"], edge["expected_sha256"])
        if marker in seen:
            raise ValueError("Duplicate typed inventory reference")
        seen.add(marker)
        actual = by_key[target]["content_sha256"] if target in by_key else None
        if edge["actual_sha256"] != actual or edge["content_hash_verified"] != (actual is not None and actual == edge["expected_sha256"]):
            raise ValueError("Reference hash claims must bind actual raw content")
    for key,item in by_key.items():
        if item["content_sha256"] is not None and key not in policy["metadata_keys"]:
            if (item["role"] not in {"historical_payload", "feature_payload"}
                    or not any(edge["target_key"] == key for edge in references)):
                raise ValueError("Read evidence requires allowlisted metadata or a known typed payload reference")
        if item["content_status"] == "payload_hash_verified" and not any(
                edge["target_key"] == key and edge["content_hash_verified"] for edge in references):
            raise ValueError("Payload verification needs an actual typed verified reference")
    stable = (report["capacity_before"] is not None and report["capacity_before"] == report["capacity_after"]
              and not set(report["failure_codes"]) & {"sdk_error", "metadata_unavailable", "metadata_changed", "worker_error"})
    if report["metadata_observation_stable"] != stable:
        raise ValueError("Metadata consistency claim disagrees with observations")
    if (report["status"] == "completed") != (not report["failure_codes"] and stable and summary["metadata_passes"] == 2 and report["details_complete"]):
        raise ValueError("Execution status does not match bounded observations")
    if len(_encoded(report)) > policy["max_report_bytes"]:
        raise ValueError("Inventory report exceeds its frozen output bound")
    return json.loads(_encoded(report))


class _Failure(Exception):
    def __init__(self, code):
        assert code in _FAILURES
        self.code = code


def _parse_json(raw, max_depth):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Nonfinite JSON token")
    def integer(value):
        if len(value) > 32:
            raise ValueError("Oversized JSON integer token")
        return int(value)
    def floating(value):
        if len(value) > 128:
            raise ValueError("Oversized JSON numeric token")
        result=float(value)
        if not math.isfinite(result):
            raise ValueError("Nonfinite JSON number")
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant,
                       parse_int=integer, parse_float=floating)
    stack = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            raise ValueError("JSON depth bound")
        if type(node) is dict:
            stack.extend((item, depth + 1) for item in node.values())
        elif type(node) is list:
            stack.extend((item, depth + 1) for item in node)
    return value


def _stamp(raw):
    if type(raw) is not str or len(raw) > 40:
        raise ValueError("Invalid development timestamp")
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Development timestamp must have an explicit offset")
    return value.astimezone(timezone.utc)


class _WindowError(ValueError):
    pass


def _window(raw):
    if type(raw) is not dict or set(raw) != {"start", "end_exclusive"}:
        raise _WindowError("Invalid development window")
    try:
        start, end = _stamp(raw["start"]), _stamp(raw["end_exclusive"])
    except (ValueError,TypeError,OverflowError):
        raise _WindowError("Unknown development window dates") from None
    # Compare in the declared America/New_York calendar:2024-01-01T00:00-05:00
    # is the first reserved instant, not midnight UTC five hours earlier.
    cutoff = datetime.fromisoformat("2024-01-01T00:00:00-05:00").astimezone(timezone.utc)
    if not start < end <= cutoff:
        raise _WindowError("Reserved or unknown development window")
    return start, end


def _reference(source, raw, expected_family):
    if type(raw) is not dict or set(raw) != {"key", "sha256"} or not _hash(raw["sha256"]):
        raise ValueError("Invalid typed reference")
    key = _key(raw["key"])
    target = key if key.startswith(PREFIX) else PREFIX + key
    _key(target)
    if (target != expected_family + raw["sha256"] + ".json"
            or _role(target) not in {"historical_payload", "feature_payload"}):
        raise ValueError("Reference namespace or content-digest domain mismatch")
    return {"source_key": source, "target_key": target, "expected_sha256": raw["sha256"]}


def _metadata_edges(key, document):
    """Return known typed references plus payload authorizations, never rows."""
    role = _role(key)
    if type(document) is not dict:
        return None
    if role in {"historical_window", "historical_intent"}:
        match = _HIST.fullmatch(key);version = int(match[1])
        identity_fields = {"schema_version", "plan_hash", "synthetic", "window"}
        if (type(document.get("schema_version")) is not int or document["schema_version"] != version
                or not _hash(document.get("plan_hash")) or type(document.get("synthetic")) is not bool
                or not identity_fields <= set(document)):
            return None
        _window(document["window"])
        expected_name = _digest({name: document[name] for name in ("plan_hash", "synthetic", "window")})
        if match[3] != expected_name:
            raise ValueError("Window filename is identity digest, not content hash")
        if role == "historical_intent":
            return ([], []) if set(document) == identity_fields else None
        required = identity_fields | {"status", "plan_identity", "batches", "record_count", "snapshot_count",
            "unique_sid_count", "missing_values", "provider_calls", "full_historical_US200_certified",
            "actual_availability_certified", "research_certified", "row_values_exported"}
        if version == 2:
            required |= {"observation_policy", "duplicate_projection_records", "conflicting_projection_records"}
        if (set(document) != required or document["status"] != "completed"
                or type(document["plan_identity"]) is not dict or _digest(document["plan_identity"]) != document["plan_hash"]
                or type(document["batches"]) is not list
                or any(document[name] is not False for name in ("full_historical_US200_certified",
                    "actual_availability_certified", "research_certified", "row_values_exported"))
                or (version == 2 and document["observation_policy"] != "retain_source_occurrences")):
            return None
        family = PREFIX + "historical-snapshots/v" + str(version) + "/objects/"
        edges, authorizations = [], []
        for index, ref in enumerate(document["batches"]):
            edge = _reference(key, ref, family)
            edges.append(dict(edge, kind="historical_window_batch"))
            authorizations.append((edge, {"kind": "historical", "schema_version": version,
                "plan_hash": document["plan_hash"], "synthetic": document["synthetic"],
                "window": document["window"], "batch_index": index}))
        return edges, authorizations
    if role in {"feature_manifest", "feature_intent"}:
        request = document.get("request") if role == "feature_manifest" else document
        fields = {"dataset", "fields", "sids", "start", "end", "data_version", "universe_hash", "normalization", "timezone"}
        if (type(request) is not dict or set(request) != fields or request["timezone"] != "America/New_York"
                or _FEATURE.fullmatch(key)[2] != sha256(json.dumps(request,sort_keys=True,ensure_ascii=True,
                    separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()):
            return None
        _window({"start":request["start"], "end_exclusive":request["end"]})
        if role == "feature_intent":
            return [], []
        if (set(document) != {"request", "payload", "sha256", "rows", "provenance", "status"}
                or document["status"] != "complete" or type(document["rows"]) is not int or document["rows"] < 0):
            return None
        edge = _reference(key, {"key":document["payload"], "sha256":document["sha256"]},PREFIX+"feature-cache/v1/objects/")
        return [dict(edge,kind="feature_manifest_payload")], [(edge,{"kind":"feature","request":request,"rows":document["rows"]})]
    # Historical receipt metadata can have versioned optional evidence and
    # compressed receiver formats. Keep its actual hash, but do not invent
    # a complete parser or follow opaque references in this first audit.
    return None


def _validate_payload(document, authorization):
    if authorization["kind"] == "historical":
        fields = {"schema_version", "plan_hash", "synthetic", "window", "batch_index", "records"}
        if (type(document) is not dict or set(document) != fields
                or any(type(document[name]) is not type(authorization[name]) or document[name] != authorization[name]
                       for name in fields - {"records"}) or type(document["records"]) is not list):
            raise ValueError("Historical payload header mismatch")
        start,end = _window(document["window"])
        for row in document["records"]:
            if type(row) is not dict or "snapshot_at" not in row or not start <= _stamp(row["snapshot_at"]) < end:
                raise ValueError("Historical payload timestamp outside authorized development window")
    else:
        request=authorization["request"];start,end=_window({"start":request["start"],"end_exclusive":request["end"]})
        if type(document) is not list or len(document)!=authorization["rows"]:
            raise ValueError("Feature payload shape mismatch")
        for row in document:
            if (type(row) is not list or len(row)!=6 or type(row[0]) is not str or row[0] not in request["sids"]
                    or row[1] not in request["fields"] or not start <= _stamp(row[2]) < end
                    or _stamp(row[3]) >= datetime.fromisoformat("2024-01-01T00:00:00-05:00").astimezone(timezone.utc)):
                raise ValueError("Feature payload identity or availability exceeds authorized development data")


def run_inventory(object_store, policy, identity, *, clock=time.monotonic):
    """Return bounded typed audit metadata; never save/delete/clear or fetch data."""
    policy,identity=validate_policy(policy),_identity(identity)
    report={"schema_version":1,"kind":"object_store_inventory_v1","identity":identity,
        "policy_sha256":_digest(policy),"status":"failed","failure_codes":[],
        "capacity_before":None,"capacity_after":None,"metadata_observation_stable":False,
        "details_complete":True,"objects":[],"references":[],
        "read_summary":{name:0 for name in _SUMMARY},"retention":dict(_RETENTION),"limitations":list(_LIMITATIONS)}
    summary=report["read_summary"];summary["metadata_keys_requested"]=len(policy["metadata_keys"])
    summary["missing_metadata_keys"]=len(policy["metadata_keys"])
    started=clock();errors=[False];subscribed=False;by_key={};read_cache={};pending=[];seen_edges=set()
    def on_error(sender,arguments):errors[0]=True
    def check():
        if errors[0]:raise _Failure("sdk_error")
        if clock()-started > policy["max_seconds"]:raise _Failure("time_limit")
    def snapshot():
        check();maximum,maximum_files=object_store.max_size,object_store.max_files
        if not _integer(maximum) or not _integer(maximum_files):raise _Failure("metadata_unavailable")
        sizes={}
        for raw_key in object_store.keys:
            check()
            try:key=_key(raw_key)
            except ValueError:raise _Failure("duplicate_or_invalid_key") from None
            if key in sizes:raise _Failure("duplicate_or_invalid_key")
            if len(sizes)>=policy["max_keys"]:raise _Failure("key_limit")
            if object_store.contains_key(key) is not True:raise _Failure("metadata_unavailable")
            path=object_store.get_file_path(key)
            if type(path) is not str or not path or "\x00" in path:raise _Failure("metadata_unavailable")
            info=os.stat(path,follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or not _integer(info.st_size) or object_store.contains_key(key) is not True:
                raise _Failure("metadata_unavailable")
            sizes[key]=info.st_size
        check()
        if object_store.max_size!=maximum or object_store.max_files!=maximum_files:raise _Failure("metadata_changed")
        used=sum(sizes.values());free=maximum-used
        value={"max_size_bytes":maximum,"max_files":maximum_files,"used_size_bytes":used,"used_files":len(sizes),
            "key_size_sha256":_digest([[key,sizes[key]] for key in sorted(sizes)]),"free_size_bytes":free,
            "lean_required_bytes":73728,"lean_byte_envelope_sufficient":free>=73728}
        summary["metadata_passes"]+=1
        return value,sizes
    def read(key,*,metadata):
        check()
        if key in read_cache:return read_cache[key]
        item=by_key[key];size=item["size_bytes"]
        if size>policy["max_object_read_bytes"] or summary["total_read_bytes"]+size>policy["max_total_read_bytes"]:
            raise _Failure("read_limit")
        if object_store.contains_key(key) is not True:raise _Failure("metadata_unavailable")
        summary["metadata_read_calls" if metadata else "payload_read_calls"]+=1
        raw=bytes(object_store.read_bytes(key))
        if len(raw)!=size or object_store.contains_key(key) is not True:raise _Failure("metadata_changed")
        check();item["content_sha256"]=sha256(raw).hexdigest()
        summary["total_read_bytes"]+=len(raw);summary["objects_hashed"]+=1
        try:document=_parse_json(raw,policy["max_json_depth"])
        except (ValueError,UnicodeError,RecursionError):document=None
        read_cache[key]=document
        return document
    def add_edge(edge):
        marker=(edge["source_key"],edge["target_key"],edge["kind"],edge["expected_sha256"])
        if marker in seen_edges:return
        if len(seen_edges)>=policy["max_edges"]:raise _Failure("edge_limit")
        seen_edges.add(marker);report["references"].append(edge)
    try:
        object_store.error_raised += on_error;subscribed=True
        before,sizes=snapshot();report["capacity_before"]=before
        for key,size in sorted(sizes.items()):
            item={"key":key,"size_bytes":size,"role":_role(key),"content_sha256":None,
                  "content_status":"not_read","deletion_authorized":False}
            by_key[key]=item;report["objects"].append(item)
        found=[key for key in policy["metadata_keys"] if key in by_key]
        summary["metadata_keys_found"]=len(found);summary["missing_metadata_keys"]=len(policy["metadata_keys"])-len(found)
        for key in found:
            item=by_key[key];document=read(key,metadata=True)
            try:parsed=_metadata_edges(key,document)
            except _WindowError:
                item["content_status"]="retained_reserved_or_unknown_dates"
                continue
            except (ValueError,TypeError,KeyError,OverflowError):
                item["content_status"]="rejected_metadata"
                continue
            if parsed is None:
                item["content_status"]="retained_unknown_schema";summary["unrecognized_metadata_objects"]+=1
                continue
            item["content_status"]="metadata_verified"
            edges,authorized=parsed
            for edge in edges:add_edge(edge)
            pending.extend(authorized)
        # Every authorization was derived from a verified known metadata schema
        # and development window. No other payload or unknown namespace is read.
        for edge,authorization in pending:
            check();key=edge["target_key"]
            if key not in by_key:continue
            item=by_key[key];document=read(key,metadata=False)
            if item["content_sha256"]!=edge["expected_sha256"]:
                item["content_status"]="rejected_metadata";raise _Failure("reference_hash_mismatch")
            try:_validate_payload(document,authorization)
            except (ValueError,TypeError,KeyError,OverflowError):
                item["content_status"]="rejected_metadata";raise _Failure("metadata_integrity_error") from None
            item["content_status"]="payload_hash_verified"
        after,after_sizes=snapshot();report["capacity_after"]=after
        if sizes!=after_sizes or before!=after:raise _Failure("metadata_changed")
        check();report["metadata_observation_stable"]=True;report["status"]="completed"
    except _Failure as error:
        report["failure_codes"].append(error.code)
    except Exception:
        report["failure_codes"].append("worker_error")
    finally:
        if subscribed:
            try:object_store.error_raised -= on_error
            except Exception:report["failure_codes"].append("sdk_error")
        if errors[0]:report["failure_codes"].append("sdk_error")
    for edge in report["references"]:
        target=by_key.get(edge["target_key"]);actual=target["content_sha256"] if target else None
        edge.update(target_exists=target is not None,actual_sha256=actual,
                    content_hash_verified=actual is not None and actual==edge["expected_sha256"])
    summary["unread_objects"]=len(by_key)-summary["objects_hashed"]
    report["failure_codes"]=sorted(set(report["failure_codes"]))
    if report["failure_codes"]:report["status"]="failed"
    report["metadata_observation_stable"]=(report["capacity_before"] is not None and report["capacity_before"]==report["capacity_after"]
        and not set(report["failure_codes"]) & {"sdk_error","metadata_unavailable","metadata_changed","worker_error"})
    if len(_encoded(report))>policy["max_report_bytes"]:
        report.update(status="failed",details_complete=False,objects=[],references=[],capacity_before=None,
            capacity_after=None,metadata_observation_stable=False,
            failure_codes=sorted(set(report["failure_codes"]+["report_limit"])))
    return validate_report(report,policy,identity)
