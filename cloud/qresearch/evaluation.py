"""Development-only rolling evaluation of supplied, realized label records.

No prices, returns, costs, trading rules, or model family are invented here.
Each input row binds one SID's formation time to actual entry, exit and label
availability times. All timestamps must be aware; final-test formations fail
closed. Training and validation independently discard cross-boundary labels.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence
import math

import numpy as np
import pandas as pd

TIMEZONE = "America/New_York"
DEVELOPMENT_END = pd.Timestamp("2024-01-01", tz=TIMEZONE)
TIME_COLUMNS = ("formation_at", "entry_at", "exit_at", "label_available_at")


class EvaluationError(ValueError):
    """Invalid or prohibited development evaluation input."""


@dataclass(frozen=True)
class RollingFold:
    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp  # exclusive; also the parameter-fit boundary
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp  # exclusive


def six_rolling_folds() -> tuple[RollingFold, ...]:
    """2010–2017/2018 through 2015–2022/2023; fixed eight-year windows."""
    return tuple(RollingFold(i + 1, pd.Timestamp(f"{2010 + i}-01-01", tz=TIMEZONE),
                             pd.Timestamp(f"{2018 + i}-01-01", tz=TIMEZONE),
                             pd.Timestamp(f"{2018 + i}-01-01", tz=TIMEZONE),
                             pd.Timestamp(f"{2019 + i}-01-01", tz=TIMEZONE)) for i in range(6))


fixed_rolling_folds = six_rolling_folds


@dataclass(frozen=True)
class FoldSplit:
    fold: RollingFold
    train: pd.DataFrame
    validation: pd.DataFrame
    excluded_train: int
    excluded_validation: int


def _aware_series(series: pd.Series, name: str) -> pd.Series:
    for value in series:
        try:
            timestamp = pd.Timestamp(value)
        except (ValueError, TypeError) as exc:
            raise EvaluationError(f"Invalid {name}") from exc
        if pd.isna(timestamp) or timestamp.tzinfo is None:
            raise EvaluationError(f"{name} must contain nonmissing timezone-aware timestamps")
    return pd.to_datetime(series, utc=True).dt.tz_convert(TIMEZONE)


def _validate_records(records: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(records, pd.DataFrame):
        raise EvaluationError("records must be a DataFrame")
    missing = set(TIME_COLUMNS + ("sid",)) - set(records.columns)
    if missing:
        raise EvaluationError(f"Missing record columns: {sorted(missing)}")
    result = records.copy().reset_index(drop=True)
    for column in TIME_COLUMNS:
        result[column] = _aware_series(result[column], column)
    if result["sid"].isna().any() or result.duplicated(["formation_at", "sid"]).any():
        raise EvaluationError("Each formation/SID pair must identify one label record")
    if (result["formation_at"] >= DEVELOPMENT_END).any():
        raise EvaluationError("Final-test formations (2024 onward) cannot enter development evaluation")
    ordered = ((result["formation_at"] <= result["entry_at"])
               & (result["entry_at"] < result["exit_at"])
               & (result["exit_at"] <= result["label_available_at"]))
    if not ordered.all():
        raise EvaluationError("Records must satisfy formation <= entry < exit <= label_available_at")
    return result


def _validate_fold(fold: RollingFold) -> None:
    if fold not in six_rolling_folds():
        raise EvaluationError("Only the six registered eight-year/one-year development folds are allowed")


def build_fold_splits(records: pd.DataFrame, fold: RollingFold) -> FoldSplit:
    """Use only labels that have matured strictly before each exclusive boundary.

    This implements label purging, not a guessed embargo. Any extra embargo
    derived from the frozen experiment must be applied before this function.
    Validation trades and label availability must stay inside the validation
    year, so their outcomes cannot draw on the final test period.
    """
    _validate_fold(fold)
    data = _validate_records(records)
    train_candidates = ((data.formation_at >= fold.train_start) & (data.formation_at < fold.train_end))
    valid_candidates = ((data.formation_at >= fold.validation_start) & (data.formation_at < fold.validation_end))
    train_mask = (train_candidates & (data.entry_at >= fold.train_start)
                  & (data.exit_at < fold.train_end) & (data.label_available_at < fold.train_end))
    valid_mask = (valid_candidates & (data.entry_at >= fold.validation_start)
                  & (data.exit_at < fold.validation_end) & (data.label_available_at < fold.validation_end))
    return FoldSplit(fold, data.loc[train_mask].copy(), data.loc[valid_mask].copy(),
                     int(train_candidates.sum() - train_mask.sum()),
                     int(valid_candidates.sum() - valid_mask.sum()))


def _numeric_rows(data: pd.DataFrame, columns: Sequence[str]) -> tuple[pd.DataFrame, pd.Series]:
    if any(column not in data for column in columns):
        raise EvaluationError("A required feature/label column is missing")
    try:
        numeric = data.loc[:, list(columns)].astype(float).replace([np.inf, -np.inf], np.nan)
    except (TypeError, ValueError) as exc:
        raise EvaluationError("Features and labels must be numeric") from exc
    return numeric, numeric.notna().all(axis=1)


@dataclass(frozen=True)
class WalkForwardResult:
    predictions: pd.DataFrame
    folds: pd.DataFrame
    daily_ic: pd.DataFrame
    ic_statistics: dict[str, Any]
    model_artifacts: tuple[dict[str, Any], ...] = ()


def walk_forward_evaluate(records: pd.DataFrame, feature_columns: Sequence[str],
                          label_column: str, model_factory: Callable[[], Any],
                          folds: Iterable[RollingFold] | None = None,
                          min_ic_names: int = 3,
                          artifact_callback: Callable[[Any, RollingFold, pd.DataFrame], dict] | None = None) -> WalkForwardResult:
    """Refit a newly constructed caller-supplied model independently each fold.

    Model protocol: ``fit(X_dataframe, y_series)`` and ``predict(X_dataframe)``.
    The caller freezes model family, hyperparameters and training procedure.
    Only complete, common numeric feature/label rows enter each fold's metrics.
    A factory returning a previously used model instance is rejected.
    An optional artifact_callback receives the fitted model, current fold and
    exact mature, complete training-row metadata. Its artifact is captured per
    fold; without the callback the previous return/API behavior is preserved.
    """
    feature_columns = tuple(feature_columns)
    if not feature_columns or len(set(feature_columns)) != len(feature_columns) or label_column in feature_columns:
        raise EvaluationError("Use distinct feature columns and a separate label column")
    if any(name in TIME_COLUMNS + ("sid",) for name in feature_columns):
        raise EvaluationError("Metadata cannot be a model feature")
    data = _validate_records(records)
    chosen_folds = tuple(six_rolling_folds() if folds is None else folds)
    if not chosen_folds or len({f.fold_id for f in chosen_folds}) != len(chosen_folds):
        raise EvaluationError("Folds must be nonempty and unique")
    models, predictions, summaries, artifacts = [], [], [], []
    for fold in chosen_folds:
        split = build_fold_splits(data, fold)
        train_values, train_good = _numeric_rows(split.train, feature_columns + (label_column,))
        valid_values, valid_good = _numeric_rows(split.validation, feature_columns + (label_column,))
        if not train_good.any() or not valid_good.any():
            raise EvaluationError(f"Fold {fold.fold_id} has no complete training or validation observations")
        model = model_factory()
        if any(model is previous for previous in models):
            raise EvaluationError("model_factory must create a fresh model instance for every fold")
        if not callable(getattr(model, "fit", None)) or not callable(getattr(model, "predict", None)):
            raise EvaluationError("Injected model must implement fit and predict")
        models.append(model)  # Keep identities alive across all folds.
        model.fit(train_values.loc[train_good, list(feature_columns)].copy(),
                  train_values.loc[train_good, label_column].copy())
        if artifact_callback is not None:
            artifact = artifact_callback(model, fold, split.train.loc[train_good, ["sid", *TIME_COLUMNS]].copy())
            if not isinstance(artifact, dict) or not artifact:
                raise EvaluationError("A model artifact callback must return an explicit artifact dictionary")
            artifacts.append(deepcopy(artifact))
        scores = np.asarray(model.predict(valid_values.loc[valid_good, list(feature_columns)].copy()), dtype=float)
        if scores.shape not in {(int(valid_good.sum()),), (int(valid_good.sum()), 1)}:
            raise EvaluationError("Model prediction count/shape does not match validation observations")
        output = split.validation.loc[valid_good, ["sid", *TIME_COLUMNS]].copy()
        output["fold_id"] = fold.fold_id
        output["prediction"] = scores.reshape(-1)
        output["label"] = valid_values.loc[valid_good, label_column]
        predictions.append(output)
        summaries.append({"fold_id": fold.fold_id, "train_start": fold.train_start,
                          "train_end_exclusive": fold.train_end,
                          "validation_start": fold.validation_start,
                          "validation_end_exclusive": fold.validation_end,
                          "train_n": int(train_good.sum()), "validation_n": int(valid_good.sum()),
                          "purged_train_n": split.excluded_train,
                          "purged_validation_n": split.excluded_validation,
                          "missing_train_n": int((~train_good).sum()),
                          "missing_validation_n": int((~valid_good).sum()),
                          "invalid_prediction_n": int((~np.isfinite(scores)).sum())})
    combined = pd.concat(predictions, ignore_index=True)
    daily = daily_rank_ic(combined, min_names=min_ic_names)
    return WalkForwardResult(combined, pd.DataFrame(summaries), daily, summarize_ic(daily), tuple(artifacts))


def _centered_unit(values: np.ndarray) -> np.ndarray | None:
    """Center finite float64 observations without squaring their original scale.

    A power-of-two scale bounds subtraction and preserves neighboring floats.
    Remove an observation first so a large shared offset cannot round away the
    mean of small differences. Rescale those differences before taking a norm;
    no extended-precision dtype or product of raw variances is required.
    """
    largest = float(np.max(np.abs(values)))
    if largest == 0:
        return None
    exponent = math.frexp(largest)[1]
    # Components negligible beside the largest observation may underflow here;
    # the largest survives, so this cannot turn a varying vector into a constant.
    with np.errstate(under="ignore"):
        scaled = np.ldexp(values, -exponent)
    offsets = scaled - scaled[0]
    centered = offsets - math.fsum(float(value) for value in offsets) / len(offsets)
    spread = float(np.max(np.abs(centered)))
    if spread == 0:
        return None
    centered = centered / spread
    norm = math.sqrt(math.fsum(float(value) * float(value) for value in centered))
    return centered / norm


def _correlation(left: np.ndarray, right: np.ndarray, method: str) -> float:
    if len(left) < 2:
        return float("nan")
    if method == "spearman":
        # Spearman depends only on order. Testing raw-value variance first can
        # underflow for distinct, finite scores (or overflow at large scales).
        # Average ranks preserve ties and have a well-scaled variance.
        left = pd.Series(left).rank(method="average").to_numpy()
        right = pd.Series(right).rank(method="average").to_numpy()
        # Retain the accepted rank-correlation path, including exact perfect
        # rank outputs used by constant-IC statistics. Ranks need no raw-scale
        # stabilization; applying another normalization changes last-bit rounding.
        if np.std(left) == 0 or np.std(right) == 0:
            return float("nan")
        return float(np.corrcoef(left, right)[0, 1])
    elif method != "pearson":
        raise EvaluationError("Correlation method must be pearson or spearman")
    left, right = _centered_unit(left), _centered_unit(right)
    if left is None or right is None:
        return float("nan")
    correlation = math.fsum(float(x) * float(y) for x, y in zip(left, right))
    # The exact normalized dot product is bounded; trim final rounding only.
    return max(-1.0, min(1.0, correlation))


def daily_rank_ic(records: pd.DataFrame, score_column: str = "prediction", label_column: str = "label",
                  date_column: str = "formation_at", min_names: int = 3) -> pd.DataFrame:
    """Daily Spearman IC and its exact common, finite cross-sectional sample size."""
    if isinstance(min_names, bool) or not isinstance(min_names, int) or min_names < 2:
        raise EvaluationError("min_names must be an integer of at least two")
    if date_column not in records or "sid" not in records:
        raise EvaluationError("IC records need date and SID columns")
    data = records.copy().reset_index(drop=True)
    data["date"] = _aware_series(data[date_column], date_column).dt.normalize()
    if (data["date"] >= DEVELOPMENT_END).any():
        raise EvaluationError("Final-test data cannot enter development IC")
    if data.duplicated(["date", "sid"]).any():
        raise EvaluationError("Daily IC needs one observation per SID per local date")
    numeric, good = _numeric_rows(data, (score_column, label_column))
    result = []
    for date, group in data.groupby("date", sort=True):
        use = group.index[good.loc[group.index]]
        values = numeric.loc[use]
        n = len(values)
        ic = (_correlation(values[score_column].to_numpy(), values[label_column].to_numpy(), "spearman")
              if n >= min_names else float("nan"))
        result.append({"date": date, "n": n, "ic": ic})
    return pd.DataFrame(result, columns=["date", "n", "ic"])


def summarize_ic(daily: pd.DataFrame) -> dict[str, Any]:
    """ICIR = arithmetic mean / sample standard deviation, without annualization."""
    values = pd.to_numeric(daily["ic"], errors="raise").replace([np.inf, -np.inf], np.nan).dropna()
    mean = float(values.mean()) if len(values) else float("nan")
    std = float(values.std(ddof=1)) if len(values) >= 2 else float("nan")
    return {"valid_days": len(values), "total_days": len(daily), "mean_ic": mean,
            "sample_std_ic": std, "icir": mean / std if np.isfinite(std) and std > 0 else float("nan"),
            "icir_annualized": False, "common_observations": int(daily["n"].sum())}


def paired_factor_correlation(left: pd.Series, right: pd.Series, method: str = "pearson") -> dict[str, Any]:
    """Correlation on the same aligned, finite observations; sign and absolute value."""
    if method not in {"pearson", "spearman"}:
        raise EvaluationError("Correlation method must be pearson or spearman")
    if not left.index.is_unique or not right.index.is_unique:
        raise EvaluationError("Factor correlation indices must uniquely identify observations")
    pair = pd.concat([left.rename("left"), right.rename("right")], axis=1, join="inner")
    pair = pair.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    corr = _correlation(pair.left.to_numpy(), pair.right.to_numpy(), method)
    return {"method": method, "n": len(pair), "correlation": corr, "absolute_correlation": abs(corr)}


def pairwise_factor_correlations(features: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Pairwise Pearson/Spearman absolute correlations and exact pair sample counts."""
    if not features.columns.is_unique:
        raise EvaluationError("Factor names must be unique")
    output = {name: pd.DataFrame(index=features.columns, columns=features.columns, dtype=float)
              for name in ("absolute_pearson", "absolute_spearman", "n")}
    for left in features:
        for right in features:
            for method in ("pearson", "spearman"):
                result = paired_factor_correlation(features[left], features[right], method)
                output[f"absolute_{method}"].loc[left, right] = result["absolute_correlation"]
                output["n"].loc[left, right] = result["n"]
    return output
