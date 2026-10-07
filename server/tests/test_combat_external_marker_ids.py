import unittest

from wakfu_server.combat.combat_multiplayer_wire import (
    EXTERNAL_MARKER_UID_BASE,
    external_marker_actor_id,
)


class ExternalMarkerActorIdTests(unittest.TestCase):
    def test_ids_are_stable_in_reserved_signed_i64_namespace(self):
        first = external_marker_actor_id(1)
        next_id = external_marker_actor_id(2)
        largest_fight = external_marker_actor_id(2**31 - 1)

        self.assertEqual(first, EXTERNAL_MARKER_UID_BASE + 1)
        self.assertEqual(next_id, first + 1)
        self.assertLess(largest_fight, 2**63)
        self.assertEqual(len({first, next_id, largest_fight}), 3)

    def test_rejects_invalid_or_bool_fight_ids(self):
        for fight_id in (0, -1, 2**31, True, 1.0, "7"):
            with self.subTest(fight_id=fight_id):
                with self.assertRaises(ValueError):
                    external_marker_actor_id(fight_id)


if __name__ == "__main__":
    unittest.main()
