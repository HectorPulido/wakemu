import unittest
import struct

from wakfu_server.combat_spectators import (
    ObserverSession,
    SpectatorRegistry,
    TerminalAck,
)
from wakfu_server.combat_spectator_wire import (
    decode_spectator_bootstrap,
    decode_spectator_request,
    decode_timeline_snapshot,
    spectator_bootstrap,
    timeline_snapshot,
)


def bootstrap_fixture():
    return {
        "fight_id": 456,
        "kind": 1,
        "bqh": 123,
        "myo": 234,
        "myp": 345,
        "myD": b"topology",
        "myG": b"",
        "myI": 1,
        "myJ": 2,
        "compact": False,
        "participants": [
            {
                "actor_id": 10,
                "myB": 0,
                "myn": 1,
                "myC": 2,
                "myE": b"stats",
                "myF": b"effects",
            }
        ],
        "myH": [],
        "myM": [],
        "myN": [],
        "myK": [],
    }


def native_snapshot(fight_id, marker=b"topology"):
    value = bootstrap_fixture()
    value["fight_id"] = fight_id
    value["myD"] = marker
    timeline = timeline_snapshot(3)
    return spectator_bootstrap(value, phase_code=2, timeline_snapshot=timeline)


class SpectatorRegistryTests(unittest.TestCase):
    def setUp(self):
        self.owner = ObserverSession(1, 10, "owner-gen", 1134, 7)
        self.observer = ObserverSession(2, 20, "observer-gen", 1134, 7)
        self.other = ObserverSession(3, 30, "other-gen", 1134, 7)
        self.live = {self.owner, self.observer, self.other}
        self.registry = SpectatorRegistry(lambda session: session in self.live)
        self.registry.publish_fight(
            900,
            map_id=1134,
            instance_id=7,
            participant_sessions=(self.owner,),
            revision=4,
            snapshot_packets=(native_snapshot(900),),
            visible=True,
        )

    def test_existing_observer_receives_events_while_new_entry_requires_fresh_snapshot(
        self,
    ):
        self.registry.enter(self.observer, 900, authorize=lambda *_: True)
        self.registry.defer_enter(self.other, 900, authorize=lambda *_: True)
        self.registry.publish_events(
            900, revision=5, event_packets=((13091, b"summon"), (13624, b"move"))
        )
        delivery = self.registry.poll(self.observer)
        self.assertEqual(delivery[0].packets, ((13091, b"summon"), (13624, b"move")))
        self.assertEqual(self.registry.observing(self.other), 900)
        self.assertEqual(self.registry.poll(self.other), ())
        with self.assertRaisesRegex(ValueError, "snapshot is not current"):
            self.registry.enter(self.other, 900, authorize=lambda *_: True)
        self.registry.publish_update(
            900,
            revision=6,
            snapshot_packets=(native_snapshot(900, b"includes-summon"),),
            event_packets=((12588, b"spell"),),
        )
        self.assertEqual(
            self.registry.poll(self.observer)[0].packets, ((12588, b"spell"),)
        )
        # The explicit failed entry removed its pending lease; it can now enter
        # at the rebuilt current roster, then consume only future actions.
        late = self.registry.enter(self.other, 900, authorize=lambda *_: True)
        self.assertTrue(late.is_snapshot)
        self.registry.publish_events(
            900, revision=7, event_packets=((13624, b"next-move"),)
        )
        self.assertEqual(
            self.registry.poll(self.other)[0].packets, ((13624, b"next-move"),)
        )

    def test_native_cva_bootstrap_roundtrip_matches_inherited_cvb_layout(self):
        timeline = timeline_snapshot(
            3,
            # Mirrors the installed Trove map iteration order in the native
            # golden verifier; the format itself does not promise map order.
            actor_entries=((20, 9, False), (10, 7, True)),
            fYZ_entries={4: ()},
            fZb_entries={5: ()},
        )
        opcode, body = spectator_bootstrap(
            bootstrap_fixture(), phase_code=2, timeline_snapshot=timeline
        )
        self.assertEqual(opcode, 12044)
        decoded = decode_spectator_bootstrap(body)
        self.assertEqual(decoded["fight_id"], 456)
        self.assertEqual(decoded["participants"][0]["myE"], b"stats")
        self.assertEqual(decoded["participants"][0]["myF"], b"effects")
        self.assertEqual(decoded["myD"], b"topology")
        self.assertEqual(decoded["phase_code"], 2)
        self.assertEqual(decoded["timeline_snapshot"], timeline)
        for damaged in (body[:-1], body + b"\x00"):
            with self.assertRaises(ValueError):
                decode_spectator_bootstrap(damaged)
        with self.assertRaises(ValueError):
            spectator_bootstrap(
                bootstrap_fixture(), phase_code=6, timeline_snapshot=timeline
            )
        with self.assertRaises(ValueError):
            spectator_bootstrap(
                bootstrap_fixture(), phase_code=2, timeline_snapshot=b""
            )

    def test_native_feN_snapshot_roundtrip_is_current_state_and_strict(self):
        snapshot = timeline_snapshot(
            3,
            actor_entries=((10, 7, True), (20, 9, False)),
            fYZ_entries={4: (11, 12)},
            fZb_entries={5: (21,)},
        )
        self.assertEqual(
            decode_timeline_snapshot(snapshot),
            {
                "period": 3,
                "actor_entries": [(10, 7, True), (20, 9, False)],
                "fYZ_entries": {4: [11, 12]},
                "fZb_entries": {5: [21]},
            },
        )
        for bad in (
            b"",
            snapshot[:-1],
            timeline_snapshot(3) + b"\x00",
        ):
            with self.assertRaises(ValueError):
                decode_timeline_snapshot(bad)
        with self.assertRaises(ValueError):
            timeline_snapshot(0)
        with self.assertRaises(ValueError):
            timeline_snapshot(3, actor_entries=((10, 7, 1),))

    def test_enter_and_leave_requests_are_exact_positive_i32(self):
        self.assertEqual(decode_spectator_request(struct.pack(">i", 456)), 456)
        for body in (
            b"",
            b"\0\0\1",
            struct.pack(">i", 0),
            struct.pack(">i", -1),
            struct.pack(">i", 456) + b"\0",
        ):
            with self.assertRaises(ValueError):
                decode_spectator_request(body)

    def enter(self, session=None):
        return self.registry.enter(
            session or self.observer,
            900,
            authorize=lambda _session, _fight: True,
        )

    def test_entry_delivers_current_snapshot_not_historical_events(self):
        initial = self.enter()
        self.assertEqual(self.registry.observing(self.observer), 900)
        self.assertEqual(self.registry.sessions(900), (self.observer,))
        self.assertEqual(initial.revision, 4)
        self.assertTrue(initial.is_snapshot)
        self.assertEqual(initial.packets, (native_snapshot(900),))
        self.assertEqual(self.registry.poll(self.observer), ())

        self.registry.publish_update(
            900,
            revision=5,
            snapshot_packets=(native_snapshot(900, b"updated-state"),),
            event_packets=((13000, b"future-event"),),
        )
        deliveries = self.registry.poll(self.observer)
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].fight_id, 900)
        self.assertEqual(deliveries[0].revision, 5)
        self.assertEqual(deliveries[0].packets, ((13000, b"future-event"),))
        self.assertFalse(deliveries[0].is_snapshot)

    def test_reentry_snapshot_discards_older_queued_events(self):
        self.enter()
        self.registry.publish_update(
            900,
            revision=5,
            snapshot_packets=(native_snapshot(900, b"revision-five"),),
            event_packets=((13000, b"revision-five-event"),),
        )
        current = self.enter()
        self.assertEqual(current.revision, 5)
        self.assertEqual(current.packets, (native_snapshot(900, b"revision-five"),))
        self.assertEqual(self.registry.poll(self.observer), ())

    def test_ack_gap_delivers_public_events_then_only_latest_snapshot_to_pending_entry(
        self,
    ):
        self.enter(self.observer)
        self.assertTrue(
            self.registry.defer_enter(self.other, 900, authorize=lambda *_: True)
        )
        self.assertEqual(self.registry.observing(self.other), 900)
        self.assertEqual(self.registry.poll(self.other), ())

        self.registry.publish_events(
            900, revision=5, event_packets=((12502, b"turn-ended"),)
        )
        existing = self.registry.poll(self.observer)
        self.assertEqual(
            [entry.packets for entry in existing], [((12502, b"turn-ended"),)]
        )
        self.assertEqual(self.registry.poll(self.other), ())

        self.registry.publish_update(
            900,
            revision=6,
            snapshot_packets=(native_snapshot(900, b"after-ack-current-state"),),
            event_packets=((13482, b"next-turn"),),
        )
        deferred = self.registry.poll(self.other)
        self.assertEqual(len(deferred), 1)
        self.assertTrue(deferred[0].is_snapshot)
        self.assertEqual(deferred[0].revision, 6)
        self.assertEqual(
            deferred[0].packets,
            (native_snapshot(900, b"after-ack-current-state"),),
        )
        # The entrant gets the current state, not events already represented by
        # that state. Existing subscribers continue receiving ordinary batches.
        self.assertEqual(self.registry.poll(self.other), ())
        released = self.registry.poll(self.observer)
        self.assertEqual(
            [entry.packets for entry in released], [((13482, b"next-turn"),)]
        )

    def test_pending_entry_is_canceled_by_leave_disconnect_stale_lease_and_terminal(
        self,
    ):
        self.registry.defer_enter(self.other, 900, authorize=lambda *_: True)
        self.assertTrue(self.registry.leave(self.other, 900))
        self.registry.publish_update(
            900,
            revision=5,
            snapshot_packets=(native_snapshot(900, b"new"),),
            event_packets=(),
        )
        self.assertIsNone(self.registry.observing(self.other))

        self.registry.defer_enter(self.other, 900, authorize=lambda *_: True)
        self.live.remove(self.other)
        self.registry.publish_update(
            900,
            revision=6,
            snapshot_packets=(native_snapshot(900, b"newer"),),
            event_packets=(),
        )
        self.assertIsNone(self.registry.observing(self.other))
        self.live.add(self.other)

        self.registry.defer_enter(self.other, 900, authorize=lambda *_: True)
        self.assertTrue(self.registry.disconnect(self.other))
        self.assertIsNone(self.registry.observing(self.other))

        self.registry.defer_enter(self.other, 900, authorize=lambda *_: True)
        self.registry.publish_terminal(
            900, revision=7, event_packets=((12238, b"finished"),)
        )
        self.assertIsNone(self.registry.observing(self.other))
        self.assertEqual(self.registry.poll(self.other), ())

    def test_pending_entries_are_bounded_and_replaced_by_current_generation(self):
        bounded = SpectatorRegistry(
            lambda session: session in self.live,
            max_pending_batches=1,
        )
        bounded.publish_fight(
            900,
            map_id=1134,
            instance_id=7,
            participant_sessions=(self.owner,),
            revision=4,
            snapshot_packets=(native_snapshot(900),),
            visible=True,
        )
        bounded.defer_enter(self.other, 900, authorize=lambda *_: True)
        self.assertTrue(bounded.defer_enter(self.other, 900, authorize=lambda *_: True))
        with self.assertRaisesRegex(ValueError, "queue is full"):
            bounded.defer_enter(self.observer, 900, authorize=lambda *_: True)
        replacement = ObserverSession(3, 30, "other-next", 1134, 7)
        self.live.add(replacement)
        bounded.defer_enter(replacement, 900, authorize=lambda *_: True)
        bounded.publish_update(
            900,
            revision=5,
            snapshot_packets=(native_snapshot(900, b"replacement"),),
            event_packets=(),
        )
        self.assertIsNone(bounded.observing(self.other))
        queued = bounded.poll(replacement)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].packets, (native_snapshot(900, b"replacement"),))

    def test_pending_entry_rechecks_authoritative_location_before_snapshot(self):
        locations = {self.other: (1134, 7)}
        registry = SpectatorRegistry(
            lambda session: session in self.live,
            live_location=lambda session: locations.get(session)
            == (session.map_id, session.instance_id),
        )
        registry.publish_fight(
            903,
            map_id=1134,
            instance_id=7,
            participant_sessions=(self.owner,),
            revision=0,
            snapshot_packets=(native_snapshot(903),),
            visible=True,
        )
        registry.defer_enter(self.other, 903, authorize=lambda *_: True)
        locations[self.other] = (1134, 8)
        registry.publish_update(
            903,
            revision=1,
            snapshot_packets=(native_snapshot(903, b"new-instance"),),
            event_packets=(),
        )
        self.assertIsNone(registry.observing(self.other))
        self.assertEqual(registry.poll(self.other), ())

    def test_hidden_default_location_and_explicit_authorization_fail_closed(self):
        self.registry.publish_fight(
            901,
            map_id=1134,
            instance_id=7,
            participant_sessions=(self.owner,),
            revision=0,
            snapshot_packets=(native_snapshot(901),),
        )
        with self.assertRaises(ValueError):
            self.registry.enter(self.observer, 901, authorize=lambda *_: True)
        with self.assertRaises(ValueError):
            self.registry.enter(self.observer, 900, authorize=lambda *_: 1)
        foreign = ObserverSession(4, 40, "foreign", 1134, 8)
        self.live.add(foreign)
        with self.assertRaises(ValueError):
            self.registry.enter(foreign, 900, authorize=lambda *_: True)

    def test_participant_cannot_observe_or_gain_a_second_membership(self):
        with self.assertRaises(ValueError):
            self.registry.enter(self.owner, 900, authorize=lambda *_: True)
        same_account_alt = ObserverSession(1, 11, "alt", 1134, 7)
        self.live.add(same_account_alt)
        with self.assertRaises(ValueError):
            self.registry.enter(same_account_alt, 900, authorize=lambda *_: True)

    def test_leave_disconnect_and_fight_close_are_idempotent_and_isolated(self):
        self.enter()
        self.registry.enter(self.other, 900, authorize=lambda *_: True)
        self.assertTrue(self.registry.leave(self.observer, 900))
        self.assertIsNone(self.registry.observing(self.observer))
        self.assertFalse(self.registry.leave(self.observer, 900))
        self.assertEqual(len(self.registry.poll(self.observer)), 0)
        self.assertTrue(self.registry.disconnect(self.other))
        self.assertFalse(self.registry.disconnect(self.other))
        self.assertEqual(self.registry.close_fight(900), ())
        self.assertEqual(self.registry.close_fight(900), ())

    def test_terminal_cleanup_reaches_observers_then_retires_snapshot(self):
        self.registry.publish_fight(
            901,
            map_id=1134,
            instance_id=7,
            participant_sessions=(self.owner,),
            revision=0,
            snapshot_packets=(native_snapshot(901),),
            visible=True,
        )
        self.registry.publish_terminal(
            901,
            revision=1,
            event_packets=((12238, b"native-end"),),
        )
        self.assertNotIn(901, self.registry.fights)

    def test_terminal_snapshot_is_removed_after_last_observer_drains(self):
        self.enter()
        self.registry.publish_terminal(
            900,
            revision=5,
            event_packets=((12238, b"native-end"),),
        )
        # Keep the closed fight indexed until every observer has received its
        # terminal event, then release all fight and session references.
        self.assertIn(900, self.registry.fights)
        deliveries = self.registry.poll(self.observer)
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].packets, ((12238, b"native-end"),))
        self.assertNotIn(900, self.registry.fights)
        self.assertIsNone(self.registry.observing(self.observer))

    def test_repeated_owner_terminal_publication_does_not_duplicate_native_cleanup(
        self,
    ):
        self.enter()
        first = (12238, b"native-end-one")
        self.registry.publish_terminal(900, revision=5, event_packets=(first,))
        self.assertEqual(
            self.registry.publish_terminal(
                900, revision=6, event_packets=((12238, b"native-end-two"),)
            ),
            (),
        )
        self.assertEqual(self.registry.poll(self.observer)[0].packets, (first,))

    def test_new_generation_does_not_inherit_subscription(self):
        self.enter()
        self.live.remove(self.observer)
        replacement = ObserverSession(2, 20, "replacement-gen", 1134, 7)
        self.live.add(replacement)
        self.assertEqual(self.registry.poll(replacement), ())
        self.assertEqual(self.registry.disconnect(self.observer), True)
        self.assertEqual(
            self.registry.enter(replacement, 900, authorize=lambda *_: True).revision,
            4,
        )

    def test_revision_regression_malformed_packets_and_bounded_slow_observer(self):
        self.enter()
        with self.assertRaises(ValueError):
            self.registry.publish_update(
                900, revision=4, snapshot_packets=(), event_packets=()
            )
        with self.assertRaises(ValueError):
            self.registry.publish_update(
                900, revision=5, snapshot_packets=((12044, "bad"),), event_packets=()
            )
        bounded = SpectatorRegistry(
            lambda session: session in self.live, max_pending_batches=1
        )
        bounded.publish_fight(
            902,
            map_id=1134,
            instance_id=7,
            participant_sessions=(self.owner,),
            revision=0,
            snapshot_packets=(native_snapshot(902),),
            visible=True,
        )
        bounded.enter(self.observer, 902, authorize=lambda *_: True)
        for revision in (1, 2):
            bounded.publish_update(
                902,
                revision=revision,
                snapshot_packets=(native_snapshot(902, str(revision).encode()),),
                event_packets=((13000, bytes((revision,))),),
            )
        self.assertEqual(bounded.poll(self.observer), ())
        # Only the slow observer was detached; the fight remains published.
        self.assertIn(902, bounded.fights)
        self.assertEqual(
            bounded.enter(self.observer, 902, authorize=lambda *_: True).revision, 2
        )

    def test_terminal_ack_requires_same_lease_fight_and_native_loss_flag(self):
        pending = TerminalAck(self.observer, 900)
        self.assertTrue(pending.validate(self.observer, struct.pack(">iB", 900, 1)))
        replacement = ObserverSession(2, 20, "new-generation", 1134, 7)
        for session, body in (
            (replacement, struct.pack(">iB", 900, 1)),
            (self.observer, struct.pack(">iB", 901, 1)),
            (self.observer, struct.pack(">iB", 900, 0)),
        ):
            with self.assertRaises(ValueError):
                pending.validate(session, body)


if __name__ == "__main__":
    unittest.main()
