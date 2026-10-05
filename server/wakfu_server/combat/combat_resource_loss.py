"""Verified eVZ AP/MP loss calculation and eVI collision definition.

UP.bt is stochastic rounding, not ceil/round. Applying positive loss also
executes eWu state5227; callers must supply that executor, never omit it.
This module is independent of factory registration and transaction ownership.
"""
from dataclasses import dataclass, replace
import math
import struct
from .combat_parameters import _float32
from .combat_effects import _integer, _varint


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def stochastic_native_round(value, random_fraction=None):
    """UP.bt(float): floor + GT.l(fraction); Java saturating double->int."""
    value = _float32(value)
    if not math.isfinite(value):
        return 0 if math.isnan(value) else (2147483647 if value > 0 else -2147483648)
    result = math.floor(value)
    fraction = value - result
    if fraction:
        if not callable(random_fraction):
            raise ValueError("Native eVZ fractional loss requires transactional RNG")
        draw = random_fraction()
        if (
            type(draw) not in (int, float)
            or not math.isfinite(draw)
            or not 0 <= draw < 1
        ):
            raise ValueError("Invalid native GT stochastic draw")
        result += draw < fraction
    return min(2147483647, max(-2147483648, result))


@dataclass(frozen=True)
class ResourceLossPlan:
    requested: int
    calculated: int
    actual: int
    before: int
    after: int
    event_override: int | None
    calculation_status: int
    # eVZ.d executes this on the TARGET after applying actual loss.
    state_5227_parameters: tuple | None


def resolve_resource_loss(
    *,
    stat_id,
    requested,
    current,
    minimum,
    maximum,
    caster_willpower,
    target_willpower,
    same_actor,
    ignores_willpower=False,
    frozen=False,
    suppresses_loss_state=False,
    random_fraction=None,
    value_context=None
):
    """eVZ.C -> eWR.d, explicit native characteristic presence already resolved.

    Snapshot absence is not zero. Caller may pass0 only if the native actor
    characteristic is absent (PV.a(shF)=false) or its actual value is0.
    """
    if stat_id not in (2, 3) or any(
        type(v) is not int or not -2147483648 <= v <= 2147483647
        for v in (
            requested,
            current,
            minimum,
            maximum,
            caster_willpower,
            target_willpower,
        )
    ):
        raise ValueError("Missing complete native AP/MP loss snapshot")
    if requested < 0:
        raise ValueError(
            "Native triggering resource loss must be resolved before calculation"
        )
    if any(
        type(v) is not bool
        for v in (same_actor, ignores_willpower, frozen, suppresses_loss_state)
    ):
        raise ValueError("Missing native loss flags or mutability")
    if not minimum <= current <= maximum:
        raise ValueError("Incoherent native resource bounds")
    caster = target = 0
    if not same_actor and not ignores_willpower:
        caster, target = caster_willpower, target_willpower
    factor = _float32(
        _float32(1 + _float32(_float32(caster) / 100))
        - _float32(_float32(target) / 100)
    )
    raw = _float32(_float32(_float32(requested) * _float32(0.5)) * factor)
    calculated = min(requested, max(0, stochastic_native_round(raw, random_fraction)))
    override = (58 if stat_id == 2 else 75) if calculated != requested else None
    calculation_status = 3 if calculated == 0 else 0
    # eZR.n applies SQ after eVZ.C. C's event/status decisions are preserved;
    # eWR.d consumes the replaced value and records its actual resource delta.
    from .combat_value_transfer import apply_context_value

    calculated = apply_context_value(calculated, value_context)
    after = (
        current if frozen else max(minimum, min(maximum, _i32(current - calculated)))
    )
    actual = current - after
    state = (
        None
        if actual <= 0 or suppresses_loss_state
        else (5227, 0, _i32(actual * 10), 0, 100, 0)
    )
    return ResourceLossPlan(
        requested,
        calculated,
        actual,
        current,
        after,
        override,
        calculation_status,
        state,
    )


def rebase_resource_loss_application(
    plan, *, calculated, current, minimum, maximum, frozen, suppresses_loss_state
):
    """eWR.d consumes live aSg after L2 without repeating eVZ.C/UP.bt.

    C's event override/status remain unchanged. PA is read at application time;
    native eVZ.d then creates state5227 from the actual resulting loss.
    """
    if (
        not isinstance(plan, ResourceLossPlan)
        or any(
            type(v) is not int or not -(2**31) <= v < 2**31
            for v in (calculated, current, minimum, maximum)
        )
        or type(frozen) is not bool
        or type(suppresses_loss_state) is not bool
        or not minimum <= current <= maximum
    ):
        raise ValueError("Missing live native loss application snapshot")
    after = (
        current if frozen else max(minimum, min(maximum, _i32(current - calculated)))
    )
    actual = current - after
    return replace(
        plan,
        calculated=calculated,
        before=current,
        after=after,
        actual=actual,
        state_5227_parameters=None
        if actual <= 0 or suppresses_loss_state
        else (5227, 0, _i32(actual * 10), 0, 100, 0),
    )


def collision_ap_packet(
    fight_id, action_id, *, uid, caster_id, target_id, amount, base_uid=0, sequence=-1
):
    """12613/eVZ55 using genuine synthetic eVI(-13), originValue rCB=0."""
    if (
        type(uid) is not int
        or not 0 < uid < (1 << 63)
        or type(base_uid) is not int
        or not 0 <= base_uid < (1 << 63)
        or type(amount) is not int
        or not 0 <= amount <= 1
    ):
        raise ValueError("Invalid owned synthetic collision AP effect")
    if any(
        type(v) is not int or v == 0 or not -(1 << 63) <= v < (1 << 63)
        for v in (caster_id, target_id)
    ):
        raise ValueError("Invalid native collision actors")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, base_uid),
            (3, -13),
            (4, amount),
            (6, caster_id),
            (7, target_id),
        )
    )
    additional = _integer(12, 2) + _integer(25, 0)
    payload += b"\x42" + _varint(len(additional)) + additional
    return (
        12613,
        struct.pack(">iiiBih", fight_id, action_id, sequence, 0, 55, len(payload))
        + payload,
    )


def resource_loss_event_ids(*, stat_id, phase, plan, extra_event_ids=()):
    """Native eWR.bbx/eVZ.C/d sets for Qe L1..L4, including ox2254 if supplied.

    AP/MP native fZu are77/79; calculation modification adds58/75. Actual zero
    removes the characteristic event only after d. IDs are not effect classes.
    """
    if (
        stat_id not in (2, 3)
        or phase not in (1, 2, 3, 4)
        or not isinstance(plan, ResourceLossPlan)
    ):
        raise ValueError("Missing verified native resource-loss lifecycle")
    if not isinstance(extra_event_ids, tuple) or any(
        type(v) is not int or v < 0 for v in extra_event_ids
    ):
        raise ValueError("Unknown native extra loss event IDs")
    characteristic = 77 if stat_id == 2 else 79
    events = {0, characteristic, *extra_event_ids}
    if phase >= 2 and plan.event_override is not None:
        events.add(plan.event_override)
    if phase >= 3 and plan.actual <= 0:
        events.discard(characteristic)
    return tuple(sorted(events))


def apply_resource_loss(
    fight,
    *,
    caster_id,
    target_id,
    stat_id,
    plan,
    secondary_state,
    after_apply,
    native_guards_verified,
    executable
):
    """Apply on a private transaction preview with mandatory native callbacks.

    after_apply handles eVZ lifecycle/events. State executor receives exact
    parameters, loss target as both caster+target and the plan as triggering source.
    Caller owns wire and retained-effect UID; no persistence is guessed here.
    """
    if native_guards_verified is not True or type(executable) is not bool:
        raise ValueError("Unverified native eVZ bbH/fMy application guards")
    if not executable:
        return False
    if not isinstance(plan, ResourceLossPlan) or not callable(after_apply):
        raise ValueError("Verified loss plan and native lifecycle executor required")
    if plan.state_5227_parameters is not None and not callable(secondary_state):
        raise ValueError("Positive eVZ loss requires native state5227 executor")
    target = fight.actors[target_id]
    name = {2: "ap", 3: "mp"}.get(stat_id)
    if name is None or getattr(target, name) != plan.before:
        raise ValueError("Stale native resource-loss plan")
    if (
        not isinstance(target.effect_stats, dict)
        or target.effect_stats.get(stat_id) != plan.before
    ):
        raise ValueError("Missing coherent native resource-loss characteristic")
    setattr(target, name, plan.after)
    target.effect_stats[stat_id] = plan.after
    if plan.state_5227_parameters is not None:
        secondary_state(target_id, target_id, plan.state_5227_parameters, plan)
    after_apply(caster_id, target_id, stat_id, plan)
    return True


def remove_resource_loss(*, current, minimum, maximum, actual, frozen):
    """eWR.fNM -> PA.nG(actual applied loss), never the preclamp request."""
    if (
        any(
            type(v) is not int or not -2147483648 <= v <= 2147483647
            for v in (current, minimum, maximum, actual)
        )
        or type(frozen) is not bool
        or not minimum <= current <= maximum
    ):
        raise ValueError("Invalid owned native resource-loss restoration")
    return current if frozen else max(minimum, min(maximum, _i32(current + actual)))
