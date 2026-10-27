"""Pay native movement to leave an observed hazard before ending a QA turn."""
from collections import deque
import struct


def move_to_safety(runtime, component, stats_serializer, *, npc_distance=0):
    from wakfu_server.combat_effect_area import native_effect_areas
    from wakfu_server.combat_effect_area_geometry import contains_area_actor
    from wakfu_server.combat_area_affiliation import area_affiliation
    from wakfu_server.combat_qi_movement import movement_blocked_cells
    from wakfu_server.combat_tackle_movement import movement_tackle_cost
    from wakfu_server.combat_movement_runtime import apply_client
    from wakfu_server.combat_area_transaction import prepare_area_movement

    fight, actor = runtime.fight, runtime.fight.current
    if actor is None or not actor.controlled:
        return ()
    enemies = [
        member
        for member in fight.actors.values()
        if member.team == component.roles.npc_team and fight._in_play(member)
    ]
    hostile = [
        row
        for row in fight.native_effect_areas.values()
        if native_effect_areas()[str(row["reference"])]["type"] == "GLYPH"
        and row["reference"] not in range(1574, 1581)
        and area_affiliation(fight, row) == component.roles.npc_team
    ]

    def safe(cell):
        return not any(
            contains_area_actor(row, cell, actor.physical_radius) for row in hostile
        ) and all(
            abs(cell[0] - member.position[0]) + abs(cell[1] - member.position[1])
            > npc_distance
            for member in enemies
        )

    if safe(actor.position):
        return ()
    blocked = set(movement_blocked_cells(fight, actor, fight.walkable) or ())
    blocked.update(
        tuple(row["cell"])
        for row in fight.native_effect_areas.values()
        if row.get("native_area_contract") == "faM"
    )
    previous, distances, queue = (
        {actor.position: None},
        {actor.position: 0},
        deque([actor.position]),
    )
    while queue:
        origin = queue.popleft()
        if distances[origin] >= actor.mp:
            continue
        for start, end in sorted(fight.edges):
            if start != origin or end in previous or end in blocked:
                continue
            previous[end] = origin
            distances[end] = distances[origin] + 1
            queue.append(end)
    paths = []
    for destination in previous:
        if not safe(destination):
            continue
        path, cursor = [], destination
        while cursor != actor.position:
            path.append(cursor)
            cursor = previous[cursor]
        path.reverse()
        ap, mp = movement_tackle_cost(fight, actor, path)
        if path and len(path) + mp <= actor.mp and ap <= actor.ap:
            paths.append(path)
    if not paths:
        # No legal movement is available at this boundary. Ending the turn
        # still executes every original damage/timer callback and lets native
        # START refresh resources; the component must survive it naturally.
        print(
            "native_rift_hazard_exit_deferred",
            dict(
                actor=actor.id,
                position=actor.position,
                hp=actor.hp,
                ap=actor.ap,
                mp=actor.mp,
                hostile=[
                    dict(
                        uid=row["uid"],
                        reference=row["reference"],
                        owner=row.get("owner_id"),
                        cell=row["cell"],
                    )
                    for row in hostile
                ],
                npc_distance=npc_distance,
            ),
            flush=True,
        )
        return ()
    path = min(paths, key=lambda value: (len(value), value))
    packets, result = apply_client(
        runtime,
        actor.owner_id,
        struct.pack(">q", actor.id)
        + b"".join(struct.pack(">iih", *cell) for cell in path),
        lambda selected: stats_serializer(selected, runtime.fight),
        runtime_stats_serializer=stats_serializer,
        area_provider=lambda current, **kw: prepare_area_movement(
            component.characters[actor.id],
            current.rift_monsters,
            current,
            component.decks[actor.id],
            rng=component.rng,
            player_characters=component.characters,
            deck_blobs=component.decks,
            **kw,
        ),
    )
    if not result or not packets or runtime.fight.phase != "active":
        raise ValueError(
            "Actual paid hazard exit did not survive: "
            + repr(
                dict(
                    actor=actor.id,
                    path=path,
                    phase=runtime.fight.phase,
                    hp=runtime.fight.actors[actor.id].hp,
                    events=runtime.fight.events[-24:],
                )
            )
        )
    return tuple(packets)
