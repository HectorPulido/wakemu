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

    def lifecycle_handler(self, *, reapply=None):
        from types import SimpleNamespace
        from wakfu_server.combat_state_decurse import NativeStateDecurseHandler

        self.phases = []

        def phase(effect, invocation, **source):
            levels = tuple(
                entry.level for entry in self.fight.actors[7].state_ledger.entries
            )
            self.phases.append(
                (
                    source["channel"],
                    source["value"],
                    levels,
                    source["_event_ids"],
                    source["uid"],
                    invocation,
                )
            )

        return NativeStateDecurseHandler(
            self.fight,
            self.packets,
            self.catalog,
            action_id=2,
            state_handler=self.handler,
            reapply_state=reapply,
            allocate_uid=lambda: next(self.uids),
            rng=lambda: 0.0,
            event_lifecycle=SimpleNamespace(phase=phase),
        )

    def produced_effect(self):
        return {"effect_class": 321, "target_masks": [None] * 6 + [[2288]]}

    def test_reduction_delivers_native_source_after_reapplication(self):
        from wakfu_server.combat_native_events import subscription_selection

        self.apply()

        def reapply(effect, reference, level, invocation):
            self.handler(
                self.effect, {"parameters": [reference, level, -1]}, invocation
            )

        decurse = self.lifecycle_handler(reapply=reapply)
        selected = decurse.prepare(
            self.produced_effect(), {"parameters": [3442, 7]}, self.invocation
        )
        self.assertTrue(
            decurse(self.produced_effect(), {"parameters": [3442, 7]}, selected)
        )
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in self.phases],
            [(1, 0, (20,)), (2, 3442, (20,)), (3, 3442, (13,)), (4, 3442, (13,))],
        )
        self.assertEqual({row[4] for row in self.phases}, {selected.native_running_uid})
        self.assertTrue(all(row[3] == (0, 2225, 2288) for row in self.phases))
        self.assertTrue(
            all(
                row[5].reference == 91
                and row[5].caster_id == 7
                and row[5].target_id == 7
                for row in self.phases
            )
        )
        # Actual398436's third-phase subscription becomes eligible on2288,
        # after the reduced state is available to its condition/group level.
        self.assertEqual(
            subscription_selection(
                masks=[None, None, None, [2287, 2288], None, None, None],
                event_ids=self.phases[2][3],
                channel=3,
                global_subscription=False,
                reversed_subscription=False,
                flags=[],
                source_present=True,
            ),
            "activate",
        )
        self.assertEqual(decurse.prepared, {})

    def test_event_clone_calculates_reference_before_first_phase(self):
        self.apply()
        decurse = self.lifecycle_handler()
        selected = decurse.prepare_activation(
            self.produced_effect(),
            {"parameters": [3442]},
            self.invocation,
            clone_uid=901,
        )
        self.assertTrue(
            decurse(self.produced_effect(), {"parameters": [3442]}, selected)
        )
        self.assertEqual(
            [(row[0], row[1], row[2]) for row in self.phases],
            [(1, 3442, (20,)), (2, 3442, (20,)), (3, 3442, ()), (4, 3442, ())],
        )
        self.assertEqual({row[4] for row in self.phases}, {901})
        self.assertEqual([packet[0] for packet in self.packets], [12613, 13560])

    def test_empty_selection_stays_false_but_frs_only_suppresses_notification(self):
        decurse = self.lifecycle_handler()
        self.assertFalse(
            decurse(self.produced_effect(), {"parameters": [3442]}, self.invocation)
        )
        self.assertEqual([row[0] for row in self.phases], [1, 2, 3, 4])
        self.assertEqual(self.packets, [])
        self.assertEqual(decurse.prepared, {})
