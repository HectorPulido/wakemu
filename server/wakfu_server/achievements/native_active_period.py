"""Native eIj.a active-period projection from an authenticated acceptance clock.

The caller owns the independent active flag and acceptance timestamp. Completion
is intentionally absent: native Running adds that separate condition. This
helper neither accepts missions nor substitutes definition dates for receipts.
"""


def _truncated_division(value, divisor):
    """Java integer division truncates toward zero, including before the anchor."""
    return value // divisor if value >= 0 else -((-value) // divisor)


def period_boundary_ms(definition, *, now_ms):
    """Return native TP.a's boundary, or None when no reset anchor is configured.

    aZx loads cjT with TP.fl (epoch milliseconds) and cjU with TS.fm (seconds).
    TP uses UTC calendar fields at second precision. Its exact-anchor-second
    branch selects the previous boundary; preserve that native edge case.
    Invalid anchored definitions raise ValueError rather than losing the period.
    """
    if not isinstance(definition, dict) or type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid native active-period input")
    anchor = definition.get("cjT")
    if type(anchor) is not int or anchor < 0:
        raise ValueError("Invalid native reset anchor")
    if anchor == 0:
        return None
    period = definition.get("cjU")
    if type(period) is not int or period <= 0:
        raise ValueError("Invalid native reset period")
    anchor_seconds = anchor // 1000
    delta = now_ms // 1000 - anchor_seconds
    ordinal = _truncated_division(delta, period) - (1 if delta <= 0 else 0)
    return (anchor_seconds + ordinal * period) * 1000


def active_for_period(definition, *, active, accepted_at_ms, now_ms):
    """Fail closed when period or authentic acceptance-clock authority is missing.

    The caller must pass a persisted acceptance clock, never a completion date,
    inventory timestamp, native anchor, wall-clock fallback or client input.
    A False result does not itself mutate or reset any durable mission state.
    """
    if type(active) is not bool or not active:
        return False
    try:
        boundary = period_boundary_ms(definition, now_ms=now_ms)
    except ValueError:
        return False
    if boundary is None:
        return True
    if type(accepted_at_ms) is not int or accepted_at_ms < 0:
        return False
    return boundary <= (accepted_at_ms // 1000) * 1000
