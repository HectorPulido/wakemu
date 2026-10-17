"""Native eYg child failure containment; no unconditional empty-lottery success."""
import unittest
from wakfu_server.combat_effect_groups import EffectGroupMode, execute_ordered_group
from wakfu_server.combat_random_group import (
    NativeRandomProbabilityExhausted,
    weighted_children,
)


class NativeGroupFailureTests(unittest.TestCase):
    def execute(self, mode, callback, *, cells=None):
        return execute_ordered_group(
            mode,
            (10, 20, 30),
            caster_id=7,
            target_id=8,
            target_cell=(0, 0, 0),
            execute_child=callback,
            cell_targets=cells,
        )

    def test_direct_empty_lottery_still_rejects_without_rng(self):
        draws = []
        with self.assertRaisesRegex(
            NativeRandomProbabilityExhausted, "positive remaining"
        ):
            weighted_children(
                (), 1, draw_integer=lambda bound: draws.append(bound) or 0
            )
        self.assertEqual(draws, [])

    def test_actor_group_keeps_prior_children_and_stops_after_native_lottery_error(
        self,
    ):
        visited = []
        state = []

        def child(inv):
            visited.append(inv.child_id)
            if inv.child_id == 20:
                return weighted_children(
                    (), 1, draw_integer=lambda _: self.fail("Unexpected RNG")
                )
            state.append(inv.child_id)
            return True

        with self.assertLogs("wakfu_server.combat_effect_groups", level="ERROR"):
            calls = self.execute(EffectGroupMode(), child)
        self.assertEqual(visited, [10, 20])
        self.assertEqual(state, [10])
        self.assertEqual([c.child_id for c in calls], [10])

    def test_cell_group_stops_other_cells_and_siblings_on_same_native_failure(self):
        visited = []

        def child(inv):
            visited.append((inv.child_id, inv.cell))
            return weighted_children(
                (), 1, draw_integer=lambda _: self.fail("Unexpected RNG")
            )

        with self.assertLogs("wakfu_server.combat_effect_groups", level="ERROR"):
            calls = self.execute(
                EffectGroupMode(on_target=False), child, cells=((0, 0, 0), (1, 0, 0))
            )
        self.assertEqual(calls, ())
        self.assertEqual(visited, [(10, (0, 0, 0))])

    def test_authority_or_malformed_rng_errors_still_escape_group(self):
        for failure in (
            ValueError("Missing source authority"),
            ValueError("Invalid native eXR bounded integer RNG"),
        ):
            with self.subTest(failure=str(failure)):

                def child(inv):
                    raise failure

                with self.assertRaisesRegex(ValueError, str(failure)):
                    self.execute(EffectGroupMode(), child)

    def test_exhaustion_keeps_native_rng_draw_and_applies_no_partial_random_child(self):
        draws = []
        visited = []

        def child(inv):
            visited.append(inv.child_id)
            return weighted_children(
                ((101, 100),), 2, draw_integer=lambda bound: draws.append(bound) or 0
            )

        with self.assertLogs("wakfu_server.combat_effect_groups", level="ERROR"):
            calls = self.execute(EffectGroupMode(), child)
        self.assertEqual(draws, [100])
        self.assertEqual(visited, [10])
        self.assertEqual(calls, ())
