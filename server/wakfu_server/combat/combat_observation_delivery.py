"""Native aTR registration guard and evaluated-runner delivery selection.

Inputs are facts from the original runner/PK and resolved manager, never
inferred from effect family or visible characteristic changes.
"""
import struct


def observation_registers(*, persistent, delayed, has_event_masks, manager_present):
    values = (persistent, delayed, has_event_masks, manager_present)
    if any(type(value) is not bool for value in values):
        raise ValueError("Explicit native Ty/bbW/aZN/manager facts required")
    return manager_present and (persistent or delayed) and (has_event_masks or delayed)


def retained_delivery_opcode(*, persistent, delayed, has_event_masks, manager_present):
    """Select delivery for an already evaluated, authoritatively retained UID.

    cvX/eIK=false is required when aTR would discard a persistent runner.
    Delay subscriptions retain cvY. An unresolved manager cannot be repaired
    by changing the packet type and must fail before committing delivery.
    """
    registers = observation_registers(
        persistent=persistent,
        delayed=delayed,
        has_event_masks=has_event_masks,
        manager_present=manager_present,
    )
    if not manager_present:
        raise ValueError("Missing native retained-effect manager")
    if registers:
        return 13497
    if persistent:
        return 12613
    raise ValueError("Runner has no proven native retention contract")


def choose_delivery(
    *, native_ty, subscribed, native_delayed, manager_id, observation_owner, full_owner
):
    """Check the actual Qf manager for each original action before selection."""
    for owner in (manager_id, observation_owner, full_owner):
        if type(owner) is not int or owner == 0 or not -(1 << 63) <= owner < (1 << 63):
            raise ValueError("Explicit native effect manager identities required")
    registers = observation_registers(
        persistent=native_ty,
        delayed=native_delayed,
        has_event_masks=subscribed,
        manager_present=True,
    )
    if registers and observation_owner == manager_id:
        return 13497
    if native_ty and full_owner == manager_id:
        return 12613
    raise ValueError("Native action cannot retain runner on its authoritative manager")


def evaluated_application_from_observation(body, *, execute=False):
    """Convert cvY to cvX with an explicit decoded-runner execution flag."""
    if type(execute) is not bool:
        raise ValueError("Explicit native decoded-runner execution flag required")
    if not isinstance(body, bytes) or len(body) < 18:
        raise ValueError("Incomplete native observation packet")
    size = struct.unpack_from(">h", body, 16)[0]
    if size <= 0 or len(body) != 18 + size:
        raise ValueError("Native observation protobuf length mismatch")
    return body[:12] + bytes((int(execute),)) + body[12:]
