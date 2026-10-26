"""Observed coverage diagnostics; current vendor coverage remains uncertified.

Raw records are written only to the supplied cloud store (or an explicit
synthetic fixture store). The returned dictionary contains counts and digests,
not market values. A complete fixed-two-stock fixture is not the historical
US200. No current adapter supplies the receipts needed for production timing,
financial vintage, classification or source-revision certification.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

import numpy as np
import pandas as pd

from .artifacts import canonical_json, content_hash, validate_key
from .audits import COVERAGE_ISSUER
from .contracts import DEVELOPMENT_END, RECORD_COLUMNS, DataRequest, aware
from .pipeline import _registered_subject
from .point_in_time import causal_window
from .runtime import execution_plan_identity
from .study import AuditEvidence, StudySpec


class CoverageIntegrityError(ValueError):
    """A raw snapshot, reference or registered subject is inconsistent."""


RESEARCH_GAPS = (
    "actual_historical_vendor_receipt_and_ingestion_evidence_not_supported",
    "historical_all_market_universe_and_classification_receipts_not_supported",
    "financial_publication_and_vintage_receipts_not_supported",
    "authoritative_vendor_source_revision_receipt_not_supported",
)


def _hash(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise CoverageIntegrityError("A SHA256 is required for " + name)
    return value


def _store_boundary(store, synthetic):
    if type(synthetic) is not bool:
        raise CoverageIntegrityError("Synthetic fixture classification must be explicit")
    if not synthetic and getattr(store, "residency", None) != "quantconnect_cloud":
        raise CoverageIntegrityError("Real records and coverage inputs must remain in QuantConnect Cloud")


def _number(value):
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if np.isfinite(number) else None


def _records(frame):
    if not isinstance(frame, pd.DataFrame) or not set(RECORD_COLUMNS) <= set(frame.columns):
        raise CoverageIntegrityError("Raw coverage input needs the complete record schema")
    data = frame.loc[:, RECORD_COLUMNS].copy(deep=True)
    for name in ("event_time", "available_time"):
        try:
            data[name] = (pd.DatetimeIndex([aware(value) for value in data[name]]) if len(data)
                          else pd.DatetimeIndex([], tz="America/New_York"))
        except (TypeError, ValueError) as exc:
            raise CoverageIntegrityError("Coverage timestamps must be explicit and finite") from exc
        if len(data) and (data[name].isna().any() or (data[name] >= DEVELOPMENT_END).any()):
            raise CoverageIntegrityError("Final-period records cannot enter development coverage")
    return data


def _rows(data):
    # Diagnostic copies preserve whether a value was unusable. Their payloads
    # never leave the permitted store and are not a feature-cache replacement.
    rows = []
    for row in data.itertuples(index=False):
        number = _number(row.value)
        value = number if number is not None else {"invalid_numeric_type": type(row.value).__name__,
                                                  "representation": repr(row.value)}
        rows.append([str(row.sid), str(row.field), row.event_time.isoformat(),
                     row.available_time.isoformat(), value, str(row.revision)])
    return sorted(rows, key=lambda row: canonical_json(row))


def _source_payloads(store, references, request):
    if not isinstance(references, (tuple, list)):
        raise CoverageIntegrityError("Source references must be explicit raw-payload references")
    normalized, frames, seen = [], [], set()
    for reference in references:
        if not isinstance(reference, dict) or set(reference) != {"key", "sha256"}:
            raise CoverageIntegrityError("Each raw reference needs only key and SHA256")
        key, digest = validate_key(reference["key"]), _hash(reference["sha256"], "raw payload")
        if key in seen:
            raise CoverageIntegrityError("Duplicate raw reference cannot inflate coverage")
        seen.add(key)
        payload = store.read_bytes(key)
        if sha256(payload).hexdigest() != digest:
            raise CoverageIntegrityError("Referenced raw payload hash changed")
        raw = json.loads(payload)
        if not isinstance(raw, list) or any(not isinstance(row, list) or len(row) != len(RECORD_COLUMNS) for row in raw):
            raise CoverageIntegrityError("Source refs must point to record arrays, not claimed approval metadata")
        frame = _records(pd.DataFrame(raw, columns=RECORD_COLUMNS))
        frame = frame[(frame.event_time >= request.start) & (frame.event_time < request.end)
                      & frame.sid.isin(request.sids) & frame.field.isin(request.fields)]
        frames.append(frame)
        normalized.append({"key": key, "sha256": digest})
    all_records = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=RECORD_COLUMNS)
    return sorted(normalized, key=lambda item: item["key"]), all_records


def _envelope(store, report):
    report_hash = content_hash(report)
    key = "audit-evidence/" + report_hash + ".json"
    store.write_once(key, canonical_json(report))
    raw = {"schema_version": 1, "audit_id": report_hash, "issuer": COVERAGE_ISSUER,
           "issuer_kind": "fixed_program", "created_at": datetime.now(timezone.utc).isoformat(),
           "subject_hash": report["subject_hash"], "source_hash": report["source_hash"],
           "scope": report["scope"],
           "checks": [{"name": name, "passed": passed, "evidence_hash": report_hash}
                      for name, passed in sorted(report["checks"].items())],
           "evidence_refs": [{"key": key, "sha256": report_hash}]}
    evidence = AuditEvidence.from_dict(raw, expected_subject_hash=report["subject_hash"],
        expected_source_hash=report["source_hash"], allowed_issuers=(COVERAGE_ISSUER,))
    return evidence, {"key": key, "sha256": report_hash}


def _produce(store, *, request, records, decisions, sids, policies, expected_events,
             membership, provenance, subject_hash, source_hash, max_age, source_refs,
             synthetic, scope):
    _store_boundary(store, synthetic)
    _hash(subject_hash, "subject")
    _hash(source_hash, "source")
    if not isinstance(request, DataRequest) or request.normalization != "raw":
        raise CoverageIntegrityError("A development-only raw DataRequest is required")
    if not isinstance(provenance, dict):
        raise CoverageIntegrityError("Provider provenance must be recorded separately from certification")
    provenance = json.loads(canonical_json(provenance))
    policies = dict(policies)
    expected_events = {aware(key): aware(value) for key, value in expected_events.items()}
    max_age = dict(max_age or {})
    decisions, sids = tuple(aware(value) for value in decisions), tuple(sorted(sids))
    if any(value >= DEVELOPMENT_END for value in decisions):
        raise CoverageIntegrityError("Final-period formations are prohibited")
    if not set(sids) <= set(request.sids):
        raise CoverageIntegrityError("Formation SIDs must belong to the frozen request")
    if not isinstance(membership, pd.DataFrame):
        raise CoverageIntegrityError("An explicit historical membership matrix is required")
    membership = membership.copy(deep=True)
    membership.index = pd.DatetimeIndex([aware(value) for value in membership.index])
    plan = execution_plan_identity(request, decisions, sids, policies, expected_events, max_age, membership)
    plan_hash = content_hash(plan)
    data = _records(records)
    refs, source_records = _source_payloads(store, source_refs, request)
    actual_rows = _rows(data)
    source_match = bool(refs) and actual_rows == _rows(source_records)
    snapshot = {"schema_version": 1, "request_hash": request.key, "rows": actual_rows}
    snapshot_hash = content_hash(snapshot)
    snapshot_key = "coverage-inputs/v1/" + snapshot_hash + ".json"
    store.write_once(snapshot_key, canonical_json(snapshot))
    snapshot_ref = {"key": snapshot_key, "sha256": snapshot_hash}
    provenance_hash = content_hash(provenance)
    provenance_key = "coverage-inputs/v1/provenance/" + provenance_hash + ".json"
    store.write_once(provenance_key, canonical_json(provenance))
    provenance_ref = {"key": provenance_key, "sha256": provenance_hash}

    numeric = np.array([np.nan if _number(value) is None else _number(value) for value in data.value], dtype=float)
    invalid_numeric = int((~np.isfinite(numeric)).sum())
    duplicate = int(data.duplicated(["sid", "field", "event_time", "available_time", "revision"]).sum())
    ambiguous = int(data.duplicated(["sid", "field", "event_time", "available_time"]).sum())
    outside = int(((data.event_time < request.start) | (data.event_time >= request.end)).sum())
    order_violations = int((data.event_time > data.available_time).sum())
    identities = all(isinstance(value, str) and bool(value.strip())
                     for name in ("sid", "field", "revision") for value in data[name])
    declared = set(data.sid) <= set(request.sids) and set(data.field) <= set(request.fields)
    expected_cells = int(membership.to_numpy(dtype=bool).sum()) * len(request.fields)
    available_cells, window_error = 0, None
    if identities and declared and not duplicate and not ambiguous and not order_violations:
        clean = data.copy()
        clean["value"] = numeric
        try:
            window = causal_window(clean, decisions, sids, policies, expected_events, max_age, membership)
            active = membership.reindex(columns=sids).to_numpy(dtype=bool)
            available_cells = sum(int((np.isfinite(frame.to_numpy(dtype=float)) & active).sum())
                                  for frame in window.matrices.values())
        except (ValueError, TypeError):
            # Failure metadata is deliberate; never print an exception that
            # might contain market values or a row-level representation.
            window_error = "causal_window_rejected_input"
    else:
        window_error = "record_integrity_prevents_window"
    observations = {"record_count": len(data), "declared_field_count": len(request.fields),
        "observed_field_count": int(data.field.nunique()), "declared_sid_count": len(request.sids),
        "observed_sid_count": int(data.sid.nunique()), "formation_count": len(decisions),
        "expected_member_field_cells": expected_cells, "available_member_field_cells": available_cells,
        "missing_member_field_cells": max(0, expected_cells - available_cells),
        "duplicate_vintage_rows": duplicate, "ambiguous_simultaneous_vintage_rows": ambiguous,
        "invalid_numeric_rows": invalid_numeric, "outside_request_rows": outside,
        "event_after_availability_rows": order_violations, "source_payload_count": len(refs)}
    checks = {"nonempty_records": bool(len(data)), "declared_field_and_sid_identities": bool(declared and identities),
        "events_inside_request": outside == 0, "no_duplicate_vintage_identity": duplicate == 0,
        "no_ambiguous_simultaneous_vintage": ambiguous == 0, "finite_real_observations": invalid_numeric == 0,
        "events_precede_availability": order_violations == 0,
        "complete_formation_coverage": expected_cells > 0 and available_cells == expected_cells and window_error is None,
        "source_payloads_match_records": bool(source_match),
        "declared_source_version_consistent": provenance.get("data_version") == request.data_version,
        "development_only": True, "execution_plan_bound": True}
    if scope == "research":
        # These cannot be inferred from a feed version string, an end_time,
        # fixture membership, or a caller-supplied `certified` boolean.
        checks.update(historical_universe_coverage=False, actual_availability_verified=False,
                      source_revision_pinned=False)
    report = {"schema_version": 1, "subject_hash": subject_hash, "source_hash": source_hash,
        "issuer": COVERAGE_ISSUER, "scope": scope, "checks": checks, "observations": observations,
        "execution_plan": plan, "plan_hash": plan_hash, "raw_snapshot_ref": snapshot_ref,
        "source_payload_refs": refs, "provenance_ref": provenance_ref,
        "availability_basis": "not_certified_actual_historical_receipt",
        "historical_universe_basis": "declared_membership_only_not_full_market_certification",
        "research_certification_gaps": list(RESEARCH_GAPS), "window_error": window_error,
        "financial_evidence": False}
    evidence, report_ref = _envelope(store, report)
    return {"schema_version": 1, "scope": scope,
        "status": ("passed" if evidence.passed else "failed") if scope == "engineering" else "not_certified",
        "checks": checks, "observations": observations, "plan_hash": plan_hash,
        "report_ref": report_ref, "raw_snapshot_ref": snapshot_ref, "provenance_ref": provenance_ref,
        "research_certification_gaps": list(RESEARCH_GAPS), "research_certified": False,
        "market_values_exported": False, "financial_evidence": False, "audit_evidence": evidence.to_dict()}


def produce_engineering_coverage(store, *, request, records, decisions, sids, policies,
        expected_events, membership, provenance, subject_hash, source_hash, max_age=None,
        source_refs=(), synthetic=False):
    """Audit only a declared engineering fixture and return exportable metadata.

    source_refs point to exact immutable cache record-array payloads. Their
    hashes and the request-filtered union must equal the actual supplied frame.
    The expected exchange sessions come from the trusted calendar adapter.
    Neither this engineering result nor its evidence can authorize research.
    """
    return _produce(store, request=request, records=records, decisions=decisions, sids=sids,
        policies=policies, expected_events=expected_events, membership=membership, provenance=provenance,
        subject_hash=subject_hash, source_hash=source_hash, max_age=max_age, source_refs=source_refs,
        synthetic=synthetic, scope="engineering")


def audit_registered_coverage(store, *, study, registered_configuration, source_hash,
        field_catalog, operator_catalog, request, records, decisions, sids, policies,
        expected_events, membership, provenance, max_age=None, source_refs=()):
    """Bind a failed production audit to the real subject; never infer receipts.

    Current source adapters cannot certify the required historical facts. The
    returned research-scope AuditEvidence therefore contains mandatory failed
    checks and is rejected by verify_evidence/ResearchEngine. This is a useful
    failed audit record, not an approval or a configurable certification gate.
    """
    _store_boundary(store, False)
    if not isinstance(study, StudySpec) or not field_catalog or not operator_catalog:
        raise CoverageIntegrityError("A registered study and trusted catalogs are required")
    validated = StudySpec.from_dict(study.to_dict(), field_catalog=field_catalog,
        operator_catalog=operator_catalog, require_trading=True)
    if validated.configuration_hash != study.configuration_hash or validated.to_dict()["purpose"] != "research":
        raise CoverageIntegrityError("Only the exact research study can be audited")
    subject = _registered_subject(validated, registered_configuration, store, required=True)
    document = validated.to_dict()
    binding = document["data_binding"]
    if (source_hash != binding["code_hash"] or request.data_version != binding["data_version"]
            or request.universe_hash != binding["universe_hash"]
            or set(request.fields) != {field for spec in validated.factor_specs for field in spec.allowed_fields}):
        raise CoverageIntegrityError("Data or implementation differs from the registered study")
    times = tuple(aware(value) for value in decisions)
    start, end = aware(document["development"]["start"]), aware(document["development"]["end_exclusive"])
    if request.start < start or request.end > end or any(not start <= value < end for value in times):
        raise CoverageIntegrityError("Audit plan exceeds the registered development interval")
    return _produce(store, request=request, records=records, decisions=times, sids=sids,
        policies=policies, expected_events=expected_events, membership=membership, provenance=provenance,
        subject_hash=subject, source_hash=source_hash, max_age=max_age, source_refs=source_refs,
        synthetic=False, scope="research")
