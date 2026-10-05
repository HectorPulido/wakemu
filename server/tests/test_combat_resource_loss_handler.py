import unittest
from types import SimpleNamespace
from wakfu_server.combat_resource_loss_handler import (
    NativeResourceLossHandler,
    remove_owned_resource_loss,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effects import _integer


def actor(uid, ap=6, mp=3):
    return SimpleNamespace(
        id=uid,
        hp=60,
        max_hp=60,
        ap=ap,
        mp=mp,
        max_ap=6,
        max_mp=3,
        effect_stats={1: 60, 2: ap, 3: mp, 86: 0},
        effect_minima={2: 0, 3: 0},
        effect_maxima={2: 6, 3: 3},
        effect_frozen=frozenset(),
    )


class NativeResourceLossHandlerTests(unittest.TestCase):
    def setup_handler(self, secondary=True):
        self.fight = SimpleNamespace(
            id=100,
            phase="active",
            actors={7: actor(7), -7: actor(-7)},
            owned_stat_effects={},
        )
        self.packets = []
        self.states = []
        self.handler = NativeResourceLossHandler(
            self.fight,
            self.packets,
            action_id=200,
            allocate_uid=lambda: 901,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            rng=lambda: 0,
            properties=lambda actor: frozenset(),
            secondary_state=(lambda *args: self.states.append(args))
            if secondary
            else None,
        )

    def test_mp_actual_wire_and_secondary_state_then_exact_removal(self):
        self.setup_handler()
        effect = {
            "effect_class": 48,
            "parameters": [2.0, 0.0],
            "native_effect_flags": [],
        }
        inv = EffectInvocation(123, 1, 7, -7, (1, 0, 0))
        self.assertTrue(self.handler(effect, {}, inv))
        self.assertEqual(self.fight.actors[-7].mp, 2)
        self.assertEqual(self.states[0][3:6], (-7, -7, (5227, 0, 10, 0, 100, 0)))
        self.assertEqual(self.fight.owned_stat_effects[901]["actual"], 1)
        self.assertEqual(self.packets[0][0], 13497)
        proxy = SimpleNamespace(fight=self.fight, packets=self.packets, action_id=200)
        remove_owned_resource_loss(proxy, 901)
        self.assertEqual(self.fight.actors[-7].mp, 3)
        self.assertFalse(self.fight.owned_stat_effects)
        self.assertEqual(self.packets[-1][0], 13560)

    def test_native_application_chance_replaces_definition_chance(self):
        self.setup_handler()
        inv = EffectInvocation(123, 1, 7, -7, (1, 0, 0))
        for parameters, expected in (
            ([2.0, 0.0], 100),
            ([2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 25.0, 0.0], 25),
            ([2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 150.0, 0.0], 100),
        ):
            values = {"probability": 7}
            selected = self.handler.prepare(
                {
                    "effect_class": 48,
                    "parameters": parameters,
                    "native_effect_flags": [],
                },
                values,
                inv,
            )
            self.assertEqual(values["probability"], expected)
            self.handler.prepared.pop(selected.native_running_uid)

    def test_missing_secondary_does_not_mutate_resource_or_emit(self):
        self.setup_handler(False)
        with self.assertRaisesRegex(ValueError, "secondary state5227"):
            self.handler(
                {
                    "effect_class": 55,
                    "parameters": [2.0, 0.0],
                    "native_effect_flags": [],
                },
                {},
                EffectInvocation(123, 1, 7, -7, (1, 0, 0)),
            )
        self.assertEqual(self.fight.actors[-7].ap, 6)
        self.assertEqual(self.packets, [])

    def test_l2_live_amount_keeps_single_roll_and_secondary_state_actual(self):
        self.setup_handler()
        draws, phases = [], []
        self.handler.rng = lambda: (draws.append(True) or 0.1)

        def phase(effect, invocation, *, channel, runner_modifier, plan, **kwargs):
            phases.append((channel, None if plan is None else plan.event_override))
            if channel == 2:
                self.assertEqual(runner_modifier.value, 2)
                runner_modifier.mutate(1, 1, False)

        self.handler.event_lifecycle = SimpleNamespace(phase=phase)
        inv = EffectInvocation(123, 1, 7, -7, (1, 0, 0))
        effect = {
            "effect_class": 48,
            "parameters": [3.0, 0.0],
            "native_effect_flags": [],
        }
        inv = self.handler.prepare(effect, {}, inv)
        self.assertTrue(self.handler(effect, {}, inv))
        self.assertEqual(draws, [True])
        self.assertEqual(self.fight.actors[-7].mp, 0)
        self.assertEqual(self.states[0][5], (5227, 0, 30, 0, 100, 0))
        self.assertEqual(phases, [(1, None), (2, 75), (3, 75), (4, 75)])
        self.assertEqual(self.fight.owned_stat_effects[901]["actual"], 3)
        self.assertFalse(self.handler.runner_amounts)

    def test_l2_zero_suppresses_notification_not_application_or_phases(self):
        self.setup_handler()
        phases = []

        def phase(effect, invocation, *, channel, runner_modifier, **kwargs):
            phases.append(channel)
            if channel == 2:
                runner_modifier.mutate(1, 0, True)

        self.handler.event_lifecycle = SimpleNamespace(phase=phase)
        inv = EffectInvocation(123, 1, 7, -7, (1, 0, 0))
        effect = {
            "effect_class": 55,
            "parameters": [2.0, 0.0],
            "native_effect_flags": [],
        }
        inv = self.handler.prepare(effect, {}, inv)
        self.assertTrue(self.handler(effect, {}, inv))
        self.assertEqual(self.fight.actors[-7].ap, 6)
        self.assertEqual(self.packets, [])
        self.assertEqual(self.states, [])
        self.assertEqual(self.fight.owned_stat_effects[901]["actual"], 0)
        self.assertEqual(phases, [1, 2, 3, 4])

    def test_l3_changes_retirement_amount_without_reapplying_resource(self):
        self.setup_handler()
        wire = []
        from unittest.mock import patch
        from wakfu_server.combat_stat_effects import owned_effect_application
        from wakfu_server.combat_effect_removal import _identity_fields

        def capture(*args, **kwargs):
            wire.append(_identity_fields(kwargs["running_effect_payload"])[4])
            return owned_effect_application(*args, **kwargs)

        def phase(effect, invocation, *, channel, runner_modifier, **kwargs):
            if channel == 3:
                runner_modifier.mutate(1, 1, False)

        self.handler.event_lifecycle = SimpleNamespace(phase=phase)
        effect = {
            "effect_class": 55,
            "parameters": [4.0, 0.0],
            "native_effect_flags": [],
        }
        inv = self.handler.prepare(
            effect, {}, EffectInvocation(123, 1, 7, -7, (1, 0, 0))
        )
        with patch(
            "wakfu_server.combat_resource_loss_handler.owned_effect_application",
            side_effect=capture,
        ):
            self.assertTrue(self.handler(effect, {}, inv))
        self.assertEqual(self.fight.actors[-7].ap, 4)
        self.assertEqual(wire, [2])
        row = self.fight.owned_stat_effects[901]
        self.assertEqual(row["actual"], 3)
        self.assertEqual(_identity_fields(bytes.fromhex(row["payload"]))[4], 3)
        # Native retirement adds live amount; create room to expose3 vs2.
        self.fight.actors[-7].ap = self.fight.actors[-7].effect_stats[2] = 1
        remove_owned_resource_loss(
            SimpleNamespace(fight=self.fight, packets=self.packets, action_id=200), 901
        )
        self.assertEqual(self.fight.actors[-7].ap, 4)

    def test_native_zero_actual_at_minimum_suppresses_pr_without_430(self):
        self.setup_handler()
        self.fight.actors[-7].mp = self.fight.actors[-7].effect_stats[3] = 0
        effect = {
            "effect_class": 48,
            "parameters": [2.0, 0.0],
            "native_effect_flags": [],
        }
        self.assertTrue(
            self.handler(effect, {}, EffectInvocation(123, 1, 7, -7, (1, 0, 0)))
        )
        self.assertEqual(self.packets, [])
        self.assertEqual(self.states, [])
        self.assertEqual(self.fight.owned_stat_effects[901]["actual"], 0)

    def test_signed_sq_resource_gain_and_native_flag19_suppression(self):
        self.setup_handler()
        inv = EffectInvocation(
            123,
            1,
            7,
            -7,
            (1, 0, 0),
            native_context_hex=(_integer(6, -2) + _integer(9, 1)).hex(),
        )
        self.fight.actors[-7].ap = 3
        self.fight.actors[-7].effect_stats[2] = 3
        self.handler(
            {"effect_class": 55, "parameters": [0.0, 0.0], "native_effect_flags": [19]},
            {},
            inv,
        )
        self.assertEqual(self.fight.actors[-7].ap, 5)
        self.assertEqual(self.fight.owned_stat_effects[901]["actual"], -2)
        self.assertEqual(self.states, [])
        remove_owned_resource_loss(
            SimpleNamespace(fight=self.fight, packets=self.packets, action_id=200), 901
        )
        self.assertEqual(self.fight.actors[-7].ap, 3)
