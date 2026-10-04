import unittest
from itertools import count
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spell_audit import states_catalog
from wakfu_server.combat_state_handler import NativeStateHandler, StateCarrierContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


class NativeStateHandlerTests(unittest.TestCase):
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

    def test_native_state_retains_source_and_owned_carrier(self):
        self.assertTrue(self.apply())
        entry = self.fight.actors[7].state_ledger.entries[0]
        self.assertEqual(
            (entry.reference, entry.level, entry.caster_id, entry.uid),
            (3442, 20, 7, 200),
        )
        self.assertEqual(self.packets[0][0], 13497)
        proto = bytes.fromhex(self.fight.state_wire_payloads[200])
        fields = _identity_fields(proto)
        self.assertEqual((fields[1], fields[2]), (200, 100))
        for child in self.children:
            self.assertEqual(
                (child.base_uid, child.state_uid, child.level), (None, 200, 20)
            )

    def test_accumulation_replaces_only_original_owned_carrier(self):
        self.apply()
        self.apply()
        self.assertEqual([p[0] for p in self.packets], [13497, 13560, 13497])
        self.assertEqual(set(self.fight.state_wire_payloads), {201})
        entry = self.fight.actors[7].state_ledger.entries[0]
        self.assertEqual((entry.uid, entry.level), (201, 40))
        removal = self.packets[1][1]
        self.assertEqual(_identity_fields(removal[18:-16])[1], 200)

    def test_bad_context_rejects_before_ledger_change(self):
        self.handler.context = lambda *args: None
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertEqual(self.packets, [])

    def test_unhandled_child_rolls_back_state_and_carrier_payload(self):
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            run_effect_transaction,
            UnsupportedEffectExecution,
        )
        from wakfu_server.combat_conditions import ConditionContext

        effects = dict(self.catalog["effects"])
        effects["91"] = dict(
            effect_class=304,
            parameters=[3442, 0, 20, 0, -1, 0],
            parameter_count=3,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            criteria="",
            children=[],
        )

        def factory(preview):
            packets = []
            dispatcher = EffectDispatcher(
                effects,
                {},
                resolve=lambda e, i: (i,),
                condition_context=lambda _: ConditionContext({}),
                probability_accepts=lambda p, i: p == 100,
                group_cells=lambda *args: (),
                actor_position=lambda uid: preview.actors[uid].position,
            )
            dispatcher.handlers[304] = NativeStateHandler(
                preview,
                packets,
                self.catalog,
                action_id=1,
                allocate_uid=lambda: 200,
                execute_child=dispatcher.execute,
                context=lambda *args: StateCarrierContext(
                    -1, 0, False, None, 100, False, False, False, 0, None
                ),
            )
            return dispatcher

        with self.assertRaisesRegex(UnsupportedEffectExecution, "No handler"):
            run_effect_transaction(self.fight, [self.invocation], factory)
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertEqual(self.fight.state_wire_payloads, {})

    def test_real_catalogue_applicator_consumes_all_three_parameters(self):
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.spell_audit import catalog as effect_catalog

        effect = effect_catalog()["effects"]["167716"]
        values = effect_profile(effect, 1)
        self.assertEqual(values["parameters"], [3896, 1, -1])
        native = EffectInvocation(167716, 1, 7, 7, (0, 0, 0))
        self.assertTrue(self.handler(effect, values, native))
        event = next(e for e in self.fight.events if e["kind"] == "state_applied")
        self.assertEqual((event["state_id"], event["level"]), (3896, 1))

    def test_non_sentinel_chance_never_silently_applies(self):
        from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution

        for chance in (0, 50, 100, -2):
            with self.assertRaisesRegex(UnsupportedEffectExecution, "chance"):
                self.handler(
                    self.effect, {"parameters": [3442, 20, chance]}, self.invocation
                )
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertEqual(self.packets, [])
