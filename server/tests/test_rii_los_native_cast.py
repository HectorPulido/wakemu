"""Exercise owned LOS training against actual server spell dispatch."""
import random
import struct
import unittest
from unittest.mock import patch

import test_combat_spell_transaction as fixture_module
from wakfu_server.achievements import rii_los_encounter
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.spells import encode_deck


class LineOfSightNativeCastTests(unittest.TestCase):
    def test_four_hits_in_native_rii_arena_with_real_rocks_and_rays(self):
        from wakfu_server.combat_actor_snapshot import (
            build_npc_snapshot,
            native_npc_creation_values,
        )
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        fixture = fixture_module.SpellTransactionTests()
        character, monster, prior = fixture.native_server_fixture(
            3, 15, target_ref=5466, target_level=1
        )
        character["map_id"] = 1388
        monster["map_id"] = 1388
        owner, target = prior.actors[7], prior.actors[-7]
        owner.position, target.position = (3, -16, 0), (-1, -16, 0)
        monsters = {-7: monster}
        rocks = []
        for identity, pos in zip(
            (-8, -9, -10), ((-2, -16, 0), (-1, -17, 0), (-1, -15, 0))
        ):
            values = native_npc_creation_values(4528, 1)
            rock = Actor(
                identity,
                1,
                pos,
                values[1]["current"],
                values[2]["current"],
                values[3]["current"],
                0,
                1,
                max_hp=values[1]["maximum"],
            )
            monsters[identity] = dict(id=identity, ref=4528, map_id=1388)
            build_npc_snapshot(
                monsters[identity], rock, wp_current=0, wp_maximum=0, running_effects=()
            ).install(rock)
            rocks.append(rock)
        arena = local_arena(
            1388,
            7,
            owner.position,
            [target.position, *(r.position for r in rocks)],
            relocate_monsters=False,
            compact=False,
        )
        fight = Fight(
            78,
            [owner, target, *rocks],
            arena["validated_cells"],
            {0: {owner.position}, 1: {target.position, *(r.position for r in rocks)}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, (7, -7, -8, -9, -10))
        registry = prepare_fresh_actor_slots(
            fight,
            physical_radii={a.id: a.physical_radius for a in [owner, target, *rocks]},
        )
        install_fresh_actor_slots(fight, registry)
        fight.ready(3)
        fight.native_effect_uid_next = 1
        fight.native_obstacle_cells = frozenset()
        fight.rii_los_lesson_contract = {
            "owner": 7,
            "target": -7,
            "hits": 0,
            "rocks": [-8, -9, -10],
        }
        rii_los_encounter.initialize(fight, [], action_id=1)
        request = struct.pack(">qqiih", 7, 7968, *target.position)
        for action in range(2, 6):
            result = prepare_server_spell(
                request,
                character,
                monsters,
                fight,
                3,
                encode_deck([]),
                action_id=action,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(action),
            )
            fight = result.fight
        self.assertEqual(fight.rii_los_lesson_contract["hits"], 4)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))

    def test_damage_requires_server_ray_even_when_cast_adapter_accepts(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3, 15, native_qi=True, target_ref=5466, target_level=1, target_distance=4
        )
        fight.rii_los_lesson_contract = {"owner": 7, "target": -7, "hits": 0}
        packets = []
        # This focused dispatcher fixture has no owned rock formation.
        with patch.object(rii_los_encounter, "ensure_initial_shot", return_value=True):
            rii_los_encounter.initialize(fight, packets, action_id=1)
        request = struct.pack(">qqiih", 7, 7968, *fight.actors[-7].position)

        def cast(source):
            return prepare_server_spell(
                request,
                character,
                {-7: monster},
                source,
                3,
                encode_deck([]),
                action_id=2,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )

        with patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=False
        ):
            with self.assertRaisesRegex(ValueError, "casting eligibility rejected"):
                cast(fight)
        self.assertEqual(fight.actors[-7].hp, 100)
        self.assertEqual(fight.rii_los_lesson_contract["hits"], 0)
        with patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=True
        ), patch(
            "wakfu_server.achievements.rii_los_encounter.move_one_rock",
            return_value=True,
        ):
            allowed = cast(fight)
        self.assertEqual(allowed.fight.actors[-7].hp, 75)
        self.assertEqual(allowed.fight.rii_los_lesson_contract["hits"], 1)


if __name__ == "__main__":
    unittest.main()
