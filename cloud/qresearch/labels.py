"""Realized development labels from explicitly supplied completed executions.

This is a round-trip label adapter, not a portfolio accounting engine or a fill
simulator. It never requests prices and is never passed to factor evaluators.
Initial support is long-only, equal-quantity, one-entry/one-exit round trips.
Non-cash corporate actions are rejected until an audited share-adjustment
adapter exists. Spread and slippage are already inside actual fill prices and
are not charged a second time here.
"""
from dataclasses import dataclass
import json
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


def build_execution_labels(trades, protocol):
    """Return gross/net realized return labels on entry notional, with timing.

    Every cost and distribution is an explicit total money amount in the common
    currency. Cash distributions include only realized cash for this round trip.
    A supplied label_available_at may delay maturity; it may not move it earlier
    than either fill, cost or corporate-action receipt. Missing or partial
    trades fail rather than being silently discarded.
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
    for column in NUMBER_COLUMNS:
        if data[column].map(lambda value: isinstance(value, (bool, np.bool_))).any():
            raise LabelValidationError("Boolean monetary/quantity values are prohibited")
        try:
            data[column] = pd.to_numeric(data[column], errors="raise")
        except (ValueError, TypeError) as exc:
            raise LabelValidationError("Execution quantities, prices and costs must be numeric") from exc
        if np.iscomplexobj(data[column].to_numpy()) or not np.isfinite(data[column].to_numpy(dtype=float)).all():
            raise LabelValidationError("Missing or infinite execution values are prohibited")
    if (data[list(NUMBER_COLUMNS)] < 0).any().any():
        raise LabelValidationError("Negative quantity, price, costs or distributions are unsupported")
    if (data[["entry_quantity", "exit_quantity", "entry_price", "exit_price"]] <= 0).any().any():
        raise LabelValidationError("Completed round trips require positive prices and quantities")
    if not np.isclose(data.entry_quantity, data.exit_quantity, rtol=0, atol=1e-12).all():
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
    all_costs = data.entry_fee + data.exit_fee + data.other_costs
    if all_costs.eq(0).any() and not spec.get("zero_cost_reason"):
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
    with np.errstate(over="ignore", invalid="ignore"):
        notional = data.entry_quantity * data.entry_price
        price_pnl = data.exit_quantity * data.exit_price - notional
        output["gross_return"] = (price_pnl + data.cash_distributions) / notional
        output["net_return"] = (price_pnl + data.cash_distributions - all_costs) / notional
    if not np.isfinite(notional.to_numpy()).all() or not np.isfinite(output[["gross_return", "net_return"]].to_numpy()).all():
        raise LabelValidationError("Execution arithmetic overflowed; no finite label can be produced")
    output["label"] = output[spec["target_kind"]]
    output["target_kind"] = spec["target_kind"]
    output["label_protocol_hash"] = protocol.configuration_hash
    output["purpose"] = spec["purpose"]
    output.attrs["label_protocol"] = spec
    return output
