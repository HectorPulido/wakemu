"""PA memo reuse preserves private graph aliases and failed-action isolation."""
from copy import deepcopy
from random import Random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_entry_executor import private_entry_preview
from wakfu_server.combat_preview_copy import scalar_actor_memo
from wakfu_server.combat_retained_collections import bound_collections
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.native import native_oracle


class StopAfterClone(Exception):
    pass


class CustomPA(dict):
    copies = 0

    def __deepcopy__(self, memo):
        type(self).copies += 1
        result = type(self)()
        memo[id(self)] = result
        result.update(deepcopy(dict(self), memo))
        return result


def fixture():
    live = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
    retired = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
    fight = Fight(
        505,
        [live, retired],
        {live.position, retired.position},
        {0: {live.position}, 1: {retired.position}},
    )
    retired.hp = 0
    retired.native_obstacle_id = -1
    shared = {1: 0, 2: 1.5, 3: True, 4: "value", 5: None}
    retired.effect_minima = retired.effect_base_minima = fight.future_pa_alias = shared
    live.effect_stats = {1: 60, 4: 6}
    live.effect_percentages = {1: {"values": [1]}}
    live.effect_maxima = CustomPA({1: 60})
    return fight


class NativePreviewPACopyTests(unittest.TestCase):
    def test_entry_commit_and_turn_boundaries_keep_aliases_and_rollback(self):
        fight = fixture()
        retired = fight.actors[-7]
        before = deepcopy(fight)
        calls = []
        original_memo = scalar_actor_memo

        def memo(source):
            result = original_memo(source)
            calls.append(source)
            self.assertIn(id(retired.effect_minima), result)
            return result

        def assert_private(copied):
            self.assertEqual(set(copied.actors), set(fight.actors))
            self.assertEqual(
                {
                    k: v
                    for k, v in vars(copied.actors[-7]).items()
                    if k != "state_ledger"
                },
                {
                    k: v
                    for k, v in vars(before.actors[-7]).items()
                    if k != "state_ledger"
                },
            )
            self.assertEqual(
                copied.actors[-7].state_ledger.entries,
                before.actors[-7].state_ledger.entries,
            )
            self.assertIs(copied.future_pa_alias, copied.actors[-7].effect_minima)
            self.assertIs(copied.future_pa_alias, copied.actors[-7].effect_base_minima)
            self.assertIsNot(copied.future_pa_alias, fight.future_pa_alias)
            self.assertIsNot(
                bound_collections(vars(copied)), bound_collections(vars(fight))
            )
            self.assertEqual(
                copied.actors[7].effect_maxima, fight.actors[7].effect_maxima
            )
            self.assertIs(
                type(copied.actors[7].effect_maxima),
                type(fight.actors[7].effect_maxima),
            )
            copied.future_pa_alias[1] = 999
            copied.actors[7].effect_percentages[1]["values"].append(2)
            self.assertEqual(fight.future_pa_alias[1], 0)
            self.assertEqual(fight.actors[7].effect_percentages[1]["values"], [1])

        with patch("wakfu_server.combat_preview_copy.scalar_actor_memo", new=memo):
            source, copied = private_entry_preview(
                fight, snapshot=lambda value: value.id
            )
            self.assertEqual(source, fight.id)
            assert_private(copied)
            custom_calls = []

            def custom_clone(value):
                custom_calls.append(value)
                return deepcopy(value)

            _, custom = private_entry_preview(
                fight, snapshot=lambda value: value.id, clone=custom_clone
            )
            self.assertEqual(len(calls), 1)
            self.assertEqual(custom_calls, [fight])
            assert_private(custom)

            oracle = NativeOracle.__new__(NativeOracle)
            oracle._rng = lambda state, action: Random(1)

            def factory(state, action_id, rng):
                assert_private(state)
                raise StopAfterClone()

            oracle.factory = factory
            for method in (oracle.start_boundary, oracle.end_boundary):
                with self.assertRaises(StopAfterClone):
                    method(fight, actor_id=7, action_id=1)

            fight.actors[7].effect_maxima = dict(fight.actors[7].effect_maxima)
            runtime = RuntimeMessages(fight)
            runtime.extra_actor_alias = retired
            oracle.runtime = runtime
            oracle.authorities = lambda runtime: {}
            oracle.flags = {}

            def clone_runtime(value, copy_memo):
                self.assertIs(value, runtime)
                copied_runtime = deepcopy(value, copy_memo)
                self.assertIs(
                    copied_runtime.extra_actor_alias, copied_runtime.fight.actors[-7]
                )
                assert_private(copied_runtime.fight)
                raise StopAfterClone()

            with patch.object(native_oracle, "deepcopy", new=clone_runtime):
                with self.assertRaises(StopAfterClone):
                    oracle._commit(
                        {"type": "end_turn"}, stats_serializer=lambda actor: ()
                    )
            self.assertEqual(len(calls), 4)
        self.assertEqual(retired.effect_minima, before.actors[-7].effect_minima)
        self.assertEqual(
            retired.state_ledger.entries, before.actors[-7].state_ledger.entries
        )
        self.assertGreaterEqual(CustomPA.copies, 5)

        # Both actual registry seams must discard failed private transactions.
        from test_combat_shared import SharedCombatTests

        case = SharedCombatTests()
        case.setUp()
        original = case.fight
        historical = Actor(-201, 1, (2, 0, 0), 10, 6, 3, 1, 1)
        historical.hp = 0
        historical.native_obstacle_id = -1
        original.actors[-201] = historical
        historical.effect_minima = historical.effect_base_minima = {1: 0}
        case.shared.runtime["actor_alias"] = historical
        case.shared.runtime["fight"] = original
        seen = []

        def operation(candidate, runtime):
            seen.append(True)
            self.assertIs(runtime["fight"], candidate)
            self.assertIs(runtime["actor_alias"], candidate.actors[-201])
            self.assertIs(
                candidate.actors[-201].effect_minima,
                candidate.actors[-201].effect_base_minima,
            )
            self.assertIsNot(candidate.actors[-201], historical)
            candidate.actors[-201].effect_minima[1] = 99
            raise StopAfterClone()

        with self.assertRaises(StopAfterClone):
            case.registry.execute(99, case.one, 10, operation, require_turn=False)
        original.phase = "active"
        original.order = [-200, 10]
        original.turn_index = 0
        with self.assertRaises(StopAfterClone):
            case.registry.execute_server(
                99, -200, operation, expected_sequence=case.shared.sequence
            )
        self.assertEqual(len(seen), 2)
        self.assertIs(case.shared.fight, original)
        self.assertIs(case.shared.runtime["actor_alias"], historical)
        self.assertEqual(historical.effect_minima, {1: 0})
