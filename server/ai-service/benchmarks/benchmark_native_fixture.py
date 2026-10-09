"""Self-contained native encounter fixture; usable in the live world image."""
from types import SimpleNamespace


def fixture(
    *,
    npc_position=(-7, -7, -1),
    pc_position=(-8, -7, -1),
    map_id=1134,
    pc_hp=60,
    monster_reference=5525,
    monster_level=1,
):
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.monsters import owned_instance
    from wakfu_server.spells import default_deck

    if (
        type(pc_hp) is not int
        or not 1 <= pc_hp <= 60
        or type(map_id) is not int
        or map_id <= 0
        or any(type(value) is not int for value in (*pc_position, *npc_position))
    ):
        raise ValueError("Invalid benchmark encounter inputs")

    character = dict(
        id=7,
        account_id=9,
        breed=15,
        level=1,
        active_build_index=0,
        map_id=map_id,
        instance_id=0,
        x=pc_position[0],
        y=pc_position[1],
        z=pc_position[2],
        hp=pc_hp,
        max_hp=60,
        builds={},
        inventory_items=[],
    )
    monster = owned_instance(
        monster_reference,
        monster_level,
        -200,
        map_id=map_id,
        x=npc_position[0],
        y=npc_position[1],
        z=npc_position[2],
        instance_id=0,
    )
    terrain = local_arena(map_id, 1, tuple(pc_position), tuple(npc_position))
    fight, _ = create_placement(
        character,
        monster,
        terrain,
        fight_id=1,
        player_ap=6,
        player_mp=3,
        player_wp=6,
        player_initiative=0,
        terrain_effect_id=46,
        terrain_instance_id=-300,
    )
    initialize_fight_snapshots(
        fight,
        characters={character["id"]: character},
        monsters={monster["id"]: monster},
        wp_resources={
            character["id"]: (6, 6),
            monster["id"]: (monster["wp"], monster["wp"]),
        },
        running_effects={character["id"]: (), monster["id"]: ()},
        initial_effect_uid=1,
    )
    fight.ready(character["account_id"])
    # The benchmark begins at the NPC's activation while retaining the exact
    # placement-produced actor, terrain, QI slots and serialized sources.
    fight.order = [monster["id"], character["id"]]
    fight.turn_index = 0
    fight.current.turn_count = 1
    runtime = RuntimeMessages(fight)
    description = SimpleNamespace(
        pc=fight.actors[character["id"]],
        npc=fight.actors[monster["id"]],
        fight=fight,
        character=character,
        monster=monster,
        arena=terrain,
    )
    return (
        runtime,
        {character["id"]: character},
        {monster["id"]: monster},
        {character["id"]: default_deck(character)},
        {character["id"]: frozenset()},
        description,
    )
