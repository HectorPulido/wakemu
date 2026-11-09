"""Native multi-owner roster used by isolated multiplayer test fixtures.

The constructors and terrain are native; identities and characters are synthetic.
"""
from collections import defaultdict, deque
import gzip
from types import SimpleNamespace


def _connected_monster_positions(map_id, origin, count):
    """Choose deterministic reachable map cells using only exported edges."""
    from wakfu_server.combat_terrain import map_geometry

    geometry = map_geometry(map_id)
    forward = defaultdict(list)
    for source, destination in geometry["edges"]:
        forward[tuple(source)].append(tuple(destination))
    distance = {tuple(origin): 0}
    queue = deque([tuple(origin)])
    while queue:
        source = queue.popleft()
        for destination in forward[source]:
            if destination not in distance:
                distance[destination] = distance[source] + 1
                queue.append(destination)

    cells = [tuple(cell) for cell in geometry["cells"]]
    selected = []
    for minimum_distance in range(4, 32):
        for cell in cells:
            if distance.get(cell) != minimum_distance:
                continue
            if any(
                max(abs(cell[0] - other[0]), abs(cell[1] - other[1])) <= 1
                for other in selected
            ):
                continue
            selected.append(cell)
            if len(selected) == count:
                return tuple(selected)
    raise ValueError("Map has too few separated reachable monster positions")


def fixture(
    *,
    map_id=1134,
    pc_position=(-8, -7, -1),
    monster_references=(5462, 5462, 5462, 5462, 5462, 5525),
    monster_level=1,
    fight_id=41001,
    first_character_id=7001,
    first_account_id=9001,
    first_monster_id=-2001,
    player_count=6,
    owner_accounts=None,
    ready=True,
):
    """Return a bounded native multi-owner encounter and all owned sources.

    Five reference 5462 actors exercise generic walking without an implied
    attack. The final reference 5525 owns catalogued native spell 7962 at level
    one; its cast is still accepted only if the native oracle certifies it.
    """
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import placement_messages, player_payload
    from wakfu_server.combat_cosmetic_conditions import (
        initialize_fresh_player_cosmetics,
    )
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_qi_snapshot import NativeQISnapshot
    from wakfu_server.combat_qi_surface_catalog import native_qi_surface_provenance
    from wakfu_server.combat_actor import actor_effects, monster_actor_stats
    from wakfu_server.monsters import native_abilities, owned_instance
    from wakfu_server.spells import default_deck

    if (
        not 1 <= len(monster_references) <= 12
        or type(player_count) is not int
        or not 1 <= player_count <= 6
        or (owner_accounts is not None and len(owner_accounts) != player_count)
        or type(map_id) is not int
        or type(monster_level) is not int
        or len(pc_position) != 3
        or any(type(value) is not int for value in pc_position)
    ):
        raise ValueError(
            "The native roster fixture requires bounded rosters and a valid origin"
        )

    monster_positions = _connected_monster_positions(
        map_id, pc_position, len(monster_references)
    )
    monsters = {
        first_monster_id
        - index: owned_instance(
            reference,
            monster_level,
            first_monster_id - index,
            map_id=map_id,
            x=position[0],
            y=position[1],
            z=position[2],
            team=1,
            instance_id=0,
        )
        for index, (reference, position) in enumerate(
            zip(monster_references, monster_positions)
        )
    }
    arena = local_arena(
        map_id,
        0,
        tuple(pc_position),
        monster_positions,
        relocate_monsters=(len(monster_references) == 6),
    )
    pc_slots = set(arena["placement_cells"][0])
    if tuple(pc_position) not in pc_slots or len(pc_slots) < player_count:
        raise ValueError("Official placement did not supply the requested player slots")
    pc_positions = (
        tuple(pc_position),
        *sorted(pc_slots - {tuple(pc_position)})[: player_count - 1],
    )
    if len(set(pc_positions + tuple(monster_positions))) != player_count + len(
        monster_references
    ):
        raise ValueError("Official placement produced overlapping roster coordinates")

    characters = {}
    actors = []
    for index, position in enumerate(pc_positions):
        character_id = first_character_id + index
        account_id = (
            first_account_id + index
            if owner_accounts is None
            else owner_accounts[index]
        )
        character = {
            "id": character_id,
            "account_id": account_id,
            "breed": 15,
            "level": 1,
            "active_build_index": 0,
            "map_id": map_id,
            "instance_id": 0,
            "x": position[0],
            "y": position[1],
            "z": position[2],
            "hp": 60,
            "max_hp": 60,
            "builds": {},
            "inventory_items": [],
        }
        characters[character_id] = character
        actor = Actor(
            character_id,
            0,
            position,
            character["hp"],
            6,
            3,
            0,
            1,
            account_id,
            True,
            max_hp=character["max_hp"],
            direction=0,
        )
        initialize_fresh_player_cosmetics(actor, character)
        actors.append(actor)

    npc_actors = [
        Actor(
            monster["id"],
            1,
            (monster["x"], monster["y"], monster["z"]),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            monster["level"],
            max_hp=monster["max_hp"],
            direction=3,
        )
        for monster in monsters.values()
    ]
    actors.extend(npc_actors)
    fight = Fight(
        fight_id,
        actors,
        arena["validated_cells"],
        arena["placement_cells"],
        arena["valid_edges"],
    )
    initialize_global_pv_collections(fight, tuple(fight.actors))

    qi_names = ("x", "y", "width", "height", "cell_masks")
    qi_snapshot = NativeQISnapshot({name: arena[name] for name in qi_names})
    fight.native_qi_snapshot = {
        "x": qi_snapshot.x,
        "y": qi_snapshot.y,
        "width": qi_snapshot.width,
        "height": qi_snapshot.height,
        "cell_masks": list(qi_snapshot.masks),
    }
    freeze_terrain(fight)
    provenance = arena.get("native_qi_surface_provenance")
    if provenance != native_qi_surface_provenance(map_id):
        raise ValueError("Official arena QI surface provenance changed")
    fight.native_qi_surface_provenance = dict(provenance)
    fight.native_obstacle_cells = (
        frozenset() if arena.get("team_values") == [] else None
    )

    wp_resources = {actor_id: (6, 6) for actor_id in characters}
    wp_resources.update(
        {
            monster_id: (monster["wp"], monster["wp"])
            for monster_id, monster in monsters.items()
        }
    )
    initialize_fight_snapshots(
        fight,
        characters=characters,
        monsters=monsters,
        wp_resources=wp_resources,
        running_effects={identity: () for identity in fight.actors},
        initial_effect_uid=1,
    )

    payloads = {
        character_id: player_payload(
            characters[character_id], fight.actors[character_id], fight_id, wp=6
        )
        for character_id in characters
    }
    payloads.update(
        {
            monster_id: (
                monster_actor_stats(
                    monster,
                    fight_id,
                    direction=3,
                    obstacle_id=fight.actors[monster_id].native_obstacle_id,
                ),
                actor_effects(),
            )
            for monster_id, monster in monsters.items()
        }
    )
    placement_packets = placement_messages(
        fight,
        arena,
        payloads,
        terrain_effect_id=46,
        terrain_instance_id=-300,
        leaders={0: next(iter(characters)), 1: next(iter(monsters))},
    )
    if ready:
        for account_id in dict.fromkeys(
            character["account_id"] for character in characters.values()
        ):
            fight.ready(account_id)

    runtime = RuntimeMessages(fight)
    decks = {
        identity: default_deck(character) for identity, character in characters.items()
    }
    excluded_decks = {identity: frozenset() for identity in characters}
    abilities = {
        str(monster["id"]): native_abilities(monster["ref"], monster["level"])
        for monster in monsters.values()
    }
    description = SimpleNamespace(
        map_id=map_id,
        arena=arena,
        pc_ids=tuple(characters),
        monster_ids=tuple(monsters),
        pc_positions=pc_positions,
        monster_positions=monster_positions,
        abilities=abilities,
        placement_packets=placement_packets,
        join_context={
            "arena": arena,
            "terrain_effect_id": 46,
            "terrain_instance_id": -300,
            "leaders": {0: next(iter(characters)), 1: next(iter(monsters))},
            "duration_ms": 60000,
            "monsters": monsters,
            "roster": {
                "owners": [
                    character["account_id"] for character in characters.values()
                ],
                "characters": list(characters),
                "monsters": list(monsters),
            },
            "benchmarkFutureField": {"kept": True, "schema": 1},
        },
        completeRoster=True,
        rosterSource="explicit benchmark characters and owned_instance monsters initialized by official native constructors; not live Store leases",
        privateAckHarnessOnly=True,
        sharedRegistryAdmission="not_used",
    )
    from wakfu_server.wakia_bridge.wakfu_ai.context.native_context import encode_bytes

    # Carry complete synthetic join metadata, including an unknown future
    # field, through the normal complete-state graph. This is benchmark data,
    # not a fabricated SharedFight/Registry lease.
    raw_context = encode_bytes({"join_context": description.join_context})
    runtime.native_ai_shared_context = gzip.compress(
        raw_context, compresslevel=1, mtime=0
    )
    description.join_context_raw_bytes = len(raw_context)
    description.join_context_compressed_bytes = len(runtime.native_ai_shared_context)
    return runtime, characters, monsters, decks, excluded_decks, description
