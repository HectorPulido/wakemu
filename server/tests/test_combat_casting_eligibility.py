import unittest
from types import SimpleNamespace

from wakfu_server.combat_casting_eligibility import (
    NativeCastingFlags,
    native_casting_distance,
    native_casting_eligibility,
    native_use_gate_effect,
)
from wakfu_server.combat_conditions import UnknownCondition


class NativeCastingEligibilityTests(unittest.TestCase):
    def hooks(self, **changes):
        self.calls = []
        values = dict(
            container_present=True,
            current_turn_matches=True,
            effective_range=(1, 4),
            cell_and_qi_present=True,
            resolve_target_fighter=None,
            range_distance=2,
            qi_in_bounds=True,
            qi_p=False,
            qi_r=True,
            qi_j=True,
            criterion_present=False,
            criterion_objects=[],
            roots=[],
            target_fighter_present=False,
        )
        values.update(changes)

        def callback(name, value):
            def consume(*args):
                self.calls.append((name, args))
                return value(*args) if callable(value) else value

            return consume

        return SimpleNamespace(
            **{name: callback(name, value) for name, value in values.items()}
        )

    def evaluate(self, **changes):
        return native_casting_eligibility(self.hooks(**changes), NativeCastingFlags())

    def test_trace_preserves_consumption_and_distinguishes_criterion_stage(self):
        hooks = self.hooks(criterion_present=True, criterion_cell=False)
        trace = []
        result = native_casting_eligibility(hooks, NativeCastingFlags(), trace=trace)
        self.assertEqual(result, "twV")
        self.assertEqual(
            [row["stage"] for row in trace[:-1]], [name for name, _ in self.calls]
        )
        self.assertEqual(
            trace[-2], dict(stage="criterion_cell", arguments=[], value=False)
        )
        self.assertNotIn("criterion_objects", [name for name, _ in self.calls])

    def test_early_rejection_does_not_demand_later_geometry(self):
        hooks = SimpleNamespace(container_present=lambda: False)
        self.assertEqual(native_casting_eligibility(hooks, NativeCastingFlags()), "twF")

    def test_target_lookup_precedes_range_and_bounds(self):
        self.assertEqual(self.evaluate(range_distance=8), "twI")
        names = [name for name, _ in self.calls]
        self.assertLess(
            names.index("resolve_target_fighter"), names.index("range_distance")
        )
        self.assertNotIn("qi_in_bounds", names)

    def test_qi_p_and_qi_r_are_distinct(self):
        hooks = self.hooks(qi_p=True)
        self.assertEqual(
            native_casting_eligibility(hooks, NativeCastingFlags(forbid_qi_p=True)),
            "twH",
        )
        self.assertNotIn("qi_r", [name for name, _ in self.calls])
        self.assertEqual(self.evaluate(qi_p=True), "twD")

    def test_missing_authority_is_not_a_success(self):
        hooks = self.hooks()
        del hooks.qi_j
        with self.assertRaisesRegex(UnknownCondition, "qi_j"):
            native_casting_eligibility(hooks, NativeCastingFlags())

    def test_criterion_requires_cell_and_one_actual_object(self):
        self.assertEqual(
            self.evaluate(
                criterion_present=True,
                criterion_cell=True,
                criterion_objects=[7, 8],
                criterion_object=lambda obj: obj == 8,
            ),
            "twD",
        )
        self.assertEqual(
            self.evaluate(criterion_present=True, criterion_cell=False), "twV"
        )
        self.assertNotIn("criterion_objects", [name for name, _ in self.calls])

    def test_collision_precedes_free_cell_and_selector_check(self):
        hooks = self.hooks(
            roots=[1],
            root_has_shape=True,
            root_has_selector=True,
            root_collision_clear=False,
            qi_g=True,
            target_fighter_present=True,
        )
        self.assertEqual(
            native_casting_eligibility(hooks, NativeCastingFlags(free_cell=True)), "twX"
        )
        self.assertNotIn("qi_g", [name for name, _ in self.calls])

    def test_null_selector_accepts_without_shape(self):
        self.assertEqual(
            self.evaluate(
                roots=[1],
                root_has_shape=False,
                root_has_selector=False,
                target_fighter_present=True,
                target_sd_r_other=False,
                caster_sd_g_lower_level=False,
            ),
            "twD",
        )

    def test_target_with_empty_container_roots_rejects_selector(self):
        self.assertEqual(
            self.evaluate(
                target_fighter_present=True,
                target_sd_r_other=False,
                caster_sd_g_lower_level=False,
            ),
            "twE",
        )

    def test_abs_and_sum_preserve_java_overflow(self):
        self.assertEqual(native_casting_distance((0, 0), (-(1 << 31), 0)), -(1 << 31))
        self.assertEqual(
            native_casting_distance((0, 0), ((1 << 31) - 1, 2)), -(1 << 31) + 1
        )

    def test_original_fcj_distance_acceptance_rows(self):
        # ProbeNativeCastingDistance executes the original fcj overload.
        rows = [
            ((0, 0), (2, 0), 1, 4, False, True),
            ((0, 0), (0, 0), 1, 4, False, False),
            ((0, 0), (0, 0), 1, 4, True, True),
            ((0, 0), (-(1 << 31), 0), 1, 4, True, False),
            ((0, 0), (-(1 << 31), 0), -(1 << 31), 4, False, True),
            ((0, 0), ((1 << 31) - 1, 2), -(1 << 31), 4, False, True),
            ((-(1 << 31), 0), ((1 << 31) - 1, 0), 1, 1, False, True),
            ((0, 0), (-(1 << 31), -(1 << 31)), 1, 4, True, True),
        ]
        for source, target, minimum, maximum, allow_self, expected in rows:
            with self.subTest(source=source, target=target):
                hooks = self.hooks(
                    effective_range=(minimum, maximum),
                    range_distance=native_casting_distance(source, target),
                )
                result = native_casting_eligibility(
                    hooks, NativeCastingFlags(allow_self=allow_self)
                )
                self.assertEqual(result == "twD", expected)

    def test_use_gate_evaluates_alignment_even_after_rejected_eligibility(self):
        calls = []

        def eligibility():
            calls.append("eligibility")
            return "twI"

        def alignment():
            calls.append("alignment")
            return False

        self.assertTrue(native_use_gate_effect(eligibility, alignment))
        self.assertEqual(calls, ["eligibility", "alignment"])
        self.assertFalse(native_use_gate_effect(lambda: "twD", lambda: True))


if __name__ == "__main__":
    unittest.main()
