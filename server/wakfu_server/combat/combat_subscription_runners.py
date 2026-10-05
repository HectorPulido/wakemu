"""Audited fresh Qe.d deferred runners; calculation waits for native events."""
from .combat_effects import _integer, _varint
from .combat_stat_effects import owned_effect_payload

GROUP_SUBSCRIPTION_FAMILIES = (
    330,
    341,
    345,
    352,
    844,
    865,
    910,
    912,
    913,
    949,
    999,
    1020,
    1047,
    1076,
    1103,
)
DEFERRED_RUNNERS = {400: "eXE", 421: "eXe", 1001: "eWZ", 1093: "eZJ"}
SUBSCRIPTION_FAMILIES = GROUP_SUBSCRIPTION_FAMILIES + tuple(DEFERRED_RUNNERS)


def deferred_payload(
    *,
    family,
    uid,
    base_uid,
    generic_effect,
    caster_id,
    target_id,
    cell,
    timing_payload,
    container_type,
    container_id,
    context_payload=None
):
    """Fresh eZR is value0/status-1/unexecuted; subclass C() has not run."""
    if family not in DEFERRED_RUNNERS:
        raise ValueError("Unaudited deferred native runner")
    payload = owned_effect_payload(
        uid=uid,
        base_uid=base_uid,
        generic_effect=generic_effect,
        caster_id=caster_id,
        target_id=target_id,
        value=0,
        timing_payload=timing_payload,
        execution_status=-1,
        executed=False,
        inherit_container=False,  # explicit PL below, independent of ambient scope
    )

    def blob(field, data):
        return _varint(field << 3 | 2) + _varint(len(data)) + data

    payload += blob(5, b"".join(_integer(k, v) for k, v in enumerate(cell, 1)))
    if family == 1001:
        # eWZ constructor pJt=-1, ddL=0; b(iP) writes em/ek (12/10).
        payload += blob(8, _integer(12, -1) + _integer(10, 0))
    if (container_type is None) != (container_id is None):
        raise ValueError("Missing paired native deferred container")
    if container_type is not None:
        payload += _integer(9, container_type) + _integer(10, container_id)
    if context_payload is not None:
        from .combat_running_context import running_context_payload

        payload += running_context_payload(context_payload=context_payload)
    return payload
