"""Wakemu wave placement across the complete reachable native arena.

The placement stream is independent of species selection and combat RNG.
Physical occupancy comes from current QI membership, including registered
corpses and obstacles; HP and display height never substitute for that source.
"""
from collections import deque
import hashlib
import random


def select_positions(fight, *, references, seed, wave):
    from wakfu_server.combat_actor_snapshot import native_actor_catalog
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_pointer_qi_registry import (
        registered_obstacle,
        registered_population,
    )
    from wakfu_server.combat_qi_fight import current_registry

    references = tuple(references)
    if (
        not references
        or any(type(ref) is not int or ref <= 0 for ref in references)
        or type(seed) is not str
        or not seed
        or type(wave) is not int
        or wave < 1
    ):
        raise ValueError("Invalid Rift reinforcement placement source")
    cells = set(fight.walkable)
    roles = assigned_roles(fight)
    starts = sorted(
        {
            actor.position
            for actor in fight.actors.values()
            if actor.team == roles.player_team and fight._in_play(actor)
        }
    )
    if not starts or any(cell not in cells for cell in starts) or fight.edges is None:
        raise ValueError("Missing native Rift placement component")
    outgoing = {}
    for origin, destination in fight.edges:
        if origin not in cells or destination not in cells:
            raise ValueError("Rift native edge leaves its arena")
        outgoing.setdefault(origin, []).append(destination)
    reached, pending = set(starts), deque(starts)
    while pending:
        for destination in outgoing.get(pending.popleft(), ()):
            if destination not in reached:
                reached.add(destination)
                pending.append(destination)

    # Exactly one current registry/population projection per placement operation.
    # Memoize only operation-local physical facts, never mutable fight state.
    registry = current_registry(fight)
    qi, population = registered_population(registry)
    obstacle_rows, free_cells = {}, {}

    def free(cell):
        if cell in free_cells:
            return free_cells[cell]
        x, y = cell
        allowed = qi.aK(x, y)
        if allowed:
            index = (y - qi.y) * qi.width + x - qi.x
            allowed = not qi.masks[index] & 768
        if allowed:
            for slot in population(x, y):
                if slot not in obstacle_rows:
                    obstacle_rows[slot] = registered_obstacle(registry, slot)
                row = obstacle_rows[slot]
                if row is not None and row["movement_blocking"]:
                    allowed = False
                    break
        free_cells[cell] = allowed
        return allowed

    profiles = native_actor_catalog()["npc_profiles"]
    radii = {}
    for ref in set(references):
        profile = profiles.get(str(ref))
        radius = None if profile is None else profile.get("physical_radius")
        if type(radius) is not int or not -128 <= radius <= 127:
            raise ValueError("Missing native Rift reinforcement physical radius")
        radii[ref] = radius
    catalog = fight.rift_wave_state["catalog"]
    material = f'{catalog["wave_id"]}:{seed}:{wave}:reinforcement-placement-v1'
    rng = random.Random(
        int.from_bytes(hashlib.sha256(material.encode()).digest(), "big")
    )
    candidates = sorted(reached)
    rng.shuffle(candidates)
    selected, reserved = {}, set()
    # Admit larger native footprints first without changing species/UID order.
    for index in sorted(
        range(len(references)), key=lambda i: (-radii[references[i]], i)
    ):
        radius = radii[references[index]]
        extent = max(0, radius)
        if 2 * extent + 1 > qi.width or 2 * extent + 1 > qi.height:
            raise ValueError("Rift reinforcement footprint exceeds its native arena")
        for position in candidates:
            if not qi.aK(position[0] - extent, position[1] - extent) or not qi.aK(
                position[0] + extent, position[1] + extent
            ):
                continue
            area = footprint(position, radius)
            if not any(cell in reserved for cell in area) and all(
                free(cell) for cell in area
            ):
                selected[index] = position
                reserved.update(area)
                break
        else:
            raise ValueError(
                "Rift arena lacks physically free reachable reinforcement cells"
            )
    return tuple(selected[index] for index in range(len(references)))
