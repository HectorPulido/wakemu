"""Native fcb.fVh/ayT/fcd ordering for explicitly captured PV iterators.

This helper does not derive a native iterator from Python roster order. The
producer must supply the actual fighter, Qs.bdm and fbX.fUn sequence order.
Membership is checked on each next(), as fcd.v does, rather than cached before
reactions. Duplicate PV appearances across segments are preserved.
"""


def native_global_event_iterator(
    *,
    fighter_order,
    area_order,
    extra_order,
    eligible,
    caster_only=False,
    caster_id=None
):
    """Yield captured native candidates with live fcd.v membership filtering.

    eligible(identity) represents the native OR: eligible eGj status, current
    Qs.do(Sn), or current fbX.rf(Sn). Null Qf is a delivery concern, not an
    iterator exclusion. fbZ.rRo with an actual PV caster bypasses fcd entirely.
    """
    if type(caster_only) is not bool or not callable(eligible):
        raise ValueError("Explicit native iterator mode and membership required")
    if caster_only:
        if type(caster_id) is not int:
            raise ValueError("Actual native PV caster required")
        yield caster_id
        return
    for order in (fighter_order, area_order, extra_order):
        if not isinstance(order, tuple) or any(
            type(identity) is not int for identity in order
        ):
            raise ValueError("Captured native PV segment order required")
    for order in (fighter_order, area_order, extra_order):
        for identity in order:
            accepted = eligible(identity)
            if type(accepted) is not bool:
                raise ValueError("Actual native fcd membership result required")
            if accepted:
                yield identity
