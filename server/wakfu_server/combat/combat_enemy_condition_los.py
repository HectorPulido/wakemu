"""eMs: any actual opposing IN_PLAY fighter has fcr LOS to target point."""


def enemy_condition_los(
    fight, actor_authority, *, affiliation, target_id, target_position
):
    if target_position is None:
        return False
    if type(affiliation) is not int or not -128 <= affiliation <= 127:
        raise ValueError("Missing selected native LOS eHg.bcM authority")
    from .combat_native_actor_lookup import native_actor, native_actor_population
    from .combat_global_pv_collections import global_fighter_guards
    from .combat_state_managers import registered_area_pv
    from .combat_casting_los import native_casting_los

    selected = native_actor(fight, target_id)
    if selected is None:
        selected = registered_area_pv(fight, target_id)
    if selected is None:
        return False  # Actual eII.b returned null/non-eHg.
    if not hasattr(fight, "native_global_pv_collections"):
        raise ValueError("Missing complete native enemy LOS fdt population")
    for enemy in native_actor_population(fight):
        metadata = actor_authority(fight, enemy)
        if metadata.targeting.get("is_eGj") is not True:
            raise ValueError("Missing actual enemy LOS eGj type")
        team = getattr(enemy, "native_fight_affiliation", enemy.team)
        if type(team) is not int or not -128 <= team <= 127:
            raise ValueError("Missing actual enemy LOS fdt affiliation")
        if team == affiliation or not global_fighter_guards(fight, enemy.id)["baF"]:
            continue
        try:
            if native_casting_los(
                fight, actor_authority, enemy.id, target_position, selected
            ):
                return True
        finally:
            # Native fcr.a clears QI.biO even after its first accepted ray.
            fight.native_qi_visibility_ignored_slots = []
    return False
