"""Owned PvE departure policy: native QI.g and fdt.bx, preserving history."""

SOURCE = "wakemu.pve_withdrawal.QI_g.fdt_bx.v1"


def retired_pve_actor_ids(fight):
    records = getattr(fight, "native_pve_departures", {})
    if not isinstance(records, dict):
        raise ValueError("Malformed owned PvE departure source")
    retired = set()
    for identity, record in records.items():
        actor = fight.actors.get(identity)
        if (
            not isinstance(record, dict)
            or record.get("source") != SOURCE
            or record.get("actor_id") != identity
            or actor is None
            or getattr(actor, "pve_withdrawn", False) is not True
            or actor.native_obstacle_id != -1
        ):
            raise ValueError("Missing actual owned PvE departure authority")
        root = fight.actors.get(record.get("root_actor_id"))
        if root is None or root.owner_id != record.get("owner_id"):
            raise ValueError("Missing owned PvE departure owner")
        collections = getattr(fight, "native_global_pv_collections", None)
        if collections is not None:
            from .combat_global_pv_collections import global_fighter_participates

            if identity not in collections.get(
                "retired_fighters", []
            ) or global_fighter_participates(fight, identity):
                raise ValueError("Stale owned PvE departure population")
        retired.add(identity)
    return frozenset(retired)


def retire_pve_actor(fight, actor, *, root_actor_id, owner_id):
    """Called only on the detached withdrawal candidate, before HP changes."""
    has_qi = getattr(fight, "native_qi_slots", None) is not None
    has_population = hasattr(fight, "native_global_pv_collections")
    if not has_qi and not has_population:
        return  # Legacy domains remain uncertified, never fabricate topology.
    records = getattr(fight, "native_pve_departures", {})
    if not isinstance(records, dict) or actor.id in records:
        raise ValueError("Duplicate owned PvE departure")
    registry = None
    old_slot = actor.native_obstacle_id
    if has_qi:
        from .combat_qi_fight import current_registry

        registry = current_registry(fight)
        registry.remove(old_slot, ["actor", actor.id])
    if has_population:
        from .combat_global_pv_collections import unregister_global_fighter

        unregister_global_fighter(fight, actor.id)
    if registry is not None:
        if hasattr(fight, "native_pointer_checkpoint"):
            from .combat_carrying import _publish_registry

            _publish_registry(fight, registry)
        else:
            fight.native_qi_slots = registry.serialized_slots()
            fight.native_qi_touched_cells = registry.serialized_cells()
            fight.native_qi_byte_topology = registry.serialized_byte_topology()
    actor.native_obstacle_id = -1  # Original QI.g calls QK.M(-1).
    fight.native_pve_departures = dict(records)
    fight.native_pve_departures[actor.id] = dict(
        source=SOURCE,
        actor_id=actor.id,
        previous_slot=old_slot,
        root_actor_id=root_actor_id,
        owner_id=owner_id,
    )
