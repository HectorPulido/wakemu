"""Wakemu action routing for registered summons owned by an actual NPC.

A native control effect can leave a child fqL=false while its current controller
is an NPC. The server supplies that controller's actions without changing fqL.
Player controllers, absent/dead roots and cyclic relations never authorize AI.
"""
POLICY = "wakemu.registered-npc-controller-actions-v1"


def npc_controller_routes_ai(fight, actor):
    source = getattr(actor, "native_summon_source", None)
    if not isinstance(source, dict):
        return False
    registration = getattr(fight, "native_summon_registrations", {}).get(actor.id)
    authority = (
        registration.get("authority") if isinstance(registration, dict) else None
    )
    if (
        fight.actors.get(actor.id) is not actor
        or actor.hp <= 0
        or source.get("native_relation_source")
        != "big.new_bje.fdt_initial_registration"
        or not isinstance(authority, dict)
        or authority.get("is_summon") is not True
        or authority.get("native_actor_type") != 1
        or registration.get("actor_id") != actor.id
        or registration.get("caster_id") != source.get("caster_id")
        or authority.get("breed_id") != source.get("ref")
        or authority.get("native_real_level") != source.get("level")
    ):
        raise ValueError("Missing actual registered NPC-controlled summon authority")
    from .combat_qi_fight import current_registry

    registry = current_registry(fight)
    slot = getattr(actor, "native_obstacle_id", None)
    if (
        type(slot) is not int
        or not 0 <= slot < len(registry.slots)
        or registry.slots[slot] is None
        or registry.slots[slot].get("identity") != ["actor", actor.id]
    ):
        raise ValueError("Missing actual QI slot for NPC-controlled summon")
    from .combat_controller_registry import current_native_controller

    seen = {actor.id}
    identity = current_native_controller(fight, actor.id)
    while identity is not None:
        if identity in seen:
            return False
        seen.add(identity)
        controller = fight.actors.get(identity)
        if controller is None or controller.hp <= 0:
            return False
        # Immutable original player identity wins, even if the creation source
        # was an NPC; current fdy transfer is authoritative over that source.
        if controller.controlled:
            return False
        flag = getattr(controller, "native_controlled_by_ai", None)
        if type(flag) is not bool:
            raise ValueError("Missing actual NPC controller AI authority")
        if flag:
            return True
        if getattr(controller, "native_summon_source", None) is None:
            return False
        identity = current_native_controller(fight, controller.id)
    return False
