"""Partial-search cancellation runs after execution and before another action."""
import unittest
from unittest.mock import patch

import test_native_turn as fixtures
from wakfu_ai.native import native_turn
from wakfu_ai.native.native_deadline import check, remaining


class PostCommitCleanupTests(unittest.TestCase):
    def fixture(self, *, cancel_failure=None, cancel_expiry=False):
        fixture = fixtures.NativeTurnDriverTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        now, events, release = [0.0], [], []
        original_commit = fixture.oracle.commit

        def commit(action, **kwargs):
            events.append("commit:" + action["type"])
            result = original_commit(action, **kwargs)
            if action["type"] == "cast":
                now[0] += 0.05
            return result

        class Session(fixtures.FakeSession):
            def decide(self, *, certify=True):
                if type(self).calls == 1:
                    # Mandatory partial recertification is covered through the
                    # real NativeSession in test_native_partial_decision.
                    events.append("recertified")
                    self.needs_cleanup = True
                    now[0] = 0.7
                    return dict(
                        action=dict(type="cast", spellId=77, level=1), partial=True
                    )
                events.append("next_decision")
                if not release:
                    raise AssertionError("next decision preceded backend cancellation")
                return dict(action=dict(type="end_turn"))

            def cancel(self):
                events.append("cancel")
                self_test.assertEqual(
                    fixture.oracle.commits[-1]["action"]["type"], "cast"
                )
                self_test.assertAlmostEqual(remaining(), 0.25)
                if cancel_failure is not None:
                    raise cancel_failure
                if cancel_expiry:
                    now[0] += 0.251
                    check()
                release.append(True)
                self.needs_cleanup = False

        self_test = self
        return fixture, now, events, Session, commit

    def test_recertify_commit_cancel_order_and_release_before_next_decision(self):
        fixture, now, events, session, commit = self.fixture()
        with patch.object(native_turn, "NativeSession", session), patch.object(
            fixture.oracle, "commit", commit
        ):
            deliveries = list(
                fixture.run_turn(budget_seconds=1.2, clock=lambda: now[0])
            )
        self.assertEqual(
            events,
            [
                "recertified",
                "commit:cast",
                "cancel",
                "next_decision",
                "commit:end_turn",
            ],
        )
        self.assertEqual(deliveries[0][0], [("committed", "cast")])
        self.assertIn("search_cleanup", deliveries[0][1]["stageElapsedMs"])
        self.assertEqual(fixture.runtime.fight.actors[-9].ap, 5)

    def test_resource_error_during_cancel_does_not_undo_or_hide_committed_delivery(
        self,
    ):
        fixture, now, events, session, commit = self.fixture(
            cancel_failure=ConnectionError("backend unavailable")
        )
        with patch.object(native_turn, "NativeSession", session), patch.object(
            fixture.oracle, "commit", commit
        ):
            driver = fixture.run_turn(
                budget_seconds=1.2, clock=lambda: now[0], max_actions=1
            )
            packets, decision = next(driver)
            driver.close()
        self.assertEqual(events, ["recertified", "commit:cast", "cancel"])
        self.assertEqual(packets, [("committed", "cast")])
        self.assertEqual(decision["nativeSearchCleanupError"], "ConnectionError")
        self.assertEqual(fixture.runtime.fight.actors[-9].ap, 5)

    def test_cleanup_deadline_is_separate_and_never_authorizes_another_action(self):
        fixture, now, events, session, commit = self.fixture(cancel_expiry=True)
        with patch.object(native_turn, "NativeSession", session), patch.object(
            fixture.oracle, "commit", commit
        ):
            driver = fixture.run_turn(
                budget_seconds=1.2, clock=lambda: now[0], max_actions=1
            )
            packets, decision = next(driver)
            driver.close()
        self.assertEqual(events, ["recertified", "commit:cast", "cancel"])
        self.assertEqual(decision["nativeSearchCleanupError"], "TimeoutError")
        self.assertEqual(packets, [("committed", "cast")])
        self.assertEqual(fixture.runtime.fight.actors[-9].ap, 5)


if __name__ == "__main__":
    unittest.main()
