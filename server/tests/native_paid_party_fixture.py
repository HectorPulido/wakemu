"""Persisted normal-player builds and native pre-Ready party construction.

Inventory grants are explicit fixture premises, not evidence of acquisition.
Callers must identify ordinary native equipment producers separately. No
companion-only emblem, administrator authority or combat-state grant is added.
"""
from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class NativeGear:
    reference: int
    slot: int
    damage_mask: int = 0
    resistance_mask: int = 0


@dataclass(frozen=True)
class NativePartyBuild:
    breed: int
    level: int
    active_spells: tuple
    aptitudes: tuple
    gear: tuple = ()
    passive_spells: tuple = ()


def native_endgame_iop_build():
    """Loot-backed ordinary eleven-slot245 inventory premise, no emblems for companions.

    Source records: party245-other-slots-source.json and
    uhu-drop-native-gear-source.json in the private readiness evidence folder.
    Three chosen elements use native bit positions1/3/4: fire/earth/air.
    """
    return NativePartyBuild(
        breed=8,
        level=245,
        active_spells=(4777, 4780, 4778, 4781, 4789),
        aptitudes=(
            (1, 52),
            (16, 10),
            (26, 40),
            (23, 22),
            (12, 62),
            (2, 1),
            (3, 1),
            (8, 1),
            (4, 1),
            (5, 1),
        ),
        gear=(
            NativeGear(29633, 15),
            NativeGear(29521, 0),
            NativeGear(32514, 3),
            NativeGear(29527, 4),
            NativeGear(27066, 5),
            NativeGear(32559, 10),
            NativeGear(32547, 12, damage_mask=26),
            NativeGear(29462, 13),
            NativeGear(32541, 7, damage_mask=26),
            NativeGear(32540, 8, damage_mask=26),
            NativeGear(32613, 17),
        ),
    )


def persisted_party_character(store, build, *, name, map_id, position):
    """Create an owned healthy build in the caller's isolated test schema."""
    import struct
    from wakfu_server import health_store
    from wakfu_server.aptitudes import validate
    from wakfu_server.equipment_stats import bonuses, combat_resources
    from wakfu_server.inventory_items import grant
    from wakfu_server.progression import level_xp
    from wakfu_server.spells import encode_deck
    from wakfu_server.wire import proto_field

    if not isinstance(build, NativePartyBuild) or not 1 <= build.level <= 245:
        raise ValueError("Published owned player build required")
    if len({item.slot for item in build.gear}) != len(build.gear):
        raise ValueError("Owned gear must use distinct equipment slots")
    aptitudes = proto_field(24, build.level) + b"".join(
        proto_field(34, proto_field(8, bonus) + proto_field(16, points))
        for bonus, points in build.aptitudes
    )
    validate({"level": build.level}, aptitudes)
    account = store.register(name, "isolated-party-test-password")["id"]
    character = store.create_character(
        account, name.replace("-", " "), breed=build.breed, sex=0
    )
    generation = store.begin_session(account)
    store.select_character(account, generation, character["id"])
    with store.connection() as database:
        database.execute(
            "UPDATE characters SET level=%s,map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
            (build.level, map_id, *position, character["id"]),
        )
        database.execute(
            "UPDATE character_progression SET xp=%s WHERE character_id=%s",
            (level_xp(build.level), character["id"]),
        )
    character = health_store.initialize(store, account, generation, character["id"])
    container = next(
        row["uid"] for row in character["inventory_containers"] if row["kind"] == 0
    )
    equipment = b""
    admitted = []
    for index, selection in enumerate(build.gear):
        item = grant(
            store,
            account,
            generation,
            character["id"],
            reference=selection.reference,
            quantity=1,
            container=container,
            slot=index,
            allowed_references={selection.reference},
        )
        if selection.damage_mask or selection.resistance_mask:
            from wakfu_server.items.element_selection import select

            select(
                store,
                account,
                generation,
                character["id"],
                struct.pack(
                    ">qBB",
                    item["uid"],
                    selection.damage_mask,
                    selection.resistance_mask,
                ),
            )
        equipment += proto_field(
            10, proto_field(8, item["uid"]) + proto_field(16, selection.slot)
        )
        admitted.append(
            dict(reference=selection.reference, uid=item["uid"], slot=selection.slot)
        )
    deck = encode_deck(build.active_spells, build.passive_spells)
    character = store.save_build(
        account,
        generation,
        character["id"],
        0,
        dict(
            sheet=(
                proto_field(8, 0)
                + proto_field(18, b"Native party")
                + proto_field(24, build.level)
                + proto_field(56, 0)
            ),
            aptitudes=aptitudes,
            equipment=equipment,
            deck=deck,
        ),
    )
    character = health_store.initialize(store, account, generation, character["id"])
    if character["hp"] != character["max_hp"]:
        raise ValueError("Fresh party owner has nonzero canonical wounds")
    evaluated = bonuses(character)
    if set(evaluated["equipped_uids"]) != {item["uid"] for item in admitted}:
        raise ValueError(
            "Equipment admission did not preserve the declared owned items"
        )
    resources = combat_resources(character)
    if resources["unsupported"]:
        raise ValueError(
            "Party build contains unevaluated native combat resource bonuses"
        )
    return character, generation, deck, resources, admitted


def native_paid_party_fixture(
    store,
    scene,
    builds,
    player_cells,
    *,
    name_prefix,
    fight_id=78,
    initialization_seed=0,
    encounter_layout=None,
    production_scene=False,
    placement_directions=None,
):
    """Construct one to six normal owned PCs and one untouched native NPC.

    Positions must already exist in the configured native room. No turns,
    movement, damage, score or phase advancement are performed by this helper.
    """
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import INITIAL_PLAYER_DIRECTION
    from wakfu_server.combat_cosmetic_conditions import (
        initialize_fresh_player_cosmetics,
    )
    from wakfu_server.combat_environment_glyphs import prepare_environment_glyphs
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_haven_world_context import (
        bind_placement,
        placement_context,
    )
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.monsters import owned_instance
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.combat_encounter_roles import (
        assigned_roles,
        roles_from_record,
        bind_roles,
    )

    if type(production_scene) is not bool:
        raise ValueError("Explicit production scene selection required")
    if not 1 <= len(builds) <= 6 or len(builds) != len(player_cells):
        raise ValueError("One to six independently owned builds and cells required")
    if placement_directions is not None:
        from wakfu_server.combat_orientation import CARDINAL_DIRECTIONS

        if (
            not isinstance(placement_directions, tuple)
            or len(placement_directions) != len(builds)
            or any(
                type(direction) is not int or direction not in CARDINAL_DIRECTIONS
                for direction in placement_directions
            )
        ):
            raise ValueError(
                "One native cardinal placement direction per owned player required"
            )
    cells = tuple(map(tuple, player_cells))
    if encounter_layout is None:
        boss_cell = tuple(
            enemy_formation(
                {
                    "map_id": scene["map_id"],
                    "cells": scene["cells"],
                    "edges": scene["edges"],
                },
                scene["anchor"],
                1,
                player_slots=6,
            )[0]
        )
    else:
        if encounter_layout["map_id"] != scene["map_id"]:
            raise ValueError("Party layout belongs to another native map")
        boss_cell = tuple(encounter_layout["source"])
        if not set(cells) <= set(map(tuple, encounter_layout["party_placement_cells"])):
            raise ValueError("Party placement leaves the declared encounter blue cells")
    if len(set((*cells, boss_cell))) != len(cells) + 1 or not set(
        (*cells, boss_cell)
    ) <= set(scene["cells"]):
        raise ValueError("Party placement must use distinct existing native room cells")
    characters, decks, resources, generations, equipment = {}, {}, {}, {}, {}
    for index, (build, position) in enumerate(zip(builds, cells)):
        character, generation, deck, values, gear = persisted_party_character(
            store,
            build,
            name=f"{name_prefix}-{chr(97 + index)}",
            map_id=scene["map_id"],
            position=position,
        )
        identity = character["id"]
        characters[identity], generations[identity] = character, generation
        decks[identity], resources[identity], equipment[identity] = deck, values, gear
    monster = owned_instance(
        scene["reference"],
        scene["level"],
        -200,
        map_id=scene["map_id"],
        x=boss_cell[0],
        y=boss_cell[1],
        z=boss_cell[2],
    )
    first = next(iter(characters.values()))
    if encounter_layout is None:
        arena = local_arena(
            scene["map_id"],
            fight_id,
            cells[0],
            boss_cell,
            compact=False,
            relocate_monsters=False,
            allowed_cells=scene["cells"],
        )
    else:
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene

        arena = prepare_encounter_scene(
            first,
            [monster],
            {"map_id": scene["map_id"], "instance_id": fight_id},
            layout=encounter_layout,
        )
    if production_scene and encounter_layout is None:
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene

        arena = prepare_encounter_scene(
            first,
            [monster],
            dict(arena, placement_cells={0: set(cells), 1: {boss_cell}}),
        )
    role_record = arena.get("native_encounter_roles")
    roles = (
        assigned_roles(None)
        if role_record is None
        else roles_from_record(
            role_record, map_id=scene["map_id"], monster_references=[scene["reference"]]
        )
    )
    actors = [
        Actor(
            identity,
            roles.player_team,
            position,
            character["hp"],
            resources[identity]["ap"],
            resources[identity]["mp"],
            resources[identity]["initiative"],
            character["level"],
            character["account_id"],
            True,
            max_hp=character["max_hp"],
            direction=INITIAL_PLAYER_DIRECTION,
        )
        for (identity, character), position in zip(characters.items(), cells)
    ]
    actors.append(
        Actor(
            -200,
            roles.npc_team,
            boss_cell,
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            monster["level"],
            max_hp=monster["max_hp"],
            direction=arena.get("native_encounter_scene_layout", {}).get(
                "boss_direction", 3
            ),
        )
    )
    placement = (
        roles.placement_cells(cells, {boss_cell})
        if encounter_layout is None and not production_scene
        else arena["placement_cells"]
    )
    fight = Fight(
        fight_id, actors, arena["validated_cells"], placement, arena["valid_edges"]
    )
    if role_record is not None:
        bind_roles(fight, roles, player_ids=tuple(characters), npc_ids=(-200,))
    if "native_encounter_scene_layout" in arena:
        from copy import deepcopy

        fight.native_encounter_scene_layout = deepcopy(
            arena["native_encounter_scene_layout"]
        )
    bind_placement(fight, placement_context(first, [monster], fight_id=fight_id))
    for actor in actors[:-1]:
        initialize_fresh_player_cosmetics(actor, characters[actor.id])
    initialize_global_pv_collections(
        fight, tuple(fight.actors), controller_registration=True
    )
    fight.native_qi_snapshot = {
        key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
    }
    fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
    freeze_terrain(fight)
    if arena.get("native_border_policy") is not None:
        fight.native_border_constructor = dict(
            reference=arena.get("terrain_effect_id", 46),
            identity=9001,
            arena={
                key: arena[key]
                for key in (
                    "native_border_policy",
                    "native_border_cells",
                    "min_z",
                    "native_border_scope_cells",
                )
                if key in arena
            },
        )
    prepare_environment_glyphs(fight, arena, 9001)
    initialize_fight_snapshots(
        fight,
        characters=characters,
        monsters={-200: monster},
        wp_resources={
            **{
                identity: (values["wp"], values["wp"])
                for identity, values in resources.items()
            },
            -200: (monster["wp"], monster["wp"]),
        },
        running_effects={identity: () for identity in fight.actors},
        initial_effect_uid=1,
    )
    orientation_receipts = []
    if placement_directions is not None:
        import struct
        from wakfu_server.combat_orientation import apply as apply_orientation
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        placement_runtime = RuntimeMessages(fight)
        for actor, direction in zip(actors[:-1], placement_directions):
            result = apply_orientation(
                placement_runtime,
                actor.owner_id,
                struct.pack(">qB", actor.id, direction),
            )
            orientation_receipts.append(result["event"])
    for character in characters.values():
        fight.ready(character["account_id"])
    for index, (identity, character) in enumerate(characters.items(), 1):
        fight, _ = prepare_server_initialization(
            character,
            {-200: monster},
            fight,
            character["account_id"],
            decks[identity],
            action_id=index,
            rng=Random(initialization_seed),
            fight_start=index == len(characters),
            player_characters=characters,
            deck_blobs=decks,
        )
    receipt = dict(
        map_id=scene["map_id"],
        reference=scene["reference"],
        native_level=scene["level"],
        inventory_premise="Explicit native gear grant before construction; acquisition authority audited separately",
        equipment=equipment,
        resources=resources,
        health={
            identity: (character["hp"], character["max_hp"])
            for identity, character in characters.items()
        },
        administrator_grants=False,
        combat_state_grants=False,
        score_seed=False,
        encounter_roles=role_record,
        production_scene=production_scene,
        placement_orientations=orientation_receipts,
    )
    return fight, characters, {-200: monster}, decks, resources, generations, receipt
