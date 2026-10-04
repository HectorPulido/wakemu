"""Generic eVy/Tt -> SU/TC expiration scheduling (no event-ID mapping)."""
from .combat_state_timing import StateTimer, _short


def schedule_effect_timer(
    *, duration, expire_at_end, extend_on_clock_turn, clock_actor_id, timeline
):
    if duration <= 0:
        return None
    if any(type(value) is not bool for value in (expire_at_end, extend_on_clock_turn)):
        raise ValueError("Missing native Tt phase/extension flags")
    on_clock_turn = (
        timeline.current_actor_id == clock_actor_id
        and timeline.current_phase == "active"
    )
    not_reached = (
        timeline.clock_actor_index < 0
        or timeline.clock_actor_index > timeline.current_actor_index
    )
    baseline = _short(
        max(timeline.round_number, 1) + int(not not_reached and not on_clock_turn)
    )
    expiration = _short(baseline + duration)
    if expire_at_end:
        expiration = _short(expiration - 1)
    if on_clock_turn and extend_on_clock_turn:
        expiration = _short(expiration + 1)
    expiration = _short(max(baseline, expiration))
    return StateTimer(clock_actor_id, expiration, "end" if expire_at_end else "start")
