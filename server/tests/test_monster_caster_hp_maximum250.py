"""Installed eWM250 PA mutation/removal and real owned-area consumers."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
import test_combat_kill as fixture
import test_monster_hp_minimum830 as area830
from wakfu_server.combat_caster_hp_maximum import (
    NativeCasterHPMaximumHandler,
    hp_operand,
)
from wakfu_server.combat_hp_raw import install_fresh_hp_operand, SOURCE
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_damage_handler import _wall_target


class CasterMaximum250Tests(unittest.TestCase):
    def fixture(self, minimum=0, current=80, frozen=False):
        (
            fight,
            target,
            packets,
            phases,
            old,
            _,
            invocation,
        ) = fixture.NativeKillTests().fixture(minimum=minimum)
        target.hp = target.effect_stats[1] = current
        install_fresh_hp_operand(
            target, dict(producer=SOURCE, actor_id=target.id, raw_current=current)
        )
        target.effect_frozen = frozenset((1,)) if frozen else frozenset()
        handler = NativeCasterHPMaximumHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=old.allocate_uid,
            context=old.context,
            rng=lambda: 0.5,
        )
        return fight, target, packets, handler, replace(invocation, caster_id=target.id)

    def effect(self, percentage, apply=True, remove=False):
        return dict(
            effect_class=250,
            parameters=[percentage, 0, int(apply), 0, int(remove), 0],
            target_masks=[[] for _ in range(7)],
            native_effect_flags=[],
        )

    def remove(self, fight, packets, uid):
        handler = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=5,
            allocate_uid=lambda: 999,
            context=lambda *a: None,
        )
        handler.remove(uid)

    def test_installed_java_apply_removal_matrix_ignores_remove_current_flag(self):
        cases = json.loads(
            (
                Path(__file__).parent / "fixtures/monster_maximum250_native.json"
            ).read_text()
        )
        for case in cases:
            with self.subTest(case=case):
                fight, actor, packets, handler, invocation = self.fixture(
                    case["minimum"], case["current"], case["frozen"]
                )
                effect = self.effect(
                    case["delta"], case["apply_current"]
                )  # caster maximum=100
                self.assertTrue(handler(effect, {}, invocation))
                row = fight.owned_stat_effects[101]
                self.assertEqual(
                    (
                        actor.effect_base_maxima[1],
                        actor.max_hp,
                        actor.hp,
                        row["actual"],
                        row["effective_delta"],
                        row["reversible"],
                    ),
                    tuple(
                        case[k]
                        for k in (
                            "applied_raw_maximum",
                            "applied_maximum",
                            "applied_current",
                            "actual",
                            "effective_delta",
                            "reversible",
                        )
                    ),
                )
                self.remove(fight, packets, 101)
                self.assertEqual(
                    (actor.effect_base_maxima[1], actor.max_hp, actor.hp),
                    tuple(
                        case[k]
                        for k in (
                            "removed_raw_maximum",
                            "removed_maximum",
                            "removed_current",
                        )
                    ),
                )

    def test_installed_java_caster_calculation_overflow_and_truncation(self):
        cases = json.loads(
            (
                Path(__file__).parent
                / "fixtures/monster_maximum250_calculation_native.json"
            ).read_text()
        )
        for case in cases:
            with self.subTest(case=case):
                fight, actor, _, handler, invocation = self.fixture(current=0)
                actor.max_hp = actor.effect_maxima[1] = actor.effect_base_maxima[
                    1
                ] = case["maximum"]
                _, amount, apply_current, remove_current = handler._calculate(
                    self.effect(case["percentage"]), invocation
                )
                self.assertEqual(
                    (amount, apply_current, remove_current),
                    (case["amount"], True, False),
                )

    def test_actual_faw_and_fbd_maximum_visible_to_damage_wire_and_rollback(self):
        for reference in (566, 1063):
            with self.subTest(reference=reference):
                fight, _, packets, _ = area830.HPMinimum830Tests().area(reference)
                fight.owned_stat_effects = {}
                handler = NativeCasterHPMaximumHandler(
                    fight,
                    packets,
                    action_id=1,
                    allocate_uid=lambda: 950,
                    context=lambda *a: StatExecutionContext(
                        True, True, None, True, b"", None
                    ),
                )
                before = deepcopy(fight.native_effect_areas[901])
                slots = deepcopy(fight.native_qi_slots)
                operand = hp_operand(fight, 901)
                maximum = operand["maximum"]
                invocation = EffectInvocation(50, 30, 901, 901, (2, 3, 0))
                self.assertTrue(handler(self.effect(100), {}, invocation))
                from wakfu_server.combat_casting_range import int32

                product = int32(100 * maximum)
                delta = (abs(product) // 100) * (-1 if product < 0 else 1)
                expected = maximum + delta
                self.assertEqual(
                    (
                        _wall_target(fight, 901)["snapshot"]["current_hp"],
                        _wall_target(fight, 901)["snapshot"]["maximum_hp"],
                    ),
                    (expected, expected),
                )
                self.assertNotIn(901, fight.actors)
                self.assertEqual(fight.native_qi_slots, slots)
                if reference == 566:
                    from wakfu_server.combat_fake_fighter_resources import (
                        fake_fighter_hp_wire,
                    )
                    import struct

                    self.assertEqual(
                        fake_fighter_hp_wire(
                            fight.native_effect_areas[901],
                            hp_operand(fight, 901)["area"]["definition"],
                        ),
                        struct.pack(">ii", maximum * 2, maximum * 2),
                    )
                self.remove(fight, packets, 950)
                self.assertEqual(hp_operand(fight, 901)["maximum"], maximum)
                fight.native_effect_areas[901] = before
                self.assertEqual(hp_operand(fight, 901)["maximum"], maximum)

    def test_actual_area_current_writer_preserves_over_max_raw_current(self):
        fight, _, packets, _ = area830.HPMinimum830Tests().area(566)
        handler = NativeCasterHPMaximumHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 950,
            context=lambda *a: StatExecutionContext(True, True, None, False, b"", None),
        )
        inv = EffectInvocation(50, 30, 901, 901, (2, 3, 0))
        self.assertTrue(handler(self.effect(-50, False), {}, inv))
        op = hp_operand(fight, 901)
        self.assertEqual((op["maximum"], op["current"], op["raw_current"]), (4, 4, 8))
        from wakfu_server.combat_fake_fighter_resources import update_fake_fighter_hp

        update_fake_fighter_hp(op["area"]["row"], op["area"]["definition"], 3)
        self.assertEqual(hp_operand(fight, 901)["raw_current"], 3)
        fight.native_effect_areas[901]["native_area_hp_pa"]["maximum"] = 77
        with self.assertRaisesRegex(ValueError, "mismatch"):
            hp_operand(fight, 901)

    def test_area_overlay_percentage_frozen_and_minimum_event_use_actual_pa(self):
        from wakfu_server.combat_area_hp_pa import set_area_hp_maximum

        for reference in (566, 1063):
            fight, minimum_handler, packets, events = area830.HPMinimum830Tests().area(
                reference
            )
            operand = hp_operand(fight, 901)
            state = {
                k: v for k, v in operand.items() if k not in ("area", "current_key")
            }
            state.update(percentage=50, frozen=True)
            # Explicit PA fixture mutability/percentage operands; no actor defaults.
            set_area_hp_maximum(
                operand["area"]["row"],
                state,
                operand["raw_maximum"],
                operand["current_key"],
            )
            before = hp_operand(fight, 901)
            self.assertTrue(
                minimum_handler(
                    {"effect_class": 830},
                    {},
                    EffectInvocation(50, 30, 7, 901, (2, 3, 0)),
                )
            )
            self.assertEqual(hp_operand(fight, 901)["current"], before["current"])
            self.assertEqual(events[-1]["hp"], before["current"])
            self.assertEqual(hp_operand(fight, 901)["maximum"], before["maximum"])

    def test_null_and_proven_hp_absent_target_do_not_execute(self):
        fight, _, packets, _ = area830.HPMinimum830Tests().area(1035)
        handler = NativeCasterHPMaximumHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 950,
            context=lambda *a: StatExecutionContext(True, True, None, False, b"", None),
        )
        before = len(packets)
        self.assertFalse(
            handler(
                self.effect(100), {}, EffectInvocation(50, 30, None, 901, (2, 3, 0))
            )
        )
        self.assertEqual(len(packets), before)
