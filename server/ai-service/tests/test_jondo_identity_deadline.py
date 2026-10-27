"""Each source fingerprint owns the unchanged native turn allowance."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from test_jondo_bridge import Oracle, Runtime, reply, request_fixture
from test_jondo_busy_retry import BusyTransport
from wakfu_ai.bridge import jondo_entry
from wakfu_ai.native.native_deadline import bounded as native_bounded, check, remaining


class JondoIdentityDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0

    @contextmanager
    def allowance(self, deadline):
        with native_bounded(deadline, clock=lambda: self.now):
            yield

    @contextmanager
    def environment(self):
        with patch.object(jondo_entry, "bounded", self.allowance), patch.object(
            jondo_entry, "build_snapshot", request_fixture
        ), patch.object(jondo_entry.time, "monotonic", side_effect=lambda: self.now):
            yield

    def drive(self, oracle, transport):
        return jondo_entry.run_prepared_turn(
            oracle.runtime, oracle, object(), transport, deadline=101.0, max_actions=1
        )

    def test_all_four_identity_reads_enforce_deadline_during_fingerprint(self):
        # request_fixture does not fingerprint: these calls are precisely the
        # busy reply, accepted reply, pre-candidate and rejected-action guards.
        for site, trigger, status in (
            ("busy_reply", 1, 503),
            ("accepted_reply", 1, 200),
            ("pre_candidate", 2, 200),
            ("rejected_action", 3, 200),
        ):
            with self.subTest(site=site):
                self.now = 100.0
                clock = self

                class CheckingOracle(Oracle):
                    identities = 0

                    def state_identity(self, runtime):
                        self.identities += 1
                        if self.identities == trigger:
                            clock.now = 102.0
                        # The real complete fingerprint reducer/frame writer
                        # calls this same cooperative native deadline check.
                        check()
                        return super().state_identity(runtime)

                oracle = CheckingOracle(Runtime())
                spell = 99 if site == "rejected_action" else 7
                action = dict(type="cast", spellId=spell, level=1, target=[1, 0, 0])
                transport = BusyTransport(
                    lambda request, count: (status, reply(request, action))
                )
                with self.environment(), self.assertRaisesRegex(
                    TimeoutError, "deadline reached"
                ):
                    list(self.drive(oracle, transport))
                self.assertEqual(oracle.identities, trigger)
                self.assertEqual(len(transport.requests), 1)
                self.assertEqual(
                    [a["spellId"] for a in oracle.calls],
                    [99] if site == "rejected_action" else [],
                )
                self.assertEqual(oracle.runtime.ends, 0)
                self.assertIsNone(remaining())

    def test_rejected_mutation_and_changed_fresh_source_still_abort(self):
        for kind in ("mutated_rejection", "changed_reply"):
            with self.subTest(kind=kind):

                class MutatingOracle(Oracle):
                    def state_identity(self, runtime):
                        check()
                        return super().state_identity(runtime)

                    def commit(self, action, **kwargs):
                        self.identity = "illegal-mutation"
                        raise ValueError("Rejected native spell")

                oracle = MutatingOracle(Runtime())

                def choose(request, count):
                    if kind == "changed_reply":
                        oracle.identity = "foreign-transition"
                    return 200, reply(
                        request,
                        dict(type="cast", spellId=99, level=1, target=[1, 0, 0]),
                    )

                expected = (
                    "mutated native state"
                    if kind == "mutated_rejection"
                    else "source changed"
                )
                with self.environment(), self.assertRaisesRegex(ValueError, expected):
                    list(self.drive(oracle, BusyTransport(choose)))
                self.assertEqual(oracle.runtime.ends, 0)
                self.assertIsNone(remaining())

    def test_valid_alternative_yield_and_native_barrier_keep_existing_custody(self):
        clock = self

        class CheckingRuntime(Runtime):
            def end_server_turn(self, actor, turn):
                if remaining() is not None:
                    raise AssertionError(
                        "Final native barrier inherited planning allowance"
                    )
                return super().end_server_turn(actor, turn)

        class CheckingOracle(Oracle):
            def state_identity(self, runtime):
                check()
                if remaining() is None:
                    raise AssertionError("Source fingerprint has no native allowance")
                return super().state_identity(runtime)

        oracle = CheckingOracle(CheckingRuntime())
        bad = dict(type="cast", spellId=99, level=1, target=[1, 0, 0])
        good = dict(type="cast", spellId=7, level=1, target=[1, 0, 0])
        transport = BusyTransport(
            lambda request, count: (200, reply(request, bad, [good]))
        )
        with self.environment():
            driver = self.drive(oracle, transport)
            packets, diagnostic = next(driver)
            self.assertEqual(diagnostic["action"], good)
            self.assertEqual(packets, [(12588, b"native")])
            self.assertIsNone(remaining())
            clock.now = 102.0
            tail = list(driver)
        self.assertEqual([a["spellId"] for a in oracle.calls], [99, 7])
        self.assertEqual(tail[0][1]["reason"], "jondo_native_turn_barrier")
        self.assertEqual(oracle.runtime.ends, 1)
        self.assertIsNone(remaining())

    def test_slow_stage_threshold_reports_wall_and_cpu_even_on_failure(self):
        for duration, failed in ((0.999, False), (1.0, False), (1.2, True)):
            with self.subTest(duration=duration, failed=failed):
                original = ValueError("Original native failure")
                with patch.object(
                    jondo_entry.time, "monotonic", side_effect=[100.0, 100.0 + duration]
                ), patch.object(
                    jondo_entry.time, "process_time", side_effect=[5.0, 5.25]
                ), patch.object(
                    jondo_entry._LOG, "warning"
                ) as warning:
                    try:
                        with jondo_entry._slow_native_stage(
                            "identity_rejection", -7, 3, 8497
                        ):
                            if failed:
                                raise original
                    except ValueError as error:
                        self.assertIs(error, original)
                    self.assertEqual(warning.call_count, int(duration >= 1))
                    if warning.called:
                        args = warning.call_args.args
                        self.assertEqual(args[1:5], ("identity_rejection", -7, 3, 8497))
                        self.assertAlmostEqual(args[5], duration * 1000)
                        self.assertEqual(args[6], 250.0)

    def test_telemetry_sink_failure_preserves_original_native_exception(self):
        original = ValueError("Actual native rejection")
        with patch.object(
            jondo_entry.time, "monotonic", side_effect=[100.0, 102.0]
        ), patch.object(
            jondo_entry._LOG,
            "warning",
            side_effect=OSError("Diagnostic sink unavailable"),
        ):
            with self.assertRaises(ValueError) as caught:
                with jondo_entry._slow_native_stage("native_commit", -7, 3):
                    raise original
        self.assertIs(caught.exception, original)

    def test_commit_timing_finishes_before_generator_yield_and_ack_wait(self):
        clock = self

        class SlowBarrierRuntime(Runtime):
            def end_server_turn(self, actor, turn):
                if remaining() is not None:
                    raise AssertionError(
                        "Final native barrier inherited planning allowance"
                    )
                clock.now += 1.4
                return super().end_server_turn(actor, turn)

        class SlowOracle(Oracle):
            def commit(self, action, **kwargs):
                clock.now += 1.2
                return super().commit(action, **kwargs)

        oracle = SlowOracle(SlowBarrierRuntime())
        good = dict(type="cast", spellId=7, level=1, target=[1, 0, 0])
        transport = BusyTransport(lambda request, count: (200, reply(request, good)))
        with self.environment(), patch.object(jondo_entry._LOG, "warning") as warning:
            driver = jondo_entry.run_prepared_turn(
                oracle.runtime,
                oracle,
                object(),
                transport,
                deadline=110.0,
                max_actions=1,
            )
            next(driver)
            self.assertEqual(warning.call_count, 1)
            self.assertEqual(warning.call_args.args[1], "native_commit")
            self.assertAlmostEqual(warning.call_args.args[5], 1200)
            self.now += 20
            list(driver)
            self.assertEqual(warning.call_count, 2)
            self.assertEqual(warning.call_args.args[1], "native_turn_barrier")
            self.assertAlmostEqual(warning.call_args.args[5], 1400)
            self.assertEqual(oracle.runtime.ends, 1)


if __name__ == "__main__":
    unittest.main()
