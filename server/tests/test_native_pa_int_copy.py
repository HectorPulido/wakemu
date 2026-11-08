"""Focused compatibility tests for native PA-map deepcopy memo priming."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_preview_copy import scalar_actor_memo


reader_events = []


class ObservablePA(dict):
    def __deepcopy__(self, memo):
        reader_events.append("deepcopy")
        clone = type(self)()
        memo[id(self)] = clone
        for key, value in self.items():
            clone[deepcopy(key, memo)] = deepcopy(value, memo)
        return clone

    def items(self):
        reader_events.append("items")
        return super().items()


class CountingMeta(type):
    eq_calls = 0
    hash_calls = 0

    def __eq__(cls, other):
        type(cls).eq_calls += 1
        return type.__eq__(cls, other)

    def __hash__(cls):
        type(cls).hash_calls += 1
        return type.__hash__(cls)


class MetaInt(int, metaclass=CountingMeta):
    pass


def make_fight():
    first = Actor(101, 0, (0, 0, 0), 50, 6, 3, 12, 10, controlled=True, owner_id=1)
    second = Actor(202, 1, (1, 0, 0), 45, 6, 3, 11, 10, controlled=True, owner_id=2)
    fight = Fight(
        991, [first, second], {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
    )

    exact_ints = {-(10**90): 10**90, 3: -7, 9: 0}
    first.effect_stats = exact_ints
    second.effect_minima = exact_ints
    fight.external_pa_alias = exact_ints

    broad_scalars = {1: True, 2: 1.25, 3: "native", 4: None}
    first.effect_minima = broad_scalars

    nested = {17: {"items": [1, 2]}}
    first.effect_maxima = nested
    second.effect_base_maxima = nested

    custom = ObservablePA({5: {"nested": ["kept"]}})
    second.effect_base_minima = custom

    # Hashing a class as a dictionary key uses its metaclass. Tests clear that
    # setup call before invoking the memo selector.
    odd_key = {MetaInt: 23}
    second.effect_percentages = odd_key
    return fight, exact_ints, broad_scalars, nested, custom, odd_key


class NativePAIntCopyTests(unittest.TestCase):
    def test_scalar_memo_keeps_aliases_and_all_legacy_fallbacks(self):
        exact_actor = Actor(
            301, 0, (0, 0, 0), 20, 4, 2, 5, 3, controlled=True, owner_id=1
        )
        other_actor = Actor(
            302, 1, (1, 0, 0), 20, 4, 2, 4, 3, controlled=True, owner_id=2
        )
        exact_fight = Fight(
            992,
            [exact_actor, other_actor],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        exact_only = {-(10**90): 10**90, 3: -7}
        exact_actor.effect_stats = exact_only
        # An exact-int-only map must take the fast path without consulting the
        # broader scalar predicate at all.
        with patch(
            "wakfu_server.combat_preview_copy._scalar",
            side_effect=AssertionError("broad scalar fallback used"),
        ):
            exact_memo = scalar_actor_memo(exact_fight)
        self.assertIn(id(exact_only), exact_memo)
        self.assertIsNot(exact_memo[id(exact_only)], exact_only)

        fight, exact_ints, broad_scalars, nested, custom, odd_key = make_fight()
        reader_events.clear()
        CountingMeta.eq_calls = CountingMeta.hash_calls = 0

        memo = scalar_actor_memo(fight)
        # Exact-int PA maps use the narrow path; mixed exact scalar maps keep
        # the broader pre-existing scalar behavior.
        self.assertIn(id(exact_ints), memo)
        self.assertIn(id(broad_scalars), memo)
        self.assertIsNot(memo[id(exact_ints)], exact_ints)
        self.assertIsNot(memo[id(broad_scalars)], broad_scalars)
        self.assertNotIn(id(nested), memo)
        self.assertNotIn(id(custom), memo)
        self.assertNotIn(id(odd_key), memo)
        self.assertEqual(reader_events, [])
        self.assertEqual((CountingMeta.eq_calls, CountingMeta.hash_calls), (0, 0))

        baseline = deepcopy(fight)
        baseline_delta = (CountingMeta.eq_calls, CountingMeta.hash_calls)
        baseline_reader_events = reader_events[:]

        reader_events.clear()
        CountingMeta.eq_calls = CountingMeta.hash_calls = 0
        optimized = deepcopy(fight, scalar_actor_memo(fight))
        optimized_delta = (CountingMeta.eq_calls, CountingMeta.hash_calls)
        optimized_reader_events = reader_events[:]
        self.assertEqual(optimized_delta, baseline_delta)
        self.assertEqual(optimized_reader_events, baseline_reader_events)

        for copied in (baseline, optimized):
            self.assertIs(
                copied.actors[101].effect_stats, copied.actors[202].effect_minima
            )
            self.assertIs(copied.external_pa_alias, copied.actors[101].effect_stats)
            self.assertIsNot(copied.external_pa_alias, exact_ints)
            self.assertEqual(copied.actors[101].effect_stats, exact_ints)
            self.assertEqual(copied.actors[101].effect_minima, broad_scalars)
            self.assertIs(
                copied.actors[101].effect_maxima, copied.actors[202].effect_base_maxima
            )
            self.assertIsNot(copied.actors[101].effect_maxima, nested)
            self.assertIs(type(copied.actors[202].effect_base_minima), ObservablePA)
            self.assertEqual(copied.actors[202].effect_percentages, odd_key)

        optimized.external_pa_alias[3] = 999
        optimized.actors[101].effect_minima[1] = False
        optimized.actors[101].effect_maxima[17]["items"].append(3)
        self.assertEqual(exact_ints[3], -7)
        self.assertIs(baseline.external_pa_alias, baseline.actors[101].effect_stats)
        self.assertEqual(broad_scalars[1], True)
        self.assertEqual(nested[17]["items"], [1, 2])
        self.assertEqual(fight.external_pa_alias[3], -7)


if __name__ == "__main__":
    unittest.main()
