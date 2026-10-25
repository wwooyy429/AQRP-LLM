"""PIT liquidity ranking, consuming complete historical all-market snapshots."""
import numpy as np
import pandas as pd
from .contracts import aware, DEVELOPMENT_END

INCLUDED = {"common_stock", "adr", "reit_common"}


def select_liquid_universe(rows, formation_at, expected_sessions, size=200, lookback=20):
    """No current-symbol input or financial-coverage filter. Returns SIDs only.

    rows: sid/session/available_at/dollar_volume/instrument_type/listed.
    expected_sessions must come from the LEAN exchange calendar, include every
    expected session, and end at the last completed session before formation.
    Caller must certify full all-market and classification coverage separately.
    """
    required = {"sid", "session", "available_at", "dollar_volume", "instrument_type", "listed"}
    if not required <= set(rows.columns):
        raise ValueError("Historical liquidity/classification columns are missing")
    if type(size) is not int or type(lookback) is not int or size < 1 or lookback < 1:
        raise ValueError("Positive universe size and lookback required")
    sessions = pd.DatetimeIndex([aware(x) for x in expected_sessions])
    formation = aware(formation_at)
    if formation >= DEVELOPMENT_END:
        raise ValueError("Final-test universe is isolated from research")
    if len(sessions) != lookback or not sessions.is_unique or not sessions.is_monotonic_increasing or sessions[-1] >= formation:
        raise ValueError("Exact complete trailing exchange-session list required")
    data = rows.copy()
    data["session"] = [aware(x) for x in data.session]
    data["available_at"] = [aware(x) for x in data.available_at]
    if (data.session > data.available_at).any():
        raise ValueError("Liquidity cannot be available before its session completes")
    data = data[data.session.isin(sessions) & (data.available_at <= formation)]
    if data.duplicated(["sid", "session"]).any():
        raise ValueError("Resolve snapshot vintages before universe selection")
    ranked = []
    for sid, group in data.groupby("sid", sort=True):
        if len(group) != lookback or set(group.session) != set(sessions):
            continue
        latest = group.sort_values("session").iloc[-1]
        values = pd.to_numeric(group.dollar_volume, errors="raise").to_numpy()
        if not np.isfinite(values).all() or (values < 0).any():
            continue
        if (latest.instrument_type in INCLUDED and
                isinstance(latest.listed, (bool, np.bool_)) and bool(latest.listed)):
            ranked.append((str(sid), float(values.mean())))
    ranked.sort(key=lambda pair: (-pair[1], pair[0]))
    if len(ranked) < size:
        raise ValueError("Fewer than required eligible names; no silent smaller universe")
    return tuple(sid for sid, _ in ranked[:size])
