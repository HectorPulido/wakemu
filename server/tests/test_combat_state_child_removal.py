import json
import struct
import unittest
from itertools import count
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spell_audit import states_catalog
from wakfu_server.combat_state_handler import NativeStateHandler, StateCarrierContext
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_dispatch import (
    EffectInvocation,
    EffectDispatcher,
    run_effect_transaction,
    UnsupportedEffectExecution,
)
from wakfu_server.combat_conditions import ConditionContext


class StateChildRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native = states_catalog()
        cls.catalog = dict(native, effects=dict(native["effects"]))
        # Use native3442 replacement policy with an audited current-stat family
        # instead of its indicator. This tests ownership, not spell identity.
        cls.catalog["effects"]["150327"] = dict(
            native["effects"]["150327"],
            effect_class=120,
            parameters=[0, 1],
            parameter_count=1,
        )
        cls.registry = json.loads(
            (DATA_ROOT / "effect-characteristic-registry.json").read_text()
        )

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
        pc.effect_stats = {20: 80}
        pc.effect_minima = {20: 0}
        pc.effect_maxima = {20: 100}
        pc.effect_frozen = frozenset()
        self.packets = []
        self.uid = count(200)
        self.stat, self.handler = self.handlers(
            self.fight, self.packets, lambda: next(self.uid)
        )
        self.invocation = EffectInvocation(91, 1, 7, 7, (0, 0, 0))

    def handlers(self, fight, packets, allocate):
        stat = NativeStatHandler(
            fight,
            packets,
            self.registry,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
        )
        state = NativeStateHandler(
            fight,
            packets,
            self.catalog,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *a: StateCarrierContext(
                -1, 0, False, None, 100, False, False, False, 0, None
            ),
            execute_child=lambda i: stat(
                self.catalog["effects"][str(i.reference)], {}, i
            ),
            remove_child_effect=stat.remove,
        )
        return stat, state

    def apply(self):
        return self.handler(
            dict(effect_class=304), dict(parameters=[3442, 20, -1]), self.invocation
        )

    def test_replacement_undoes_actual_bonus_before_carrier_then_reapplies(self):
        self.assertTrue(self.apply())
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
        old = self.fight.actors[7].state_ledger.entries[0]
        self.assertEqual(self.fight.owned_stat_effects[201]["actual"], 20)
        self.assertTrue(self.apply())
        new = self.fight.actors[7].state_ledger.entries[0]
        self.assertEqual((old.uid, new.uid, new.level), (200, 202, 40))
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
        self.assertEqual(set(self.fight.owned_stat_effects), {203})
        self.assertEqual(self.fight.owned_stat_effects[203]["state_uid"], 202)
        self.assertEqual(self.fight.owned_stat_effects[203]["actual"], 20)
        classes = [
            struct.unpack(">i", data[13:17] if opcode == 12613 else data[12:16])[0]
            for opcode, data in self.packets
        ]
        self.assertEqual(
            list(zip([opcode for opcode, data in self.packets], classes)),
            [
                (12613, 310),
                (13497, 120),
                (13560, 120),
                (13560, 310),
                (12613, 310),
                (13497, 120),
            ],
        )
        self.handler.remove_state_children(new.uid)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_state_uid_ownership_leaves_unrelated_retained_effect(self):
        self.apply()
        unrelated = EffectInvocation(500, 1, 7, 7, (0, 0, 0), base_uid=90, state_uid=90)
        self.stat(dict(effect_class=400, parameters=[]), {}, unrelated)
        self.apply()
        self.assertIn(202, self.fight.owned_stat_effects)
        self.assertEqual(self.fight.owned_stat_effects[202]["state_uid"], 90)
        self.assertNotIn(201, self.fight.owned_stat_effects)

    def test_missing_or_ineffective_callback_rejects_retained_children(self):
        self.apply()
        before = len(self.packets)
        original_entries = self.fight.actors[7].state_ledger.entries
        definition = dict(
            effect_class=304,
            parameters=[3442, 0, 20, 0, -1, 0],
            parameter_count=3,
            probability_base=100,
            probability_per_level=0,
            minimum_level=0,
            maximum_level=200,
            criteria="",
            children=[],
        )

        def factory(preview):
            uids = count(300)
            stat, state = self.handlers(preview, [], lambda: next(uids))
            state.remove_child_effect = None
            return EffectDispatcher(
                {"91": definition},
                {304: state},
                resolve=lambda e, i: (i,),
                condition_context=lambda i: ConditionContext({}),
                probability_accepts=lambda p, i: True,
                group_cells=lambda *a: (),
                actor_position=lambda uid: preview.actors[uid].position,
            )

        with self.assertRaisesRegex(
            UnsupportedEffectExecution, "explicit removal callback"
        ):
            run_effect_transaction(self.fight, [self.invocation], factory)
        self.assertEqual(len(self.packets), before)
        self.assertEqual(self.fight.actors[7].state_ledger.entries, original_entries)
        self.assertIn(200, self.fight.state_wire_payloads)
        self.assertIn(201, self.fight.owned_stat_effects)
        self.handler.remove_child_effect = lambda uid: None
        with self.assertRaisesRegex(UnsupportedEffectExecution, "did not remove"):
            self.handler.remove_state_children(200)

    def test_callback_bound_to_original_fight_cannot_mutate_preview(self):
        from copy import deepcopy

        preview = deepcopy(self.fight)
        uids = count(300)
        _, handler = self.handlers(preview, [], lambda: next(uids))
        # Build a retained child on preview, then deliberately bind wrong owner.
        handler(
            dict(effect_class=304), dict(parameters=[3442, 20, -1]), self.invocation
        )
        handler.remove_child_effect = self.stat.remove
        with self.assertRaisesRegex(
            UnsupportedEffectExecution, "another fight preview"
        ):
            handler.remove_state_children(300)
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_failure_after_replacement_and_reapplied_child_rolls_back_original(self):
        self.apply()
        original_payloads = dict(self.fight.state_wire_payloads)
        original_children = dict(self.fight.owned_stat_effects)
        original_entries = self.fight.actors[7].state_ledger.entries
        definitions = dict(self.catalog["effects"])
        definitions["91"] = dict(
            effect_class=304,
            parameters=[3442, 0, 20, 0, -1, 0],
            parameter_count=3,
            probability_base=100,
            probability_per_level=0,
            minimum_level=0,
            maximum_level=200,
            criteria="",
            children=[],
        )

        def factory(preview):
            packets = []
            uids = count(400)
            stat, state = self.handlers(preview, packets, lambda: next(uids))

            def fail_after_child(invocation):
                stat(self.catalog["effects"][str(invocation.reference)], {}, invocation)
                raise UnsupportedEffectExecution("later nested effect failure")

            state.execute_child = fail_after_child
            return EffectDispatcher(
                definitions,
                {304: state},
                resolve=lambda e, i: (i,),
                condition_context=lambda i: ConditionContext({}),
                probability_accepts=lambda p, i: True,
                group_cells=lambda *a: (),
                actor_position=lambda uid: preview.actors[uid].position,
            )

        with self.assertRaisesRegex(
            UnsupportedEffectExecution, "later nested effect failure"
        ):
            run_effect_transaction(self.fight, [self.invocation], factory)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
        self.assertEqual(self.fight.actors[7].state_ledger.entries, original_entries)
        self.assertEqual(self.fight.owned_stat_effects, original_children)
        self.assertEqual(self.fight.state_wire_payloads, original_payloads)
        self.assertEqual(len(self.packets), 2)
