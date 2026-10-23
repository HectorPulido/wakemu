"""Expired owner deadlines cannot suppress bounded remote-search cleanup."""
import unittest
from unittest.mock import patch

import test_native_turn as fixtures
from wakfu_ai.native.native_deadline import bounded, check, cleanup_budget, remaining


class NativeCleanupBudgetTests(unittest.TestCase):
    def test_expired_outer_deadline_allows_cancel_but_no_additional_game_action(self):
        fixture = fixtures.NativeTurnDriverTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        now, cancellations = [0.0], []

        def late(session, *, certify=True):
            now[0] = 3.5
            return dict(action=dict(type="cast", spellId=77, level=1))

        def cancel(session):
            cancellations.append(remaining())

        with patch.object(fixtures.FakeSession, "decide", late), patch.object(
            fixtures.FakeSession, "cancel", cancel, create=True
        ):
            with bounded(3.0, clock=lambda: now[0]):
                deliveries = list(
                    fixture.run_turn(budget_seconds=3, clock=lambda: now[0])
                )
                with self.assertRaises(TimeoutError):
                    remaining()
        self.assertEqual(cancellations, [0.25])
        self.assertEqual(
            [row["action"]["type"] for row in fixture.oracle.commits], ["end_turn"]
        )
        self.assertEqual(fixture.runtime.fight.actors[-9].ap, 6)
        self.assertEqual(deliveries[0][1]["error"], "TimeoutError")
        self.assertIsNone(remaining())

    def test_cleanup_expires_after_250ms_and_restores_expired_outer(self):
        now = [0.0]
        with bounded(1.0, clock=lambda: now[0]):
            now[0] = 2.0
            with cleanup_budget(clock=lambda: now[0]):
                self.assertEqual(remaining(), 0.25)
                now[0] += 0.2
                self.assertAlmostEqual(remaining(), 0.05)
                now[0] += 0.051
                with self.assertRaises(TimeoutError):
                    check()
            with self.assertRaises(TimeoutError):
                remaining()
        self.assertIsNone(remaining())

    def test_nested_cleanup_and_bounded_cannot_renew_the_allowance(self):
        now = [10.0]
        with cleanup_budget(clock=lambda: now[0]):
            now[0] += 0.1
            with cleanup_budget(clock=lambda: now[0]):
                self.assertAlmostEqual(remaining(), 0.15)
                with bounded(99.0, clock=lambda: now[0]):
                    self.assertAlmostEqual(remaining(), 0.15)
            now[0] += 0.151
            with self.assertRaises(TimeoutError):
                check()
            with self.assertRaises(TimeoutError):
                with cleanup_budget(clock=lambda: now[0]):
                    self.fail("nested cleanup renewed an expired cleanup deadline")
        self.assertIsNone(remaining())

    def test_cleanup_exception_restores_exact_outer_context(self):
        now = [0.0]
        with bounded(5.0, clock=lambda: now[0]):
            with self.assertRaisesRegex(ValueError, "cleanup failed"):
                with cleanup_budget(clock=lambda: now[0]):
                    now[0] = 0.1
                    raise ValueError("cleanup failed")
            self.assertAlmostEqual(remaining(), 4.9)
        self.assertIsNone(remaining())

    def test_normal_nested_deadlines_still_never_extend_parent(self):
        now = [0.0]
        with bounded(1.0, clock=lambda: now[0]):
            with bounded(10.0, clock=lambda: now[0]):
                self.assertEqual(remaining(), 1.0)
            now[0] = 1.1
            with self.assertRaises(TimeoutError):
                with bounded(10.0, clock=lambda: now[0]):
                    self.fail("normal nested budget extended expired parent")
        self.assertIsNone(remaining())

    def test_failed_cancel_preserves_original_failure_and_owner_deadline(self):
        fixture = fixtures.NativeTurnDriverTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        now, cancellations = [0.0], []

        def rejected(session, *, certify=True):
            now[0] = 3.5
            raise ValueError("original native query rejection")

        def cancel(session):
            cancellations.append(remaining())
            raise ConnectionError("remote cancel unavailable")

        with patch.object(fixtures.FakeSession, "decide", rejected), patch.object(
            fixtures.FakeSession, "cancel", cancel, create=True
        ):
            with bounded(3.0, clock=lambda: now[0]):
                deliveries = list(
                    fixture.run_turn(budget_seconds=3, clock=lambda: now[0])
                )
                with self.assertRaises(TimeoutError):
                    remaining()
        self.assertEqual(cancellations, [0.25])
        self.assertEqual(deliveries[0][1]["error"], "ValueError")
        self.assertEqual(deliveries[0][1]["detail"], "original native query rejection")
        self.assertEqual(
            [row["action"]["type"] for row in fixture.oracle.commits], ["end_turn"]
        )

    def test_cancel_that_reaches_cleanup_deadline_does_not_renew_owner(self):
        fixture = fixtures.NativeTurnDriverTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        now, cancellations = [0.0], []

        def late(session, *, certify=True):
            now[0] = 3.5
            return dict(action=dict(type="cast", spellId=77, level=1))

        def cancel(session):
            cancellations.append(True)
            now[0] += 0.251
            check()

        with patch.object(fixtures.FakeSession, "decide", late), patch.object(
            fixtures.FakeSession, "cancel", cancel, create=True
        ):
            with bounded(3.0, clock=lambda: now[0]):
                deliveries = list(
                    fixture.run_turn(budget_seconds=3, clock=lambda: now[0])
                )
                with self.assertRaises(TimeoutError):
                    remaining()
        self.assertEqual(cancellations, [True])
        self.assertEqual(deliveries[0][1]["error"], "TimeoutError")
        self.assertEqual(fixture.runtime.fight.actors[-9].ap, 6)
        self.assertIsNone(remaining())


if __name__ == "__main__":
    unittest.main()
