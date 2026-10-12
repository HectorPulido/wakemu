"""Native fighter/QI registration at owned placement admission.

The caller owns an unpublished candidate fight. A joined PC is a fresh
ordinary actor, not a summon and not a reconstruction of the existing roster.
"""


def register_joined_fighter(fight, actor, position):
    if fight.phase != "placement" or actor.id in fight.actors:
        raise ValueError("Fresh joined placement fighter required")
    position = tuple(position)
    if len(position) != 3 or any(type(v) is not int for v in position):
        raise ValueError("Joined fighter requires actual placement XYZ")
    physical = getattr(actor, "native_physical_position", None)
    if physical is not None and tuple(physical) != tuple(actor.position):
        raise ValueError("Joined actor physical source disagrees with position")
    registry = None
    if getattr(fight, "native_qi_snapshot", None) is not None:
        from .combat_qi_fight import current_registry

        # Validate the prior population before inserting the new identity.
        registry = current_registry(fight)
        if type(actor.physical_radius) is not int or physical is None:
            raise ValueError("Joined fighter requires fresh physical authority")
        if not registry.terrain.aK(*position[:2]):
            raise ValueError("Joined native QI placement is outside arena")
    actor.position = position
    if physical is not None:
        # Same ordinary coordinate setter used at initial placement; efR is
        # updated before the actual QK registration and snapshot serialization.
        actor.native_physical_position = position
    fight.actors[actor.id] = actor
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import register_global_fighter

        register_global_fighter(fight, actor.id)
    if registry is not None:
        if hasattr(fight, "native_pointer_checkpoint"):
            from .combat_carrying import _publish_registry

            if actor.native_obstacle_id is None:
                # Fresh joined eGj crosses the QK constructor boundary here.
                actor.native_obstacle_id = -1
            slot = registry.register_constructor_actor(actor)
            if slot < 0:
                raise ValueError("Native QI fighter capacity exhausted")
            _publish_registry(fight, registry)
            return
        slot = registry.register(
            dict(
                identity=["actor", actor.id],
                position=list(position[:2]),
                radius=actor.physical_radius,
                indexed=True,
                movement_blocking=True,
            )
        )
        if slot < 0:
            raise ValueError("Native QI fighter capacity exhausted")
        actor.native_obstacle_id = slot
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
