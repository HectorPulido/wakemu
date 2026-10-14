"""Independently constructed native Xelor owners; staged acceptance."""
import os
import random
import struct
import unittest
from unittest.mock import patch


class TwoXelorFixture:
    def __init__(self):
        from wakfu_server import combat_retained_runtime

        self.active_retained_metadata = (
            combat_retained_runtime.native_retained_metadata()
        )

    def fixture(
        self,
        *,
        active_spells=(),
        passive_spells=(),
        injury=0,
        level=1,
        caster_breed=5,
        second_player_breed=5,
        second_player_spells=(),
        second_player_passives=(),
        caster_aptitudes=(),
        enemy_position=(-5, -7, -1),
        third_player_position=(-8, -6, -1),
        second_player_position=(-7, -7, -1),
        compact_arena=True,
        initialization_seed=0,
    ):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server import combat_retained_runtime
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import encode_deck
        from tests.test_aptitude_catalog_coverage import aptitude_sheet
        from wakfu_server.wire import proto_field

        positions = {
            7: (-8, -7, -1),
            8: tuple(second_player_position),
            9: tuple(third_player_position),
            -7: enemy_position,
        }
        arena = local_arena(
            1134,
            78,
            positions[7],
            positions[-7],
            compact=compact_arena,
            relocate_monsters=compact_arena,
        )
        # Select extra participants only from this exact frozen native arena.
        # Requested cells are preferences, never unverified terrain authority.
        occupied = {positions[7], positions[-7]}
        for identity in (8, 9):
            preferred = positions[identity]
            candidates = [
                cell for cell in arena["validated_cells"] if cell not in occupied
            ]
            if not candidates:
                raise ValueError("Native arena lacks additional owned placement")
            positions[identity] = min(
                candidates,
                key=lambda cell: (
                    abs(cell[0] - preferred[0]) + abs(cell[1] - preferred[1]),
                    cell,
                ),
            )
            occupied.add(positions[identity])
        characters = {
            7: effective_character(
                dict(
                    id=7,
                    account_id=3,
                    map_id=1134,
                    breed=caster_breed,
                    level=level,
                    hp=maximum(caster_breed, level) - injury,
                    builds={
                        0: {
                            "sheet": proto_field(24, 0xFFFFFFFF).hex(),
                            "aptitudes": aptitude_sheet(caster_aptitudes).hex(),
                        }
                    },
                    inventory_items=[],
                )
            ),
            8: effective_character(
                dict(
                    id=8,
                    account_id=4,
                    map_id=1134,
                    breed=second_player_breed,
                    level=level,
                    hp=maximum(second_player_breed, level) - injury,
                    builds={
                        0: {
                            "sheet": proto_field(24, 0xFFFFFFFF).hex(),
                            "aptitudes": aptitude_sheet([]).hex(),
                        }
                    },
                    inventory_items=[],
                )
            ),
            9: effective_character(
                dict(
                    id=9,
                    account_id=5,
                    map_id=1134,
                    breed=5,
                    level=level,
                    hp=maximum(5, level) - injury,
                    builds={},
                    inventory_items=[],
                )
            ),
        }
        actors = [
            Actor(
                identity,
                0,
                positions[identity],
                characters[identity]["hp"],
                6,
                3,
                initiative,
                level,
                characters[identity]["account_id"],
                True,
                max_hp=characters[identity]["max_hp"],
            )
            for identity, initiative in ((7, 30), (8, 20), (9, 10))
        ]
        actors.append(Actor(-7, 1, positions[-7], 1000, 6, 3, 1, 1))
        fight = Fight(
            78,
            actors,
            arena["validated_cells"],
            {0: {positions[7], positions[8], positions[9]}, 1: {positions[-7]}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        initialize_global_pv_collections(fight, (7, 8, 9, -7))
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        monster = dict(id=-7, ref=5525, map_id=1134)
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={-7: monster},
            wp_resources={7: (6, 6), 8: (6, 6), 9: (6, 6), -7: (0, 0)},
            running_effects={7: (), 8: (), 9: (), -7: ()},
            initial_effect_uid=1,
        )
        for owner in (3, 4, 5):
            fight.ready(owner)

        decks = {
            7: encode_deck(active_spells, passive_spells),
            8: encode_deck(second_player_spells, second_player_passives),
            9: encode_deck(),
        }
        with patch.object(
            combat_retained_runtime,
            "native_retained_metadata",
            return_value=self.active_retained_metadata,
        ):
            for action_id, identity in enumerate((7, 8, 9), 1):
                fight, _ = prepare_server_initialization(
                    characters[identity],
                    {-7: monster},
                    fight,
                    characters[identity]["account_id"],
                    decks[identity],
                    action_id=action_id,
                    rng=random.Random(initialization_seed),
                    fight_start=(identity == 9),
                    player_characters=characters,
                    deck_blobs=decks,
                )
        return fight, characters, monster, decks
