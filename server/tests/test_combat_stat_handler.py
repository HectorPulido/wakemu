import json
import unittest
from itertools import count
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_removal import _identity_fields


class StatHandlerTests(unittest.TestCase):
    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        for a in (pc, npc):
            a.effect_stats = {20: 80, 4: 5}
            a.effect_maxima = {20: 100, 4: 6, 2: 6, 3: 3}
            a.effect_minima = {20: 0, 4: 0, 2: 0, 3: 0}
            a.effect_frozen = frozenset()
        self.registry = json.loads(
            (DATA_ROOT / "effect-characteristic-registry.json").read_text()
        )
        self.packets = []
        uids = count(100)
        self.handler = NativeStatHandler(
            self.fight,
            self.packets,
            self.registry,
            action_id=1,
            allocate_uid=lambda: next(uids),
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
        )
        self.invocation = EffectInvocation(
            123, 1, 7, 7, (0, 0, 0), base_uid=90, state_uid=90
        )

    def test_clamped_gain_and_removal_use_actual_delta(self):
        effect = dict(effect_class=120, parameters=[30, 0])
        self.handler(effect, {}, self.invocation)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
        entry = self.fight.owned_stat_effects[100]
        self.assertEqual((entry["actual"], entry["state_uid"]), (20, 90))
        messages = {}
        fields = _identity_fields(bytes.fromhex(entry["payload"]), messages=messages)
        self.assertEqual(fields[4], 20)
        self.assertEqual(
            _identity_fields(messages[8], integer_fields=(12, 25)), {12: 20, 25: 30}
        )
        self.handler.remove(100)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.assertEqual([p[0] for p in self.packets], [13497, 13560])

    def test_wp_and_ap_modify_authoritative_resources(self):
        self.handler(dict(effect_class=193, parameters=[3, 0]), {}, self.invocation)
        self.assertEqual(self.fight.actors[7].effect_stats[4], 6)
        self.fight.actors[7].ap = 2
        self.handler(dict(effect_class=33, parameters=[2, 0]), {}, self.invocation)
        self.assertEqual(self.fight.actors[7].ap, 4)
        self.handler.remove(101)
        self.assertEqual(self.fight.actors[7].ap, 2)

    def test_null400_does_not_change_characteristics(self):
        self.assertTrue(
            self.handler(dict(effect_class=400, parameters=[]), {}, self.invocation)
        )
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)
        self.assertEqual(self.fight.owned_stat_effects[100]["stat_id"], None)

    def test_resistance_cap_is_rejected_without_mutation(self):
        with self.assertRaises(ValueError):
            self.handler(dict(effect_class=90, parameters=[30, 0]), {}, self.invocation)
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_initial_zero_rejects_without_allocating_owned_effect(self):
        self.assertFalse(
            self.handler(dict(effect_class=120, parameters=[0, 0]), {}, self.invocation)
        )
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.handler(dict(effect_class=120, parameters=[1, 0]), {}, self.invocation)
        self.assertIn(100, self.fight.owned_stat_effects)

    def test_clamped_zero_still_records_native_application(self):
        self.fight.actors[7].effect_stats[20] = 100
        self.assertTrue(
            self.handler(
                dict(effect_class=120, parameters=[30, 0]), {}, self.invocation
            )
        )
        self.assertEqual(self.fight.owned_stat_effects[100]["actual"], 0)
        self.assertEqual([packet[0] for packet in self.packets], [13497])
        self.handler.remove(100)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
