"""Strict metadata for explicitly authorized engineering quota rounds.

These receipts bind a trusted operator's transcription of a human instruction.
Their hashes detect changed metadata; they do not authenticate a human. This
interface is deliberately separate from FactorSpec and generated task plans.
"""
import re

from .artifacts import canonical_json, content_hash


RESOURCES = ("configurations", "research", "lean")


def validate_round_id(value):
    if not isinstance(value, str) or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value) is None:
        raise ValueError("round_id must be a bounded identifier")
    return value


def validate_grant(grant, authorization, global_limits):
    """Validate exact immutable scope, not a claim of independent approval."""
    fields = {"schema_version", "round_id", "project_id", "allocation", "limits",
              "authorization_ref", "final_test_enabled", "extra_spend_usd"}
    if not isinstance(grant, dict) or set(grant) != fields:
        raise ValueError("Engineering round grant has an unexpected schema")
    if type(grant["schema_version"]) is not int or grant["schema_version"] != 1:
        raise ValueError("Unsupported engineering round schema")
    validate_round_id(grant["round_id"])
    if type(grant["project_id"]) is not int or grant["project_id"] <= 0:
        raise ValueError("Engineering round requires a positive project identity")
    if grant["allocation"] not in ("normal", "reserve"):
        raise ValueError("Engineering rounds use an existing normal or reserve allocation")
    limits = grant["limits"]
    if (not isinstance(limits, dict) or set(limits) != set(RESOURCES)
            or any(type(limits[key]) is not int or limits[key] < 0 for key in RESOURCES)
            or limits["configurations"] < 1 or limits["research"] < 1):
        raise ValueError("Engineering round requires explicit nonnegative resource bounds")
    if grant["final_test_enabled"] is not False or type(grant["extra_spend_usd"]) is not int or grant["extra_spend_usd"] != 0:
        raise ValueError("Engineering round cannot enable final testing or extra spend")
    auth_fields = (fields - {"authorization_ref"}) | {"authority_kind", "scope", "global_limits_hash", "request_text"}
    scope = "stage2_engineering_round"
    if grant["allocation"] == "normal":
        # This is an explicit exception to the reserve-only default. The
        # operator must check and transcribe the complete human exchange;
        # matching hashes bind its bytes and do not authenticate its speaker.
        scope = "stage2_normal_allocation_exception"
        auth_fields |= {"normal_allocation_approval"}
    if not isinstance(authorization, dict) or set(authorization) != auth_fields:
        raise ValueError("Explicit user authorization metadata is required")
    if (authorization["authority_kind"] != "explicit_human_user_message"
            or authorization["scope"] != scope
            or authorization["global_limits_hash"] != content_hash(global_limits)
            or not isinstance(authorization["request_text"], str)
            or not authorization["request_text"].strip() or len(authorization["request_text"]) > 8000):
        raise ValueError("Authorization does not bind this global budget and user instruction")
    if grant["allocation"] == "normal":
        approval = authorization["normal_allocation_approval"]
        if (not isinstance(approval, dict) or set(approval) != {"question", "answer"}
                or type(approval["question"]) is not str or not approval["question"].strip()
                or len(approval["question"]) > 8000
                or type(approval["answer"]) is not str or approval["answer"] != "允许"
                or len(approval["answer"]) > 1000):
            raise ValueError("Normal allocation requires the complete bounded question and explicit human reply")
    # Canonical bytes distinguish booleans from integer counters as well.
    for key in fields - {"authorization_ref"}:
        if canonical_json(authorization[key]) != canonical_json(grant[key]):
            raise ValueError("Authorization differs from grant field " + key)
    digest = content_hash(authorization)
    if grant["authorization_ref"] != {"key": "engineering/rounds/user-authorizations/" + digest + ".json", "sha256": digest}:
        raise ValueError("Authorization content reference mismatch")
    return grant
