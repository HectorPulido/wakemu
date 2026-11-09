"""Select at most one bounded, native-previewable trap movement candidate."""
import sys


def candidate(
    oracle, baseline, geometry, actor, visible, spell, compiled, root_parameters, level
):
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_published_catalogs import static_catalog_descriptor
    from ..native.native_control import (
        effective_affiliation,
        effective_server_controlled,
    )

    prepare = sys.modules.get(
        "wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_trap_prepare"
    )
    if prepare is None or len(root_parameters) != 1:
        return None
    parameters = root_parameters[0]
    if (
        len(parameters) < 2
        or any(type(value) is not int for value in parameters[:2])
        or parameters[0] <= 0
        or not 0 <= parameters[1] <= 32767
    ):
        return None
    descriptor = static_catalog_descriptor(compiled.effects)
    metadata = prepare.get_or_schedule(
        baseline["catalogRevision"], descriptor, parameters[0], parameters[1]
    )
    if metadata is None:
        return None
    rows = metadata.get("effects")
    if (
        not isinstance(rows, list)
        or not 1 <= len(rows) <= 8
        or not set(metadata.get("entryMasks", ())) & {10001, 10008}
        or any(
            row.get("family") not in (2, 3, 4, 5, 56, 57)
            or row.get("criteria") != ""
            or row.get("children")
            or row.get("probability") != 100
            for row in rows
        )
    ):
        return None
    fight = oracle.runtime.fight
    living = [row for row in fight.actors.values() if row.hp > 0]
    if (
        len(living) > 8
        or {row.id for row in visible if row.hp > 0} != {row.id for row in living}
        or fight.native_effect_areas
        or not fight.order
        or spell.get("needsLineOfSight")
        or spell.get("inLine")
        or not spell.get("needsFreeCell")
    ):
        return None
    target_id = fight.order[(fight.turn_index + 1) % len(fight.order)]
    target = fight.actors.get(target_id)
    if (
        target is None
        or target.hp <= 0
        or effective_server_controlled(fight, target)
        or effective_affiliation(fight, target) == effective_affiliation(fight, actor)
    ):
        return None
    occupied = set()
    for row in living:
        occupied.update(footprint(row.position, row.physical_radius))
    origin = tuple(actor.position)
    trigger_origin = tuple(target.position)
    for destination in geometry.adjacency.get(trigger_origin, ())[:8]:
        destination = tuple(destination)
        cell = geometry.indices.get(destination)
        if cell is None or destination[:2] in occupied:
            continue
        distance = abs(destination[0] - origin[0]) + abs(destination[1] - origin[1])
        if not spell["minRange"] <= distance <= spell["maxRange"]:
            continue
        return dict(
            fightInstanceId=baseline["fightInstanceId"],
            turnId=baseline["turnId"],
            actorId=actor.id,
            nativeIdentity=baseline["nativeIdentity"],
            catalogRevision=baseline["catalogRevision"],
            catalogGeneration=descriptor["revision"],
            catalogCollection=descriptor["collection"],
            spellId=spell["id"],
            grade=level,
            fromCell=geometry.indices[origin],
            aimCell=cell,
            origin=list(origin),
            aim=list(destination),
            triggerActorId=target.id,
            triggerOrigin=list(trigger_origin),
            triggerCell=cell,
            triggerCellXYZ=list(destination),
            areaReference=parameters[0],
            livingActorIds=[row.id for row in living],
        )
    return None
