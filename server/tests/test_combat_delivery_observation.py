"""Actual Registry mailbox/dispatch observations never certify client receipt."""
from contextlib import ExitStack
import copy
import os
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_shared import Registry, Session, Batch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_reproduction_state import decode_state
from wakfu_server.combat_shared_incident_capture import suppress_shared_incidents
import wakfu_server.combat_delivery_observation as delivery
import test_combat_shared_reproduction as shared_fixture
import test_combat_shared as registry_fixture


class DeliveryObservationTests(unittest.TestCase):
    def setUp(self):
        self.history = delivery.DeliveryHistory()
        self.receipts = []
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "WAKFU_COMBAT_INCIDENT_DIR": "/private/test-deliveries",
                    "WAKFU_COMBAT_INCIDENT_MODE": "all",
                },
            )
        )
        stack.enter_context(patch.object(delivery, "_HISTORY", self.history))
        stack.enter_context(
            patch(
                "wakfu_server.combat_incident_capture._identity",
                return_value={"test": True},
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.combat_incident_capture._enqueue",
                side_effect=lambda root, receipt: self.receipts.append(receipt),
            )
        )
        fixture = shared_fixture.SharedReproductionTests()
        fixture.setUp()
        self.registry, self.shared = fixture.registry, fixture.shared
        self.one, self.two = fixture.one, fixture.two

    def streams(self, shared=None):
        return decode_state(delivery.delivery_history(shared or self.shared))["streams"]

    def test_dispatch_failure_still_attempts_second_peer_and_keeps_queues_drained(self):
        self.registry.publish(88, self.one, ((13420, b"first"),))
        self.registry.publish(88, self.one, ((13420, b"second"),))
        failure = OSError("first socket failed")
        calls = []

        def send(session, batches):
            calls.append((session, tuple(batch.sequence for batch in batches)))
            if session == self.one:
                raise failure

        with self.assertRaises(OSError) as raised:
            self.registry.dispatch_connected(88, send)
        self.assertIs(raised.exception, failure)
        self.assertEqual(calls, [(self.one, (1, 2)), (self.two, (1, 2))])
        self.assertEqual(
            [len(queue) for queue in self.shared.outboxes.values()], [0, 0]
        )
        self.assertEqual(len(self.receipts), 1)
        receipt = self.receipts[0]
        self.assertEqual(receipt["schema"], delivery.SIDECAR_SCHEMA)
        attempts = decode_state(receipt["attempts"])
        self.assertEqual([row["status"] for row in attempts], ["raised", "returned"])
        self.assertEqual([row["batches"][0]["sequence"] for row in attempts], [1, 1])
        self.assertFalse(receipt["client_receipt_confirmed"])
        self.assertFalse(receipt["replay_qualified"])
        for stream in self.streams():
            self.assertEqual(
                [event["kind"] for event in stream["events"]],
                ["enqueue", "enqueue", "drain", "dispatch_attempt"],
            )
            self.assertTrue(stream["bootstrap_missing"])
            self.assertTrue(stream["history_gap"])

    def test_duel_registration_records_exact_per_owner_bootstrap_and_enqueue(self):
        one, two = Session(1, 10, "duel-one", 1134, 0), Session(
            2, 20, "duel-two", 1134, 0
        )
        actors = [
            Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
            Actor(20, 1, (1, 0, 0), 60, 6, 3, 90, 1, 2, True),
        ]
        fight = Fight(
            99,
            actors,
            {actor.position for actor in actors},
            {0: {actors[0].position}, 1: {actors[1].position}},
        )
        packets = {
            1: ((12847, b"one-first"), (13026, b"one-second")),
            2: ((12847, b"two-first"), (13026, b"two-second")),
        }
        registry = Registry(lambda session: session in (one, two))
        shared = registry.register_duel(fight, (one, two), initial_packets=packets)
        streams = self.streams(shared)
        self.assertEqual(
            [stream["bootstrap"]["packets"] for stream in streams],
            [packets[1], packets[2]],
        )
        self.assertTrue(
            all(
                not stream["bootstrap_missing"] and not stream["history_gap"]
                for stream in streams
            )
        )
        for stream in streams:
            self.assertEqual(
                [row["kind"] for row in stream["events"]], ["bootstrap", "enqueue"]
            )
            self.assertEqual(stream["events"][1]["batches"][0]["sequence"], 1)

    def test_join_and_generation_takeover_do_not_reuse_previous_bootstrap(self):
        fixture = registry_fixture.SharedCombatTests()
        fixture.setUp()
        fixture.join()
        joined = self.streams(fixture.shared)
        second = next(
            stream for stream in joined if stream["session"]["account_id"] == 2
        )
        self.assertEqual(second["bootstrap"]["producer"], "join")
        original = fixture.two
        fixture.live.remove(original)
        replacement = Session(2, 20, "new-generation", 1134, 0)
        fixture.live.add(replacement)
        packets = (
            (12847, b"fresh-generation-first"),
            (13026, b"fresh-generation-second"),
        )
        fixture.registry.takeover(99, replacement, lambda *args: packets)
        stream = next(
            item
            for item in self.streams(fixture.shared)
            if item["session"]["account_id"] == 2
        )
        self.assertEqual(stream["session"]["generation"], "new-generation")
        self.assertEqual(stream["bootstrap"]["packets"], packets)
        self.assertEqual(
            stream["bootstrap"]["previous_generation"], original.generation
        )
        self.assertEqual(
            [row["kind"] for row in stream["events"]], ["bootstrap", "enqueue"]
        )
        self.assertNotEqual(
            stream["bootstrap"]["packets"], second["bootstrap"]["packets"]
        )

    def test_direct_starter_bootstrap_preserves_bytes_and_attempt_failure(self):
        packets = [(12847, b"bootstrap-one"), (13026, b"bootstrap-two")]
        observation = delivery.begin_direct_bootstrap(88, self.one, packets)
        packets.reverse()  # Recorded evidence was frozen before the sends.
        failure = OSError("direct send interrupted")
        delivery.finish_direct_bootstrap(observation, error=failure)
        stream = self.streams()[0]
        expected = ((12847, b"bootstrap-one"), (13026, b"bootstrap-two"))
        self.assertEqual(stream["bootstrap"]["packets"], expected)
        self.assertIsNone(stream["bootstrap"]["sequence"])
        receipt = self.receipts[0]
        attempt = decode_state(receipt["attempts"])[0]
        self.assertEqual(attempt["packets"], expected)
        self.assertEqual(attempt["status"], "raised")
        self.assertFalse(receipt["client_receipt_confirmed"])

    def test_missing_evicted_and_oversized_history_are_explicit(self):
        history = delivery.DeliveryHistory(
            max_streams=1, max_events=2, max_bytes=4096, max_event_bytes=1024
        )
        history.record(88, self.one, "bootstrap", packets=((12847, b"one"),))
        history.record(88, self.two, "bootstrap", packets=((12847, b"two"),))
        snapshot = decode_state(history.snapshot(88, (self.one, self.two)))
        self.assertTrue(snapshot["streams"][0]["bootstrap_missing"])
        self.assertTrue(snapshot["streams"][0]["history_evicted"])
        self.assertTrue(snapshot["streams"][0]["history_gap"])
        history.record(88, self.two, "oversized", packets=((12847, b"x" * 4096),))
        snapshot = decode_state(history.snapshot(88, (self.two,)))
        self.assertTrue(snapshot["streams"][0]["oversized"])
        self.assertTrue(snapshot["streams"][0]["history_gap"])
        self.assertLessEqual(history.bytes, history.max_bytes)
        history.record(88, self.two, "enqueue", batches=())
        history.record(88, self.two, "enqueue", batches=())
        snapshot = decode_state(history.snapshot(88, (self.two,)))
        self.assertTrue(snapshot["streams"][0]["bootstrap_missing"])
        self.assertTrue(snapshot["streams"][0]["history_gap"])

    def test_disabled_and_offline_suppressed_paths_do_not_record_or_write(self):
        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_DIR": ""}), patch.object(
            self.history, "record", side_effect=AssertionError("Disabled history")
        ):
            self.registry.publish(88, self.one, ((13420, b"disabled"),))
            self.registry.dispatch_connected(88, lambda *args: None)
        with suppress_shared_incidents(), patch.object(
            self.history, "record", side_effect=AssertionError("Offline history")
        ):
            self.registry.publish(88, self.one, ((13420, b"offline"),))
            self.registry.dispatch_connected(88, lambda *args: None)
        self.assertEqual(self.history.streams, {})
        self.assertEqual(self.receipts, [])

    def test_shared_receipt_embeds_preceding_bootstrap_without_future_dispatch_claim(
        self,
    ):
        for session in (self.one, self.two):
            delivery.record_bootstrap(
                88,
                session,
                ((12847, b"actual-bootstrap"),),
                sequence=0,
                producer="fixture",
            )
        self.registry.execute(
            88, self.one, 100, lambda fight, runtime: ((13420, b"action"),)
        )
        receipt = self.receipts[0]
        self.assertTrue(receipt["bootstrap_available"])
        self.assertTrue(receipt["delivery_history_continuous"])
        preceding = decode_state(receipt["preceding_delivery_history"])
        self.assertEqual(
            [len(stream["events"]) for stream in preceding["streams"]], [1, 1]
        )
        self.assertFalse(receipt["dispatch_observed"])
        self.registry.dispatch_connected(88, lambda *args: None)
        sidecar = self.receipts[-1]
        self.assertEqual(
            sidecar["process_boot_id"],
            receipt["delivery_correlation"]["process_boot_id"],
        )
        self.assertEqual(
            sidecar["fight_id"], receipt["delivery_correlation"]["fight_id"]
        )
        self.assertEqual(
            decode_state(sidecar["attempts"])[0]["batches"][0]["sequence"], 1
        )

    def test_diagnostic_writer_failure_preserves_original_socket_error(self):
        self.registry.publish(88, self.one, ((13420, b"action"),))
        failure = OSError("socket rejected")
        attempts = []

        def send(session, batches):
            attempts.append(session)
            if session == self.one:
                raise failure

        with patch(
            "wakfu_server.combat_incident_capture._enqueue",
            side_effect=RuntimeError("writer failed"),
        ):
            with self.assertRaises(OSError) as raised:
                self.registry.dispatch_connected(88, send)
        self.assertIs(raised.exception, failure)
        self.assertEqual(attempts, [self.one, self.two])

    def test_actual_serial_dispatch_completions_have_immutable_stream_ordinals(self):
        for payload in (b"first", b"second"):
            self.registry.publish(88, self.one, ((13420, payload),))
            self.registry.dispatch_connected(88, lambda *args: None)
        self.assertEqual(len(self.receipts), 2)
        first = decode_state(self.receipts[0]["attempts"])
        second = decode_state(self.receipts[1]["attempts"])
        for initial, later in zip(first, second):
            self.assertEqual(initial["session"], later["session"])
            self.assertEqual(
                initial["ordinal_boundary"], "serialized-registry-callback-completion"
            )
            self.assertIsInstance(initial["observation_id"], int)
            self.assertGreater(later["observation_id"], initial["observation_id"])
        # Later captures/retention changes cannot mutate encoded sidecars.
        frozen = copy.deepcopy(self.receipts[0]["attempts"])
        self.history.record(88, self.one, "extra", packets=())
        self.assertEqual(self.receipts[0]["attempts"], frozen)


if __name__ == "__main__":
    unittest.main()
