"""Passive observations preserve gameplay objects, calls and failures."""
import random
import threading
import unittest
from unittest.mock import patch

from wakfu_server.combat_input_observation import (
    observe_combat_inputs,
    observe_rng,
    observe_clock,
    observe_fact,
    observe_catalog,
    wall_time,
    wall_time_ns,
    replay_combat_inputs,
    InputReplayMismatch,
    replay_rng_argument,
    replay_prepare_rng_argument,
)


class CombatInputObservationTests(unittest.TestCase):
    def test_prepare_rng_argument_preserves_clock_before_binding_order(self):
        rng = random.Random(17)
        with observe_combat_inputs() as observed:
            observe_clock("before-entry", 12.5)
            observe_rng("entry", rng, external=True)
            rng.random()
        with replay_combat_inputs(observed.snapshot()):
            argument = replay_prepare_rng_argument("entry", None)
            self.assertIsNotNone(argument)
            self.assertIs(replay_prepare_rng_argument("entry", None), argument)
            self.assertEqual(observe_clock("before-entry", 0.0), 12.5)
            self.assertIs(observe_rng("entry", argument, external=True), argument)
            argument.random()

    def test_prepare_rng_argument_allows_decoder_rejection_but_not_missing_binding(
        self,
    ):
        empty = {
            "schema": "wakemu-combat-observed-inputs-v1",
            "events": [],
            "rng_streams": [],
            "incomplete": [],
        }
        rejection = ValueError("actual decoder rejection")
        with self.assertRaises(ValueError) as caught:
            with replay_combat_inputs(empty):
                self.assertIsNone(replay_prepare_rng_argument("entry", None))
                raise rejection
        self.assertIs(caught.exception, rejection)
        with self.assertRaises(InputReplayMismatch):
            with replay_combat_inputs(empty):
                argument = replay_prepare_rng_argument("entry", random.Random(17))
                observe_rng("entry", argument, external=True)

    def test_prepare_rng_argument_fallback_identity_and_unknown_ownership(self):
        fallback = random.Random(17)
        self.assertIs(replay_prepare_rng_argument("entry", fallback), fallback)
        with observe_combat_inputs() as observed:
            observe_rng("entry", fallback)
        with self.assertRaises(InputReplayMismatch):
            with replay_combat_inputs(observed.snapshot()):
                replay_prepare_rng_argument("entry", None)

    def test_rng_argument_without_tape_preserves_fallback_identity(self):
        fallback = random.Random(17)
        before = fallback.getstate()
        self.assertIs(replay_rng_argument("unused", fallback), fallback)
        self.assertIsNone(replay_rng_argument("unused", None))
        self.assertEqual(fallback.getstate(), before)

    def test_rng_argument_peek_is_nonconsuming_and_preserves_stream_identity(self):
        with observe_combat_inputs() as observed:
            rng = observe_rng("entry", random.Random(17), external=True)
            rng.random()
        with replay_combat_inputs(observed.snapshot()) as receipt:
            first = replay_rng_argument("entry", None)
            self.assertIs(replay_rng_argument("entry", None), first)
            self.assertIs(observe_rng("entry", first, external=True), first)
            first.random()
            self.assertTrue(receipt.ownership_known)

    def test_rng_argument_requires_matching_label_state_and_known_ownership(self):
        with observe_combat_inputs() as observed:
            observe_rng("entry", random.Random(17), external=True)
        for change in ("label", "state", "ownership"):
            snapshot = observed.snapshot()
            if change == "ownership":
                snapshot["events"][0].pop("external")
            elif change == "state":
                snapshot["events"][0]["state"] = random.Random(42).getstate()
            with self.subTest(change=change), self.assertRaises(InputReplayMismatch):
                with replay_combat_inputs(snapshot):
                    replay_rng_argument("wrong" if change == "label" else "entry", None)

    def test_rng_argument_respects_real_external_rollback_and_internal_draws(self):
        from wakfu_server.combat_random_transaction import rollback_external_rng

        @rollback_external_rng
        def rejected(*, rng=None):
            owned = observe_rng(
                "entry",
                random.Random(17) if rng is None else rng,
                external=rng is not None,
            )
            owned.random()
            raise ValueError("expected gameplay rejection")

        for external in (False, True):
            with self.subTest(external=external):
                original = random.Random(17) if external else None
                with self.assertRaises(ValueError):
                    with observe_combat_inputs() as observed:
                        rejected(rng=original)
                snapshot = observed.snapshot()
                stream = snapshot["rng_streams"][0]
                self.assertEqual(
                    stream["initial_state"] == stream["final_state"], external
                )
                with self.assertRaises(ValueError):
                    with replay_combat_inputs(snapshot) as receipt:
                        argument = replay_rng_argument("entry", random.Random(0))
                        self.assertEqual(argument is None, not external)
                        rejected(rng=argument)
                self.assertTrue(receipt.ownership_known)

    def test_rng_ownership_records_explicit_external_and_internal_bindings(self):
        rng = random.Random(17)
        before = rng.getstate()
        with observe_combat_inputs() as observed:
            self.assertIs(observe_rng("created", rng, external=False), rng)
            self.assertIs(observe_rng("factory", rng, external=True), rng)
        events = observed.snapshot()["events"]
        self.assertIs(events[0]["external"], False)
        self.assertIs(events[1]["external"], True)
        self.assertEqual(rng.getstate(), before)
        with replay_combat_inputs(observed.snapshot()) as replay:
            first = observe_rng("created", random.Random(0), external=False)
            self.assertIs(observe_rng("factory", first, external=True), first)
            self.assertTrue(replay.ownership_known)
            self.assertEqual(replay.ownership_unknown, [])

    def test_replay_rejects_rng_ownership_mismatch(self):
        with observe_combat_inputs() as observed:
            observe_rng("created", random.Random(17), external=False)
        with self.assertRaisesRegex(InputReplayMismatch, "ownership differs"):
            with replay_combat_inputs(observed.snapshot()):
                observe_rng("created", random.Random(17), external=True)

    def test_historical_rng_ownership_remains_explicitly_unknown(self):
        with observe_combat_inputs() as observed:
            observe_rng("historical", random.Random(17), external=True)
        snapshot = observed.snapshot()
        snapshot["events"][0].pop("external")
        with replay_combat_inputs(snapshot) as replay:
            observe_rng("historical", random.Random(0), external=True)
            self.assertFalse(replay.ownership_known)
            self.assertEqual(replay.ownership_unknown[0]["source"], "capture")

    def test_unknown_replay_ownership_cannot_qualify_known_capture(self):
        with observe_combat_inputs() as observed:
            observe_rng("created", random.Random(17), external=False)
        with replay_combat_inputs(observed.snapshot()) as replay:
            observe_rng("created", random.Random(0))
            self.assertFalse(replay.ownership_known)
            self.assertEqual(replay.ownership_unknown[0]["source"], "replay")

    def test_invalid_rng_ownership_is_diagnostic_in_live_scope_and_replay_error(self):
        rng = random.Random(17)
        with observe_combat_inputs() as observed:
            self.assertIs(observe_rng("invalid", rng, external=1), rng)
        self.assertTrue(observed.snapshot()["incomplete"])
        with observe_combat_inputs() as observed:
            observe_rng("valid", rng, external=True)
        snapshot = observed.snapshot()
        snapshot["events"][0]["external"] = 1
        with self.assertRaises(InputReplayMismatch):
            with replay_combat_inputs(snapshot):
                pass

    def captured_sequence(self):
        first, second = random.Random(17), random.Random(42)
        with observe_combat_inputs() as observed:
            observe_fact("unrelated-authority", {"id": 7})
            observe_rng("critical", first)
            critical = first.random()
            observe_clock("deadline", 123.25)
            observe_rng("effect", first)
            damage = first.randint(1, 20)
            observe_rng("boundary", second)
            trigger = second.random()
            observe_clock("wall", 1700000000.25)
        return observed.snapshot(), (critical, damage, trigger)

    def test_replay_restores_independent_streams_and_aliases_without_extra_draws(self):
        snapshot, expected = self.captured_sequence()
        ignored = random.Random(777)
        before = ignored.getstate()
        with replay_combat_inputs(snapshot):
            first = observe_rng("critical", ignored)
            critical = first.random()
            self.assertEqual(observe_clock("deadline", -1.0), 123.25)
            alias = observe_rng("effect", ignored)
            self.assertIs(alias, first)
            damage = alias.randint(1, 20)
            second = observe_rng("boundary", ignored)
            self.assertIsNot(second, first)
            trigger = second.random()
            with patch(
                "wakfu_server.combat_input_observation.time.time",
                side_effect=AssertionError("Replay used live clock"),
            ):
                self.assertEqual(wall_time("wall"), 1700000000.25)
        self.assertEqual((critical, damage, trigger), expected)
        self.assertEqual(ignored.getstate(), before)

    def test_replay_rejects_mismatched_labels_order_and_unused_evidence(self):
        snapshot, _ = self.captured_sequence()
        for attempt in ("wrong", "clock", "unused"):
            with self.subTest(attempt=attempt), self.assertRaises(
                InputReplayMismatch
            ) as caught:
                with replay_combat_inputs(snapshot):
                    if attempt == "wrong":
                        observe_rng("wrong", random.Random(0))
                    elif attempt == "clock":
                        observe_clock("deadline", 1.0)
            self.assertNotIsInstance(caught.exception, ValueError)

    def test_replay_rejects_wrong_binding_and_final_rng_states(self):
        with observe_combat_inputs() as observed:
            rng = observe_rng("stream", random.Random(17))
            rng.random()
            observe_rng("next", rng)
        snapshot = observed.snapshot()
        with self.assertRaisesRegex(InputReplayMismatch, "binding state"):
            with replay_combat_inputs(snapshot):
                observe_rng("stream", random.Random(0))
                observe_rng("next", random.Random(0))
        with observe_combat_inputs() as observed:
            rng = observe_rng("stream", random.Random(17))
            rng.random()
        with self.assertRaisesRegex(InputReplayMismatch, "final RNG"):
            with replay_combat_inputs(observed.snapshot()):
                observe_rng("stream", random.Random(0))

    def test_replay_rejects_incomplete_or_malformed_receipts(self):
        snapshot, _ = self.captured_sequence()
        for change in (
            {"incomplete": ["event_limit_exceeded"]},
            {"rng_streams": []},
            {
                "events": [
                    {"sequence": 0, "kind": "clock", "label": "clock", "value": 1}
                ]
            },
            {"schema": "unknown"},
        ):
            with self.subTest(change=list(change)), self.assertRaises(
                InputReplayMismatch
            ):
                with replay_combat_inputs(dict(snapshot, **change)):
                    pass

    def test_replay_preserves_matching_gameplay_failure_and_restores_context(self):
        rng = random.Random(17)
        before = rng.getstate()
        failure = ValueError("game rejection")
        with self.assertRaises(ValueError):
            with observe_combat_inputs() as observed:
                observe_rng("transaction", rng)
                rng.random()
                rng.setstate(before)
                raise failure
        with self.assertRaises(ValueError) as caught:
            with replay_combat_inputs(observed.snapshot()):
                private = observe_rng("transaction", random.Random(0))
                private.random()
                private.setstate(before)
                raise failure
        self.assertIs(caught.exception, failure)
        outside = random.Random(1)
        self.assertIs(observe_rng("outside", outside), outside)

    def test_replay_rejects_nested_scope_and_unobserved_extra_inputs(self):
        empty = {
            "schema": "wakemu-combat-observed-inputs-v1",
            "events": [],
            "rng_streams": [],
            "incomplete": [],
        }
        with replay_combat_inputs(empty):
            with self.assertRaises(InputReplayMismatch):
                with replay_combat_inputs(empty):
                    pass
        with self.assertRaises(InputReplayMismatch):
            with replay_combat_inputs(empty):
                observe_clock("unknown", 1.0)

    def test_disabled_rng_never_reads_state_or_consumes_a_draw(self):
        class Unobservable:
            def getstate(self):
                raise AssertionError("Disabled observer read state")

        rng = Unobservable()
        self.assertIs(observe_rng("off", rng), rng)
        real = random.Random(17)
        before = real.getstate()
        self.assertIs(observe_rng("off", real), real)
        self.assertEqual(real.getstate(), before)

    def test_identity_initial_bindings_and_final_rng_states_are_distinct(self):
        rng = random.Random(17)
        other = random.Random(17)
        expected_initial = rng.getstate()
        with observe_combat_inputs() as observed:
            self.assertIs(observe_rng("critical", rng), rng)
            rng.random()
            observe_rng("effects", rng)
            observe_rng("other", other)
        evidence = observed.snapshot()
        self.assertEqual(
            [event["stream_id"] for event in evidence["events"]], [0, 0, 1]
        )
        self.assertEqual(evidence["rng_streams"][0]["initial_state"], expected_initial)
        self.assertEqual(evidence["rng_streams"][0]["final_state"], rng.getstate())
        self.assertNotEqual(
            evidence["events"][0]["state"], evidence["events"][1]["state"]
        )
        self.assertEqual(evidence["incomplete"], [])

    def test_clock_helpers_preserve_exact_values_and_call_counts(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                with patch(
                    "wakfu_server.combat_input_observation.time.time",
                    return_value=17.125,
                ) as seconds, patch(
                    "wakfu_server.combat_input_observation.time.time_ns",
                    return_value=17125000000,
                ) as nanos:
                    if enabled:
                        with observe_combat_inputs() as observed:
                            self.assertEqual(wall_time("wall"), 17.125)
                            self.assertEqual(wall_time_ns("ns"), 17125000000)
                            observe_clock("runtime", 5.75)
                        self.assertEqual(
                            [event["value"] for event in observed.snapshot()["events"]],
                            [17.125, 17125000000, 5.75],
                        )
                    else:
                        self.assertEqual(wall_time("wall"), 17.125)
                        self.assertEqual(wall_time_ns("ns"), 17125000000)
                    seconds.assert_called_once_with()
                    nanos.assert_called_once_with()

    def test_fact_copy_retains_binary_key_types_and_is_detached(self):
        value = {7: (b"exact", {3, 2}), "frozen": frozenset({8})}
        with observe_combat_inputs() as observed:
            self.assertIs(observe_fact("authority", value), value)
            value[7][1].add(4)
        saved = observed.snapshot()["events"][0]["value"]
        self.assertEqual(saved[7], (b"exact", {2, 3}))
        self.assertIsInstance(saved["frozen"], frozenset)

    def test_observer_error_does_not_replace_gameplay_exception(self):
        class Broken:
            def getstate(self):
                raise RuntimeError("private diagnostic text")

        failure = ValueError("actual gameplay failure")
        with self.assertRaises(ValueError) as caught:
            with observe_combat_inputs() as observed:
                observe_rng("broken", Broken())
                raise failure
        self.assertIs(caught.exception, failure)
        evidence = observed.snapshot()
        self.assertEqual(evidence["incomplete"], ["observer_failed:RuntimeError"])
        self.assertEqual(
            evidence["events"][-1]["exception_type"], "builtins.ValueError"
        )
        self.assertNotIn("private diagnostic text", repr(evidence))

    def test_bounds_are_explicit_and_do_not_reject_gameplay_values(self):
        with observe_combat_inputs(limit=1, max_value_bytes=32) as observed:
            blob = b"a" * 33
            self.assertIs(observe_fact("large", blob), blob)
            observe_fact("first", 1)
            observe_fact("second", 2)
        self.assertEqual(len(observed.snapshot()["events"]), 1)
        self.assertTrue(observed.snapshot()["incomplete"])

    def test_contexts_nest_and_do_not_leak_to_other_threads(self):
        with observe_combat_inputs() as outer:
            observe_fact("outer-before", 1)
            with observe_combat_inputs() as inner:
                observe_fact("inner", 2)
            worker = threading.Thread(target=lambda: observe_fact("thread", 3))
            worker.start()
            worker.join()
            observe_fact("outer-after", 4)
        observe_fact("outside", 5)
        self.assertEqual(
            [event["label"] for event in outer.snapshot()["events"]],
            ["outer-before", "outer-after"],
        )
        self.assertEqual(
            [event["label"] for event in inner.snapshot()["events"]], ["inner"]
        )

    def test_catalog_observation_retains_actual_index_lookup_and_missing_record(self):
        result = {"id": 7, "effect": [1, 2]}
        with observe_combat_inputs() as observed:
            self.assertIs(
                observe_catalog(
                    "record",
                    "catalog.json",
                    result,
                    revision="release",
                    collection="effects",
                    record_key="7",
                ),
                result,
            )
            self.assertIsNone(
                observe_catalog(
                    "record",
                    "catalog.json",
                    None,
                    revision="release",
                    collection="effects",
                    record_key="8",
                )
            )
        events = observed.snapshot()["events"]
        self.assertEqual(events[0]["value"], result)
        self.assertEqual(events[1]["record_key"], "8")
        self.assertIsNone(events[1]["value"])

    def test_final_rng_observation_failure_is_explicit(self):
        class BreaksAfterBinding:
            def __init__(self):
                self.calls = 0

            def getstate(self):
                self.calls += 1
                if self.calls > 1:
                    raise RuntimeError("private")
                return (1,)

        with observe_combat_inputs() as observed:
            observe_rng("stream", BreaksAfterBinding())
        evidence = observed.snapshot()
        self.assertIsNone(evidence["rng_streams"][0]["final_state"])
        self.assertIn("rng_final_state_failed:RuntimeError", evidence["incomplete"])
