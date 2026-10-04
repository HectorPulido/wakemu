import unittest
from wakfu_server.combat_relative_probability import relative_candidates


class RelativeProbabilityTests(unittest.TestCase):
    def test_independent_rolls_can_accept_both_or_neither(self):
        rows = [(7, 50), (8, 50)]
        self.assertEqual(
            relative_candidates(
                rows,
                draw_integer=lambda total: 1,
                draw_fraction=lambda p: self.fail("Integral weight uses no draw"),
            ),
            (7, 8),
        )
        self.assertEqual(
            relative_candidates(
                rows,
                draw_integer=lambda total: total,
                draw_fraction=lambda p: self.fail("Integral weight uses no draw"),
            ),
            (),
        )

    def test_rng_order_and_per_step_short_accumulation(self):
        seen = []

        def integer(total):
            seen.append(("integer", total))
            return 1

        def fraction(probability):
            seen.append(("fraction", probability))
            return True

        self.assertEqual(
            relative_candidates(
                [(7, 0.75), (8, 0.75)], draw_integer=integer, draw_fraction=fraction
            ),
            (7, 8),
        )
        # Each short sum truncates .75 to zero, so UK.pT(0) consumes no draw.
        self.assertEqual(seen, [("fraction", 0.75), ("fraction", 0.75)])
        seen.clear()
        relative_candidates(
            [(7, 1.5), (8, 2.5)], draw_integer=integer, draw_fraction=fraction
        )
        self.assertEqual(
            seen, [("integer", 3), ("fraction", 0.5), ("integer", 3), ("fraction", 0.5)]
        )

    def test_short_overflow_and_nonpositive_total_use_native_one(self):
        self.assertEqual(
            relative_candidates(
                [(7, 32767), (8, 1)],
                draw_integer=lambda total: self.fail("Negative total consumes no RNG"),
                draw_fraction=lambda p: self.fail("Integral weight consumes no RNG"),
            ),
            (7, 8),
        )

    def test_reject_unknown_or_invalid_authority(self):
        for raw in (float("nan"), float("inf"), None):
            with self.assertRaises(ValueError):
                relative_candidates(
                    [(7, raw)], draw_integer=lambda t: 1, draw_fraction=lambda p: True
                )
        with self.assertRaises(ValueError):
            relative_candidates(
                [(7, 50)], draw_integer=lambda t: 0, draw_fraction=lambda p: True
            )


class RelativeCandidateEligibilityTests(unittest.TestCase):
    def test_native_area_level_and_subscription_order(self):
        from wakfu_server.combat_relative_probability import (
            relative_eligible_candidates,
        )

        base = dict(
            reference=7,
            probability=50,
            native_area_has_actor=False,
            minimum_level=1,
            maximum_level=200,
            subscribed=False,
            criterion_accepts=True,
        )
        rows = [
            dict(base, reference=1, native_area_has_actor=True),
            dict(base, reference=2, minimum_level=100),
            dict(base, reference=3, criterion_accepts=False),
            dict(base, reference=4, subscribed=True, criterion_accepts=None),
            base,
        ]
        self.assertEqual(
            relative_eligible_candidates(rows, level=20), ((4, 50), (7, 50))
        )

    def test_unknown_targeting_is_not_empty(self):
        from wakfu_server.combat_relative_probability import (
            relative_eligible_candidates,
        )

        with self.assertRaisesRegex(ValueError, "amQ"):
            relative_eligible_candidates([dict(reference=7)], level=20)
