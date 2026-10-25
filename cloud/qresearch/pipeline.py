"""Registered-study bridge: realized labels, bound factor roles and six folds.

Only synthetic engineering studies can run without externally produced audit
evidence. Market inputs stay in QuantConnect Cloud. Provenance dictionaries are
consistency metadata, not certification of a vendor's historical availability;
the separate trusted coverage audit remains mandatory. This module performs no
history request, cloud submission, model search, budget debit, order or export.
"""
from dataclasses import dataclass
import json
import re

import numpy as np
import pandas as pd

from .artifacts import canonical_json, content_hash
from .audits import COVERAGE_ISSUER, FORMULA_ISSUER, verify_evidence
from .contracts import DEVELOPMENT_END, aware
from .evaluation import WalkForwardResult, walk_forward_evaluate
from .labels import LabelProtocol, build_execution_labels
from .models import ModelSpec, create_model
from .study import StudySpec


class PipelineValidationError(ValueError):
    """A study, factor panel, execution source or audit binding is inconsistent."""


@dataclass(frozen=True)
class RegisteredStudyResult:
    study_hash: str
    configuration_hash: str
    target_kind: str
    label_protocol_hash: str
    feature_bindings: dict
    input_hashes: dict
    records: pd.DataFrame
    evaluation: WalkForwardResult
    artifact_keys: tuple[str, ...] = ()

    @property
    def predictions(self):
        return self.evaluation.predictions

    @property
    def folds(self):
        return self.evaluation.folds

    @property
    def daily_ic(self):
        return self.evaluation.daily_ic

    @property
    def ic_statistics(self):
        return self.evaluation.ic_statistics

    @property
    def model_artifacts(self):
        return self.evaluation.model_artifacts


def _registered_subject(study, package, store, *, required):
    if package is None:
        if required:
            raise PipelineValidationError("Market research requires its registered workflow configuration")
        return study.configuration_hash
    fields = {"workflow_schema_version", "study", "identity", "campaign_hash"}
    if (not isinstance(package, dict) or set(package) != fields or
            type(package["workflow_schema_version"]) is not int or package["workflow_schema_version"] != 1 or
            package["study"] != study.to_dict()):
        raise PipelineValidationError("Registered configuration must bind the exact validated StudySpec")
    if not isinstance(package["campaign_hash"], str) or not re.fullmatch(r"[a-f0-9]{64}", package["campaign_hash"]):
        raise PipelineValidationError("Registered campaign identity is required")
    document = study.to_dict()
    components, binding = document["component_hashes"], document["data_binding"]
    expected = {"code_hash": binding["code_hash"], "data_hash": content_hash(binding),
                "universe_hash": binding["universe_hash"], "label_hash": components["label"],
                "factor_set_hash": content_hash(components["factors"]), "model_hash": components["model"],
                "trading_hash": components["trading"],
                "data_end_exclusive": aware(document["development"]["end_exclusive"]).isoformat()}
    identity = package["identity"]
    if (not isinstance(identity, dict) or set(identity) - set(expected) - {"data_version"} or
            any(identity.get(key) != value for key, value in expected.items()) or
            identity.get("data_version", binding["data_version"]) != binding["data_version"]):
        raise PipelineValidationError("Registered identity differs from study data, factors, labels, model or trading design")
    subject_hash = content_hash(package)
    key = "configurations/" + subject_hash + ".json"
    if store is None or not store.exists(key):
        raise PipelineValidationError("The exact configuration must already exist in the authoritative registry")
    registered = json.loads(store.read_bytes(key))
    if content_hash(registered) != subject_hash or registered != package:
        raise PipelineValidationError("Registered workflow configuration failed its content identity check")
    return subject_hash


def _market_gate(study, features, executions, store, evidence, subject_hash):
    document = study.to_dict()
    if getattr(store, "residency", None) != "quantconnect_cloud":
        raise PipelineValidationError("Market inputs and fitted artifacts require QuantConnect cloud storage")
    if document.get("trading_spec") is None:
        raise PipelineValidationError("Real execution labels require an explicit registered trading protocol")
    if not isinstance(evidence, dict) or set(evidence) != {"formula_timing", "data_coverage"}:
        raise PipelineValidationError("Program-produced formula/time and coverage evidence are required")
    source_hash = document["data_binding"]["code_hash"]
    for purpose, issuer, checks in (
            ("formula_timing", FORMULA_ISSUER,
             ("validated_study_contract", "source_hash_matches_binding", "restricted_factor_compilation", "development_only")),
            ("data_coverage", COVERAGE_ISSUER,
             ("historical_universe_coverage", "actual_availability_verified", "source_revision_pinned", "development_only"))):
        raw = evidence[purpose]
        if hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        verify_evidence(store, raw, subject_hash=subject_hash, source_hash=source_hash,
                        issuer=issuer, required_checks=checks, scope="research")
    expected = {"study_hash": study.configuration_hash, "configuration_hash": subject_hash,
                "data_version": document["data_binding"]["data_version"],
                "universe_hash": document["data_binding"]["universe_hash"], "code_hash": source_hash,
                "factor_hashes": document["component_hashes"]["factors"], "purpose": "research"}
    for frame, origin in ((features, "quantconnect_factor_engine"), (executions, "quantconnect_execution")):
        provenance = frame.attrs.get("provenance")
        if (not isinstance(provenance, dict) or any(provenance.get(key) != value for key, value in expected.items()) or
                provenance.get("origin") != origin):
            raise PipelineValidationError("Input provenance does not match the audited registered market study")
    if executions.attrs["provenance"].get("label_protocol_hash") != document["component_hashes"]["label"]:
        raise PipelineValidationError("Execution provenance is bound to a different label protocol")


def _features(study, frame):
    document = study.to_dict()
    bindings = document["feature_bindings"]
    raw_columns = set(bindings.values())
    if (not isinstance(frame, pd.DataFrame) or not frame.columns.is_unique or
            set(frame.columns) != {"sid", "formation_at"} | raw_columns):
        raise PipelineValidationError("Factor panel must contain only SID, formation time and exactly the bound factor outputs")
    values = frame.copy(deep=True)
    values["formation_at"] = pd.DatetimeIndex([aware(x) for x in values.formation_at])
    start, end = aware(document["development"]["start"]), aware(document["development"]["end_exclusive"])
    if (values.empty or values.sid.map(lambda x: not isinstance(x, str) or not x.strip()).any() or
            values.formation_at.isna().any() or values.duplicated(["formation_at", "sid"]).any() or
            ((values.formation_at < start) | (values.formation_at >= end) | (values.formation_at >= DEVELOPMENT_END)).any()):
        raise PipelineValidationError("Factor rows must be unique and remain inside the registered development interval")
    result = values[["sid", "formation_at"]].copy()
    for feature, factor in bindings.items():
        column = values[factor]
        if (not pd.api.types.is_numeric_dtype(column.dtype) or pd.api.types.is_bool_dtype(column.dtype) or
                pd.api.types.is_complex_dtype(column.dtype)):
            raise PipelineValidationError("Bound factor outputs must be real numeric scores")
        numeric = column.astype(float)
        if np.isinf(numeric.to_numpy()).any():
            raise PipelineValidationError("Infinite factor values require explicit repair before evaluation")
        result[feature] = numeric
    return result


def _record_hash(frame):
    """A cloud-resident lineage digest, not an exported panel or certification."""
    stable = frame.sort_values(["formation_at", "sid"]) if {"formation_at", "sid"} <= set(frame.columns) else frame
    rows = []
    for row in stable.itertuples(index=False, name=None):
        rows.append([x.isoformat() if isinstance(x, (pd.Timestamp,)) else
                     None if pd.isna(x) else x.item() if isinstance(x, np.generic) else x for x in row])
    return content_hash({"columns": list(frame.columns), "rows": rows})


def evaluate_registered_study(study, features, execution_trades, *, audit_store=None,
                              audit_evidence=None, registered_configuration=None):
    """Evaluate exactly six registered windows from bound realized executions.

    features has SID/formation_at plus raw factor-id columns. feature_bindings
    maps fixed model roles to these outputs. Label values are created here from
    explicit executions; existing feature labels/metadata are never imported.
    Synthetic results are engineering evidence only. Real inputs require a
    registered workflow package, cloud residency and trusted, referenced audits.
    This call never substitutes attributes for an actual coverage audit.
    """
    if not isinstance(study, StudySpec):
        raise PipelineValidationError("A validated immutable StudySpec is required")
    if not isinstance(features, pd.DataFrame) or not isinstance(execution_trades, pd.DataFrame):
        raise PipelineValidationError("Factor and execution inputs must be DataFrames")
    document = study.to_dict()
    if content_hash(document) != study.configuration_hash:
        raise PipelineValidationError("The immutable StudySpec failed its content identity check")
    is_market = document["purpose"] == "research"
    subject_hash = _registered_subject(study, registered_configuration, audit_store, required=is_market)
    if is_market:
        _market_gate(study, features, execution_trades, audit_store, audit_evidence, subject_hash)
    label_protocol = LabelProtocol.from_dict(document["label_spec"])
    model_spec = ModelSpec.from_dict(document["model_spec"])
    scores = _features(study, features)
    labels = build_execution_labels(execution_trades, label_protocol)
    expected_kind = model_spec.to_dict()["target_kind"]
    if (expected_kind != label_protocol.target_kind or labels.empty or
            not labels.target_kind.eq(expected_kind).all() or
            not labels.label_protocol_hash.eq(label_protocol.configuration_hash).all()):
        raise PipelineValidationError("Every realized label must match the registered model target and LabelProtocol")
    if labels.duplicated(["sid", "formation_at"]).any():
        raise PipelineValidationError("Label rows must identify one outcome per formation/SID")
    end = aware(document["development"]["end_exclusive"])
    if (labels.label_available_at >= end).any():
        raise PipelineValidationError("Execution outcomes exceed the study's accessible development interval")
    # Outer one-to-one join makes missing/extra outcomes visible instead of
    # silently changing the candidate/benchmark cross-sectional sample.
    records = scores.merge(labels, on=["sid", "formation_at"], how="outer", validate="one_to_one", indicator=True)
    if not records["_merge"].eq("both").all():
        raise PipelineValidationError("Factor and realized label populations differ; no silent inner-join sample selection")
    records = records.drop(columns="_merge").sort_values(["formation_at", "sid"]).reset_index(drop=True)
    if not np.isfinite(records[expected_kind].to_numpy(dtype=float)).all():
        raise PipelineValidationError("Registered return labels must be finite")
    artifact_keys = []

    def capture(model, fold, training_metadata):
        artifact = model.artifact(fit_cutoff=fold.train_end, train_start=fold.train_start,
                                  training_metadata=training_metadata)
        if audit_store is not None:
            key = "model-artifacts/" + artifact["artifact_hash"] + ".json"
            audit_store.write_once(key, canonical_json(artifact))
            artifact_keys.append(key)
        return artifact

    evaluation = walk_forward_evaluate(records, tuple(document["model_spec"]["features"]), expected_kind,
                                       lambda: create_model(model_spec), min_ic_names=3,
                                       artifact_callback=capture)
    # Bind generic metric labels back to their exact gross/net and source
    # protocol identities; no rename can silently change the training target.
    evaluation.predictions["target_kind"] = expected_kind
    evaluation.predictions["label_protocol_hash"] = label_protocol.configuration_hash
    evaluation.predictions["study_hash"] = study.configuration_hash
    return RegisteredStudyResult(study.configuration_hash, subject_hash, expected_kind,
             label_protocol.configuration_hash, dict(document["feature_bindings"]),
             {"bound_features": _record_hash(scores), "execution_labels": _record_hash(labels)},
             records, evaluation, tuple(artifact_keys))
