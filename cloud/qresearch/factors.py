"""Restricted, deterministic factors over already point-in-time-safe matrices.

The engine never loads data. A numeric literal is a constant; every other node
is a JSON object with ``op`` and ``args`` (or ``arg`` for a unary operation).
Field nodes accept ``name`` or ``field``. Lag uses positive ``periods`` and
rolling operations use a full ``window``. Missing values remain missing.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


OPERATOR_ALIASES = {
    "positive_session_lag": "lag",
    "trailing_mean": "rolling_mean",
    "trailing_std": "rolling_std",
    "trailing_correlation": "rolling_corr",
    "cross_section_rank": "rank",
    "cross_section_zscore": "zscore",
}
OPERATORS = frozenset({
    "field", "add", "subtract", "multiply", "safe_divide", "positive_log",
    "lag", "rolling_mean", "rolling_std", "rolling_corr", "rank", "zscore",
})
MAX_WINDOW = 2520
MAX_CONSTANT = 1e12
MAX_NODES = 256
MAX_DEPTH = 32


class FactorValidationError(ValueError):
    """An expression or input window violates the restricted contract."""


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise FactorValidationError("Factor configuration must be finite JSON") from exc


def _operation(value: str) -> str:
    if not isinstance(value, str):
        raise FactorValidationError("Operator names must be strings")
    result = OPERATOR_ALIASES.get(value, value)
    if result not in OPERATORS:
        raise FactorValidationError(f"Unapproved operator: {value}")
    return result


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_WINDOW:
        raise FactorValidationError(f"{name} must be an integer in [1, {MAX_WINDOW}]")
    return value


def _field_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise FactorValidationError("Field names must be nonempty strings of at most 160 characters")
    # These reserved namespaces may never be relabelled as factor inputs.
    tokens = re.split(r"[^a-z0-9]+", value.lower())
    if any(t in {"label", "labels", "target", "targets", "future", "forward"} for t in tokens):
        raise FactorValidationError(f"Label/future fields are forbidden: {value}")
    return value


def _strings(value: Any, name: str, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise FactorValidationError(f"{name} must be a list of nonempty strings")
    if nonempty and not value:
        raise FactorValidationError(f"{name} must not be empty")
    if len(set(value)) != len(value):
        raise FactorValidationError(f"{name} contains duplicates")
    return tuple(value)


@dataclass(frozen=True)
class FactorSpec:
    """Validated frozen configuration; hashes include fixed metadata and formula."""

    factor_id: str
    allowed_fields: tuple[str, ...]
    allowed_operators: tuple[str, ...]
    canonical_json: str
    formula_json: str
    configuration_hash: str
    structure_hash: str
    lookback_sessions: int

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any],
                  field_catalog: Iterable[str] | Mapping[str, Any] | None = None) -> "FactorSpec":
        if not isinstance(raw, Mapping):
            raise FactorValidationError("FactorSpec must be a JSON object")
        data = json.loads(_canonical(dict(raw)))
        factor_id = data.get("factor_id")
        if not isinstance(factor_id, str) or not factor_id.strip():
            raise FactorValidationError("factor_id must be nonempty")
        hypothesis = data.get("economic_hypothesis")
        if not isinstance(hypothesis, dict):
            raise FactorValidationError("An economic_hypothesis is required")
        if not isinstance(hypothesis.get("mechanism"), str) or not hypothesis["mechanism"].strip():
            raise FactorValidationError("A nonempty economic mechanism is required")
        direction = hypothesis.get("expected_direction")
        if isinstance(direction, bool) or direction not in (-1, 1):
            raise FactorValidationError("expected_direction must be +1 or -1")
        _positive_integer(hypothesis.get("prediction_horizon_sessions"), "prediction_horizon_sessions")
        _strings(hypothesis.get("applicable_regimes"), "applicable_regimes", True)
        _strings(hypothesis.get("failure_conditions"), "failure_conditions", True)
        fields = _strings(data.get("allowed_fields"), "allowed_fields", True)
        fields = tuple(_field_name(x) for x in fields)
        if field_catalog is not None and not set(fields).issubset(set(field_catalog)):
            raise FactorValidationError("Factor fields are outside the data dictionary whitelist")
        allowed = tuple(sorted({_operation(x) for x in
                                _strings(data.get("allowed_operators"), "allowed_operators")}))
        parameters = data.get("parameters", {})
        if not isinstance(parameters, dict):
            raise FactorValidationError("parameters must contain fixed JSON values")
        _canonical(parameters)
        nodes = 0

        def visit(node: Any, depth: int = 0) -> tuple[Any, int]:
            nonlocal nodes
            nodes += 1
            if nodes > MAX_NODES or depth > MAX_DEPTH:
                raise FactorValidationError("Expression exceeds the node/depth limit")
            if isinstance(node, (int, float)) and not isinstance(node, bool):
                if not math.isfinite(node) or abs(node) > MAX_CONSTANT:
                    raise FactorValidationError("Constant is nonfinite or exceeds the magnitude limit")
                return float(node), 0
            if not isinstance(node, dict):
                raise FactorValidationError("Each expression node must be an object or numeric constant")
            op = _operation(node.get("op"))
            if op == "field":
                if set(node) not in ({"op", "name"}, {"op", "field"}):
                    raise FactorValidationError("A field node needs exactly op and name (or field)")
                field = _field_name(node.get("name", node.get("field")))
                if field not in fields:
                    raise FactorValidationError(f"Field is outside this specification's whitelist: {field}")
                return {"op": "field", "name": field}, 0
            if op not in allowed:
                raise FactorValidationError(f"Operator is outside this specification's whitelist: {op}")
            if "arg" in node and "args" in node:
                raise FactorValidationError("Use arg or args, not both")
            children = node.get("args", [node["arg"]] if "arg" in node else None)
            if not isinstance(children, list):
                raise FactorValidationError(f"{op} requires an args list")
            arity = 2 if op in {"subtract", "safe_divide", "rolling_corr"} else 1
            if op in {"add", "multiply"}:
                if not 2 <= len(children) <= 16:
                    raise FactorValidationError(f"{op} needs between 2 and 16 arguments")
            elif len(children) != arity:
                raise FactorValidationError(f"{op} needs {arity} argument(s)")
            extras = {"periods"} if op == "lag" else ({"window"} if op.startswith("rolling_") else set())
            if set(node) != {"op", "arg" if "arg" in node else "args"} | extras:
                raise FactorValidationError(f"Unexpected or missing fixed parameters for {op}")
            visited = [visit(x, depth + 1) for x in children]
            args = [x[0] for x in visited]
            lookback = max(x[1] for x in visited)
            if op in {"add", "multiply"}:
                args.sort(key=_canonical)
            result = {"op": op, "args": args}
            if op == "lag":
                result["periods"] = _positive_integer(node.get("periods"), "periods")
                lookback += result["periods"]
            elif op.startswith("rolling_"):
                result["window"] = _positive_integer(node.get("window"), "window")
                if op in {"rolling_std", "rolling_corr"} and result["window"] < 2:
                    raise FactorValidationError(f"{op} needs at least two observations")
                lookback += result["window"] - 1
            if lookback > MAX_WINDOW:
                raise FactorValidationError("Combined expression lookback exceeds the limit")
            return result, lookback

        formula, lookback = visit(data.get("formula"))
        data["formula"] = formula
        data["allowed_fields"] = sorted(fields)
        data["allowed_operators"] = list(allowed)
        # A declared freeze hash and workflow status are not economic configuration.
        data.pop("freeze_hash", None)
        data.pop("status", None)
        serialized = _canonical(data)
        expression = _canonical(formula)
        return cls(factor_id, tuple(sorted(fields)), allowed, serialized, expression,
                   sha256(serialized.encode()).hexdigest(),
                   sha256(expression.encode()).hexdigest(), lookback)

    @property
    def formula(self) -> Any:
        return json.loads(self.formula_json)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.canonical_json)

    def compile(self) -> "CompiledFactor":
        return CompiledFactor(self)

    def evaluate(self, window: Any) -> pd.Series:
        return self.compile().evaluate(window)

    @property
    def requires_historical_membership(self) -> bool:
        """Historical ranks must not silently use the current constituents."""
        def visit(node: Any, temporal_parent: bool = False) -> bool:
            if not isinstance(node, dict):
                return False
            op = node["op"]
            if temporal_parent and op in {"rank", "zscore"}:
                return True
            return any(visit(child, temporal_parent or op == "lag" or op.startswith("rolling_"))
                       for child in node.get("args", []))
        return visit(self.formula)


def _validate_window(window: Any) -> tuple[dict[str, pd.DataFrame], tuple[str, ...], pd.DataFrame | None]:
    as_of = pd.Timestamp(window.as_of)
    if as_of.tzinfo is None:
        raise FactorValidationError("PITWindow.as_of must be timezone-aware")
    if as_of >= pd.Timestamp("2024-01-01", tz="America/New_York"):
        raise FactorValidationError("Independent final evaluation is not enabled in the development engine")
    sids = tuple(window.sids)
    if len(set(sids)) != len(sids):
        raise FactorValidationError("PITWindow contains duplicate SIDs")
    matrices = {}
    common_index = None
    for name, frame in window.matrices.items():
        _field_name(name)
        if not isinstance(frame, pd.DataFrame) or not isinstance(frame.index, pd.DatetimeIndex):
            raise FactorValidationError("PIT matrices need a DatetimeIndex")
        if frame.index.tz is None or not frame.index.is_unique or not frame.index.is_monotonic_increasing:
            raise FactorValidationError("PIT matrix times must be aware, unique and increasing")
        if len(frame) and frame.index.max() > as_of:
            raise FactorValidationError("Future rows are forbidden in a factor window")
        if not frame.columns.is_unique or set(frame.columns) != set(sids):
            raise FactorValidationError("PIT matrix columns must match the window SIDs")
        if common_index is not None and not frame.index.equals(common_index):
            raise FactorValidationError("PIT matrices must share the same formation index")
        common_index = frame.index
        try:
            matrices[name] = frame.reindex(columns=sids).astype(float).replace([np.inf, -np.inf], np.nan)
        except (TypeError, ValueError) as exc:
            raise FactorValidationError("PIT matrices must contain numeric values") from exc
    membership = getattr(window, "universe_membership", None)
    if membership is not None:
        if (not isinstance(membership, pd.DataFrame)
                or not isinstance(membership.index, pd.DatetimeIndex)
                or membership.index.tz is None or not membership.index.is_unique
                or not membership.index.is_monotonic_increasing
                or (len(membership) and membership.index.max() > as_of)
                or not membership.columns.is_unique or set(membership.columns) != set(sids)
                or (common_index is not None and not membership.index.equals(common_index))):
            raise FactorValidationError("Universe membership must match the causal matrix index and SIDs")
        if membership.isna().any().any() or not all(pd.api.types.is_bool_dtype(x) for x in membership.dtypes):
            raise FactorValidationError("Universe membership requires nonmissing boolean values")
        membership = membership.reindex(columns=sids).astype(bool).copy()
    return matrices, sids, membership


@dataclass(frozen=True)
class CompiledFactor:
    spec: FactorSpec

    def evaluate(self, window: Any) -> pd.Series:
        matrices, sids, membership = _validate_window(window)
        return self._evaluate(matrices, sids, membership)

    def _evaluate(self, matrices: Mapping[str, pd.DataFrame], sids: tuple[str, ...],
                  membership: pd.DataFrame | None = None) -> pd.Series:
        if membership is None and self.spec.requires_historical_membership:
            raise FactorValidationError("Historical rank/zscore requires an explicit membership matrix, even for a fixed pool")
        missing = set(self.spec.allowed_fields) - set(matrices)
        if missing:
            raise FactorValidationError(f"Window is missing declared fields: {sorted(missing)}")
        sample = next(iter(matrices.values()), pd.DataFrame(columns=sids))
        cache: dict[str, pd.DataFrame] = {}

        def compute(node: Any) -> pd.DataFrame:
            key = _canonical(node)
            if key in cache:
                return cache[key]
            if isinstance(node, (int, float)):
                result = pd.DataFrame(float(node), index=sample.index, columns=sids)
            elif node["op"] == "field":
                result = matrices[node["name"]]
            else:
                op = node["op"]
                args = [compute(x) for x in node["args"]]
                first = args[0]
                with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                    if op in {"add", "multiply"}:
                        result = first.copy()
                        for other in args[1:]:
                            result = result + other if op == "add" else result * other
                    elif op == "subtract":
                        result = first - args[1]
                    elif op == "safe_divide":
                        # Fixed numerical convention, not a tunable parameter.
                        result = first / args[1].where(args[1].abs() > 1e-12)
                    elif op == "positive_log":
                        result = np.log(first.where(first > 0))
                    elif op == "lag":
                        result = first.shift(node["periods"])
                    elif op == "rolling_mean":
                        result = first.rolling(node["window"], min_periods=node["window"]).mean()
                    elif op == "rolling_std":
                        result = first.rolling(node["window"], min_periods=node["window"]).std(ddof=1)
                    elif op == "rolling_corr":
                        result = first.rolling(node["window"], min_periods=node["window"]).corr(args[1], ddof=1)
                    elif op == "rank":
                        pool = first.where(membership) if membership is not None else first
                        result = pool.rank(axis=1, method="average", pct=True, na_option="keep")
                    elif op == "zscore":
                        pool = first.where(membership) if membership is not None else first
                        std = pool.std(axis=1, ddof=0).where(lambda x: x > 1e-12)
                        result = pool.sub(pool.mean(axis=1), axis=0).div(std, axis=0)
                    else:  # Construction validates the AST before execution.
                        raise FactorValidationError(f"Unsupported operation: {op}")
            result = result.replace([np.inf, -np.inf], np.nan)
            cache[key] = result
            return result

        result = compute(self.spec.formula)
        if result.empty:
            current = sids if membership is None else ()
            return pd.Series(np.nan, index=pd.Index(current, name="sid"), name=self.spec.factor_id, dtype=float)
        last = result.iloc[-1].copy()
        if membership is not None:
            last = last.loc[membership.iloc[-1]]
        last.index.name = "sid"
        last.name = self.spec.factor_id
        return last


def compile_factor(spec: FactorSpec) -> CompiledFactor:
    return CompiledFactor(spec)


def evaluate_factors(specs: Iterable[FactorSpec], window: Any) -> pd.DataFrame:
    """Evaluate a batch with one supplied window and no data-provider access."""
    specs = tuple(specs)
    if len({x.factor_id for x in specs}) != len(specs):
        raise FactorValidationError("Batch factor IDs must be unique")
    matrices, sids, membership = _validate_window(window)
    current = (sids if membership is None else
               tuple(membership.columns[membership.iloc[-1]]) if len(membership) else ())
    return pd.DataFrame({spec.factor_id: CompiledFactor(spec)._evaluate(matrices, sids, membership) for spec in specs},
                        index=pd.Index(current, name="sid"))


def structure_similarity(left: FactorSpec, right: FactorSpec) -> dict[str, Any]:
    """Subtree multiset Dice score. This cannot prove economic equivalence."""
    def subtrees(node: Any) -> Counter:
        result = Counter({_canonical(node): 1})
        if isinstance(node, dict):
            for child in node.get("args", []):
                result.update(subtrees(child))
        return result
    a, b = subtrees(left.formula), subtrees(right.formula)
    overlap = sum((a & b).values())
    return {"same_normalized_structure": left.structure_hash == right.structure_hash,
            "subtree_dice": 2 * overlap / (sum(a.values()) + sum(b.values())),
            "economic_equivalence_proven": False}
