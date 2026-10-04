import unittest
from types import SimpleNamespace as NS
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_effects import _integer


class NullExecutionStatusTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(id=7, hp=20)
        self.fight = NS(
            id=8,
            phase="active",
            current=7,
            actors={7: self.actor},
            owned_stat_effects={},
        )
        self.packets = []
        self.timing = native_time_payload()
        self.handler = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            allocate_uid=lambda: 100,
            context=lambda *a: StatExecutionContext(
                True, True, None, True, self.timing
            ),
        )
        self.invocation = EffectInvocation(999, 200, 7, 7, (0, 0, 0))

    def test_levelzero_status_retained_and_removal_payload_exact(self):
        self.assertTrue(
            self.handler(
                dict(effect_class=400, parameters=[7.0, 9.0, 123.0, 0.0]),
                {},
                self.invocation,
            )
        )
        entry = self.fight.owned_stat_effects[100]
        self.assertEqual((entry["actual"], entry["execution_status"]), (0, 7))
        payload = bytes.fromhex(entry["payload"])
        self.assertIn(self.timing + _integer(2, 7) + _integer(5, 1), payload)
        self.handler.remove(100)
        self.assertEqual([op for op, _ in self.packets], [13497, 13560])
        self.assertIn(payload, self.packets[1][1])
        self.assertEqual(self.actor.hp, 20)

    def test_signed_byte_and_fresh_default(self):
        self.handler(
            dict(effect_class=400, parameters=[130.0, 0.0]), {}, self.invocation
        )
        self.assertEqual(self.fight.owned_stat_effects[100]["execution_status"], -126)
        self.fight.owned_stat_effects.clear()
        self.handler(dict(effect_class=400, parameters=[]), {}, self.invocation)
        self.assertEqual(self.fight.owned_stat_effects[100]["execution_status"], -1)

    def test_malformed_parameter_pairs_reject_before_ownership(self):
        with self.assertRaises(ValueError):
            self.handler(dict(effect_class=400, parameters=[7.0]), {}, self.invocation)
        self.assertEqual((self.packets, self.fight.owned_stat_effects), ([], {}))
