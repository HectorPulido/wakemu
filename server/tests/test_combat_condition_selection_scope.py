import unittest

from wakfu_server.combat_cell_group import select_cell_group
from wakfu_server.combat_condition_selection_scope import (
    condition_actor_selection_scope,
    current_condition_actor_cache,
)


class ConditionSelectionScopeTests(unittest.TestCase):
    def setUp(self):
        self.adapter, self.preview = object(), object()

    def cache(self):
        return current_condition_actor_cache(self.adapter, self.preview)

    def select(self, condition, *, reuse=True, rng=lambda: 0):
        return select_cell_group(
            dict(parameters=[2, 0, 1, 0, 0, 0, 1]),
            [(0, 0, 0), (1, 0, 0)],
            caster_position=(0, 0, 0),
            condition=condition,
            rng=rng,
            reuse_condition_actors=reuse,
        )

    def test_actor_memo_shared_but_each_cell_predicate_runs(self):
        cells, caches = [], []

        def condition(cell):
            cells.append(cell)
            caches.append(self.cache())
            return cell[0] == 1

        result = self.select(condition)
        self.assertEqual(cells, [(0, 0, 0), (1, 0, 0)])
        self.assertIs(caches[0], caches[1])
        self.assertEqual(result.cells, ((1, 0, 0),))
        self.assertIsNone(self.cache())

    def test_new_selection_refreshes_and_rng_has_no_cache(self):
        observations = []
        state = [1]

        def condition(cell):
            cache = self.cache()
            observations.append(cache.setdefault(7, state[0]))
            return True

        def rng():
            self.assertIsNone(self.cache())
            return 0

        self.select(condition, rng=rng)
        state[0] = 2
        self.select(condition, rng=rng)
        self.assertEqual(observations, [1, 1, 2, 2])

    def test_arbitrary_callbacks_default_to_no_reuse(self):
        seen = []
        self.select(lambda cell: seen.append(self.cache()) or True, reuse=False)
        self.assertEqual(seen, [None, None])

    def test_failure_resets_scope(self):
        def condition(cell):
            self.assertIsNotNone(self.cache())
            raise ValueError("predicate failed")

        with self.assertRaisesRegex(ValueError, "predicate failed"):
            self.select(condition)
        self.assertIsNone(self.cache())

    def test_nested_selection_and_preview_identity_are_isolated(self):
        with condition_actor_selection_scope():
            outer = self.cache()
            outer[7] = "outer"
            other = current_condition_actor_cache(self.adapter, object())
            self.assertIsNot(other, outer)
            with condition_actor_selection_scope():
                self.assertEqual(self.cache(), {})
                self.cache()[7] = "inner"
            self.assertIs(self.cache(), outer)
            self.assertEqual(outer[7], "outer")
        self.assertIsNone(self.cache())

    def test_nested_opt_out_suspends_and_invalidates_outer_even_on_failure(self):
        with condition_actor_selection_scope():
            outer = self.cache()
            for fail in (False, True):
                outer[7] = "old projection"

                def condition(cell):
                    self.assertIsNone(self.cache())
                    if fail:
                        raise ValueError("callback mutated state then failed")
                    return True

                if fail:
                    with self.assertRaisesRegex(ValueError, "callback mutated"):
                        self.select(condition, reuse=False)
                else:
                    self.select(condition, reuse=False)
                self.assertIs(self.cache(), outer)
                self.assertEqual(outer, {})
        self.assertIsNone(self.cache())
