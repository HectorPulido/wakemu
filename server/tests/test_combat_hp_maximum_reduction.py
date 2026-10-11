"""Differential expectations from installed eVi21/eWO and actual fff HP."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_hp_raw import SOURCE, hp_raw_current
from wakfu_server.combat_hp_maximum_reduction import (
    apply_hp_maximum_reduction,
    remove_hp_maximum_reduction,
)


def actor(current=60, raw_current=None):
    return SimpleNamespace(
        id=7,
        hp=current,
        max_hp=100,
        effect_stats={1: current},
        effect_maxima={1: 100},
        effect_minima={1: 0},
        effect_base_maxima={1: 100},
        effect_base_minima={1: 0},
        effect_percentages={1: 0},
        effect_frozen=set(),
        native_hp_raw_current_source=SOURCE,
        effect_hp_raw_current=current if raw_current is None else raw_current,
    )


def snapshot(a):
    return [a.hp, a.max_hp, a.effect_minima[1], hp_raw_current(a)]


class HPMaximumReductionTests(unittest.TestCase):
    def test_native_application_removal_and_events(self):
        # Inputs: current, requested, native PK.aZD, reduce, restore.
        rows = [
            ([60, 25, 2, 1, 1], 25, [35, 75, 0, 35], (2, 4), [60, 100, 0, 60]),
            ([60, 150, 0, 1, 1], 99, [0, 1, 0, 0], (2, 4), [99, 100, 0, 99]),
            ([60, 150, 2, 1, 1], 150, [0, 0, 0, 0], (2, 4), [100, 100, 0, 100]),
            ([60, 25, 2, 0, 1], 25, [60, 75, 0, 60], (4,), [85, 100, 0, 85]),
            ([60, 25, 2, 1, 0], 25, [35, 75, 0, 35], (2, 4), [35, 100, 0, 35]),
            ([60, -25, 2, 1, 1], -25, [85, 125, 25, 85], (2, 4), [60, 100, 0, 60]),
            ([1, 99, 0, 1, 1], 99, [0, 1, 0, 0], (2, 4), [99, 100, 0, 99]),
        ]
        for inputs, applied, after, events, removed in rows:
            with self.subTest(inputs=inputs):
                current, amount, mode, reduce, restore = inputs
                a = actor(current)
                self.assertEqual(
                    apply_hp_maximum_reduction(
                        a, amount, definition_type=mode, reduce_current=bool(reduce)
                    ),
                    (applied, events),
                )
                self.assertEqual(snapshot(a), after)
                remove_hp_maximum_reduction(a, applied, restore_current=bool(restore))
                self.assertEqual(snapshot(a), removed)

    def test_hidden_raw_hp_survives_maximum_only_change(self):
        a = actor(100, 125)
        self.assertEqual(
            apply_hp_maximum_reduction(a, 25, definition_type=2, reduce_current=False),
            (25, (2, 4)),
        )
        self.assertEqual(snapshot(a), [75, 75, 0, 125])
        remove_hp_maximum_reduction(a, 25, restore_current=False)
        self.assertEqual(snapshot(a), [100, 100, 0, 125])

    def test_frozen_current_keeps_raw_operand(self):
        a = actor()
        a.effect_frozen = {1}
        apply_hp_maximum_reduction(a, 25, definition_type=2, reduce_current=True)
        self.assertEqual(snapshot(a), [60, 75, 0, 60])
        remove_hp_maximum_reduction(a, 25, restore_current=True)
        self.assertEqual(snapshot(a), [60, 100, 0, 60])

    def test_missing_raw_authority_fails_before_any_mutation(self):
        a = actor()
        a.native_hp_raw_current_source = None
        with self.assertRaises(ValueError):
            apply_hp_maximum_reduction(a, 25, definition_type=2, reduce_current=True)
        self.assertEqual((a.hp, a.max_hp, a.effect_base_minima[1]), (60, 100, 0))

    def test_unknown_definition_and_boolean_authority_rejected(self):
        for mode in (None, True, 3):
            with self.assertRaises(ValueError):
                apply_hp_maximum_reduction(
                    actor(), 25, definition_type=mode, reduce_current=True
                )
        with self.assertRaises(ValueError):
            remove_hp_maximum_reduction(actor(), 25, restore_current=1)


class HPMaximumReductionHandlerTests(unittest.TestCase):
    def setup_handler(self, retained=True):
        from test_combat_maximum_resource import MaximumResourceTests
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_hp_maximum_reduction import (
            NativeHPMaximumReductionHandler,
        )

        fixture = MaximumResourceTests()
        fixture.setUp()
        a = fixture.actor
        a.hp = a.effect_stats[1] = 60
        a.max_hp = a.effect_maxima[1] = 100
        a.effect_minima[1] = a.effect_base_minima[1] = a.effect_percentages[1] = 0
        a.effect_base_maxima[1] = 100
        a.native_hp_raw_current_source = SOURCE
        a.effect_hp_raw_current = 60
        context = StatExecutionContext(True, True, None, retained, None)
        handler = NativeHPMaximumReductionHandler(
            fixture.fight,
            fixture.packets,
            action_id=2,
            allocate_uid=fixture.handler.allocate_uid,
            context=lambda *args: context,
            rng=lambda *args: 0,
            probability=lambda *args: True,
        )
        effect = dict(
            effect_class=21,
            parameters=[25.0, 0.0],
            native_execution_mode=2,
            target_masks=[[] for _ in range(7)],
        )
        return fixture, handler, effect

    def test_retained_apply_ordinary_removal_routes_to_raw_setters(self):
        from wakfu_server.combat_stat_handler import NativeStatHandler

        f, h, e = self.setup_handler()
        self.assertTrue(h(e, (), f.invocation))
        self.assertEqual(snapshot(f.actor), [35, 75, 0, 35])
        self.assertEqual(f.fight.owned_stat_effects[101]["family"], "eWO_HP")
        NativeStatHandler(
            f.fight,
            f.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        ).remove(101)
        self.assertEqual(snapshot(f.actor), [60, 100, 0, 60])
        self.assertEqual([p[0] for p in f.packets], [12613, 13560])

    def test_prepared_native_phases_preserve_source_value_and_events(self):
        f, h, e = self.setup_handler()
        phases = []
        registered = []

        class Lifecycle:
            def phase(self, e, i, **kw):
                phases.append((kw["channel"], kw["value"], kw["_event_ids"]))

            def register_applied(self, e, i, uid):
                registered.append(uid)

        h.event_lifecycle = Lifecycle()
        invocation = h.prepare(e, (), f.invocation)
        self.assertTrue(h(e, (), invocation))
        self.assertEqual(
            phases, [(1, 0, (4,)), (2, 25, (4,)), (3, 25, (2, 4)), (4, 25, (2, 4))]
        )
        self.assertEqual(registered, [101])
        self.assertFalse(h.prepared_maxima)
        self.assertFalse(h.runner_amounts)

    def test_failed_chance_does_not_change_hp_or_emit_application(self):
        f, h, e = self.setup_handler()
        e["parameters"] = [25.0, 0.0, 50.0, 0.0]
        h.probability = lambda *args: False
        self.assertFalse(h(e, (), f.invocation))
        self.assertEqual(snapshot(f.actor), [60, 100, 0, 60])
        self.assertEqual(f.packets, [])
        self.assertEqual(f.fight.owned_stat_effects, {})

    def test_instant_effect_and_zero_value_event_contract(self):
        f, h, e = self.setup_handler(retained=False)
        e["parameters"] = [0.0, 0.0]
        self.assertTrue(h(e, (), f.invocation))
        self.assertEqual(f.fight.owned_stat_effects, {})
        self.assertEqual(snapshot(f.actor), [60, 100, 0, 60])


class HPMaximumReductionMutationTests(unittest.TestCase):
    setup_handler = HPMaximumReductionHandlerTests.setup_handler

    def test_l2_mutation_uses_actual_raw_setter_amount(self):
        f, h, e = self.setup_handler()
        phases = []

        class Lifecycle:
            def phase(self, e, i, **kw):
                phases.append(kw["channel"])
                if kw["channel"] == 2:
                    kw["runner_modifier"].mutate(1, 40, True)

            def register_applied(self, *args):
                pass

        h.event_lifecycle = Lifecycle()
        invocation = h.prepare(e, (), f.invocation)
        self.assertTrue(h(e, (), invocation))
        self.assertEqual(snapshot(f.actor), [20, 60, 0, 20])
        self.assertEqual(f.fight.owned_stat_effects[101]["actual"], 40)
        self.assertEqual(phases, [1, 2, 3, 4])

    def test_postphase_mutation_is_the_retained_removal_value(self):
        f, h, e = self.setup_handler()

        class Lifecycle:
            def phase(self, e, i, **kw):
                if kw["channel"] == 4:
                    kw["runner_modifier"].mutate(1, 10, True)

            def register_applied(self, *args):
                pass

        h.event_lifecycle = Lifecycle()
        invocation = h.prepare(e, (), f.invocation)
        self.assertTrue(h(e, (), invocation))
        self.assertEqual(snapshot(f.actor), [35, 75, 0, 35])
        self.assertEqual(f.fight.owned_stat_effects[101]["actual"], 10)

    def test_phase_error_releases_live_runner_without_resource_mutation(self):
        f, h, e = self.setup_handler()

        class Lifecycle:
            def phase(self, *args, **kw):
                raise ValueError("phase fixture")

        h.event_lifecycle = Lifecycle()
        with self.assertRaisesRegex(ValueError, "phase fixture"):
            h.prepare(e, (), f.invocation)
        self.assertEqual(snapshot(f.actor), [60, 100, 0, 60])
        self.assertFalse(h.prepared_maxima)
        self.assertFalse(h.runner_amounts)


class HPMaximumReductionTriggerSourceTests(unittest.TestCase):
    setup_handler = HPMaximumReductionHandlerTests.setup_handler

    def test_fresh_null_qe_preserves_native_minus_one_literal(self):
        f, h, e = self.setup_handler()
        e["parameters"] = [-1.0, 0.0]
        self.assertIsNone(f.invocation.native_trigger_context)
        self.assertTrue(h(e, (), f.invocation))
        self.assertEqual(snapshot(f.actor), [61, 101, 1, 61])
        self.assertEqual(f.fight.owned_stat_effects[101]["actual"], -1)
