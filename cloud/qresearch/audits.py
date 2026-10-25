"""Program-produced evidence for static contracts, not vendor certification."""
from datetime import datetime, timezone
import json
from .artifacts import canonical_json, content_hash
from .study import AuditEvidence, StudySpec

FORMULA_ISSUER = "qresearch.formula_timing.v1"
COVERAGE_ISSUER = "qresearch.data_coverage.v1"


def make_evidence(store, *, subject_hash, source_hash, issuer, checks, scope):
    """Persist actual check observations and bind every decision to that report.

    Callers are trusted fixed programs. This is a corruption-detecting metadata
    contract, not a cryptographic signature or an LLM-accessible approval tool.
    """
    if not checks or any(type(value) is not bool for value in checks.values()):
        raise ValueError("Named observed boolean checks are required")
    report = {"subject_hash": subject_hash, "source_hash": source_hash,
              "issuer": issuer, "scope": scope, "checks": checks}
    report_hash = content_hash(report)
    key = "audit-evidence/" + report_hash + ".json"
    store.write_once(key, canonical_json(report))
    raw = {"schema_version": 1, "audit_id": report_hash, "issuer": issuer,
           "issuer_kind": "fixed_program", "created_at": datetime.now(timezone.utc).isoformat(),
           "subject_hash": subject_hash, "source_hash": source_hash, "scope": scope,
           "checks": [{"name": name, "passed": value, "evidence_hash": report_hash}
                      for name, value in sorted(checks.items())],
           "evidence_refs": [{"key": key, "sha256": report_hash}]}
    return AuditEvidence.from_dict(raw, expected_subject_hash=subject_hash,
             expected_source_hash=source_hash, allowed_issuers=(issuer,))


def verify_evidence(store, raw, *, subject_hash, source_hash, issuer, required_checks, scope, require_passed=True):
    evidence = AuditEvidence.from_dict(raw, expected_subject_hash=subject_hash,
                 expected_source_hash=source_hash, allowed_issuers=(issuer,))
    document = evidence.to_dict()
    if document["scope"] != scope:
        raise ValueError("Engineering evidence cannot authorize market research")
    observed = {check["name"]: check["passed"] for check in document["checks"]}
    if not set(required_checks) <= set(observed):
        raise ValueError("Required audit checks are missing")
    for reference in document["evidence_refs"]:
        report = json.loads(store.read_bytes(reference["key"]))
        if content_hash(report) != reference["sha256"]:
            raise ValueError("Referenced check evidence changed")
        if (report["subject_hash"] != subject_hash or report["source_hash"] != source_hash or
                report["issuer"] != issuer or report["scope"] != scope):
            raise ValueError("Referenced report belongs to a different audit")
        if report["checks"] != observed:
            raise ValueError("Audit decision differs from its observed report")
    if require_passed:
        evidence.require_passed()
    return evidence


def audit_formula(store, study, *, subject_hash, source_hash):
    if not isinstance(study, StudySpec):
        raise TypeError("A validated frozen StudySpec is required")
    document = study.to_dict()
    if subject_hash != study.configuration_hash:
        package = json.loads(store.read_bytes("configurations/" + subject_hash + ".json"))
        if content_hash(package) != subject_hash or package.get("study") != document:
            raise ValueError("Audit subject does not contain this exact registered StudySpec")
    checks = {"validated_study_contract": True,
              "source_hash_matches_binding": document["data_binding"]["code_hash"] == source_hash,
              "restricted_factor_compilation": all(spec.compile() is not None for spec in study.factor_specs),
              "development_only": not document["final_evaluation"]["execution_enabled"]}
    return make_evidence(store, subject_hash=subject_hash, source_hash=source_hash,
                         issuer=FORMULA_ISSUER, checks=checks,
                         scope="engineering" if document["synthetic"] else "research")
