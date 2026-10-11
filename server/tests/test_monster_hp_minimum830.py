"""Actual eXw830 minimum assignment reuses PA authority, not kill28."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

import test_combat_kill as kill_fixture
import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_hp_minimum_set import NativeHPMinimumSetHandler
from wakfu_server.combat_hp_raw import install_fresh_hp_operand, hp_raw_current, SOURCE
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_damage_handler import _wall_target


class HPMinimum830Tests(unittest.TestCase):
    def fixture(self, *, minimum=0, frozen=()):
        (
            fight,
            target,
            packets,
            phases,
            old,
            effect,
            invocation,
        ) = kill_fixture.NativeKillTests().fixture(minimum=minimum, frozen=frozen)
        handler = NativeHPMinimumSetHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=old.allocate_uid,
            context=old.context,
            rng=old.rng,
            authority=old.authority,
        )
        handler.event_lifecycle = old.event_lifecycle
        return (
            fight,
            target,
            packets,
            phases,
            handler,
            dict(effect, effect_class=830, parameter_count=0, parameters=[]),
            invocation,
        )

    def test_installed_java_runner_differential_minimum_and_frozen_cases(self):
        cases = json.loads(
            (
                Path(__file__).parent / "fixtures/monster_hp_minimum830_native.json"
            ).read_text()
        )
        for case in cases:
            with self.subTest(case=case):
                fight, actor, _, phases, handler, effect, invocation = self.fixture(
                    minimum=case["minimum"], frozen=(1,) if case["frozen"] else ()
                )
                actor.hp = actor.effect_stats[1] = case["current"]
                phase = handler.event_lifecycle.phase

                def mutate_l1(effect, invocation, **kwargs):
                    phase(effect, invocation, **kwargs)
                    if kwargs["channel"] == 1:
                        kwargs["runner_modifier"].set_calculated(37)

                handler.event_lifecycle.phase = mutate_l1
                clock = deepcopy(
                    (
                        actor.effect_stats[14],
                        actor.effect_maxima[14],
                        actor.effect_base_maxima[14],
                    )
                )
                self.assertTrue(
                    handler(effect, {}, handler.prepare(effect, {}, invocation))
                )
                self.assertEqual(actor.hp, case["after"])
                self.assertEqual(actor.effect_maxima[1], case["maximum"])
                self.assertEqual(
                    (
                        actor.effect_stats[14],
                        actor.effect_maxima[14],
                        actor.effect_base_maxima[14],
                    ),
                    clock,
                )
                self.assertEqual([p[0] for p in phases], [1, 2, 3, 4])
                self.assertTrue(all(p[3] == (0,) for p in phases))
                self.assertTrue(all(p[2] == case["runner_value"] for p in phases[1:]))
                self.assertFalse(any(e["kind"] == "damage" for e in fight.events))

    def test_actual_raw_current_assignment_and_retained_removal_never_restore_hp(self):
        fight, actor, packets, _, handler, effect, invocation = self.fixture(minimum=17)
        actor.hp = actor.effect_stats[1] = 100
        install_fresh_hp_operand(
            actor, dict(producer=SOURCE, actor_id=actor.id, raw_current=120)
        )
        self.assertTrue(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertEqual((actor.hp, hp_raw_current(actor)), (17, 17))
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=5,
            allocate_uid=lambda: 999,
            context=lambda *args: None,
        )
        stat.remove(101)
        self.assertEqual((actor.hp, hp_raw_current(actor)), (17, 17))
        self.assertEqual([packet[0] for packet in packets], [12613, 13560])

    def test_unknown_minimum_rejects_without_resource_or_packet_mutation(self):
        fight, actor, packets, _, handler, effect, invocation = self.fixture()
        del actor.effect_minima[1]
        with self.assertRaisesRegex(ValueError, "snapshot"):
            handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(actor.hp, 80)
        self.assertEqual(packets, [])
        self.assertEqual(fight.owned_stat_effects, {})

    def test_null_is_nonexecution_but_incomplete_fighter_hp_is_unknown(self):
        fight, actor, packets, _, handler, effect, invocation = self.fixture()
        self.assertFalse(
            handler(
                effect,
                {},
                handler.prepare(effect, {}, replace(invocation, target_id=None)),
            )
        )
        del actor.effect_stats[1]
        with self.assertRaisesRegex(ValueError, "presence authority"):
            handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(actor.hp, 80)
        self.assertEqual(packets, [])

    def area(self, reference):
        fight, creator, _, packets = area_fixture.NativeFakeFighterAreaTests().create()
        creator.fake_fighter_hp_enabled = True
        creator(
            {"effect_class": 339},
            {"parameters": [reference, 30]},
            EffectInvocation(400, 30, 7, None, (2, 3, 0)),
        )
        fight.phase = "active"
        fight.effect_resolution = nullcontext
        events = []
        fight._event = lambda kind, **values: events.append(dict(kind=kind, **values))
        handler = NativeHPMinimumSetHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 950,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            rng=lambda: 0.5,
            authority=None,
        )
        return fight, handler, packets, events

    def test_actual_faw_and_fbd_hp_setter_keeps_qi_and_no_fighter_alias(self):
        for reference in (566, 1063):
            with self.subTest(reference=reference):
                fight, handler, _, events = self.area(reference)
                row = fight.native_effect_areas[901]
                before = deepcopy(row)
                slots = deepcopy(fight.native_qi_slots)
                self.assertTrue(
                    handler(
                        {"effect_class": 830},
                        {},
                        EffectInvocation(50, 30, 7, 901, (2, 3, 0)),
                    )
                )
                self.assertEqual(_wall_target(fight, 901)["snapshot"]["current_hp"], 0)
                self.assertNotIn(901, fight.actors)
                self.assertEqual(fight.native_qi_slots, slots)
                self.assertFalse(any(event["kind"] == "death" for event in events))
                fight.native_effect_areas[901] = before
                self.assertGreater(
                    _wall_target(fight, 901)["snapshot"]["current_hp"], 0
                )

    def test_actual_hp_absent_area_is_nonexecution_not_an_actor_fallback(self):
        fight, handler, packets, events = self.area(1035)
        before = len(packets)
        self.assertFalse(
            handler(
                {"effect_class": 830}, {}, EffectInvocation(50, 30, 7, 901, (2, 3, 0))
            )
        )
        self.assertEqual(len(packets), before)
        self.assertEqual(events, [])
