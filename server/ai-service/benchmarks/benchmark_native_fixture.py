"""Self-contained native encounter fixture; usable in the live world image."""
from types import SimpleNamespace


def fixture(*, npc_position=(-7, -7, -1), pc_hp=60):
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_actor_snapshot import (
        build_player_snapshot,
        build_npc_snapshot,
    )
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.spells import default_deck

    if type(pc_hp) is not int or not 1 <= pc_hp <= 60:
        raise ValueError("Invalid benchmark PC HP")
    pc = Actor(
        7, 0, (-8, -7, -1), pc_hp, 6, 3, 0, 1, owner_id=9, controlled=True, max_hp=60
    )
    npc = Actor(-200, 1, tuple(npc_position), 20, 3, 3, 10, 1)
    fight = Fight(
        1, [pc, npc], {pc.position, npc.position}, {0: {pc.position}, 1: {npc.position}}
    )
    fight.ready(9)
    monster = dict(id=npc.id, ref=5525, level=1, map_id=1134, wp=6)
    character = dict(
        id=pc.id,
        account_id=9,
        breed=15,
        level=1,
        map_id=1134,
        hp=pc.hp,
        max_hp=pc.max_hp,
        builds={},
        inventory_items=[],
    )
    pc.direction, npc.direction = 0, 3
    build_player_snapshot(
        character, pc, wp_current=6, wp_maximum=6, running_effects=()
    ).install(pc)
    build_npc_snapshot(
        monster, npc, wp_current=6, wp_maximum=6, running_effects=()
    ).install(npc)
    fight.native_effect_uid_next = 1
    fight.native_obstacle_cells = frozenset()
    terrain = local_arena(1134, fight.id, pc.position, npc.position)
    fight.walkable, fight.edges = terrain["validated_cells"], terrain["valid_edges"]
    if pc.position not in fight.walkable or npc.position not in fight.walkable:
        raise ValueError("Benchmark actor lies outside complete native arena")
    freeze_terrain(fight)
    fight.order, fight.turn_index = [npc.id, pc.id], 0
    npc.turn_count = 1
    runtime = RuntimeMessages(fight)
    description = SimpleNamespace(
        pc=pc, npc=npc, fight=fight, character=character, monster=monster
    )
    return (
        runtime,
        {pc.id: character},
        {npc.id: monster},
        {pc.id: default_deck(character)},
        {pc.id: frozenset()},
        description,
    )
