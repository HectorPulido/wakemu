import unittest
from types import SimpleNamespace
from copy import deepcopy
from dataclasses import replace
from wakfu_server.combat_armor import armor_amount, NativeArmorHandler
from wakfu_server.combat_stat_handler import StatExecutionContext, NativeStatHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


def actor(identity, position):
    return SimpleNamespace(
        id=identity,
        position=position,
        hp=100,
        max_hp=100,
        max_ap=6,
        max_mp=3,
        effect_stats={1: 100, 97: 10, 120: 50, 121: 20},
        effect_maxima={1: 100, 97: 1000000},
        effect_minima={97: 0},
        effect_frozen=frozenset(),
        physical_radius=0,
    )


class NativeArmorTests(unittest.TestCase):
    def test_actual_corpse_skips_armor_before_amount_and_uid_allocation(self):
        from test_combat_damage_handler import DamageHandlerTests
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_active_spell_id = 5037
        handler = object.__new__(NativeArmorHandler)
        handler.fight = fight
        effect = dict(
            effect_class=1013,
            native_effect_flags=[],
            target_masks=(None,) * 7,
        )
        # The real damage operation registers the corpse; raw HP0 is not proof.
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 100)
            self.assertFalse(handler.native_eligibility(effect, fixture.invocation))
            self.assertFalse(handler(effect, {}, fixture.invocation))
            with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
                handler(
                    dict(effect_class=1013, native_effect_flags=[]),
                    {},
                    fixture.invocation,
                )

    def setUp(self):
        self.source, self.target = actor(22, (0, 0, 0)), actor(-33, (1, 0, 0))
        self.effect = dict(
            effect_class=1013, parameters=[100, 0], variant=0, native_effect_flags=[]
        )

    def test_native_jar_coefficient_modes(self):
        for mode, expected in enumerate((100, 150, 120, 170)):
            effect = dict(self.effect, parameters=[100, 0, mode, 0])
            result = armor_amount(
                effect, 1, self.source, self.target, capped_player=False
            )
            self.assertEqual(result, dict(requested=expected, room=2147483637))
        self.assertEqual(
            armor_amount(self.effect, 1, self.source, self.source, capped_player=False)[
                "requested"
            ],
            120,
        )

    def test_life_steal_marker_preserves_armor_coefficients_and_final_modifier(self):
        # Original class-owned 353422: eWx1013, [0,.25,0,0], flag29.
        effect = dict(self.effect, parameters=[0, 0.25, 0, 0], native_effect_flags=[29])
        for level in (1, 20, 200):
            for modifier in (0, 37, 111):
                with self.subTest(level=level, modifier=modifier):
                    self.assertEqual(
                        armor_amount(
                            effect,
                            level,
                            self.source,
                            self.target,
                            capped_player=False,
                            additional_final=modifier,
                        ),
                        armor_amount(
                            dict(effect, native_effect_flags=[]),
                            level,
                            self.source,
                            self.target,
                            capped_player=False,
                            additional_final=modifier,
                        ),
                    )

    def test_player_cap_and_explicit_bypass(self):
        self.target.effect_stats[88] = 50
        self.assertEqual(
            armor_amount(self.effect, 1, self.source, self.target, capped_player=True),
            dict(requested=40, room=40),
        )
        bypass = dict(self.effect, parameters=[100, 0, 0, 0, 0, 0, 2, 0])
        self.assertEqual(
            armor_amount(bypass, 1, self.source, self.target, capped_player=True)[
                "requested"
            ],
            100,
        )

    def test_elemental_mastery_flags_and_negative_floor(self):
        self.source.effect_stats.update({21: 25, 20: 25, 102: 25, 103: 25})
        effect = dict(self.effect, parameters=[80, 0, 0, 0, 1, 0])
        self.assertEqual(
            armor_amount(effect, 1, self.source, self.target, capped_player=False)[
                "requested"
            ],
            160,
        )
        bad = dict(effect, native_effect_flags=[100])
        with self.assertRaises(ValueError):
            armor_amount(bad, 1, self.source, self.target, capped_player=False)

    def test_application_native_additional_and_owned_removal(self):
        fight = SimpleNamespace(
            id=1,
            actors={22: self.source, -33: self.target},
            phase="active",
            current=self.source,
            owned_stat_effects={},
            _event=lambda *a, **k: None,
        )
        packets = []
        context = StatExecutionContext(True, True, None, True, None)
        handler = NativeArmorHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 902,
            context=lambda *a: context,
            authority=lambda *a: SimpleNamespace(is_player=False),
        )
        inv = EffectInvocation(123456, 1, 22, -33, (1, 0, 0))
        self.effect["parameters"] = [100, 0, 0, 0]
        self.assertTrue(handler(self.effect, None, inv))
        self.assertEqual(self.target.effect_stats[97], 110)
        messages = {}
        _identity_fields(
            bytes.fromhex(fight.owned_stat_effects[902]["payload"]), messages=messages
        )
        self.assertEqual(messages[8].hex(), "60619801f5ffffff07c80164")
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: 903,
            context=lambda *a: context,
        )
        stat.remove(902)
        self.assertEqual(self.target.effect_stats[97], 10)
        self.assertEqual([opcode for opcode, _ in packets], [13497, 13560])
        self.effect["parameters"] = [0, 0]
        handler.allocate_uid = lambda: self.fail("Zero initial amount allocated UID")
        self.assertFalse(handler(self.effect, None, inv))
        self.assertEqual(len(packets), 2)

    def test_native_final_modifier_modes_and_cap_order(self):
        self.source.effect_stats[120] = self.target.effect_stats[121] = 0
        for mode, expected in enumerate((100, 125, 125, 125)):
            effect = dict(self.effect, parameters=[100, 0, mode, 0])
            self.assertEqual(
                armor_amount(
                    effect,
                    1,
                    self.source,
                    self.target,
                    capped_player=False,
                    additional_final=25,
                )["requested"],
                expected,
            )
        self.target.effect_stats[88] = 100
        effect = dict(self.effect, parameters=[50, 0, 3, 0])
        self.assertEqual(
            armor_amount(
                effect,
                1,
                self.source,
                self.target,
                capped_player=True,
                additional_final=100,
            )["requested"],
            90,
        )

    def test_preparation_modifies_once_clone_resets_and_retirement_restores(self):
        self.source.effect_stats[120] = self.target.effect_stats[121] = 0
        fight = SimpleNamespace(
            id=1,
            actors={22: self.source, -33: self.target},
            phase="active",
            current=self.source,
            owned_stat_effects={},
            _event=lambda *a, **k: None,
        )
        packets, calls = [], []
        counter = iter((901, 902))
        context = StatExecutionContext(True, True, None, True, None)
        handler = NativeArmorHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(counter),
            context=lambda *a: context,
            authority=lambda *a: SimpleNamespace(is_player=False),
            rng=lambda: 0.5,
        )

        def phase(
            effect, invocation, *, uid, value, channel, final_modifier, runner_modifier
        ):
            from wakfu_server.combat_final_modifier import (
                NativeFinalModifierHandler,
                final_modifier_source,
            )

            calls.append((uid, value, channel, final_modifier.value))
            if channel in (1, 2):
                modifier_handler = NativeFinalModifierHandler(
                    fight,
                    packets,
                    action_id=1,
                    allocate_uid=lambda: uid + 100,
                    context=lambda *a: StatExecutionContext(
                        True, True, None, False, None
                    ),
                )
                triggered = replace(invocation, native_trigger_context={"uid": uid})
                with final_modifier_source(
                    SimpleNamespace(
                        uid=uid, effect_action_id=1013, final_modifier=final_modifier
                    )
                ):
                    self.assertTrue(
                        modifier_handler(
                            {
                                "effect_class": 1093,
                                "parameters": [25 if channel == 1 else 50, 0],
                                "native_effect_flags": [],
                            },
                            None,
                            triggered,
                        )
                    )

        handler.event_lifecycle = SimpleNamespace(phase=phase)
        invocation = EffectInvocation(123456, 1, 22, -33, (1, 0, 0))
        effect = dict(self.effect, parameters=[100, 0, 3, 0])
        prepared = handler.prepare(effect, None, invocation)
        self.assertEqual(self.target.effect_stats[97], 10)
        self.assertTrue(handler(effect, None, prepared))
        self.assertEqual(self.target.effect_stats[97], 135)
        # Native activation bypasses d/L1 and fNk creates a fresh rBA0.
        self.assertTrue(handler(effect, None, invocation))
        self.assertEqual(self.target.effect_stats[97], 235)
        self.assertEqual(
            [(uid, channel) for uid, _, channel, _ in calls],
            [(901, 1), (901, 2), (901, 3), (901, 4), (902, 2), (902, 3), (902, 4)],
        )
        self.assertEqual(
            next(
                value for uid, value, channel, _ in calls if uid == 902 and channel == 2
            ),
            100,
        )
        self.assertFalse(handler.prepared)
        self.assertFalse(handler.final_modifiers)
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: 903,
            context=lambda *a: context,
        )
        stat.remove(901)
        stat.remove(902)
        self.assertEqual(self.target.effect_stats[97], 10)
        with self.assertRaisesRegex(ValueError, "Missing prepared"):
            handler(effect, None, replace(invocation, native_running_uid=901))

    def test_trigger_value_phases_preserve_wire_and_final_retirement(self):
        from unittest.mock import patch
        from wakfu_server.combat_stat_effects import owned_effect_application

        for phase_to_change, suppressed in ((2, False), (3, False), (2, True)):
            with self.subTest(phase=phase_to_change, suppressed=suppressed):
                source, target = actor(22, (0, 0, 0)), actor(-33, (1, 0, 0))
                source.effect_stats[120] = target.effect_stats[121] = 0
                target.effect_stats[97] = 200
                fight = SimpleNamespace(
                    id=1,
                    actors={22: source, -33: target},
                    phase="active",
                    current=source,
                    owned_stat_effects={},
                    _event=lambda *a, **k: None,
                )
                packets, phases, sent = [], [], []
                context = StatExecutionContext(True, True, None, True, None)
                handler = NativeArmorHandler(
                    fight,
                    packets,
                    action_id=1,
                    allocate_uid=lambda: 902,
                    context=lambda *a: context,
                    authority=lambda *a: SimpleNamespace(is_player=False),
                    rng=lambda: 0.5,
                )

                def phase(effect, invocation, *, channel, runner_modifier, **kwargs):
                    phases.append(channel)
                    if channel == phase_to_change:
                        if suppressed:
                            runner_modifier.mutate(1, 0, True)
                            runner_modifier.mutate(1, 10, True)
                        else:
                            runner_modifier.mutate(1, 25, False)

                handler.event_lifecycle = SimpleNamespace(phase=phase)
                effect = dict(self.effect, parameters=[100, 0, 0, 0])
                inv = handler.prepare(
                    effect, None, EffectInvocation(123456, 1, 22, -33, (1, 0, 0))
                )

                def capture(*args, **kwargs):
                    fields = _identity_fields(kwargs["running_effect_payload"])
                    sent.append(fields[4])
                    return owned_effect_application(*args, **kwargs)

                with patch(
                    "wakfu_server.combat_armor.owned_effect_application",
                    side_effect=capture,
                ):
                    self.assertTrue(handler(effect, None, inv))
                self.assertEqual(phases, [1, 2, 3, 4])
                self.assertEqual(
                    sent, [] if suppressed else [125 if phase_to_change == 2 else 100]
                )
                self.assertEqual(
                    target.effect_stats[97],
                    210 if suppressed else (325 if phase_to_change == 2 else 300),
                )
                row = fight.owned_stat_effects[902]
                self.assertEqual(row["actual"], 10 if suppressed else 125)
                self.assertEqual(
                    _identity_fields(bytes.fromhex(row["payload"]))[4], row["actual"]
                )
                stat = NativeStatHandler(
                    fight,
                    packets,
                    {"effects": {}},
                    action_id=1,
                    allocate_uid=lambda: 903,
                    context=lambda *a: context,
                )
                stat.remove(902)
                self.assertEqual(
                    target.effect_stats[97], 175 if phase_to_change == 3 else 200
                )
                self.assertFalse(handler.runner_amounts)

    def test_armor_source_events_preserve_native_masks_and_accumulator(self):
        from unittest.mock import patch
        from wakfu_server.combat_ordinary_events import (
            OrdinaryArmorEvents,
            OrdinaryHealingEvents,
        )
        from wakfu_server.combat_final_modifier import NativeFinalModifier

        lifecycle = OrdinaryArmorEvents.__new__(OrdinaryArmorEvents)
        modifier = NativeFinalModifier(901, 1013)
        invocation = EffectInvocation(123456, 1, 22, -33, (1, 0, 0))
        effect = dict(self.effect, target_masks=[None] * 6 + [[801, 0]])
        with patch.object(
            OrdinaryHealingEvents, "phase", return_value=(True,)
        ) as phase:
            for channel in range(1, 5):
                self.assertEqual(
                    lifecycle.phase(
                        effect,
                        invocation,
                        uid=901,
                        value=100,
                        channel=channel,
                        final_modifier=modifier,
                    ),
                    (True,),
                )
            self.assertEqual(phase.call_count, 4)
            for call in phase.call_args_list:
                self.assertEqual(call.kwargs["_event_ids"], (0, 801))
                self.assertIs(call.kwargs["final_modifier"], modifier)
        with self.assertRaisesRegex(ValueError, "masks"):
            lifecycle.phase(self.effect, invocation, uid=901, value=0, channel=1)
