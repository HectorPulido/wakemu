"""Pure scheduling of the verified native state expiration timer.

Client evidence: fyW.aas/fL -> Tt; eZk.bbT/fRc -> eZR.a(Tt);
SU.a(Th,Tt) -> TC.a(Th,Tt,ZZS). SU.eE invokes TC.a at turn start;
SU.e(long,bool) invokes TC.b at turn end. TC filters the absolute round
bucket by actor identity. States do not use a generic every-turn decrement.
This helper excludes native effect fallback clocks, realtime durations,
refresh/reapplication and fight-wide callback dispatch.
"""
from dataclasses import dataclass
from typing import Literal


Phase = Literal["start", "active", "end", "between", "initial"]


def _short(value: int) -> int:
    return ((value + 32768) % 65536) - 32768


@dataclass(frozen=True)
class StateTimingDefinition:
    base_duration: int
    duration_per_level: int
    maximum_level: int
    expire_at_end: bool
    clock_on_caster: bool
    # Exact fyW.cxj result, not a guess from the duration or state ID.
    skip_turn_timer: bool = False

    def duration(self, level: int) -> int:
        # fyW.aas uses an int product, then fL narrows the total to short.
        return _short(
            self.base_duration
            + min(level, self.maximum_level) * self.duration_per_level
        )


@dataclass(frozen=True)
class StateTimer:
    actor_id: int
    expiration_round: int
    phase: Literal["start", "end"]

    def expires_at_round_cleanup(self, round_number: int) -> bool:
        """TC.c(short,SU) dispatches prior-round buckets for all actors."""
        return self.expiration_round == _short(round_number - 1)

    def expires_on(self, *, actor_id: int, round_number: int, phase: Phase) -> bool:
        # TC visits an exact bucket, not every older bucket, and matches actor.
        return (
            actor_id == self.actor_id
            and round_number == self.expiration_round
            and phase == self.phase
        )


def schedule_state_timer(
    definition: StateTimingDefinition,
    *,
    level: int,
    caster_id: int,
    target_id: int,
    round_number: int,
    current_actor_id: int,
    current_actor_index: int,
    clock_actor_index: int,
    current_phase: Phase,
    timeline_is_active: bool = True,
) -> StateTimer | None:
    """Schedule a native fyW state timer using an authoritative SU snapshot.

    Actor indices are SU.eA and Tb.bik values; a negative clock index keeps
    the native not-in-current-timeline behavior. None means no turn timer,
    not an instruction to remove the state. Callback dispatch and phase
    ordering remain the caller's responsibility.
    """
    if current_phase not in ("start", "active", "end", "between", "initial"):
        raise ValueError("Unknown native timeline phase")
    duration = definition.duration(level)
    if definition.skip_turn_timer or duration <= 0:
        return None
    clock_id = caster_id if definition.clock_on_caster else target_id
    # SU.eJ only holds during ON_FIGHTER_TURN (not beginning/ending).
    on_clock_turn = (
        timeline_is_active
        and current_actor_id == clock_id
        and current_phase == "active"
    )
    # SU.a(Th,Tt,J), native iload8: index < 0 or index > current index.
    clock_not_reached = clock_actor_index < 0 or clock_actor_index > current_actor_index
    shift = int(not clock_not_reached and not on_clock_turn)
    baseline = max(round_number, 1) + shift
    expiration = _short(baseline + duration)
    if definition.expire_at_end:
        expiration = _short(expiration - 1)
    expiration = _short(max(_short(baseline), expiration))
    return StateTimer(
        clock_id, expiration, "end" if definition.expire_at_end else "start"
    )


def state_requires_retention(
    *,
    turn_duration: int,
    realtime_duration: int,
    permanent_flag: bool,
    applying_effect_has_delay: bool,
) -> bool:
    """Native eZk.Ty/bbX plus Qe.g's inherited bbW delay branch.

    turn_duration is fyW.gtL (the full int, not narrowed Tt.biT).
    realtime_duration is fyW.guH. permanent_flag is fyW.cxj, whose
    meaning depends on realtime duration; it is not sufficient by itself.
    Applying effect delay must be established from eZR.bbW/en/eo.
    """
    indefinite = (
        realtime_duration < 0
        if permanent_flag
        else turn_duration < 0 or realtime_duration < 0
    )
    native_timed = indefinite or turn_duration > 0 or realtime_duration > 0
    return native_timed or applying_effect_has_delay
