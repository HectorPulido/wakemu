import unittest
from types import SimpleNamespace
from wakfu_server.combat_affiliation_effect import (
    NativeAffiliationHandler,
    remove_affiliation,
)
from wakfu_server.combat_directional_area import directional_area_orientation
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class AffiliationAndDirectionalAreaTests(unittest.TestCase):
    def test_actual_affiliation_signed_byte_stacking_and_saved_restoration(self):
        actor = SimpleNamespace(id=7, team=0)
        fight = SimpleNamespace(
            id=1, phase="active", actors={7: actor}, owned_stat_effects={}
        )
        ids = iter((901, 902))
        packets = []
        handler = NativeAffiliationHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(ids),
            rng=lambda: 0.5,
            context=lambda *args: StatExecutionContext(True, True, None, True, b""),
            authority=lambda *args: SimpleNamespace(targeting={"is_amO": True}),
        )
        invocation = EffectInvocation(123, 1, 7, 7, (0, 0, 0))
        for amount, expected in ((130, -126), (1, 1)):
            self.assertTrue(
                handler(
                    {"effect_class": 1030, "parameters": [amount, 0]}, {}, invocation
                )
            )
            self.assertEqual(actor.native_fight_affiliation, expected)
            self.assertEqual(actor.team, 0)
        remove_affiliation(handler, 902)
        self.assertEqual(actor.native_fight_affiliation, -126)
        remove_affiliation(handler, 901)
        self.assertEqual(actor.native_fight_affiliation, 0)
        self.assertEqual([op for op, _ in packets], [13497, 13497, 13560, 13560])

    def test_adjacent_orientation_and_far_native_north_east_fallback(self):
        vectors = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))
        for direction, (x, y) in enumerate(vectors):
            self.assertEqual(
                directional_area_orientation((0, 0, 0), (x, y, 0)), direction
            )
        self.assertEqual(directional_area_orientation((0, 0, 0), (0, 0, 0)), -1)
        self.assertEqual(directional_area_orientation((0, 0, 0), (2, 0, 0)), 7)
        self.assertEqual(directional_area_orientation((0, 0, 0), (0, -2, 0)), 7)
