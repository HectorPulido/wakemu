"""Native cvx12514 transition into ACTION, not a client-side phase override.

Initial combat has no timeline bonus effects or queued timed events. The final
fdA/eHZ blob restores supplied fdy controller rows, not permanent zones.
Ordinary initial combat retains its exact typed zero-count encodings.
"""
import struct
from .combat_input_observation import wall_time


def action_transition(
    fight_id,
    *,
    timestamp_ms=None,
    duration_seconds=0,
    bonus_period=3,
    controller_records=(),
):
    if type(fight_id) is not int or not 0 < fight_id < 2**31:
        raise ValueError("Invalid fight identity")
    if type(duration_seconds) is not int or not 0 <= duration_seconds < 2**31:
        raise ValueError("Invalid phase duration")
    if type(bonus_period) is not int or not 0 < bonus_period < 2**31:
        raise ValueError("Bonus period must be positive")
    timestamp_ms = (
        int(wall_time("phase.action_transition.wall") * 1000)
        if timestamp_ms is None
        else timestamp_ms
    )
    # feI/feN dNH is a positive turn period, not a round.
    # Native fem.fYD uses fez.fYU()==3. Empty bonus collections are local policy.
    bonuses = struct.pack(">iBBB", bonus_period, 0, 0, 0)
    # TG/TC: affected-member set i16count; two i32 event-map counts.
    timed = struct.pack(">hii", 0, 0, 0)
    # cvx.mzj -> eHZ/fdA.eI restores explicit fdy rows; no control effect is invented.
    from .combat_scene_controller_snapshot import controller_snapshot

    controllers = controller_snapshot(controller_records)
    body = (
        struct.pack(">iBiqi", fight_id, 2, duration_seconds, timestamp_ms, len(bonuses))
        + bonuses
    )
    body += b"\x00"  # no feb(q actor,q reference,i effect) entries.
    body += (
        struct.pack(">i", len(timed))
        + timed
        + struct.pack(">i", len(controllers))
        + controllers
    )
    return 12514, body
