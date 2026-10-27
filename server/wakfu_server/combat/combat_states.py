"""Native state304 codec and audited Iop3425/3442 application planning.

8913's application metadata is known, but its turn expiry and armor triggers
are not executed here. Unknown state behavior is never silently discarded.
"""
import struct
from .combat_effects import _integer, _varint
from .combat_state_application import ExistingState, plan_state_application


def state_packet(
    fight_id, action_id, *, uid, generic_effect, caster_id, target_id, state_id, level
):
    if (
        type(level) is not int
        or not -32768 <= level <= 32767
        or type(state_id) is not int
        or not 0 < state_id <= 32767
        or not 0 < uid < (1 << 63)
        or not 0 < generic_effect < (1 << 31)
    ):
        raise ValueError("Invalid native state identifiers or level")
    if any(
        type(v) is not int or not -(1 << 63) <= v < (1 << 63) or v == 0
        for v in (caster_id, target_id)
    ):
        raise ValueError("Missing owned state actor")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, 0),
            (3, generic_effect),
            (4, 0),
            (6, caster_id),
            (7, target_id),
        )
    )
    additional = _integer(11, state_id) + _integer(14, level)
    payload += _varint((8 << 3) | 2) + _varint(len(additional)) + additional
    return (
        struct.pack(">iiiBih", fight_id, action_id, -1, 0, 304, len(payload)) + payload
    )


def plan_3425(existing, amount):
    """Instant3425 -> native159161/159411/159412 -> additive3442.

    3425 has0 turns;3442 has-1 turns and only NullEffect400/150327.
    eWu.fMY adds levels while old3442<400; fyW.cu clamps the resulting level
    to400. At400 its nonreplace branch suppresses the application. No invented
    damage bonus is attached.
    """
    if existing is None:
        raise ValueError("Authoritative caster state collection required")
    if set(existing) - {3442}:
        raise ValueError("Unknown caster state modifies Iop evaluation")
    if type(amount) is not int or not 0 < amount <= 200:
        raise ValueError("Unsupported3425 amount")
    old = existing.get(3442, 0)
    if type(old) is not int or not 0 <= old <= 400:
        raise ValueError("Invalid3442 state level")
    # The generic planner also handles saturated suppression and short
    # arithmetic. guN is immaterial for this additive state.
    instances = (
        ()
        if 3442 not in existing
        else (ExistingState(old, 400, True, False, False, False),)
    )
    plan = plan_state_application(amount, 400, instances)
    return {3442: plan.level if plan.accepted else old}


def state8913_metadata():
    return dict(
        state_id=8913,
        level=30,
        duration_turns=1,
        replace_if_new_level_at_least_old=True,
        trigger_group=408737,
        requires_armor_at_least=1,
        clock="caster_start",
        execution_verified=False,
        pending=["armor_trigger_effects1020_1011"],
    )


def plan_8913(*, caster_id, caster_turn, target_armor):
    """Bare target branch. eZk.fRc uses caster;Tt.biN=false uses start clock.

    fyW8913 duration1 + SU/TC schedules current caster round+1. Both trigger
    branches require ARMOR>=1 and are false while authoritative armor is zero.
    Caller must invoke expire_8913 at each caster start before later actions.
    """
    if target_armor != 0:
        raise ValueError("8913 armor triggers are not yet implemented")
    if (
        type(caster_id) is not int
        or caster_id <= 0
        or type(caster_turn) is not int
        or caster_turn < 1
    ):
        raise ValueError("Invalid8913 caster clock")
    return dict(
        state_id=8913,
        level=30,
        caster_id=caster_id,
        expires_at_caster_start=caster_turn + 1,
        armor_at_application=0,
    )


def expire_8913(states, *, caster_id, caster_turn):
    """Pure expiry at native caster-start clock; retains unrelated states."""
    output = dict(states)
    state = output.get(8913)
    if state is not None:
        if not isinstance(state, dict) or "expires_at_caster_start" not in state:
            raise ValueError("Unknown8913 timing metadata")
        if (
            state["caster_id"] == caster_id
            and caster_turn >= state["expires_at_caster_start"]
        ):
            del output[8913]
    return output
