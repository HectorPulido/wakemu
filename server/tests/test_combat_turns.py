import unittest
from wakfu_server.combat_turns import initial_order, tie_hash


def actor(uid, team, initiative, level=1):
    return dict(id=uid, team=team, initiative=initiative, effective_level=level)


class TurnTests(unittest.TestCase):
    def test_average_team_initiative_interleaves_and_keeps_remaining_members(self):
        actors = [
            actor(1, 0, 100),
            actor(2, 0, 0),
            actor(3, 0, 0),
            actor(4, 1, 40),
            actor(5, 1, 40),
        ]
        order = initial_order(3, actors)
        self.assertEqual(order[0], 4 if tie_hash(4, 3, 40) < tie_hash(5, 3, 40) else 5)
        self.assertEqual(order[1], 1)
        self.assertEqual({order[0], order[2]}, {4, 5})
        self.assertEqual(set(order[3:]), {2, 3})

    def test_team_tie_uses_fight_parity_and_effective_level_before_hash(self):
        actors = [actor(1, 0, 10), actor(2, 1, 10)]
        self.assertEqual(initial_order(2, actors), [2, 1])
        self.assertEqual(initial_order(3, actors), [1, 2])
        self.assertEqual(
            initial_order(2, [actor(1, 0, 10, 1), actor(2, 0, 10, 200)]), [2, 1]
        )

    def test_hash_handles_signed_long_ids_and_int_overflow(self):
        self.assertEqual(tie_hash(-1, 1, 0), 0)
        self.assertEqual(tie_hash(65534, 1, 0), 65281)
        self.assertEqual(initial_order(1, []), [])
        self.assertEqual(initial_order(1, [actor(-7, 0, 3)]), [-7])
        with self.assertRaises(ValueError):
            initial_order(1, [actor(1, 0, 3), actor(1, 1, 3)])

    def test_java_integer_average_overflows_and_truncates_toward_zero(self):
        # feq.P adds signed i32 then idiv, rather than unbounded Python average.
        actors = [actor(1, 0, 2147483647), actor(2, 0, 2147483647), actor(3, 1, 0)]
        self.assertEqual(initial_order(3, actors)[0], 3)
        # -1 / 2 becomes zero in Java; equal averages select team1 for even ID.
        actors = [actor(1, 0, -1), actor(2, 0, 0), actor(3, 1, 0)]
        self.assertEqual(initial_order(2, actors)[0], 3)

    def test_native_hash_vectors_and_final_signed_id_tie_break(self):
        # Verified by invoking actual fex.rG from installed wakfu-client.jar.
        expected = {
            -1706442035971439: 34832,
            -1: 228,
            0: 57,
            4: 161,
            5: 0,
            65535: 228,
            9223372036854775807: 228,
        }
        for identity, value in expected.items():
            self.assertEqual(tie_hash(identity, 3, 40), value)
        # Same low16 seed: compare signed long IDs after initiative and level.
        self.assertEqual(
            initial_order(3, [actor(65535, 0, 40), actor(-1, 0, 40)]), [-1, 65535]
        )

    def test_input_iteration_cannot_change_tied_actor_order(self):
        actors = [
            actor(65535, 0, 40),
            actor(-1, 0, 40),
            actor(4, 1, 40),
            actor(5, 1, 40),
        ]
        self.assertEqual(initial_order(3, actors), initial_order(3, reversed(actors)))
