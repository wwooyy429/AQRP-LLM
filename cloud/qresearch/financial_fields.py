"""Closed engineering projection of one native as-reported financial period.

The fixed native presence method is the only callable invoked here. A native
period property can return zero for a missing period, so the property alone,
default-period has_value and default value cannot establish 12M presence.
This projection does not authenticate currency, filing vintage or availability.
"""
from collections.abc import Mapping
import math
from numbers import Integral, Real


FINANCIAL_FIELD_PATH = "financial_statements.income_statement.total_revenue_as_reported.twelve_months"
_ERRORS = {
    "unsupported_field": "Financial projection requires its exact frozen field definition",
    "native_property_failed": "Native source property access failed",
    "native_callable": "Financial source properties cannot invoke arbitrary methods",
    "period_presence_unavailable": "Native specified-period presence check is required",
    "invalid_period_presence": "Native specified-period presence must be boolean",
    "invalid_numeric_value": "Native specified-period financial value must be finite numeric or missing",
}


class FinancialFieldError(ValueError):
    """Owned static diagnostics; native objects and values never enter errors."""

    def __init__(self, reason):
        if type(reason) is not str or reason not in _ERRORS:
            raise ValueError("Unknown financial projection diagnostic") from None
        self.reason = reason
        super().__init__(_ERRORS[reason])


def financial_field_definition():
    """Return a fresh closed catalog definition, without factor permission."""
    return {"kind": "number", "role": "as_reported_financial_value",
            "unit": "reported_currency", "period_accessor": "twelve_months"}


def _member(value, name):
    if value is None:
        return None
    if callable(value):
        raise FinancialFieldError("native_callable") from None
    try:
        return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
    except Exception:
        raise FinancialFieldError("native_property_failed") from None


def _number(value):
    if value is None:
        return None
    try:
        if isinstance(value, bool) or not isinstance(value, (Integral, Real)):
            raise ValueError
        if math.isnan(value):
            return None
        if math.isfinite(value):
            return int(value) if isinstance(value, Integral) else float(value)
    except Exception:
        # Numeric subclasses can throw arbitrary native exceptions, including
        # an apparent subclass of our error. Reconstruct an owned static one.
        raise FinancialFieldError("invalid_numeric_value") from None
    raise FinancialFieldError("invalid_numeric_value") from None


def validate_financial_field(path, definition):
    """Validate the one explicit projection before requesting native history."""
    try:
        valid = (type(path) is str and path == FINANCIAL_FIELD_PATH
            and type(definition) is dict
            and set(definition) == {"kind", "role", "unit", "period_accessor"}
            and all(type(value) is str for value in definition.values())
            and definition == financial_field_definition())
    except Exception:
        raise FinancialFieldError("unsupported_field") from None
    if not valid:
        raise FinancialFieldError("unsupported_field") from None


def _project_financial_field(native, path, definition):
    """Project only reported revenue's explicitly present native 12M value.

    Missing parents or a false native 12M presence result remain None. Missing
    API capability, invalid types and throwing properties fail closed. Only the
    literal documented has_period_value('12M') method is permitted, never an
    arbitrary method selected by a field string or caller-supplied accessor.
    """
    validate_financial_field(path, definition)
    field = native
    for name in ("financial_statements", "income_statement", "total_revenue_as_reported"):
        field = _member(field, name)
        if field is None:
            return None
    # A source mapping is not an SDK period object. It cannot install an
    # arbitrary function as an apparently native presence method.
    if callable(field):
        raise FinancialFieldError("native_callable") from None
    try:
        is_mapping = isinstance(field, Mapping)
    except Exception:
        raise FinancialFieldError("native_property_failed") from None
    if is_mapping:
        raise FinancialFieldError("period_presence_unavailable") from None
    presence = _member(field, "has_period_value")
    if not callable(presence):
        raise FinancialFieldError("period_presence_unavailable") from None
    try:
        present = presence("12M")
    except Exception:
        raise FinancialFieldError("native_property_failed") from None
    if type(present) is not bool:
        raise FinancialFieldError("invalid_period_presence") from None
    if not present:
        return None
    value = _member(field, "twelve_months")
    if callable(value):
        raise FinancialFieldError("native_callable") from None
    return _number(value)


def extract_financial_field(native, path, definition):
    """Return the fixed 12M projection, with a closed public error boundary."""
    try:
        return _project_financial_field(native, path, definition)
    except Exception as error:
        # Even predicates and synthetic numeric subclasses can throw private
        # native exceptions. Never render an exception or trust a subclass's
        # apparent owned type, message or mutable diagnostic fields.
        if type(error) is FinancialFieldError:
            try:
                reason = object.__getattribute__(error, "reason")
            except Exception:
                reason = None
            if type(reason) is str and reason in _ERRORS:
                raise FinancialFieldError(reason) from None
        raise FinancialFieldError("native_property_failed") from None
