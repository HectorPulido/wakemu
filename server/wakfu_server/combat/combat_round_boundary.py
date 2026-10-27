"""One actual SU cycle boundary shared by normal and lethal turn succession."""


def complete_round(fight):
    from .combat_equipment_external_events import queue_completed_round

    queue_completed_round(fight)
    fight.native_timeline_round += 1
    if getattr(fight, "native_base_turn_order", None) is not None:
        fight.order = [
            uid
            for uid in fight.native_base_turn_order
            if fight._in_play(fight.actors[uid])
        ]
        fight.native_base_turn_order = None
        return True
    return False


def finish_turn_budget(fight, *, completed_cycle=True):
    if getattr(fight, "rift_wave_state", None) is not None:
        from .rift_combat_adapter import finish_survival

        if finish_survival(fight):
            return True
    if completed_cycle and getattr(fight, "boss_score_profile", None) is not None:
        from wakfu_server.maps.boss_score_runtime import finish_survival

        if finish_survival(fight):
            return True
    return False
