"""Explicit frozen identity/ridge models with audited training artifacts.

No model is selected on import. These models implement the existing evaluator's
fit/predict protocol; they never choose hyperparameters or request data. A fitted
artifact is published only with exact development training-row metadata and a
mature-label cutoff. The caller supplies causally built inference windows;
this pure estimator does not itself have access to data timestamps or a feed.
"""
from dataclasses import dataclass
import json
import math
import re
from typing import Mapping

import numpy as np
import pandas as pd

from .contracts import DEVELOPMENT_END, NY, aware, digest


class ModelValidationError(ValueError):
    """Model design, training inputs or artifact are inconsistent."""


def _finite_number(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ModelValidationError(name + " must be a finite number")
    return float(value)


@dataclass(frozen=True)
class ModelSpec:
    canonical_json: str
    configuration_hash: str

    @classmethod
    def from_dict(cls, raw):
        fields = {"schema_version", "model_id", "model_family", "features", "target_kind", "preprocessing",
                  "hyperparameters", "trainable_parameters", "purpose"}
        if not isinstance(raw, Mapping) or set(raw) != fields:
            raise ModelValidationError("A complete explicit versioned ModelSpec is required")
        data = dict(raw)
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ModelValidationError("Unsupported model schema version")
        if not isinstance(data["model_id"], str) or not data["model_id"].strip():
            raise ModelValidationError("model_id is required")
        names = data["features"]
        if (not isinstance(names, list) or not names or
                any(not isinstance(x, str) or not x.strip() for x in names) or len(names) != len(set(names))):
            raise ModelValidationError("Unique explicit feature names are required")
        forbidden = {"sid", "trade_id", "formation_at", "entry_at", "exit_at", "label_available_at",
                     "label", "gross_return", "net_return", "target_kind", "purpose", "label_protocol_hash"}
        for name in names:
            if name in forbidden or any(x in {"label", "labels", "target", "targets", "future", "forward"}
                                        for x in re.split(r"[^a-z0-9]+", name.lower())):
                raise ModelValidationError("Labels and metadata cannot be model features")
        if data["target_kind"] not in {"gross_return", "net_return"}:
            raise ModelValidationError("Gross/net target convention must be explicit")
        if data["purpose"] not in {"engineering_fixture", "research"}:
            raise ModelValidationError("Explicit model purpose required")
        prep, parameters = data["preprocessing"], data["hyperparameters"]
        if (not isinstance(prep, dict) or set(prep) != {"standardize", "constant_feature_policy"} or
                type(prep["standardize"]) is not bool or prep["constant_feature_policy"] != "unit_scale"):
            raise ModelValidationError("Explicit frozen preprocessing required")
        expected_trainable = []
        if data["model_family"] == "identity":
            if len(names) != 1 or prep["standardize"] or not isinstance(parameters, dict) or set(parameters) != {"coefficient"}:
                raise ModelValidationError("Identity requires one unscaled factor and an explicit coefficient")
            parameters = {"coefficient": _finite_number(parameters["coefficient"], "coefficient")}
            if parameters["coefficient"] == 0:
                raise ModelValidationError("Identity coefficient cannot be zero")
        elif data["model_family"] == "ridge":
            if not isinstance(parameters, dict) or set(parameters) != {"alpha", "fit_intercept"}:
                raise ModelValidationError("Ridge alpha and intercept rule must be fixed")
            alpha = _finite_number(parameters["alpha"], "alpha")
            if alpha <= 0 or type(parameters["fit_intercept"]) is not bool:
                raise ModelValidationError("Ridge alpha must be positive and intercept rule boolean")
            parameters = {"alpha": alpha, "fit_intercept": parameters["fit_intercept"]}
            expected_trainable = ["coefficients"]
            if parameters["fit_intercept"]:
                expected_trainable += ["intercept"]
            if prep["standardize"]:
                expected_trainable += ["feature_mean", "feature_scale"]
        else:
            raise ModelValidationError("No registered identity/ridge model family was selected")
        if data["trainable_parameters"] != expected_trainable:
            raise ModelValidationError("Declared trainable parameters differ from the frozen estimator")
        data["hyperparameters"] = parameters
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return cls(encoded, digest(data))

    def to_dict(self):
        return json.loads(self.canonical_json)

    @property
    def features(self):
        return tuple(self.to_dict()["features"])


def _frame_identity(X, y):
    return digest({"features": list(X.columns), "index": [str(x) for x in X.index],
                   "X": X.to_numpy(dtype=float).tolist(), "target": str(y.name),
                   "y": y.to_numpy(dtype=float).tolist()})


class FrozenModel:
    """Fresh per-fold model; fitted state never accumulates a previous window."""
    def __init__(self, spec):
        if not isinstance(spec, ModelSpec):
            raise ModelValidationError("Validate an explicit ModelSpec before creating a model")
        self.spec = spec
        self._state = None
        self._training_identity = None
        self._training_index = None

    def _features(self, X):
        if (not isinstance(X, pd.DataFrame) or not X.columns.is_unique or not X.index.is_unique or
                set(X.columns) != set(self.spec.features)):
            raise ModelValidationError("Model input must contain exactly the registered factor features")
        selected = X.loc[:, self.spec.features]
        if any(pd.api.types.is_bool_dtype(kind) or pd.api.types.is_complex_dtype(kind) for kind in selected.dtypes):
            raise ModelValidationError("Boolean/complex features are not factor scores")
        values = selected.astype(float)
        if not len(values) or not np.isfinite(values.to_numpy()).all():
            raise ModelValidationError("Model inputs must be nonempty and complete finite numbers")
        return values

    def fit(self, X, y):
        self._state, self._training_identity, self._training_index = None, None, None
        values = self._features(X)
        configuration = self.spec.to_dict()
        if (not isinstance(y, pd.Series) or not y.index.equals(X.index) or
                y.name != configuration["target_kind"]):
            raise ModelValidationError("Training label rows and gross/net convention must match the ModelSpec")
        if pd.api.types.is_bool_dtype(y.dtype) or pd.api.types.is_complex_dtype(y.dtype):
            raise ModelValidationError("Boolean/complex targets are not realized returns")
        target = y.astype(float)
        if not np.isfinite(target.to_numpy()).all():
            raise ModelValidationError("Training labels must be complete finite values")
        array, outcome = values.to_numpy(), target.to_numpy()
        if configuration["model_family"] == "identity":
            self._state = {}
        else:
            standardize = configuration["preprocessing"]["standardize"]
            mean = array.mean(axis=0) if standardize else np.zeros(array.shape[1])
            scale = array.std(axis=0, ddof=0) if standardize else np.ones(array.shape[1])
            scale = np.where(scale > 1e-12, scale, 1.)
            transformed = (array - mean) / scale
            intercept_enabled = configuration["hyperparameters"]["fit_intercept"]
            center = transformed.mean(axis=0) if intercept_enabled else np.zeros(array.shape[1])
            outcome_mean = float(outcome.mean()) if intercept_enabled else 0.
            centered = transformed - center
            alpha = configuration["hyperparameters"]["alpha"]
            coefficients = np.linalg.solve(centered.T @ centered + alpha * np.eye(array.shape[1]),
                                           centered.T @ (outcome - outcome_mean))
            intercept = outcome_mean - float(center @ coefficients)
            self._state = {"feature_mean": mean.tolist(), "feature_scale": scale.tolist(),
                           "coefficients": coefficients.tolist(), "intercept": intercept}
        self._training_identity = _frame_identity(values, target)
        self._training_index = X.index.copy()
        return self

    def predict(self, X):
        if self._state is None:
            raise ModelValidationError("The registered model has not been fitted/initialized for this fold")
        values = self._features(X).to_numpy()
        spec = self.spec.to_dict()
        if spec["model_family"] == "identity":
            return values[:, 0] * spec["hyperparameters"]["coefficient"]
        return ((values - np.asarray(self._state["feature_mean"])) / np.asarray(self._state["feature_scale"])) @ np.asarray(self._state["coefficients"]) + self._state["intercept"]

    def artifact(self, *, fit_cutoff, training_metadata, train_start):
        if self._state is None or self._training_index is None:
            raise ModelValidationError("No fitted training provenance is available")
        cutoff, start = aware(fit_cutoff), aware(train_start)
        if (cutoff > DEVELOPMENT_END or start != cutoff - pd.DateOffset(years=8) or
                cutoff.month != 1 or cutoff.day != 1 or cutoff.hour or cutoff.minute or cutoff.second or cutoff.microsecond):
            raise ModelValidationError("Artifact fitting must use the declared annual eight-year window before final evaluation")
        required = {"sid", "formation_at", "entry_at", "exit_at", "label_available_at"}
        if (not isinstance(training_metadata, pd.DataFrame) or not required <= set(training_metadata) or
                not training_metadata.index.equals(self._training_index)):
            raise ModelValidationError("Training provenance must align exactly with fitted rows")
        metadata = training_metadata.loc[:, ["sid", "formation_at", "entry_at", "exit_at", "label_available_at"]].copy()
        for name in ("formation_at", "entry_at", "exit_at", "label_available_at"):
            metadata[name] = [aware(x) for x in metadata[name]]
            if metadata[name].isna().any():
                raise ModelValidationError("Training provenance times cannot be missing")
        if (metadata.sid.map(lambda value: not isinstance(value, str) or not value.strip()).any() or
                metadata.duplicated(["formation_at", "sid"]).any() or
                not ((metadata.formation_at >= start) & (metadata.formation_at <= metadata.entry_at) &
                     (metadata.entry_at < metadata.exit_at) & (metadata.exit_at <= metadata.label_available_at) &
                     (metadata.label_available_at < cutoff)).all()):
            raise ModelValidationError("Training rows cross the fitting window or have immature labels")
        rows = [[str(row.sid), row.formation_at.isoformat(), row.entry_at.isoformat(), row.exit_at.isoformat(),
                 row.label_available_at.isoformat()] for row in metadata.itertuples()]
        body = {"schema_version": 1, "model_spec": self.spec.to_dict(), "model_spec_hash": self.spec.configuration_hash,
                "fit_cutoff": cutoff.isoformat(), "train_start": start.isoformat(), "training_rows": len(metadata),
                "training_frame_hash": self._training_identity, "training_metadata_hash": digest(rows),
                "learned_state": self._state}
        return dict(body, artifact_hash=digest(body))


def create_model(spec):
    return FrozenModel(spec)


def restore_model(artifact):
    if not isinstance(artifact, dict) or "artifact_hash" not in artifact:
        raise ModelValidationError("Versioned fitted artifact required")
    body = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    if digest(body) != artifact["artifact_hash"]:
        raise ModelValidationError("Fitted artifact integrity violation")
    required = {"schema_version", "model_spec", "model_spec_hash", "fit_cutoff", "train_start", "training_rows",
                "training_frame_hash", "training_metadata_hash", "learned_state"}
    if set(body) != required or type(body["schema_version"]) is not int or body["schema_version"] != 1:
        raise ModelValidationError("Unknown fitted artifact schema")
    spec = ModelSpec.from_dict(body["model_spec"])
    cutoff, start = aware(body["fit_cutoff"]), aware(body["train_start"])
    if (body["model_spec_hash"] != spec.configuration_hash or cutoff > DEVELOPMENT_END or
            start != cutoff - pd.DateOffset(years=8) or type(body["training_rows"]) is not int or body["training_rows"] < 1 or
            cutoff.month != 1 or cutoff.day != 1 or cutoff.hour or cutoff.minute or cutoff.second or cutoff.microsecond):
        raise ModelValidationError("Artifact specification or training boundary mismatch")
    for key in ("training_frame_hash", "training_metadata_hash"):
        if not isinstance(body[key], str) or not re.fullmatch(r"[a-f0-9]{64}", body[key]):
            raise ModelValidationError("Missing fitted provenance hashes")
    model = FrozenModel(spec)
    state, n = body["learned_state"], len(spec.features)
    if spec.to_dict()["model_family"] == "identity":
        if state != {}:
            raise ModelValidationError("Parameterless identity cannot contain learned coefficients")
    else:
        if not isinstance(state, dict) or set(state) != {"feature_mean", "feature_scale", "coefficients", "intercept"}:
            raise ModelValidationError("Incomplete ridge state")
        for key in ("feature_mean", "feature_scale", "coefficients"):
            if not isinstance(state[key], list) or len(state[key]) != n:
                raise ModelValidationError("Fitted vector shape differs from registered features")
            for value in state[key]:
                _finite_number(value, key)
        _finite_number(state["intercept"], "intercept")
        if any(value <= 0 for value in state["feature_scale"]):
            raise ModelValidationError("Fitted feature scales must be positive")
    model._state = json.loads(json.dumps(state))
    return model
