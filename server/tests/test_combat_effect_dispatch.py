import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spell_audit import states_catalog
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    UnsupportedEffectExecution,
    run_effect_transaction,
)


def effect(kind, parameters=(), *, criteria="", children=()):
    return dict(
        effect_class=kind,
        parameters=[v for p in parameters for v in (p, 0)],
        parameter_count=len(parameters),
        probability_base=100,
        probability_per_level=0,
        minimum_level=1,
        maximum_level=200,
        criteria=criteria,
        children=list(children),
    )


class EffectDispatchTests(unittest.TestCase):
    def test_bounded_conditional_reentry_stops_before_cycle_guard(self):
        dispatcher = EffectDispatcher(
            {"90": effect(400, criteria="1 > 2")},
            {400: lambda *args: self.fail("Terminating condition must stop execution")},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: self.fail(
                "No roll for a rejected condition"
            ),
            group_cells=lambda *args: (),
            actor_position=lambda identity: (identity, 1, 2),
        )
        self.assertFalse(
            dispatcher.execute(
                EffectInvocation(90, 20, 7, 8, (0, 0, 0)), ancestors=(90,)
            )
        )

    def test_unconditional_recursive_group_still_rejects(self):
        dispatcher = EffectDispatcher(
            {"90": effect(330, (1, 0, 1, 0), children=(90,))},
            {},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (identity, 1, 2),
        )
        with self.assertRaisesRegex(UnsupportedEffectExecution, "Recursive immediate"):
            dispatcher.execute(EffectInvocation(90, 20, 7, 8, (0, 0, 0)))

    def test_native_null_target_group_dispatches_no_children(self):
        effects = {"90": effect(330, children=(91,)), "91": effect(400)}
        dispatcher = EffectDispatcher(
            effects,
            {400: lambda *args: self.fail("Native null bfs must stop the group")},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: self.fail(
                "Target branch must not become a cell branch"
            ),
            actor_position=lambda identity: (identity, 1, 2),
        )
        self.assertFalse(
            dispatcher.execute(EffectInvocation(90, 20, 7, None, (0, 0, 0)))
        )

    def test_native_actor_group_transmits_explicit_pv_and_target_coordinates(self):
        selected = []
        effects = {"90": effect(330, children=(91,)), "91": effect(400)}

        def resolve(definition, invocation):
            selected.append(invocation)
            return (invocation,)

        dispatcher = EffectDispatcher(
            effects,
            {400: lambda *args: True},
            resolve=resolve,
            condition_context=lambda inv: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (identity, 1, 2),
        )
        dispatcher.execute(
            EffectInvocation(90, 20, 7, 8, (0, 0, 0), native_explicit_target=True)
        )
        child = next(inv for inv in selected if inv.reference == 91)
        self.assertEqual(child.target_id, 8)
        self.assertTrue(child.native_explicit_target)
        self.assertEqual(child.cell, (8, 1, 2))

    def test_native_group_cell_and_nontransmitted_branches_have_no_explicit_pv(self):
        for parameters in ((0, 0, 1, 0, 0), (0, 0, 0, 0, 1)):
            with self.subTest(parameters=parameters):
                selected = []
                effects = {
                    "90": effect(330, parameters, children=(91,)),
                    "91": effect(400),
                }

                def resolve(definition, invocation):
                    selected.append(invocation)
                    return (invocation,)

                dispatcher = EffectDispatcher(
                    effects,
                    {400: lambda *args: True},
                    resolve=resolve,
                    condition_context=lambda inv: ConditionContext({}),
                    probability_accepts=lambda *args: True,
                    group_cells=lambda *args: ((3, 4, 0),),
                    actor_position=lambda identity: (identity, 1, 2),
                )
                dispatcher.execute(EffectInvocation(90, 20, 7, 8, (0, 0, 0)))
                children = [inv for inv in selected if inv.reference == 91]
                self.assertEqual(len(children), 1)
                self.assertIsNone(children[0].target_id)
                self.assertFalse(children[0].native_explicit_target)

    def test_relative_authority_selects_children_and_bypasses_second_probability(self):
        from types import SimpleNamespace

        effects = {
            "90": effect(330, (0, 0, 1, 1, 1, 0), children=(91, 92)),
            "91": effect(400),
            "92": effect(400),
        }
        rolls, calls = [], []
        retention = SimpleNamespace(
            is_subscription=lambda *args: False,
            begin_group=lambda *args: None,
            finish_group=lambda *args: None,
            child_context=lambda *args, **kwargs: bytes.fromhex("08001000"),
            child_level_context=lambda *args, default_level, **kwargs: (
                default_level,
                bytes.fromhex("08001000"),
            ),
            probability_bypassed=lambda invocation: invocation.native_context_hex
            is not None
            and invocation.native_context_hex.endswith("08011000"),
        )
        dispatcher = EffectDispatcher(
            effects,
            {400: lambda effect, values, inv: calls.append(inv) is None},
            resolve=lambda effect, inv: (inv,),
            condition_context=lambda inv: ConditionContext({}),
            probability_accepts=lambda chance, inv: rolls.append(inv.reference) is None,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (0, 0, 0),
            group_retention=retention,
            relative_group_children=lambda effect, values, inv, children: (91,),
        )
        self.assertTrue(dispatcher.execute(EffectInvocation(90, 1, 7, -7, (1, 0, 0))))
        self.assertEqual(rolls, [90])
        self.assertEqual([inv.reference for inv in calls], [91])

    def test_random_group_uses_native_selector_and_bypasses_child_probability(self):
        from types import SimpleNamespace
        from wakfu_server.combat_effect_removal import _identity_fields

        effects = {
            "90": effect(341, (1, 1, 1), children=(91, 92)),
            "91": effect(400),
            "92": effect(400),
        }
        # eXR.bbA reads raw So(1), i.e. the second signed parameter operand.
        # This test exercises the actor-target branch and later asserts that
        # the selected child retains target -7; make that source fact explicit.
        effects["90"]["parameters"][1] = 1
        rolls, calls = [], []

        def bypass(inv):
            return (
                inv.native_context_hex is not None
                and _identity_fields(
                    bytes.fromhex(inv.native_context_hex), integer_fields=(1, 2, 4)
                )[1]
                == 1
            )

        retention = SimpleNamespace(
            is_subscription=lambda *a: False,
            begin_group=lambda *a: None,
            finish_group=lambda *a: None,
            child_level_context=lambda *a, default_level, **k: (
                default_level,
                bytes.fromhex("080010002000"),
            ),
            probability_bypassed=bypass,
        )
        dispatcher = EffectDispatcher(
            effects,
            {400: lambda effect, values, inv: calls.append(inv) is None},
            resolve=lambda e, i: (i,),
            condition_context=lambda i: ConditionContext({}),
            probability_accepts=lambda p, i: rolls.append(i.reference) is None,
            group_cells=lambda *a: (),
            actor_position=lambda i: (0, 0, 0),
            group_retention=retention,
            random_group_children=lambda e, v, i, c: (92,),
        )
        self.assertTrue(dispatcher.execute(EffectInvocation(90, 1, 7, -7, (1, 0, 0))))
        self.assertEqual(rolls, [90])
        self.assertEqual([i.reference for i in calls], [92])
        self.assertEqual(calls[0].target_id, -7)

    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        self.effects = {
            "90": effect(330, children=(91, 92)),
            "91": effect(304, (3442, 20)),
            "92": effect(5, (3,), criteria='HasState(3442, "caster")'),
        }
        self.invocation = EffectInvocation(90, 1, 7, -7, (1, 0, 0))

    def factory(self, preview):
        def context(invocation):
            return ConditionContext(
                {
                    "caster": preview.actors[
                        invocation.caster_id
                    ].state_ledger.condition_actor(),
                    "target": preview.actors[
                        invocation.target_id
                    ].state_ledger.condition_actor(),
                }
            )

        def apply_state(effect, values, invocation):
            reference, level = values["parameters"]
            change = preview.apply_state(
                invocation.caster_id,
                invocation.caster_id,
                reference,
                level,
                uid=101,
                catalog=states_catalog(),
            )
            return change.applied is not None

        def damage(effect, values, invocation):
            preview.apply_damage(
                invocation.caster_id, invocation.target_id, values["parameters"][0]
            )
            return True

        return EffectDispatcher(
            self.effects,
            {304: apply_state, 5: damage},
            resolve=lambda effect, invocation: (invocation,),
            condition_context=context,
            probability_accepts=lambda probability, invocation: probability == 100,
            group_cells=lambda *args: (),
            actor_position=lambda actor_id: preview.actors[actor_id].position,
        )

    def test_later_condition_reads_state_from_preceding_effect(self):
        preview, outcomes = run_effect_transaction(
            self.fight, [self.invocation], self.factory
        )
        self.assertEqual(outcomes, (True,))
        self.assertEqual(preview.actors[-7].hp, 17)
        self.assertEqual(preview.actors[7].state_ledger.entries[0].reference, 3442)
        self.assertEqual(self.fight.actors[-7].hp, 20)
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())

    def test_unsupported_later_effect_does_not_commit_prior_damage(self):
        self.effects["93"] = effect(123456)
        self.effects["90"]["children"].append(93)
        with self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(self.fight, [self.invocation], self.factory)
        self.assertEqual(self.fight.actors[-7].hp, 20)
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())

    def test_rejected_condition_does_not_call_missing_handler(self):
        self.effects["93"] = effect(123456, criteria="False")
        invocation = EffectInvocation(93, 1, 7, -7, (1, 0, 0))
        _, outcomes = run_effect_transaction(self.fight, [invocation], self.factory)
        self.assertEqual(outcomes, (False,))

    def test_handler_nested_execution_preserves_cycle_guard(self):
        dispatcher = self.factory(self.fight)
        self.effects["94"] = effect(123456)
        dispatcher.handlers[123456] = lambda e, v, inv: dispatcher.execute(inv)
        invocation = EffectInvocation(94, 1, 7, -7, (1, 0, 0))
        with self.assertRaisesRegex(UnsupportedEffectExecution, "Recursive"):
            dispatcher.execute(invocation)
        # Failed nesting must restore the active chain for later casts.
        dispatcher.handlers[123456] = lambda *args: True
        self.assertTrue(dispatcher.execute(invocation))

    def test_group_cycle_is_explicit_failure(self):
        self.effects["90"]["children"] = [90]
        with self.assertRaisesRegex(UnsupportedEffectExecution, "Recursive"):
            run_effect_transaction(self.fight, [self.invocation], self.factory)

    def test_lethal_damage_then_self_healing_share_resolution(self):
        self.fight.actors[7].hp = 40
        self.effects.update({"95": effect(5, (20,)), "96": effect(25, (10,))})

        def factory(preview):
            dispatcher = self.factory(preview)

            def heal(effect, values, invocation):
                preview.apply_effect_healing(
                    invocation.caster_id, invocation.caster_id, values["parameters"][0]
                )
                return True

            dispatcher.handlers[25] = heal
            return dispatcher

        invocations = [EffectInvocation(ref, 1, 7, -7, (1, 0, 0)) for ref in (95, 96)]
        preview, outcomes = run_effect_transaction(self.fight, invocations, factory)
        self.assertEqual(outcomes, (True, True))
        self.assertEqual((preview.phase, preview.actors[7].hp), ("finished", 50))
        self.assertEqual((self.fight.phase, self.fight.actors[-7].hp), ("active", 20))

    def test_unsupported_effect_after_lethal_damage_rolls_back_death(self):
        self.effects.update({"95": effect(5, (20,)), "96": effect(123456)})
        invocations = [EffectInvocation(ref, 1, 7, -7, (1, 0, 0)) for ref in (95, 96)]
        with self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(self.fight, invocations, self.factory)
        self.assertEqual((self.fight.phase, self.fight.actors[-7].hp), ("active", 20))
        self.assertEqual(self.fight.order, [7, -7])


if __name__ == "__main__":
    unittest.main()
