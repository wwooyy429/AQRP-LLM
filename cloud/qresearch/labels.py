"""Realized development labels from explicitly supplied completed executions.

This is a round-trip label adapter, not a portfolio accounting engine or a fill
simulator. It never requests prices and is never passed to factor evaluators.
Initial support is long-only, equal-quantity, one-entry/one-exit round trips.
Non-cash corporate actions are rejected until an audited share-adjustment
adapter exists. Spread and slippage are already inside actual fill prices and
are not charged a second time here.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
from numbers import Integral, Real
from typing import Mapping

import numpy as np
import pandas as pd

from .contracts import DEVELOPMENT_END, NY, aware, digest


class LabelValidationError(ValueError):
    """A label specification or execution record is incomplete or inconsistent."""


@dataclass(frozen=True)
class LabelProtocol:
    canonical_json: str
    configuration_hash: str

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, Mapping):
            raise LabelValidationError("LabelProtocol must be an explicit JSON object")
        required = {"schema_version", "protocol_id", "target_kind", "price_basis", "currency",
                    "normalization", "corporate_action_policy", "denominator", "purpose"}
        if set(raw) - required - {"zero_cost_reason"} or required - set(raw):
            raise LabelValidationError("LabelProtocol fields are missing or unknown")
        data = dict(raw)
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise LabelValidationError("Unsupported label schema version")
        if not isinstance(data["protocol_id"], str) or not data["protocol_id"].strip():
            raise LabelValidationError("A protocol identity is required")
        if data["target_kind"] not in {"gross_return", "net_return"}:
            raise LabelValidationError("Explicit gross_return or net_return target required")
        expected = {"price_basis": "actual_fill", "normalization": "raw",
                    "corporate_action_policy": "reject_non_cash_actions", "denominator": "entry_notional"}
        if any(data[key] != value for key, value in expected.items()):
            raise LabelValidationError("Unsupported price, corporate-action or denominator convention")
        if (not isinstance(data["currency"], str) or len(data["currency"]) != 3 or
                not data["currency"].isalpha() or not data["currency"].isupper()):
            raise LabelValidationError("Explicit three-letter accounting currency required")
        if data["purpose"] not in {"engineering_fixture", "research"}:
            raise LabelValidationError("Explicit engineering_fixture or research purpose required")
        if "zero_cost_reason" in data and (not isinstance(data["zero_cost_reason"], str) or
                                           not data["zero_cost_reason"].strip()):
            raise LabelValidationError("A zero-cost declaration must contain a reason")
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return cls(encoded, digest(data))

    def to_dict(self):
        return json.loads(self.canonical_json)

    @property
    def target_kind(self):
        return self.to_dict()["target_kind"]


TIME_COLUMNS = ("formation_at", "entry_at", "exit_at", "entry_available_at", "exit_available_at",
                "costs_available_at", "corporate_actions_available_at")
NUMBER_COLUMNS = ("entry_quantity", "exit_quantity", "entry_price", "exit_price",
                  "entry_fee", "exit_fee", "other_costs", "cash_distributions")
EXECUTION_COLUMNS = ("trade_id", "sid", "side", "currency", "normalization", "execution_source",
                     "entry_execution_id", "exit_execution_id", "non_cash_corporate_action")

MAX_EXACT_INTEGER = 2 ** 53


def _exact_quantity(value, name):
    """Preserve supported original quantities for equality before narrowing.

    Fraction/as_integer_ratio are exact and do not use Decimal context rounding.
    A float64 range probe only rejects quantities that cannot participate in the
    supported arithmetic; the probe never supplies the equality representation.
    """
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise LabelValidationError("Quantity must be supported positive real numeric data: " + name)
    if isinstance(value, Integral) and abs(int(value)) > MAX_EXACT_INTEGER:
        raise LabelValidationError("Execution integer exceeds exact float64 precision: " + name)
    if isinstance(value, str):
        try:
            value = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise LabelValidationError("Quantity must be supported positive real numeric data: " + name) from exc
    if not isinstance(value, (Integral, float, np.floating, Decimal, Fraction)):
        raise LabelValidationError("Quantity type has no supported exact representation: " + name)
    try:
        probe = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise LabelValidationError("Quantity is outside supported finite float64 arithmetic: " + name) from exc
    if not np.isfinite(probe) or probe <= 0:
        raise LabelValidationError("Quantity is outside supported positive float64 arithmetic: " + name)
    if isinstance(value, Integral):
        return Fraction(int(value), 1)
    try:
        numerator, denominator = value.as_integer_ratio()
    except (AttributeError, ValueError, OverflowError) as exc:
        raise LabelValidationError("Quantity type has no supported exact representation: " + name) from exc
    if not isinstance(numerator, Integral) or not isinstance(denominator, Integral) or denominator <= 0:
        raise LabelValidationError("Quantity type returned an invalid exact representation: " + name)
    if isinstance(value, (Decimal, Fraction)) and denominator == 1 and abs(int(numerator)) > MAX_EXACT_INTEGER:
        raise LabelValidationError("Execution integer exceeds exact float64 precision: " + name)
    return Fraction(int(numerator), int(denominator))


def _float64_column(series, name):
    """Normalize before arithmetic, without silently rounding large integers.

    Checking original scalars also catches object columns mixing integers and
    floats before pandas could coerce the integers to an imprecise float dtype.
    Integral inputs outside binary64's consecutive exact-integer range are not
    supported. Explicit finite real floating inputs use binary64 arithmetic.
    """
    converted = []
    for value in series:
        if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
            raise LabelValidationError("Boolean/complex execution values are prohibited: " + name)
        if isinstance(value, Integral):
            if abs(int(value)) > MAX_EXACT_INTEGER:
                raise LabelValidationError("Execution integer exceeds exact float64 precision: " + name)
        elif isinstance(value, (str, Decimal)):
            try:
                decimal = Decimal(value)
            except (InvalidOperation, ValueError) as exc:
                raise LabelValidationError("Execution values must be real numeric data: " + name) from exc
            if not decimal.is_finite():
                raise LabelValidationError("Missing or infinite execution values are prohibited: " + name)
            if decimal == decimal.to_integral_value() and decimal.copy_abs() > MAX_EXACT_INTEGER:
                raise LabelValidationError("Execution integer exceeds exact float64 precision: " + name)
            value = decimal
        elif not isinstance(value, Real):
            raise LabelValidationError("Execution values must be real numeric data: " + name)
        try:
            numeric = float(value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise LabelValidationError("Execution value cannot be represented as float64: " + name) from exc
        if not np.isfinite(numeric):
            raise LabelValidationError("Missing or infinite execution values are prohibited: " + name)
        converted.append(numeric)
    return pd.Series(np.asarray(converted, dtype=np.float64), index=series.index)


def _finite_math(name, operation, *operands):
    """Check every float64 intermediate, not just the final return ratio."""
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            result = operation(*operands)
    except (FloatingPointError, OverflowError) as exc:
        raise LabelValidationError("Non-finite execution arithmetic: " + name) from exc
    if not np.isfinite(result).all():
        raise LabelValidationError("Non-finite execution arithmetic: " + name)
    return result


def build_execution_labels(trades, protocol):
    """Return gross/net realized return labels on entry notional, with timing.

    Every cost and distribution is an explicit total money amount in the common
    currency. Cash distributions include only realized cash for this round trip.
    A supplied label_available_at may delay maturity; it may not move it earlier
    than either fill, cost or corporate-action receipt. Missing or partial
    trades fail rather than being silently discarded. Numeric inputs are
    compared exactly in their original supported representation for quantities,
    then normalized to float64 arithmetic with exact-integer range checks;
    uint/signed input dtypes cannot change the economic result.
    """
    if not isinstance(protocol, LabelProtocol):
        raise LabelValidationError("Validate the LabelProtocol before constructing labels")
    if not isinstance(trades, pd.DataFrame):
        raise LabelValidationError("Execution records must be a DataFrame")
    if trades.empty:
        raise LabelValidationError("No completed executions are available; no label evidence can be produced")
    missing = set(TIME_COLUMNS + NUMBER_COLUMNS + EXECUTION_COLUMNS) - set(trades.columns)
    if missing:
        raise LabelValidationError("Missing explicit execution fields: " + str(sorted(missing)))
    data = trades.copy(deep=True).reset_index(drop=True)
    for column in TIME_COLUMNS + (("label_available_at",) if "label_available_at" in data else ()):
        values = []
        for value in data[column]:
            try:
                stamp = aware(value)
            except (ValueError, TypeError) as exc:
                raise LabelValidationError("Timezone-aware execution timestamps required: " + column) from exc
            if pd.isna(stamp) or stamp >= DEVELOPMENT_END:
                raise LabelValidationError("Missing/final-period execution data is prohibited in development labels")
            values.append(stamp)
        data[column] = pd.DatetimeIndex(values) if values else pd.DatetimeIndex([], tz=NY)
    if not ((data.formation_at <= data.entry_at) & (data.entry_at < data.exit_at) &
            (data.entry_at <= data.entry_available_at) & (data.exit_at <= data.exit_available_at) &
            (data.exit_at <= data.costs_available_at) & (data.exit_at <= data.corporate_actions_available_at)).all():
        raise LabelValidationError("Execution events and receipt timestamps are inconsistent")
    for entry_quantity, exit_quantity in zip(data.entry_quantity, data.exit_quantity):
        if (_exact_quantity(entry_quantity, "entry_quantity") !=
                _exact_quantity(exit_quantity, "exit_quantity")):
            raise LabelValidationError("Partial or share-changing executions require a separate accounting adapter")
    for column in NUMBER_COLUMNS:
        data[column] = _float64_column(data[column], column)
    if (data[list(NUMBER_COLUMNS)] < 0).any().any():
        raise LabelValidationError("Negative quantity, price, costs or distributions are unsupported")
    if (data[["entry_quantity", "exit_quantity", "entry_price", "exit_price"]] <= 0).any().any():
        raise LabelValidationError("Completed round trips require positive prices and quantities")
    if not data.entry_quantity.eq(data.exit_quantity).all():
        raise LabelValidationError("Partial or share-changing executions require a separate accounting adapter")
    spec = protocol.to_dict()
    if not data.side.eq("long").all():
        raise LabelValidationError("Only long completed round-trip labels are enabled")
    if not data.currency.eq(spec["currency"]).all() or not data.normalization.eq(spec["normalization"]).all():
        raise LabelValidationError("Currency or price normalization differs from the frozen protocol")
    for column in ("trade_id", "sid", "execution_source", "entry_execution_id", "exit_execution_id"):
        if data[column].map(lambda value: not isinstance(value, str) or not value.strip()).any():
            raise LabelValidationError("Execution identities/source must be explicit nonempty strings")
    if (data.trade_id.duplicated().any() or data.duplicated(["formation_at", "sid"]).any() or
            pd.concat([data.entry_execution_id, data.exit_execution_id]).duplicated().any()):
        raise LabelValidationError("A fill or formation/SID cannot be counted twice")
    if not data.non_cash_corporate_action.map(lambda x: isinstance(x, (bool, np.bool_)) and not x).all():
        raise LabelValidationError("Unresolved non-cash corporate actions are prohibited")
    if spec["purpose"] == "research" and data.execution_source.str.lower().str.contains("synthetic|fixture", regex=True).any():
        raise LabelValidationError("Synthetic executions cannot certify research labels")
    numbers = {name: data[name].to_numpy(dtype=np.float64, copy=False) for name in NUMBER_COLUMNS}
    roundtrip_fees = _finite_math("entry plus exit fees", np.add, numbers["entry_fee"], numbers["exit_fee"])
    all_costs = _finite_math("total costs", np.add, roundtrip_fees, numbers["other_costs"])
    if np.any(all_costs == 0) and not spec.get("zero_cost_reason"):
        raise LabelValidationError("Zero costs require an explicit frozen reason; no implicit zero-cost labels")
    maturity = data[["entry_available_at", "exit_available_at", "costs_available_at",
                     "corporate_actions_available_at"]].max(axis=1)
    if "label_available_at" in data:
        if (data.label_available_at < maturity).any():
            raise LabelValidationError("Supplied label availability precedes actual outcome maturity")
        maturity = data.label_available_at
    output = data[["trade_id", "sid", "formation_at", "entry_at", "exit_at", "execution_source",
                   "entry_execution_id", "exit_execution_id"]].copy()
    output["label_available_at"] = maturity
    notional = _finite_math("entry notional multiplication", np.multiply, numbers["entry_quantity"], numbers["entry_price"])
    if np.any(notional <= 0):
        raise LabelValidationError("Entry notional must remain positive after float64 multiplication")
    exit_proceeds = _finite_math("exit proceeds multiplication", np.multiply, numbers["exit_quantity"], numbers["exit_price"])
    price_pnl = _finite_math("exit proceeds minus entry notional", np.subtract, exit_proceeds, notional)
    gross_pnl = _finite_math("price PnL plus distributions", np.add, price_pnl, numbers["cash_distributions"])
    net_pnl = _finite_math("gross PnL minus total costs", np.subtract, gross_pnl, all_costs)
    output["gross_return"] = _finite_math("gross return division", np.divide, gross_pnl, notional)
    output["net_return"] = _finite_math("net return division", np.divide, net_pnl, notional)
    output["label"] = output[spec["target_kind"]]
    output["target_kind"] = spec["target_kind"]
    output["label_protocol_hash"] = protocol.configuration_hash
    output["purpose"] = spec["purpose"]
    output.attrs["label_protocol"] = spec
    return output
