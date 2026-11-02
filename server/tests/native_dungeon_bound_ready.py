"""Native constructors and paid inputs for an already admitted durable room.

No roster, winner, actor health or encounter phase is replaced by a fixture.
Admission/build acquisition are explicit caller premises. This maintained helper
stops after real Ready and native initialization; it does not drive a fight.
"""
from random import Random


def construct(test, store, owners, group, fight_id, publications):
    from native_supreme_paid_component_runtime import PaidComponentRuntime
    from wakfu_server import dungeon_runtime, dungeon_scaling_entry
    from wakfu_server.combat_actor_snapshot import (
        initialize_fight_snapshots,
        build_player_snapshot,
        native_actor_catalog,
    )
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_cosmetic_conditions import (
        initialize_fresh_player_cosmetics,
    )
    from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
    from wakfu_server.combat_encounter_scene_policy import (
        arena_scene,
        bind_scene,
        scene_state_declarations,
    )
    from wakfu_server.combat_instance_publication import bind_party_encounter
    from wakfu_server.combat_join_registration import register_joined_fighter
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_state import Actor
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.equipment_stats import combat_resources
    from wakfu_server.spells import default_deck

    characters = {
        m["character"]["id"]: store.character(m["account"], m["character"]["id"])
        for m in owners
    }
    first = next(iter(characters.values()))
    monsters = {m["id"]: m for m in group["members"]}
    with store.connection() as db:
        key = (first["map_id"], first["instance_id"], group["group_id"])
        record = dungeon_runtime.combat_room_scene(db, key)
        room_cells = dungeon_runtime.combat_room_cells(
            db,
            key,
            tuple(first[k] for k in ("x", "y", "z")),
            [tuple(m[k] for k in ("x", "y", "z")) for m in monsters.values()],
        )
    members = list(monsters.values())
    catalog = native_actor_catalog()
    arena = local_arena(
        first["map_id"],
        first["id"],
        tuple(first[k] for k in ("x", "y", "z")),
        [tuple(m[k] for k in ("x", "y", "z")) for m in members],
        allowed_cells=room_cells,
        full_room_scope=record is not None and record["descriptor"]["full_room_scope"],
        ordinary_npc_placement=True,
        variation_seed=17,
        member_radii=tuple(
            catalog["npc_profiles"][str(m["ref"])]["physical_radius"] for m in members
        ),
        player_radius=catalog["default_actor_radius"],
    )
    arena = prepare_encounter_scene(first, members, arena)
    arena = arena_scene(record, arena, first, members)
    resources = {identity: combat_resources(c) for identity, c in characters.items()}
    decks = {identity: default_deck(c) for identity, c in characters.items()}
    values = resources[first["id"]]
    from wakfu_server.combat_placement_policy import freeze

    arena = freeze(
        store,
        account_id=owners[0]["account"],
        generation=owners[0]["generation"],
        character_id=first["id"],
        fight_id=fight_id,
        map_id=first["map_id"],
        instance_id=first["instance_id"],
        selected_arena=arena,
        seeds={
            0: [tuple(first[k] for k in ("x", "y", "z"))],
            1: [tuple(m[k] for k in ("x", "y", "z")) for m in members],
        },
    )
    # World allocates a positive environmental UID before declared glyph birth.
    # Use the same producer for declared scenes and ordinary room terrain.
    import secrets

    terrain_identity = secrets.randbelow(2**60) + 1
    fight, _ = create_placement(
        first,
        members,
        arena,
        fight_id=fight_id,
        player_ap=values["ap"],
        player_mp=values["mp"],
        player_wp=values["wp"],
        player_initiative=values["initiative"],
        terrain_effect_id=arena["terrain_effect_id"],
        terrain_instance_id=terrain_identity,
    )
    test.assertTrue(
        bind_party_encounter(
            fight, publications=(publications[0],), npc_ids=tuple(monsters)
        )
    )
    bind_scene(fight, arena, monsters)
    initialize_fight_snapshots(
        fight,
        characters={first["id"]: first},
        monsters=monsters,
        wp_resources={
            **{
                first["id"]: (
                    resources[first["id"]]["wp"],
                    resources[first["id"]]["wp"],
                )
            },
            **{i: (m["wp"], m.get("max_wp", m["wp"])) for i, m in monsters.items()},
        },
        running_effects={identity: () for identity in fight.actors},
        initial_effect_uid=1,
        scene_state_declarations=scene_state_declarations(fight, monsters),
    )
    # As in the maintained Gran witness, join a fresh independently owned PC
    # through native placement registration. This does not claim a join socket.
    for character in list(characters.values())[1:]:
        values = resources[character["id"]]
        occupied = {a.position for a in fight.actors.values()}
        position = min(fight.placement[0] - occupied)
        actor = Actor(
            character["id"],
            0,
            position,
            character["hp"],
            values["ap"],
            values["mp"],
            values["initiative"],
            character["level"],
            character["account_id"],
            True,
            max_hp=character["max_hp"],
        )
        initialize_fresh_player_cosmetics(actor, character)
        build_player_snapshot(
            character,
            actor,
            wp_current=values["wp"],
            wp_maximum=values["wp"],
            running_effects=(),
        ).install(actor)
        register_joined_fighter(fight, actor, position)
    test.assertTrue(
        bind_party_encounter(
            fight, publications=tuple(publications), npc_ids=tuple(monsters)
        )
    )
    with store.connection() as db:
        fight, scaling = dungeon_scaling_entry.initialize(db, fight, monsters)
    test.assertIsNotNone(scaling)
    for character in characters.values():
        fight.ready(character["account_id"])
    for index, (identity, character) in enumerate(characters.items(), 1):
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            decks[identity],
            action_id=index,
            rng=Random(17),
            fight_start=index == len(characters),
            player_characters=characters,
            deck_blobs=decks,
        )
    case = PaidComponentRuntime(
        fight, characters, monsters, decks, map_id=first["map_id"], seed=17
    )
    case.runtime.turn_started(arm_deadline=False)
    return case
