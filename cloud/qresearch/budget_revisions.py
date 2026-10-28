"""Closed, user-authorized one-configuration reserve budget extensions.

This is trusted operator metadata, never an LLM proposal permission. Content
hashes bind the transcribed human exchange; they do not authenticate its author.
The Registry checks quiescence and appends the revision without resetting usage.
"""
import re

from .artifacts import canonical_json, content_hash


SCOPE = "configuration_reserve_increment_v1"
RESOURCES = ("configurations", "research", "lean")
_HASH = re.compile(r"[0-9a-f]{64}")
_FIELDS = {"schema_version", "revision_id", "previous_limits_hash", "new_limits",
           "authorization_ref", "final_test_enabled", "extra_spend_usd"}
_AUTH_FIELDS = (_FIELDS - {"authorization_ref"}) | {"authority_kind", "scope", "request_text", "approval"}


class BudgetRevisionError(ValueError):
    """Static failure text without interpolating user-controlled metadata."""


def _fail():
    raise BudgetRevisionError("Invalid explicit budget revision authorization") from None


def _canonical(document):
    try:
        return canonical_json(document)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        _fail()


def normalized_limits(value):
    if type(value) is not dict or set(value) != set(RESOURCES):
        _fail()
    result = {}
    for resource in RESOURCES:
        counts = value[resource]
        if (type(counts) is not dict or set(counts) != {"normal", "reserve", "total"}
                or any(type(counts[key]) is not int or counts[key] < 0 for key in counts)
                or counts["normal"] + counts["reserve"] != counts["total"]):
            _fail()
        result[resource] = {key: counts[key] for key in ("normal", "reserve", "total")}
    return result


def authorization_reference(document):
    digest = content_hash_from_bytes(document)
    return {"key": "budget-revisions/user-authorizations/" + digest + ".json", "sha256": digest}


def revision_reference(document):
    digest = content_hash_from_bytes(document)
    return {"key": "budget-revisions/revisions/" + digest + ".json", "sha256": digest}


def content_hash_from_bytes(document):
    from hashlib import sha256
    return sha256(_canonical(document)).hexdigest()


def validate_reference(reference, namespace):
    if (type(namespace) is not str or namespace not in {"revisions", "user-authorizations"}
            or type(reference) is not dict or set(reference) != {"key", "sha256"}
            or type(reference["sha256"]) is not str or _HASH.fullmatch(reference["sha256"]) is None
            or type(reference["key"]) is not str
            or reference["key"] != "budget-revisions/" + namespace + "/" + reference["sha256"] + ".json"):
        _fail()
    return reference


def _text(value):
    return type(value) is str and bool(value.strip()) and len(value) <= 8000


def validate_revision(revision, authorization, previous_limits=None):
    if (type(revision) is not dict or set(revision) != _FIELDS
            or type(revision["schema_version"]) is not int or revision["schema_version"] != 1
            or type(revision["revision_id"]) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", revision["revision_id"]) is None
            or type(revision["previous_limits_hash"]) is not str
            or _HASH.fullmatch(revision["previous_limits_hash"]) is None
            or revision["final_test_enabled"] is not False
            or type(revision["extra_spend_usd"]) is not int or revision["extra_spend_usd"] != 0):
        _fail()
    new = normalized_limits(revision["new_limits"])
    validate_reference(revision["authorization_ref"], "user-authorizations")
    if (type(authorization) is not dict or set(authorization) != _AUTH_FIELDS
            or type(authorization["authority_kind"]) is not str
            or authorization["authority_kind"] != "explicit_human_user_message"
            or type(authorization["scope"]) is not str or authorization["scope"] != SCOPE
            or not _text(authorization["request_text"])):
        _fail()
    approval = authorization["approval"]
    if (type(approval) is not dict or set(approval) != {"question", "answer"}
            or not _text(approval["question"]) or type(approval["answer"]) is not str
            or approval["answer"] != "批准"):
        _fail()
    for field in _FIELDS - {"authorization_ref"}:
        if _canonical(authorization[field]) != _canonical(revision[field]):
            _fail()
    if authorization_reference(authorization) != revision["authorization_ref"]:
        _fail()
    if previous_limits is not None:
        old = normalized_limits(previous_limits)
        if revision["previous_limits_hash"] != content_hash(old):
            _fail()
        expected = {key: dict(value) for key, value in old.items()}
        expected["configurations"]["reserve"] += 1
        expected["configurations"]["total"] += 1
        if new != expected:
            _fail()
    return revision
