"""Closed, aggregate metadata for the explicitly versioned source policy."""
import re

from .artifacts import content_hash
from .deployment_sources import SOURCE_IDENTITY_POLICY, parse_manifest


def validate_deployment_observation(value, *, deployment_hash=None):
    fields = {"schema_version", "source_identity_policy", "deployment_hash",
              "verification_mode", "declared_file_count", "verified_file_count",
              "eof_normalized_file_count", "original_source_identity_match",
              "canonical_sources_verified"}
    if (type(value) is not dict or set(value) != fields
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["source_identity_policy"] != SOURCE_IDENTITY_POLICY
            or type(value["verification_mode"]) is not str
            or value["verification_mode"] not in {"worker_terminal_lf", "project_original_source"}
            or type(value["deployment_hash"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", value["deployment_hash"]) is None
            or (deployment_hash is not None and value["deployment_hash"] != deployment_hash)):
        raise ValueError("Invalid versioned deployment observation") from None
    for name in ("declared_file_count", "verified_file_count", "eof_normalized_file_count"):
        if type(value[name]) is not int or not 0 <= value[name] <= 512:
            raise ValueError("Invalid deployment observation counts") from None
    if (not 1 <= value["declared_file_count"] == value["verified_file_count"]
            or value["eof_normalized_file_count"] > value["verified_file_count"]
            or type(value["original_source_identity_match"]) is not bool
            or value["original_source_identity_match"] != (value["eof_normalized_file_count"] == 0)
            or value["canonical_sources_verified"] is not True
            or (value["verification_mode"] == "project_original_source"
                and value["eof_normalized_file_count"] != 0)):
        raise ValueError("Deployment observation is inconsistent") from None
    return value


def validate_observation_binding(evidence, manifest, deployment_hash):
    """Validate the v2 success aggregate against the original admitted manifest.

    Historical v1 outputs remain unchanged. The original manifest is required
    here; a newly generated local deployment cannot reinterpret an old result.
    """
    version, files = parse_manifest(manifest)
    if content_hash(manifest) != deployment_hash:
        raise ValueError("Deployment observation manifest identity changed") from None
    if version == 1:
        if "deployment_verification" in evidence:
            raise ValueError("Legacy output cannot claim the versioned source policy") from None
        return
    value = validate_deployment_observation(evidence.get("deployment_verification"),
                                           deployment_hash=deployment_hash)
    if (value["declared_file_count"] != len(files)
            or value["verification_mode"] != "worker_terminal_lf"):
        raise ValueError("Worker deployment observation differs from its admitted source set") from None
