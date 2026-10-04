"""Verified player defeat path; resurrection remains an explicit separate action."""
from .combat_death import death_messages
from .combat_results import fight_report, finish_messages


def defeat_messages(
    runtime, player_id, metadata, *, duration_ms, fight_instance_id, fight_model=2
):
    """Own dead player animation followed by a normal losing result.

    HP persistence and map return wait for12925 through combat_lifecycle.
    There is no resurrection, grant or inferred Phoenix location here.
    """
    fight = runtime.fight
    player = fight.actors.get(player_id)
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or player is None
        or not player.controlled
        or player.hp != 0
        or player.team == fight.winner
    ):
        raise ValueError("Player defeat requires a dead owned losing participant")
    record = metadata.get(player_id, {})
    if record.get("gained_kamas", 0) or record.get("xp_info") is not None:
        raise ValueError("A defeated player cannot receive local victory rewards")
    # Validate report before mutating the wire action sequence.
    fight_report(
        fight,
        metadata,
        duration_ms=duration_ms,
        fight_instance_id=fight_instance_id,
        initiator_id=player_id,
        fight_model=fight_model,
    )
    packets = []
    if player_id not in getattr(runtime, "_reported_deaths", set()):
        packets.extend(death_messages(runtime, player_id))
    packets.extend(
        finish_messages(
            runtime,
            metadata,
            duration_ms=duration_ms,
            fight_instance_id=fight_instance_id,
            initiator_id=player_id,
            fight_model=fight_model,
        )
    )
    return packets
