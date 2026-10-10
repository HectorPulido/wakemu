"""Ordinary NPC client eligibility must match authoritative PB counters."""
import struct
from types import SimpleNamespace
import unittest

from wakfu_server.combat_actor import monster_actor_stats, actual_monster_actor_stats
from wakfu_server.combat_ordinary_authority import native_property_catalog
from wakfu_server.combat_property_wire import fight_property_payload


class MonsterPropertyWireTests(unittest.TestCase):
    @staticmethod
    def monster(reference):
        return dict(
            id=-7,
            ref=reference,
            level=8,
            map_id=1134,
            team=1,
            hp=20,
            max_hp=20,
            ap=6,
            mp=3,
            wp=0,
            initiative=0,
            x=2,
            y=0,
            z=0,
        )

    def decode(self, payload):
        self.assertEqual(payload[0], 2)
        stat_count = struct.unpack_from(">H", payload, 31)[0]
        property_offset = 33 + stat_count * 17
        self.assertEqual(payload[property_offset], 1)
        count = struct.unpack_from(">H", payload, property_offset + 1)[0]
        return dict(
            struct.unpack_from(">bb", payload, property_offset + 3 + i * 2)
            for i in range(count)
        )

    def test_actual_capture_profile_is_visible_to_native_client_property_gate(self):
        self.assertEqual(
            native_property_catalog()["npc"]["4"]["fight_properties"], [40]
        )
        self.assertEqual(
            self.decode(monster_actor_stats(self.monster(4), 123)), {40: 1}
        )

    def test_non_capturable_profile_does_not_gain_capture_property(self):
        self.assertEqual(
            self.decode(monster_actor_stats(self.monster(5525), 123)), {15: 1, 78: 1}
        )

    def test_refresh_preserves_added_removed_and_multiple_signed_counters(self):
        monster = self.monster(4)
        actor = SimpleNamespace(
            id=-7,
            controlled=False,
            hp=20,
            max_hp=20,
            ap=6,
            max_ap=6,
            mp=3,
            max_mp=3,
            initiative=0,
            team=1,
            native_obstacle_id=1,
            position=(2, 0, 0),
            native_controlled_by_ai=True,
            native_fight_property_counts={28: 2, 65: -128},
            native_fight_properties=frozenset({28, 65}),
        )
        payload = actual_monster_actor_stats(
            monster, actor, 123, wp_current=0, wp_maximum=0
        )
        self.assertEqual(self.decode(payload), {28: 2, 65: -128})
        actor.native_fight_property_counts = {}
        actor.native_fight_properties = frozenset()
        payload = actual_monster_actor_stats(
            monster, actor, 123, wp_current=0, wp_maximum=0
        )
        self.assertEqual(self.decode(payload), {})

    def test_malformed_counter_population_rejected(self):
        for counts in ({40: True}, {40: 128}, {128: 1}, {"40": 1}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                fight_property_payload(counts)


if __name__ == "__main__":
    unittest.main()
