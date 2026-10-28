"""Closed metadata for human-authorized configuration allowance cycles.

Only configuration capacity is renewed. Lifetime configuration charges and every
Research/LEAN charge remain in the same immutable journal. Content hashes bind
the transcribed instruction; a trusted operator must check its human origin.
"""
import re

from .artifacts import canonical_json, content_hash


SCOPE = "configuration_cycle_reset_v1"
INITIAL_CYCLE = "initial"
_HASH = re.compile(r"[0-9a-f]{64}")
_FIELDS = {"schema_version", "cycle_id", "previous_state_hash", "capacity",
           "authorization_ref", "final_test_enabled", "extra_spend_usd"}
_AUTH_FIELDS = (_FIELDS - {"authorization_ref"}) | {"authority_kind", "scope", "request_text"}


class BudgetCycleError(ValueError):
    """An invalid reset document; messages never interpolate caller data."""


def _fail():
    raise BudgetCycleError("Invalid explicit configuration-cycle authorization") from None


def _canonical(document):
    try:
        return canonical_json(document)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _fail()


def authorization_reference(document):
    from hashlib import sha256
    digest = sha256(_canonical(document)).hexdigest()
    return {"key": "budget-cycles/user-authorizations/" + digest + ".json", "sha256": digest}


def cycle_reference(document):
    from hashlib import sha256
    digest = sha256(_canonical(document)).hexdigest()
    return {"key": "budget-cycles/cycles/" + digest + ".json", "sha256": digest}


def validate_reference(reference, namespace):
    if (type(namespace) is not str or namespace not in {"cycles", "user-authorizations"}
            or type(reference) is not dict or set(reference) != {"key", "sha256"}
            or type(reference["sha256"]) is not str or _HASH.fullmatch(reference["sha256"]) is None
            or type(reference["key"]) is not str
            or reference["key"] != "budget-cycles/" + namespace + "/" + reference["sha256"] + ".json"):
        _fail()
    return reference


def validate_cycle(cycle, authorization, *, previous_state_hash=None, capacity=None):
    if (type(cycle) is not dict or set(cycle) != _FIELDS
            or type(cycle["schema_version"]) is not int or cycle["schema_version"] != 1
            or type(cycle["cycle_id"]) is not str or cycle["cycle_id"] == INITIAL_CYCLE
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", cycle["cycle_id"]) is None
            or type(cycle["previous_state_hash"]) is not str
            or _HASH.fullmatch(cycle["previous_state_hash"]) is None
            or cycle["final_test_enabled"] is not False
            or type(cycle["extra_spend_usd"]) is not int or cycle["extra_spend_usd"] != 0):
        _fail()
    counts = cycle["capacity"]
    if (type(counts) is not dict or set(counts) != {"normal", "reserve", "total"}
            or any(type(n) is not int or n < 0 for n in counts.values())
            or counts["normal"] + counts["reserve"] != counts["total"] or counts["total"] == 0):
        _fail()
    validate_reference(cycle["authorization_ref"], "user-authorizations")
    if (type(authorization) is not dict or set(authorization) != _AUTH_FIELDS
            or type(authorization["authority_kind"]) is not str
            or authorization["authority_kind"] != "explicit_human_user_message"
            or type(authorization["scope"]) is not str or authorization["scope"] != SCOPE
            or type(authorization["request_text"]) is not str
            or not authorization["request_text"].strip() or len(authorization["request_text"]) > 8000):
        _fail()
    for field in _FIELDS - {"authorization_ref"}:
        if _canonical(authorization[field]) != _canonical(cycle[field]):
            _fail()
    if authorization_reference(authorization) != cycle["authorization_ref"]:
        _fail()
    if previous_state_hash is not None and cycle["previous_state_hash"] != previous_state_hash:
        _fail()
    if capacity is not None and _canonical(counts) != _canonical(capacity):
        _fail()
    return cycle
