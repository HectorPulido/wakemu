"""Owned non-summon fighter state2 completion: fcb.aD/H/aQ removes QI, not fighter history."""
SOURCE = "wakemu.owned-npc-state2-qi-completion-v1"


def retired_ordinary_qi_ids(fight):
    from .combat_global_pv_collections import global_fighter_guards
    from .combat_ordinary_death import registered_ordinary_death

    records = getattr(fight, "native_ordinary_qi_retirements", {})
    if not isinstance(records, dict):
        raise ValueError("Invalid ordinary QI retirement ledger")
    result = set()
    for key, row in records.items():
        actor = fight.actors.get(int(key))
        if (
            actor is None
            or actor.hp != 0
            or not isinstance(row, dict)
            or row.get("source") != SOURCE
            or row.get("actor_id") != actor.id
            or getattr(actor, "native_ordinary_qi_retirement", None) != row
            or actor.native_obstacle_id != -1
            or global_fighter_guards(fight, actor.id)["baK"] is not True
            or not registered_ordinary_death(fight, actor)
        ):
            raise ValueError("Unverified ordinary QI retirement")
        result.add(actor.id)
    return result


def complete_ordinary_qi_death(fight, actor, *, fighter_state=2):
    """Complete an explicitly requested state2, never mere HP0 or reversible KO."""
    if type(fighter_state) is not int or fighter_state != 2:
        raise ValueError("Explicit native final fighter state2 required")
    from .combat_global_pv_collections import (
        global_fighter_guards,
        set_global_fighter_status,
    )
    from .combat_ordinary_death import registered_ordinary_death
    from .combat_qi_fight import current_registry

    if getattr(actor, "native_summon_source", None) is not None:
        return False
    records = getattr(fight, "native_ordinary_qi_retirements", {})
    if str(actor.id) in records:
        retired_ordinary_qi_ids(fight)
        return False
    if not hasattr(fight, "native_global_pv_collections"):
        return False  # Legacy public damage fixtures have no owned fdt authority.
    guards = global_fighter_guards(fight, actor.id)
    if guards["baG"] is not True:
        return False
    if not registered_ordinary_death(fight, actor):
        raise ValueError("Ordinary QI completion requires registered death")
    registry = current_registry(fight)
    slot = actor.native_obstacle_id
    registry.remove(slot, ("actor", actor.id))
    if not hasattr(fight, "native_pointer_checkpoint"):
        serialized_slots = registry.serialized_slots()
        serialized_cells = registry.serialized_cells()
        serialized_topology = registry.serialized_byte_topology()
    row = dict(source=SOURCE, actor_id=actor.id, qi_slot=slot)
    set_global_fighter_status(fight, actor.id, "OUT_OF_PLAY")
    actor.native_obstacle_id = -1
    actor.native_ordinary_qi_retirement = row
    fight.native_ordinary_qi_retirements = dict(records, **{str(actor.id): row})
    if hasattr(fight, "native_pointer_checkpoint"):
        from .combat_carrying import _publish_registry

        _publish_registry(fight, registry)
    else:
        fight.native_qi_slots = serialized_slots
        fight.native_qi_touched_cells = serialized_cells
        fight.native_qi_byte_topology = serialized_topology
    return True
