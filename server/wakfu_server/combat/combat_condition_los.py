"""eMr HasLineOfSight: any fcr ray to eII.aR target footprint."""


def native_condition_los(fight, authority, caster_id, target_id, cell):
    from .combat_los import authoritative_visible

    source = fight.actors.get(caster_id)
    if source is None:
        return False
    source_metadata = authority(fight, source)
    map_id = source_metadata.native_instance_id
    target = fight.actors.get(target_id)
    radius = 0 if target is None else target.physical_radius
    if type(radius) is not int or not -128 <= radius <= 127:
        raise ValueError("Missing native condition LOS target radius")
    if radius != 0:
        raise ValueError(
            "Native condition LOS expanded target footprint is not implemented"
        )
    point = tuple(cell) if target is None else tuple(target.position)
    footprints = {}
    for actor in fight.actors.values():
        if actor.hp <= 0:
            continue
        authority(fight, actor)
        if actor.physical_radius != 0:
            raise ValueError(
                "Native condition LOS nonordinary blocker footprint is not implemented"
            )
        footprints[actor.id] = {tuple(actor.position[:2])}
    return authoritative_visible(
        map_id, tuple(source.position), point, fight, blocking_footprints=footprints
    )
