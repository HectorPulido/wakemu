import unittest
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_wire import arena
from wakfu_server.monsters import owned_instance


class BootstrapOwnedInstanceTests(unittest.TestCase):
    def build(self, character_instance=0, monster_instances=(0,)):
        char = dict(
            id=100,
            account_id=1,
            breed=8,
            level=1,
            xp=0,
            hp=60,
            max_hp=60,
            map_id=1134,
            x=0,
            y=0,
            z=0,
            instance_id=character_instance,
            builds={},
            inventory_items=[],
            active_build_index=0,
        )
        cells = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
        monsters = [
            owned_instance(
                5525,
                1,
                -200 - index,
                map_id=1134,
                instance_id=instance,
                x=index + 1,
                y=0,
                z=0,
            )
            for index, instance in enumerate(monster_instances)
        ]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain.update(
            validated_cells=cells,
            valid_edges={(cells[0], cells[1]), (cells[1], cells[0])},
        )
        return create_placement(
            char,
            monsters,
            terrain,
            fight_id=7,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )

    def test_ordinary_zero_instance_still_bootstraps(self):
        fight, messages = self.build()
        self.assertEqual({100, -200}, set(fight.actors))
        self.assertTrue(messages)

    def test_owned_dungeon_instance_preserves_reference_stats(self):
        fight, messages = self.build(123456, (123456,))
        expected = owned_instance(
            5525, 1, -200, map_id=1134, instance_id=123456, x=1, y=0, z=0
        )
        self.assertEqual(expected["max_hp"], fight.actors[-200].max_hp)
        self.assertTrue(messages)

    def test_different_character_and_monster_instances_rejected(self):
        with self.assertRaisesRegex(ValueError, "different owned instance"):
            self.build(123456, (0,))

    def test_mixed_monster_instance_group_rejected(self):
        with self.assertRaisesRegex(ValueError, "different owned instance"):
            self.build(123456, (123456, 123457))

    def test_bool_character_instance_rejected(self):
        with self.assertRaisesRegex(
            ValueError, "Invalid authoritative character instance"
        ):
            self.build(True, (1,))
