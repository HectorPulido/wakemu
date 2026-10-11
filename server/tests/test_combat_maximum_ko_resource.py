"""Original eVi991/eWN PC14 oracle and shared maximum handler integration."""
import unittest
from dataclasses import replace
from wakfu_server.combat_stat_handler import NativeStatHandler


class MaximumKOResourceTests(unittest.TestCase):
    def fixture(self, raw_max=3, current=3, percent=0, frozen=False, raw_current=None):
        from test_combat_maximum_resource import MaximumResourceTests

        f = MaximumResourceTests()
        f.setUp()
        a = f.actor
        maximum = raw_max + raw_max * percent // 100
        for name, value in (
            ("effect_stats", current),
            ("effect_maxima", maximum),
            ("effect_base_maxima", raw_max),
            ("effect_minima", 0),
            ("effect_base_minima", 0),
            ("effect_percentages", percent),
        ):
            getattr(a, name)[14] = value
        if raw_current is not None:
            a.native_copy_pa_source = dict(
                producer="eHI.pRU.ffh.a",
                actor_id=a.id,
                profile=2382,
                effect_reference=1,
                source_actor_id=8,
            )
            a.effect_characteristic_raw_currents = {14: raw_current}
        a.effect_frozen = frozenset({14}) if frozen else frozenset()
        f.handler.rng = lambda: 0
        return f

    def apply(self, f, amount=2, apply=True, remove=True):
        e = dict(
            effect_class=991,
            parameters=[float(amount), 0.0, int(apply), 0.0, int(remove), 0.0],
            native_effect_flags=[],
            target_masks=[None] * 7,
        )
        return f.handler(e, (), replace(f.invocation, reference=87039)), e

    def remove(self, f):
        NativeStatHandler(
            f.fight,
            f.packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=None,
            context=None,
        ).remove(101)

    def snapshot(self, f):
        a = f.actor
        raw = getattr(a, "effect_characteristic_raw_currents", {}).get(
            14, a.effect_stats[14]
        )
        return [a.effect_stats[14], a.effect_maxima[14], a.effect_base_maxima[14], raw]

    def test_actual_native_cap_minus_one_and_ordinary_removal(self):
        for amount in (2, 10):
            with self.subTest(amount=amount):
                f = self.fixture()
                before = (f.actor.hp, f.actor.ap, f.actor.mp)
                self.assertTrue(self.apply(f, amount)[0])
                self.assertEqual(
                    self.snapshot(f), [3 + amount, 3 + amount, 3 + amount, 3 + amount]
                )
                self.assertEqual((f.actor.hp, f.actor.ap, f.actor.mp), before)
                self.assertEqual(
                    (
                        f.fight.owned_stat_effects[101]["stat_id"],
                        f.fight.owned_stat_effects[101]["actual"],
                    ),
                    (14, amount),
                )
                self.remove(f)
                self.assertEqual(self.snapshot(f), [3, 3, 3, 3])

    def test_native_percentage_removal_uses_raw_amount_not_effective_delta(self):
        f = self.fixture(raw_max=4, current=3, percent=50)
        self.apply(f)
        self.assertEqual(self.snapshot(f), [6, 9, 6, 6])
        self.assertEqual(f.fight.owned_stat_effects[101]["effective_delta"], 3)
        self.remove(f)
        self.assertEqual(self.snapshot(f), [4, 6, 4, 4])

    def test_native_current_flags_and_negative_amount(self):
        for amount, apply, remove, after, removed in (
            (2, False, True, [3, 5, 5, 3], [1, 3, 3, 1]),
            (2, True, False, [5, 5, 5, 5], [3, 3, 3, 3]),
            (-2, True, True, [0, 1, 1, 0], [1, 3, 3, 1]),
        ):
            with self.subTest(amount=amount, apply=apply, remove=remove):
                f = self.fixture()
                self.apply(f, amount, apply, remove)
                self.assertEqual(self.snapshot(f), after)
                self.remove(f)
                self.assertEqual(self.snapshot(f), removed)

    def test_copied_frozen_raw_current_reappears_on_bound_changes(self):
        f = self.fixture(current=3, frozen=True, raw_current=5)
        self.apply(f)
        self.assertEqual(self.snapshot(f), [5, 5, 5, 5])
        self.remove(f)
        self.assertEqual(self.snapshot(f), [3, 3, 3, 5])

    def test_missing_frozen_raw_authority_rejects_without_writes(self):
        f = self.fixture(frozen=True)
        with self.assertRaises(ValueError):
            self.apply(f)
        self.assertEqual(self.snapshot(f), [3, 3, 3, 3])
        self.assertEqual(f.packets, [])
        self.assertEqual(f.fight.owned_stat_effects, {})

    def test_original_event_metadata_and_all_four_phases(self):
        f = self.fixture()
        phases = []

        class Events:
            def phase(self, e, i, **kw):
                phases.append((kw["channel"], kw["_event_ids"]))

            def register_applied(self, *args):
                pass

        f.handler.event_lifecycle = Events()
        effect = dict(
            effect_class=991,
            parameters=[2.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            native_effect_flags=[],
            target_masks=[None] * 7,
        )
        invocation = f.handler.prepare(
            effect, (), replace(f.invocation, reference=87039)
        )
        self.assertTrue(f.handler(effect, (), invocation))
        self.assertEqual(phases, [(1, (0,)), (2, (0,)), (3, (0,)), (4, (0,))])


class MaximumKOFactoryTests(unittest.TestCase):
    def test_shared_factory_routes_actual_native_family991(self):
        from test_combat_effect_runtime import NativeRuntimeFactoryTests, definition
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fixture = NativeRuntimeFactoryTests()
        fixture.spells = {"effects": {}}
        fixture.states = {"states": {}, "effects": {}}
        fixture.registry = {"effects": {}}
        fixture.setUp()
        a = fixture.fight.actors[7]
        a.effect_base_maxima = dict(a.effect_maxima)
        a.effect_base_minima = dict(a.effect_minima)
        a.effect_percentages = {key: 0 for key in a.effect_stats}
        for name, value in (
            ("effect_stats", 3),
            ("effect_maxima", 3),
            ("effect_base_maxima", 3),
            ("effect_minima", 0),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            getattr(a, name)[14] = value
        effects = {"87039": definition(991, [2.0, 0.0, 1.0, 0.0, 0.0, 0.0])}
        dispatcher, packets = fixture.factory(effects=effects)(fixture.fight, {})
        dispatcher.execute(EffectInvocation(87039, 1, 7, 7, (0, 0, 0)))
        self.assertEqual((a.effect_stats[14], a.effect_maxima[14]), (5, 5))
        self.assertEqual((a.hp, a.ap, a.mp), (60, 6, 3))
        self.assertEqual([p[0] for p in packets], [12613])
