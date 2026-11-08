"""Fresh native runtime copies preserve graph aliases and failed-operation isolation."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_preview_copy import runtime_scalar_actor_memo
from wakfu_server.combat_area_boundary import atomic_area_turn
from wakfu_server.combat_native_action_ids import native_delivery_boundary
from wakfu_server.combat_movement_runtime import _with_areas


class Stopped(Exception):
    pass


class CustomPA(dict):
    copies = 0

    def __deepcopy__(self, memo):
        type(self).copies += 1
        result = type(self)(deepcopy(dict(self), memo))
        memo[id(self)] = result
        return result


class RuntimePACopyTests(unittest.TestCase):
    def test_three_native_boundaries_preserve_aliases_and_rollback_with_custom_fallback(
        self,
    ):
        a = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1)
        b = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            505, [a, b], {a.position, b.position}, {0: {a.position}, 1: {b.position}}
        )
        b.hp = 0
        shared = {1: 0, 2: 1.5, 3: True, 4: "value", 5: None}
        b.effect_minima = b.effect_base_minima = fight.future_pa_alias = shared
        a.effect_stats = {1: 60, 4: 6}
        a.effect_percentages = {1: {"values": [1]}}
        a.effect_maxima = CustomPA({1: 60})
        runtime = RuntimeMessages(fight)
        runtime.turn_start_provider = lambda *args, **kwargs: None
        runtime.future_pa_alias = shared
        plain = deepcopy(runtime)
        calls = []

        def prime(value):
            memo = runtime_scalar_actor_memo(value)
            self.assertIn(id(shared), memo)
            self.assertNotIn(id(a.effect_percentages), memo)
            self.assertNotIn(id(a.effect_maxima), memo)
            calls.append(value)
            return memo

        def mutate(candidate, *args):
            self.assertIsNot(candidate, runtime)
            self.assertIsNot(candidate.fight, fight)
            self.assertEqual(candidate.future_pa_alias, plain.future_pa_alias)
            self.assertIs(candidate.future_pa_alias, candidate.fight.future_pa_alias)
            self.assertIs(
                candidate.future_pa_alias, candidate.fight.actors[-7].effect_minima
            )
            self.assertIs(
                candidate.future_pa_alias, candidate.fight.actors[-7].effect_base_minima
            )
            self.assertIsNot(candidate.future_pa_alias, shared)
            self.assertIs(type(candidate.fight.actors[7].effect_maxima), CustomPA)
            candidate.future_pa_alias[1] = 900
            candidate.fight.actors[7].effect_percentages[1]["values"].append(2)
            candidate.fight.actors[7].hp = 1
            raise Stopped

        operations = (
            lambda: atomic_area_turn(mutate)(runtime),
            lambda: native_delivery_boundary(mutate)(runtime),
            lambda: _with_areas(runtime, lambda *args: None, mutate),
        )
        with patch(
            "wakfu_server.combat_preview_copy.runtime_scalar_actor_memo", new=prime
        ):
            for operation in operations:
                with self.assertRaises(Stopped):
                    operation()
                self.assertEqual(shared[1], 0)
                self.assertEqual(a.hp, 60)
                self.assertEqual(a.effect_percentages[1]["values"], [1])
                self.assertNotIn("_area_atomic_depth", vars(runtime))
                self.assertNotIn("_native_delivery_depth", vars(runtime))
        self.assertEqual(calls, [runtime] * 3)
        self.assertGreaterEqual(CustomPA.copies, 4)

        class CustomRuntime(RuntimeMessages):
            pass

        custom = CustomRuntime(fight)
        self.assertEqual(runtime_scalar_actor_memo(custom), {})
        copied = deepcopy(custom, runtime_scalar_actor_memo(custom))
        self.assertIsNot(copied.fight.future_pa_alias, shared)
        self.assertEqual(copied.fight.future_pa_alias, shared)
