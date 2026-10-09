from copy import deepcopy
from dataclasses import replace
import struct
import json
from pathlib import Path
import unittest
import test_combat_state_child_removal as fixtures
from wakfu_server.combat_retained_effects import (
    RetainedEffect,
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    register_owned_removals,
    default_dispel_eligible,
)
from wakfu_server.combat_dispel import select_dispel, NativeDispelHandler, dispel_flags
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_effect_dispatch import (
    EffectInvocation,
    EffectDispatcher,
    run_effect_transaction,
)
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server import native_catalog


class NativeDispelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StateChildRemovalTests.setUpClass()

    def setUp(self):
        self.fx = fixtures.StateChildRemovalTests()
        self.fx.setUp()
        self.fx.apply()
        self.fight = self.fx.fight

    def records(self, fight=None):
        fight = fight or self.fight
        records = []
        for a in fight.actors.values():
            for s in a.state_ledger.entries:
                records.append(
                    RetainedEffect(
                        s.uid,
                        a.id,
                        310,
                        -1,
                        definition_type=2,
                        definition_dispellable=True,
                        container_present=True,
                        container_type=11,
                        container_is_spell=False,
                        state_unremovable=False,
                        state_dispellable=True,
                    )
                )
        for uid, row in fight.owned_stat_effects.items():
            records.append(
                RetainedEffect(
                    uid,
                    row["target_id"],
                    row["effect_class"],
                    _identity_fields(bytes.fromhex(row["payload"]))[3],
                    owner_uid=row.get("state_uid"),
                    definition_type=2,
                    definition_dispellable=False,
                    container_present=True,
                    container_type=11,
                    container_is_spell=False,
                )
            )
        return records

    def removal(self, view, packets=None):
        packets = self.fx.packets if packets is None else packets
        stat, state = self.fx.handlers(view.fight, packets, lambda: None)
        removal = NativeRetainedRemoval(view)
        register_owned_removals(
            removal, stat_handler=stat, packets=packets, action_id=1
        )
        return removal

    def test_native_default_filter_and_exact_match_bypass_protection(self):
        row = RetainedEffect(
            99,
            7,
            400,
            123,
            definition_type=2,
            definition_dispellable=False,
            container_present=False,
        )
        self.assertFalse(default_dispel_eligible(row))
        self.assertEqual(select_dispel([row], []), ())
        self.assertEqual(select_dispel([row], [123]), (row,))
        self.assertEqual(select_dispel([row], [400, 999]), (row,))
        self.assertEqual(select_dispel([row], [456]), ())
        self.assertEqual(select_dispel([row], [0]), ())

    def test_real145261_display_flag_and_null_pv_leave_qf_unchanged(self):
        catalog = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/spell-effect-trees.json"
            )
        )["effects"]
        effect = catalog["145261"]
        self.assertEqual(effect["native_effect_flags"], [3])
        before = deepcopy(
            (
                self.fight.owned_stat_effects,
                self.fight.state_wire_payloads,
                self.fight.actors[7].state_ledger.entries,
            )
        )

        def forbidden_view():
            raise AssertionError("Native null PV return must precede Qf lookup")

        handler = NativeDispelHandler(
            view_provider=forbidden_view, removal_provider=forbidden_view
        )
        self.assertTrue(
            handler(
                effect,
                effect_profile(effect, 200),
                EffectInvocation(145261, 200, 7, None, (0, 0, 0)),
            )
        )
        self.assertEqual(
            (
                self.fight.owned_stat_effects,
                self.fight.state_wire_payloads,
                self.fight.actors[7].state_ledger.entries,
            ),
            before,
        )

    def test_unknown_flags_and_trigger_flags_without_lifecycle_reject_before_lookup(
        self,
    ):
        for flags in ([999], [3, 3], [True], [6]):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                dispel_flags({"native_effect_flags": flags}, event_lifecycle=None)
        self.assertEqual(
            dispel_flags({"native_effect_flags": [24, 20, 3]}, event_lifecycle=None),
            (24, 20, 3),
        )

    def test_generic_trigger_flag_keeps_lifecycle_and_qe_modifier_noop(self):
        effect = dict(
            effect_class=421,
            native_effect_flags=[6],
            target_masks=[None] * 7,
            native_execution_mode=0,
        )
        phases = []

        class Lifecycle:
            def phase(self, definition, invocation, **facts):
                self_flags = definition["native_effect_flags"]
                phases.append((facts["channel"], facts["value"], tuple(self_flags)))
                if facts["channel"] == 1 and 6 not in self_flags:
                    facts["runner_modifier"].mutate(0, 7, True)

        handler = NativeDispelHandler(
            view_provider=lambda: None,
            removal_provider=lambda view: None,
            allocate_uid=lambda: 777,
            rng=lambda: 0.0,
            event_lifecycle=Lifecycle(),
        )
        invocation = handler.prepare(
            effect, {}, EffectInvocation(145261, 200, 7, None, (0, 0, 0))
        )
        self.assertTrue(handler(effect, {"parameters": [145257]}, invocation))
        self.assertEqual(
            phases, [(1, 0, (6,)), (2, 0, (6,)), (3, 0, (6,)), (4, 0, (6,))]
        )
        self.assertEqual(handler.prepared, {})
        phases.clear()
        effect = dict(effect, native_effect_flags=[])
        invocation = handler.prepare(
            effect, {}, EffectInvocation(145261, 200, 7, None, (0, 0, 0))
        )
        self.assertTrue(handler(effect, {"parameters": [145257]}, invocation))
        # eXe inherits both the no-op eZR.C and Qe.a(int,float,boolean).
        self.assertEqual(phases, [(1, 0, ()), (2, 0, ()), (3, 0, ()), (4, 0, ())])
        invocation = handler.prepare(
            effect, {}, EffectInvocation(145261, 200, 7, None, (0, 0, 0))
        )
        handler.cancel_prepared(invocation)
        handler.cancel_prepared(invocation)
        self.assertEqual(handler.prepared, {})

    def test_activated_clone_preserves_actual_uid_and_removes_retained_target(self):
        catalog = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/spell-effect-trees.json"
            )
        )["effects"]
        self.fx.stat(
            catalog["308267"],
            effect_profile(catalog["308267"], 1),
            EffectInvocation(308267, 1, 7, 7, (0, 0, 0)),
        )
        packets, phases = [], []
        provider = lambda: NativeRetainedEffectView(
            self.fight, self.records(), population_verified_complete=True
        )

        class Lifecycle:
            def phase(self, effect, invocation, **facts):
                phases.append((facts["channel"], facts["uid"], facts["value"]))

        handler = NativeDispelHandler(
            view_provider=provider,
            removal_provider=lambda view: self.removal(view, packets),
            allocate_uid=lambda: self.fail("Activation must use its actual clone UID"),
            rng=lambda: 0.0,
            event_lifecycle=Lifecycle(),
        )
        dispatcher = EffectDispatcher(
            catalog,
            {421: handler},
            resolve=lambda *args: self.fail("Activated target is already rebound"),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda probability, invocation: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (0, 0, 0),
        )
        self.assertTrue(
            dispatcher.execute_activation(
                EffectInvocation(308272, 1, 7, 7, (0, 0, 0)),
                source=None,
                condition_context=lambda *args: ConditionContext({}),
                executable=True,
                allocate_uid=lambda: 777,
            )
        )
        self.assertEqual(phases, [(3, 777, 0), (4, 777, 0)])
        self.assertNotIn(202, self.fight.owned_stat_effects)
        self.assertIn(201, self.fight.owned_stat_effects)
        self.assertEqual([opcode for opcode, _ in packets], [13560])
        self.assertEqual(handler.prepared, {})
        self.assertEqual(handler.activated, set())

    def test_native_probe_container_matrix_and_unknown_metadata(self):
        row = RetainedEffect(
            99,
            7,
            400,
            123,
            definition_type=2,
            definition_dispellable=True,
            container_present=True,
            container_is_spell=False,
        )
        for kind in (1, 3, 11):
            self.assertTrue(default_dispel_eligible(replace(row, container_type=kind)))
        self.assertFalse(default_dispel_eligible(replace(row, container_type=12)))
        self.assertFalse(default_dispel_eligible(replace(row, container_present=False)))
        with self.assertRaisesRegex(ValueError, "container type"):
            default_dispel_eligible(row)
        with self.assertRaisesRegex(ValueError, "presence"):
            default_dispel_eligible(replace(row, container_present=None))
        self.assertEqual(
            select_dispel([replace(row, effect_class=421, container_type=1)], []), ()
        )

    def test_complete_view_rejects_omissions_and_false_attestation(self):
        rows = self.records()
        with self.assertRaisesRegex(ValueError, "population"):
            NativeRetainedEffectView(
                self.fight, rows, population_verified_complete=False
            )
        with self.assertRaisesRegex(ValueError, "omitted"):
            NativeRetainedEffectView(
                self.fight, rows[:1], population_verified_complete=True
            )
        with self.assertRaisesRegex(ValueError, "disagrees"):
            NativeRetainedEffectView(
                self.fight,
                [rows[0], replace(rows[1], generic_effect=123)],
                population_verified_complete=True,
            )

    def test_state_removal_restores_children_before_carrier(self):
        view = NativeRetainedEffectView(
            self.fight, self.records(), population_verified_complete=True
        )
        packets = []
        removal = self.removal(view, packets)
        self.assertEqual([e.uid for e in removal.remove([200])], [201, 200])
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.assertEqual(self.fight.state_wire_payloads, {})
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertEqual(
            [struct.unpack(">i", p[12:16])[0] for op, p in packets], [120, 310]
        )

    def test_new_family_owned_child_requires_callback_then_removes_first(self):
        rows = self.records()
        extra = RetainedEffect(202, 7, 9876, 4321, owner_uid=200)
        view = NativeRetainedEffectView(
            self.fight, [*rows, extra], population_verified_complete=True
        )
        packets = []
        removal = self.removal(view, packets)
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            removal.remove([200])
        self.assertEqual(packets, [])
        self.assertIn(201, self.fight.owned_stat_effects)
        live = {202}
        removed = []
        removal.register(
            9876,
            exists=lambda uid: uid in live,
            remove=lambda uid: (live.remove(uid), removed.append(uid)),
            validate=lambda e: None,
        )
        plan = removal.remove([200, 201])
        self.assertEqual([e.uid for e in plan], [201, 202, 200])
        self.assertEqual(removed, [202])

    def test_targeted_child_removal_retains_owner_state(self):
        rows = self.records()
        view = NativeRetainedEffectView(
            self.fight, rows, population_verified_complete=True
        )
        target = select_dispel(rows, [rows[1].generic_effect])
        self.removal(view).remove(e.uid for e in target)
        self.assertIn(200, self.fight.state_wire_payloads)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)

    def test_real_catalog421_removes_owned400_by_generic_id(self):
        catalog = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/spell-effect-trees.json"
            )
        )["effects"]
        invocation = EffectInvocation(308267, 1, 7, 7, (0, 0, 0))
        self.fx.stat(
            catalog["308267"], effect_profile(catalog["308267"], 1), invocation
        )
        packets = []
        provider = lambda: NativeRetainedEffectView(
            self.fight, self.records(), population_verified_complete=True
        )
        handler = NativeDispelHandler(
            view_provider=provider, removal_provider=lambda v: self.removal(v, packets)
        )
        self.assertTrue(
            handler(
                catalog["308272"],
                effect_profile(catalog["308272"], 1),
                EffectInvocation(308272, 1, 7, 7, (0, 0, 0)),
            )
        )
        self.assertNotIn(202, self.fight.owned_stat_effects)
        self.assertIn(201, self.fight.owned_stat_effects)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 13560)
        self.assertEqual(struct.unpack(">i", packets[0][1][12:16])[0], 400)

    def test_handler_executes_empty_match_and_rolls_back_later_failure(self):
        definition = dict(
            effect_class=421,
            parameters=[123, 0],
            parameter_count=1,
            probability_base=100,
            probability_per_level=0,
            minimum_level=0,
            maximum_level=200,
            criteria="",
            children=[],
            native_effect_flags=[],
            native_execution_mode=0,
        )
        packets = []

        def factory(preview):
            provider = lambda: NativeRetainedEffectView(
                preview, self.records(preview), population_verified_complete=True
            )
            handler = NativeDispelHandler(
                view_provider=provider,
                removal_provider=lambda v: self.removal(v, packets),
            )
            return EffectDispatcher(
                {"1": definition, "2": dict(definition, effect_class=987654)},
                {421: handler},
                resolve=lambda e, i: (i,),
                condition_context=lambda i: ConditionContext({}),
                probability_accepts=lambda p, i: True,
                group_cells=lambda *a: (),
                actor_position=lambda uid: preview.actors[uid].position,
            )

        preview, outcomes = run_effect_transaction(
            self.fight, [EffectInvocation(1, 1, 7, 7, (0, 0, 0))], factory
        )
        self.assertEqual(outcomes, (True,))
        self.assertEqual(packets, [])
        definition["parameters"] = []
        definition["parameter_count"] = 0
        with self.assertRaisesRegex(ValueError, "No handler"):
            run_effect_transaction(
                self.fight,
                [
                    EffectInvocation(1, 1, 7, 7, (0, 0, 0)),
                    EffectInvocation(2, 1, 7, 7, (0, 0, 0)),
                ],
                factory,
            )
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
        self.assertIn(200, self.fight.state_wire_payloads)


if __name__ == "__main__":
    unittest.main()
