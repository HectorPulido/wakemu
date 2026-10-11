"""Three actual controlled players: native carry then a real Iop area attack."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaCarryDeathRuntimeTests(unittest.TestCase):
    def fixture(
        self,
        *,
        carrier_level,
        carried_level,
        pandawa_passives=(),
        attacker_spell=4784,
        injured_ally=False,
        positions=None,
        attacker_distance=None,
        pandawa_actives=(),
        attacker_level=200,
        pandawa_aptitudes=None,
        pandawa_amulet=False
    ):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.equipment_stats import effective_character, combat_resources
        from wakfu_server.health import maximum
        from wakfu_server.spells import encode_deck

        positions = positions or {7: (-8, -7, -1), 8: (-7, -7, -1), 9: (-8, -6, -1)}
        arena = local_arena(1134, 781, positions[7], positions[8], variation_seed=17)
        if attacker_distance is not None:
            candidates = sorted(
                cell
                for cell in arena["validated_cells"]
                if cell[2] == positions[7][2]
                and abs(cell[0] - positions[7][0]) + abs(cell[1] - positions[7][1])
                == attacker_distance
                and (cell[0] == positions[7][0] or cell[1] == positions[7][1])
                and cell not in (positions[7], positions[8])
            )
            self.assertTrue(
                candidates, "No actual terrain cell at requested attack distance"
            )
            positions[9] = candidates[0]
        specs = {
            7: (12, carrier_level, 0, 3),
            8: (7, carried_level, 0, 4),
            9: (8, attacker_level, 1, 5),
        }
        characters, actors = {}, []
        pandawa_builds = {}
        if pandawa_aptitudes is not None:
            from test_aptitude_catalog_coverage import aptitude_sheet
            from wakfu_server.wire import proto_field

            pandawa_builds = {
                0: {
                    "aptitudes": aptitude_sheet(pandawa_aptitudes).hex(),
                    "sheet": proto_field(24, (1 << 64) - 1).hex(),
                    "equipment": proto_field(
                        10, proto_field(8, 1000) + proto_field(16, 4)
                    ).hex()
                    if pandawa_amulet
                    else "",
                }
            }
        for identity, (breed, level, team, owner) in specs.items():
            character = effective_character(
                dict(
                    id=identity,
                    account_id=owner,
                    breed=breed,
                    level=level,
                    hp=maximum(breed, level),
                    map_id=1134,
                    builds=pandawa_builds if identity == 7 else {},
                    inventory_items=[
                        dict(uid=1000, character_id=7, reference=2021, quantity=1)
                    ]
                    if identity == 7 and pandawa_amulet
                    else [],
                )
            )
            if injured_ally and identity == 8:
                character["hp"] = character["max_hp"] // 2
            characters[identity] = character
            resources = combat_resources(character)
            actors.append(
                Actor(
                    identity,
                    team,
                    positions[identity],
                    character["hp"],
                    resources["ap"],
                    resources["mp"],
                    resources["initiative"],
                    level,
                    owner,
                    True,
                    max_hp=character["max_hp"],
                )
            )
        self.assertTrue(set(positions.values()) <= set(arena["validated_cells"]))
        fight = Fight(
            781,
            actors,
            arena["validated_cells"],
            {0: {positions[7], positions[8]}, 1: {positions[9]}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        initialize_global_pv_collections(fight, (7, 8, 9))
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={},
            wp_resources={identity: (6, 6) for identity in characters},
            running_effects={identity: () for identity in characters},
            initial_effect_uid=1,
        )
        decks = {
            7: encode_deck(pandawa_actives, pandawa_passives),
            8: encode_deck(),
            9: encode_deck([attacker_spell]),
        }
        for owner in (3, 4, 5):
            fight.ready(owner)
        for action_id, identity in enumerate((7, 8, 9), 1):
            fight, _ = prepare_server_initialization(
                characters[identity],
                {},
                fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=action_id,
                rng=random.Random(0),
                fight_start=identity == 9,
                player_characters=characters,
                deck_blobs=decks,
            )
        return fight, characters, decks

    def reach(self, fight, characters, decks, identity):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from tools.combat_audit_turns import advance_actual_turn

        for _ in range(20):
            if fight.current.id == identity:
                return fight
            owner = fight.current.id
            runtime = RuntimeMessages(
                fight,
                turn_end_provider=lambda p, **b: prepare_server_turn_end(
                    characters[owner],
                    {},
                    p,
                    decks[owner],
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                    **b
                ),
                turn_start_provider=lambda p, **b: prepare_server_turn_start(
                    characters[p.current.id],
                    {},
                    p,
                    decks[p.current.id],
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                    **b
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    characters[owner],
                    {},
                    decks[owner],
                    action_id=action_id,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                )[0],
            )
            advance_actual_turn(runtime)
            fight = runtime.fight
        self.fail("Owned actor did not receive a real turn")

    def test_actual_third_attacker_clears_pair_after_carried_or_carrier_death(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_carrying import carrying_relations
        from wakfu_server.combat_qi_fight import current_registry

        for victim in (7, 8):
            with self.subTest(victim=victim):
                fight, characters, decks = self.fixture(
                    carrier_level=1 if victim == 7 else 200,
                    carried_level=1 if victim == 8 else 200,
                )
                fight = self.reach(fight, characters, decks, 7)
                uid = granted_spells(fight, 7)[6847]["uid"]
                carried = prepare_server_spell(
                    struct.pack(">qqiih", 7, uid, *fight.actors[8].position),
                    characters[7],
                    {},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                fight = self.reach(carried.fight, characters, decks, 9)
                # Native 4784 -> 398388 enumerates a 3x3 square around SELF;
                # child152202 applies actual earth damage, including the stacked cell.
                for action_id in range(11, 31):
                    fight = self.reach(fight, characters, decks, 9)
                    try:
                        attack = prepare_server_spell(
                            struct.pack(
                                ">qqiih", 9, (9 << 32) | 4784, *fight.actors[9].position
                            ),
                            characters[9],
                            {},
                            fight,
                            5,
                            decks[9],
                            action_id=action_id,
                            line_of_sight=lambda *args: True,
                            critical=False,
                            rng=random.Random(0),
                            player_characters=characters,
                            deck_blobs=decks,
                        )
                    except ValueError as error:
                        if str(error) != "Insufficient authoritative spell resources":
                            raise
                        # Advance a real turn before retrying; never refill AP directly.
                        other = next(
                            identity
                            for identity in (7, 8)
                            if fight.actors[identity].hp > 0
                        )
                        fight = self.reach(fight, characters, decks, other)
                        continue
                    fight = attack.fight
                    if fight.actors[victim].hp == 0:
                        break
                self.assertEqual(attack.fight.actors[victim].hp, 0)
                self.assertFalse(getattr(attack.fight, "native_carry_pairs", {}))
                for identity in (7, 8):
                    self.assertEqual(
                        carrying_relations(attack.fight, attack.fight.actors[identity]),
                        dict(is_carried=False, is_carrying=False),
                    )
                current_registry(attack.fight)
