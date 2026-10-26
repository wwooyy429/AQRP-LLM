"""Causal feature views; price windows preserve missing exchange sessions."""
import pandas as pd
from .contracts import PITWindow, aware, canonical_membership, formation_index, validate_records


def causal_window(records, decisions, sids, policies, expected_events, max_age=None, membership=None):
    """Materialize each historical row using THAT row's own information set.

    policies[field] is 'exact_session' or 'latest_available'. expected_events is
    a timezone-aware Series indexed by decisions from a real exchange calendar.
    Fundamentals require explicit max_age[field] Timedelta (no infinite carry).
    Records must contain actual vintage availability; this function cannot
    certify a vendor's historical release timestamps or repair their absence.
    """
    data = validate_records(records)
    times = formation_index(decisions)
    if not len(times) or not times.is_unique or not times.is_monotonic_increasing:
        raise ValueError("Sorted unique formation times required")
    expected = {aware(k): aware(v) for k, v in expected_events.items()}
    if set(times) != set(expected):
        raise ValueError("Every formation must map to its actual completed exchange session")
    if membership is not None:
        membership = canonical_membership(membership)
        if (not membership.index.equals(times) or not membership.columns.is_unique
                or set(membership.columns) != set(sids)):
            raise ValueError("Historical membership must cover every formation and union SID exactly")
        if membership.isna().any().any() or any(str(kind) != "bool" for kind in membership.dtypes):
            raise ValueError("Historical membership must contain explicit booleans")
    matrices = {}
    for field, policy in policies.items():
        if policy not in ("exact_session", "latest_available"):
            raise ValueError("Unknown availability policy")
        if policy == "latest_available" and (max_age is None or field not in max_age):
            raise ValueError("Financial carry requires a registered maximum age")
        result = pd.DataFrame(float("nan"), index=times, columns=sids)
        observations = data[(data.field == field) & data.sid.isin(sids)]
        for formation in times:
            event = expected[formation]
            if event >= formation:
                raise ValueError("Expected session must have completed before decision")
            visible = observations[(observations.available_time <= formation) & (observations.event_time <= event)]
            if policy == "exact_session":
                visible = visible[visible.event_time == event]
            else:
                age = pd.Timedelta(max_age[field])
                if age <= pd.Timedelta(0):
                    raise ValueError("Maximum age must be positive")
                visible = visible[visible.event_time >= formation - age]
            # Latest economic period, then latest then-known revision. Old-period
            # restatement received later must not replace a newer-period report.
            visible = visible.sort_values(["event_time", "available_time", "revision"]).drop_duplicates("sid", keep="last")
            for row in visible.itertuples():
                result.at[formation, row.sid] = row.value
        matrices[field] = result
    return PITWindow(times[-1].to_pydatetime(), matrices, tuple(sids), universe_membership=membership)
