import unittest
from itertools import count
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spell_audit import states_catalog
from wakfu_server.combat_state_handler import NativeStateHandler, StateCarrierContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


class NativeStateDecurseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = states_catalog()

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
        self.packets = []
        self.children = []
        self.uids = count(200)
        self.handler = NativeStateHandler(
            self.fight,
            self.packets,
            self.catalog,
            action_id=1,
            allocate_uid=lambda: next(self.uids),
            execute_child=lambda inv: self.children.append(inv),
            context=lambda *args: StateCarrierContext(
                -1, 0, False, None, 100, False, False, False, 0, None
            ),
        )
        self.effect = dict(effect_class=304)
        self.invocation = EffectInvocation(91, 1, 7, 7, (0, 0, 0))

    def apply(self):
        return self.handler(
            self.effect, {"parameters": [3442, 20, -1]}, self.invocation
        )

    def test_full_removal_owns_payload_and_preserves_other_carriers(self):
        from wakfu_server.combat_state_decurse import NativeStateDecurseHandler

        self.apply()
        handler = NativeStateDecurseHandler(
            self.fight,
            self.packets,
            self.catalog,
            action_id=2,
            state_handler=self.handler,
        )
        self.assertTrue(
            handler({"effect_class": 321}, {"parameters": [3442]}, self.invocation)
        )
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertNotIn(200, self.fight.state_wire_payloads)
        self.assertEqual(self.packets[-1][0], 13560)

    def test_reduction_reapplies_with_decurse_invocation(self):
        from wakfu_server.combat_state_decurse import NativeStateDecurseHandler

        self.apply()
        calls = []
        handler = NativeStateDecurseHandler(
            self.fight,
            self.packets,
            self.catalog,
            action_id=2,
            state_handler=self.handler,
            reapply_state=lambda effect, ref, level, inv: calls.append(
                (ref, level, inv)
            ),
        )
        handler({"effect_class": 321}, {"parameters": [3442, 7]}, self.invocation)
        self.assertEqual(calls, [(3442, 13, self.invocation)])

    def test_unsupported_reduction_fails_before_mutating(self):
        from wakfu_server.combat_state_decurse import NativeStateDecurseHandler
        from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution

        self.apply()
        handler = NativeStateDecurseHandler(
            self.fight,
            self.packets,
            self.catalog,
            action_id=2,
            state_handler=self.handler,
        )
        with self.assertRaises(UnsupportedEffectExecution):
            handler({"effect_class": 321}, {"parameters": [3442, 7]}, self.invocation)
        self.assertEqual(self.fight.actors[7].state_ledger.entries[0].level, 20)
