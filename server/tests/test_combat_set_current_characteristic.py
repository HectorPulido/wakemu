"""eWX setter lifecycle preserves post-clamp value and immutable removal delta."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from wakfu_server.combat_set_current_characteristic import (
    NativeSetCurrentCharacteristicHandler,
    remove_set_current_characteristic,
    set_current_transition,
    remove_set_current_transition,
    set_current_registry,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class SetCurrentCharacteristicTests(unittest.TestCase):
    def test_java_wrap_clamp_frozen_and_intervening_change(self):
        self.assertEqual(
            set_current_transition(
                current=10, requested=100, minimum=-5000, maximum=50
            ),
            (50, 40),
        )
        self.assertEqual(
            remove_set_current_transition(
                current=20, delta=40, minimum=-5000, maximum=50
            ),
            -20,
        )
        self.assertEqual(
            set_current_transition(
                current=10, requested=-100, minimum=-50, maximum=50, frozen=True
            ),
            (10, 0),
        )
        self.assertEqual(
            set_current_transition(
                current=-(2**31),
                requested=2**31 - 1,
                minimum=-(2**31),
                maximum=2**31 - 1,
            ),
            (2**31 - 1, -1),
        )

    def fixture(self, family=560, retained=True):
        stat = set_current_registry()[str(family)]["fixed_stat_id"]

        def actor(uid, value):
            return SimpleNamespace(
                id=uid,
                hp=100,
                max_hp=100,
                ap=6,
                mp=3,
                max_ap=6,
                max_mp=3,
                effect_stats={stat: value},
                effect_minima={stat: -5000},
                effect_maxima={stat: 50000},
                effect_frozen=frozenset(),
            )

        caster, target = actor(7, 30), actor(8, 10)
        if stat == 1:
            caster.hp, caster.max_hp = 30, 50000
            target.hp, target.max_hp = 10, 50000
        fight = SimpleNamespace(
            id=1,
            phase="active",
            actors={7: caster, 8: target},
            owned_stat_effects={},
            _event=lambda *a, **k: None,
        )
        fight.apply_effect_damage = lambda source, uid, amount: setattr(
            fight.actors[uid], "hp", fight.actors[uid].hp - amount
        )
        fight.apply_effect_healing = lambda source, uid, amount: setattr(
            fight.actors[uid], "hp", fight.actors[uid].hp + amount
        )
        packets = []
        ids = iter(range(901, 950))
        lifecycle = []

        class Events:
            def phase(self, effect, invocation, **kw):
                lifecycle.append((kw["channel"], kw["value"], kw["_event_ids"]))
                if kw["channel"] == 2:
                    target.effect_stats[stat] = 20
                    if stat == 1:
                        target.hp = 20
                if kw["channel"] == 3:
                    kw["runner_modifier"].set_applied(77)

            def register_applied(self, *args):
                pass

        handler = NativeSetCurrentCharacteristicHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: next(ids),
            context=lambda *args: StatExecutionContext(
                True, True, None, retained, None
            ),
            rng=lambda: 0.5,
            event_lifecycle=Events(),
        )
        effect = {
            "effect_class": family,
            "parameters": [100, 0],
            "target_masks": [None] * 7,
        }
        invocation = EffectInvocation(
            reference=123, caster_id=7, target_id=8, level=30, cell=(0, 0, 0)
        )
        catalog = {"characteristics": {str(stat): {"expandable": False}}}
        return handler, effect, invocation, target, packets, lifecycle, catalog, stat

    def test_all_fixed_prototypes_have_single_shared_handler(self):
        for family in set_current_registry():
            self.assertEqual(set_current_registry()[family]["runner"], "eWX")
            self.assertEqual(set_current_registry()[family]["events"], [0])
        self.assertEqual(len(set_current_registry()), 12)

    def test_lifecycle_packet_value_and_removal_delta_are_independent(self):
        (
            handler,
            effect,
            invocation,
            target,
            packets,
            events,
            catalog,
            stat,
        ) = self.fixture()
        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value=catalog,
        ):
            invocation = handler.prepare(effect, {}, invocation)
            self.assertTrue(handler(effect, {}, invocation))
            entry = handler.fight.owned_stat_effects[901]
            self.assertEqual(
                (target.effect_stats[stat], entry["actual"], entry["setter_delta"]),
                (100, 77, 80),
            )
            target.effect_stats[stat] = 70
            remove_set_current_characteristic(handler, 901)
        self.assertEqual(target.effect_stats[stat], -10)
        self.assertEqual([e[0] for e in events], [1, 2, 3, 4])
        self.assertEqual([p[0] for p in packets], [13497, 13560])
        self.assertFalse(handler.prepared)
        self.assertFalse(handler.runner_amounts)

    def test_each_fixed_pc_uses_actual_shared_lifecycle(self):
        for family in map(int, set_current_registry()):
            (
                handler,
                effect,
                invocation,
                target,
                packets,
                events,
                catalog,
                stat,
            ) = self.fixture(family)
            catalog["characteristics"][str(stat)]["expandable"] = stat == 1
            with self.subTest(family=family), patch(
                "wakfu_server.combat_actor_snapshot.native_actor_catalog",
                return_value=catalog,
            ):
                invocation = handler.prepare(effect, {}, invocation)
                self.assertTrue(handler(effect, {}, invocation))
                self.assertEqual(target.effect_stats[stat], 100)
                self.assertEqual(events[2][2], (0,))

    def test_same_caster_pc_event_is_distinct_from_target_delta(self):
        (
            handler,
            effect,
            invocation,
            target,
            packets,
            events,
            catalog,
            stat,
        ) = self.fixture()
        invocation = replace(invocation, target_id=7)
        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value=catalog,
        ):
            invocation = handler.prepare(effect, {}, invocation)
            handler(effect, {}, invocation)
        self.assertIn(set_current_registry()["560"]["gain_event"], events[2][2])

    def test_expandable_hidden_raw_current_is_explicit_unknown(self):
        (
            handler,
            effect,
            invocation,
            target,
            packets,
            events,
            catalog,
            stat,
        ) = self.fixture(574)
        catalog["characteristics"][str(stat)]["expandable"] = True
        effect["parameters"] = [50001, 0]
        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value=catalog,
        ):
            invocation = handler.prepare(effect, {}, invocation)
            with self.assertRaisesRegex(ValueError, "raw current"):
                handler(effect, {}, invocation)
        self.assertFalse(packets)

    def test_caster_sample_occurs_after_l1_and_extra_parameters_are_ignored(self):
        (
            handler,
            effect,
            invocation,
            target,
            packets,
            events,
            catalog,
            stat,
        ) = self.fixture(retained=False)
        effect["parameters"] = []
        phase = handler.event_lifecycle.phase

        def phase_with_caster_change(effect, invocation, **kw):
            if kw["channel"] == 1:
                handler.fight.actors[7].effect_stats[stat] = 42
            phase(effect, invocation, **kw)

        handler.event_lifecycle.phase = phase_with_caster_change
        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value=catalog,
        ):
            invocation = handler.prepare(effect, {}, invocation)
            handler(effect, {}, invocation)
        self.assertEqual(target.effect_stats[stat], 42)
        (
            handler,
            effect,
            invocation,
            target,
            packets,
            events,
            catalog,
            stat,
        ) = self.fixture(retained=False)
        effect["parameters"] = [100, 0, 999, 100, -5, 0]
        with patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value=catalog,
        ):
            invocation = handler.prepare(effect, {}, invocation)
            handler(effect, {}, invocation)
        self.assertEqual(target.effect_stats[stat], 100)

    def test_cancel_prepared_removes_unapplied_runner_and_is_idempotent(self):
        handler, effect, invocation, *_ = self.fixture()
        invocation = handler.prepare(effect, {}, invocation)
        self.assertIn(invocation.native_running_uid, handler.prepared)
        handler.cancel_prepared(invocation)
        handler.cancel_prepared(invocation)
        self.assertFalse(handler.prepared)
        self.assertFalse(handler.runner_amounts)

    def test_missing_snapshot_and_malformed_pairs_never_become_zero(self):
        handler, effect, invocation, *_ = self.fixture()
        effect["parameters"] = [1]
        with self.assertRaisesRegex(ValueError, "pairs"):
            handler.prepare(effect, {}, invocation)
        self.assertFalse(handler.prepared)
        self.assertFalse(handler.runner_amounts)
