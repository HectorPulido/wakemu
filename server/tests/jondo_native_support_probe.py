"""Opt-in real Ready/TCP support components; no scripted support selection."""
from random import Random
from types import SimpleNamespace
from unittest.mock import patch
from copy import deepcopy
import struct
import uuid


def build_fixture(
    reference,
    level,
    *,
    allies=(),
    npc_position=(-4, -7, -1),
    player_position=(-8, -7, -1),
    additional_humans=0,
    map_id=1134,
    allowed_cells=None,
    full_room_scope=False,
    fixed_member_positions=None,
    encounter_scene_record=None,
    lifecycle_observer=None,
    role_record=None,
    character_source=None,
    before_initialize=None,
    terrain_instance_id=-300,
    instance_id=0,
):
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import create_placement
    from wakfu_server.combat_encounter_scene_policy import bind_scene
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.health import maximum
    from wakfu_server.monsters import owned_instance
    from wakfu_server.spells import default_deck
    from tests.native_supreme_paid_component_runtime import PaidComponentRuntime

    if type(additional_humans) is not int or not 0 <= additional_humans <= 5:
        raise ValueError(
            "Additional native human owners must fit the six-player placement"
        )
    hp = maximum(8, 200)
    if character_source is None:
        character = effective_character(
            dict(
                id=7,
                account_id=3,
                map_id=map_id,
                instance_id=instance_id,
                breed=8,
                level=200,
                hp=hp,
                max_hp=hp,
                active_build_index=0,
                x=player_position[0],
                y=player_position[1],
                z=player_position[2],
                builds={},
                inventory_items=[],
            )
        )
    else:
        identity = character_source["id"]
        character = effective_character(
            dict(
                character_source,
                id=identity,
                map_id=map_id,
                instance_id=instance_id,
                x=player_position[0],
                y=player_position[1],
                z=player_position[2],
            )
        )
    player_id = character["id"]
    resources = combat_resources(character)
    roster = [(reference, level, npc_position), *allies]
    monsters = {
        -7
        - i: owned_instance(
            ref,
            lvl,
            -7 - i,
            map_id=map_id,
            instance_id=instance_id,
            x=pos[0],
            y=pos[1],
            z=pos[2],
            team=1,
        )
        for i, (ref, lvl, pos) in enumerate(roster)
    }
    characters = {player_id: character}
    decks = {player_id: default_deck(character)}
    positions = [(m["x"], m["y"], m["z"]) for m in monsters.values()]
    arena = local_arena(
        map_id,
        1,
        player_position,
        positions if len(positions) > 1 else positions[0],
        relocate_monsters=False,
        variation_seed=17,
        allowed_cells=allowed_cells,
        full_room_scope=full_room_scope,
        fixed_member_positions=fixed_member_positions,
    )
    if role_record is not None:
        arena["native_encounter_roles"] = deepcopy(role_record)
    if encounter_scene_record is not None:
        from wakfu_server.combat_encounter_scene_policy import arena_scene

        arena = arena_scene(
            encounter_scene_record, arena, character, list(monsters.values())
        )
    fight, _ = create_placement(
        character,
        list(monsters.values()),
        arena,
        fight_id=1,
        player_ap=resources["ap"],
        player_mp=resources["mp"],
        player_wp=resources["wp"],
        player_initiative=resources["initiative"],
        terrain_effect_id=46,
        terrain_instance_id=terrain_instance_id,
    )
    if lifecycle_observer is not None:
        lifecycle_observer("create_placement", fight, monsters)
    bind_scene(fight, arena, monsters)
    if before_initialize is not None:
        before_initialize(fight, characters, monsters)
    initialize_fight_snapshots(
        fight,
        characters=characters,
        monsters=monsters,
        wp_resources={
            player_id: (resources["wp"], resources["wp"]),
            **{i: (m["wp"], m["wp"]) for i, m in monsters.items()},
        },
        running_effects={i: () for i in fight.actors},
        initial_effect_uid=1,
    )
    if lifecycle_observer is not None:
        lifecycle_observer("initialize_fight_snapshots", fight, monsters)
    if additional_humans:
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_cosmetic_conditions import (
            initialize_fresh_player_cosmetics,
        )
        from wakfu_server.combat_join_registration import register_joined_fighter
        from wakfu_server.combat_state import Actor

        for index in range(1, additional_humans + 1):
            occupied = {actor.position for actor in fight.actors.values()}
            position = min(
                fight.placement[0] - occupied,
                key=lambda cell: (
                    sum(abs(a - b) for a, b in zip(cell, player_position)),
                    cell,
                ),
            )
            peer = deepcopy(character)
            peer.update(
                id=player_id + index,
                account_id=3 + index,
                x=position[0],
                y=position[1],
                z=position[2],
            )
            values = combat_resources(peer)
            actor = Actor(
                peer["id"],
                0,
                position,
                peer["hp"],
                values["ap"],
                values["mp"],
                values["initiative"],
                peer["level"],
                peer["account_id"],
                True,
                max_hp=peer["max_hp"],
            )
            initialize_fresh_player_cosmetics(actor, peer)
            build_player_snapshot(
                peer,
                actor,
                wp_current=values["wp"],
                wp_maximum=values["wp"],
                running_effects=(),
            ).install(actor)
            register_joined_fighter(fight, actor, position)
            characters[peer["id"]], decks[peer["id"]] = peer, default_deck(peer)
    for owned in characters.values():
        fight.ready(owned["account_id"])
    for index, (identity, owned) in enumerate(characters.items(), 1):
        fight, _ = prepare_server_initialization(
            owned,
            monsters,
            fight,
            owned["account_id"],
            decks[identity],
            action_id=index,
            rng=Random(17),
            fight_start=index == len(characters),
            player_characters=characters,
            deck_blobs=decks,
            before_fight_start=(
                None
                if lifecycle_observer is None
                else lambda preview: lifecycle_observer(
                    "before_fight_start_events", preview, monsters
                )
            ),
        )
        if lifecycle_observer is not None:
            lifecycle_observer("prepare_server_initialization", fight, monsters)
    case = PaidComponentRuntime(
        fight, characters, monsters, decks, map_id=map_id, seed=17
    )
    case.runtime.tactical_encounter_id = uuid.uuid4().hex
    case.runtime.turn_started(arm_deadline=False)
    return case


def _oracle(case):
    from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle

    return NativeOracle(
        case.runtime,
        characters=case.characters,
        monsters=case.monsters,
        decks=case.decks,
        excluded_decks={7: frozenset()},
        viewer_id=7,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )


def _drain(case):
    for _ in range(64):
        if case.runtime.awaiting_ack is None:
            return
        case.runtime.acknowledge_turn(struct.pack(">i", case.runtime.awaiting_ack))
    raise AssertionError("Native ACK chain exceeded its fixture bound")
