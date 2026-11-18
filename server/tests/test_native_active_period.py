"""Native recurring active-window boundaries and acceptance-clock fencing."""

import unittest

from wakfu_server.achievements.native_active_period import (
    active_for_period,
    period_boundary_ms,
)


class NativeActivePeriodTests(unittest.TestCase):
    def setUp(self):
        self.definition = {"cjT": 1_000_000, "cjU": 60}

    def test_period_boundary_matches_native_second_precision_edges(self):
        cases = (
            (-61_000, 880_000),
            (-60_000, 880_000),
            (-59_000, 940_000),
            (-1_000, 940_000),
            (-1, 940_000),
            (0, 940_000),
            (1, 940_000),
            (999, 940_000),
            (1_000, 1_000_000),
            (59_999, 1_000_000),
            (60_000, 1_060_000),
            (60_001, 1_060_000),
            (120_000, 1_120_000),
        )
        for offset, expected in cases:
            with self.subTest(offset=offset):
                self.assertEqual(
                    period_boundary_ms(self.definition, now_ms=1_000_000 + offset),
                    expected,
                )

    def test_unanchored_active_period_does_not_require_acceptance_clock(self):
        definition = {"cjT": 0, "cjU": 0}
        self.assertIsNone(period_boundary_ms(definition, now_ms=1_000_000))
        self.assertTrue(
            active_for_period(
                definition, active=True, accepted_at_ms=None, now_ms=1_000_000
            )
        )
        self.assertFalse(
            active_for_period(
                definition, active=False, accepted_at_ms=1_000_000, now_ms=1_000_000
            )
        )

    def test_anchored_period_requires_valid_definition_and_persisted_acceptance(self):
        for definition in (
            {"cjT": True, "cjU": 60},
            {"cjT": 1_000_000, "cjU": True},
            {"cjT": 1_000_000, "cjU": 0},
        ):
            with self.subTest(definition=definition):
                self.assertFalse(
                    active_for_period(
                        definition,
                        active=True,
                        accepted_at_ms=1_000_000,
                        now_ms=1_000_000,
                    )
                )
        for accepted_at in (None, True, -1):
            with self.subTest(accepted_at=accepted_at):
                self.assertFalse(
                    active_for_period(
                        self.definition,
                        active=True,
                        accepted_at_ms=accepted_at,
                        now_ms=1_000_000,
                    )
                )

    def test_old_acceptance_expires_at_the_exact_boundary(self):
        self.assertFalse(
            active_for_period(
                self.definition,
                active=True,
                accepted_at_ms=939_999,
                now_ms=1_000_000,
            )
        )
        self.assertTrue(
            active_for_period(
                self.definition,
                active=True,
                accepted_at_ms=940_000,
                now_ms=1_000_000,
            )
        )


if __name__ == "__main__":
    unittest.main()
