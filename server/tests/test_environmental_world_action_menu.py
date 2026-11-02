"""Keep native interaction targets alive while excluding their fight offer."""
import struct
import unittest

from protocol_codec import Reader
from wakfu_server.combat_monster_world import world_actor
from wakfu_server.monsters import owned_instance, reference
from wakfu_server.objectives.environmental_monster_actions import decode_request


def native_world_properties(blob):
    reader = Reader(blob)
    reader.take(1 + 8 + 1 + 8)
    reader.text("H")
    reader.take(2 + 4 + 4 + 2 + 8 + 1 + 1 + 1 + 2)
    assert reader.number("H") == 0
    reader.take(1 + 4 + 1 + 1 + 1 + 1 + 1 + 1)
    if not reader.number("B"):
        return {}
    return {reader.number("B"): reader.number("B") for _ in range(reader.number("H"))}


class EnvironmentalWorldActionMenuTests(unittest.TestCase):
    def actor(self, identity=2808):
        return owned_instance(
            identity,
            reference(identity)["min_level"],
            -17801,
            map_id=711,
            instance_id=0,
            x=0,
            y=0,
            z=0,
        )

    def test_action_only_is_unattackable_and_alive_across_native_species(self):
        for identity in (2808, 2373):
            with self.subTest(reference=identity):
                actor = dict(self.actor(identity), environmental_world_action_only=True)
                self.assertEqual(
                    native_world_properties(world_actor(actor, group_id=178)), {13: 1}
                )

    def test_ordinary_alive_and_corpse_keep_original_property_contract(self):
        actor = self.actor()
        self.assertEqual(native_world_properties(world_actor(actor, group_id=178)), {})
        self.assertEqual(
            native_world_properties(world_actor(actor, group_id=178, dead=True)),
            {19: 1},
        )

    def test_invalid_marker_keeps_strict_actor_validation(self):
        for invalid in (False, None, 1):
            with self.subTest(marker=invalid), self.assertRaises(ValueError):
                world_actor(
                    dict(self.actor(), environmental_world_action_only=invalid),
                    group_id=178,
                )

    def test_original_destroy_request_uses_target_and_native_action(self):
        self.assertEqual(
            decode_request(struct.pack(">qq", -17801, 437)),
            dict(monster_id=-17801, action_id=437),
        )
