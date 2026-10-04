import struct, threading, unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_multiplayer_wire import (
    decode_added,
    decode_join,
    external,
    decode_external,
)


class SharedCombatTests(unittest.TestCase):
    def setUp(self):
        self.one = Session(1, 10, "first", 1134, 0)
        self.two = Session(2, 20, "second", 1134, 0)
        self.live = {self.one, self.two}
        self.registry = Registry(lambda session: session in self.live)
        self.fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (3, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        self.shared = self.registry.register(
            self.fight, self.one, runtime={"native": "own"}, group_lease=("own-group",)
        )

    def join(self, session=None):
        session = session or self.two
        actor = Actor(
            session.character_id,
            0,
            (0, 0, 0),
            60,
            6,
            3,
            90,
            1,
            session.account_id,
            True,
        )
        return self.registry.join(
            session,
            struct.pack(">qB", 10, 0),
            actor,
            actor_payload=lambda *args: (b"ownstats", b"owneffects"),
            bootstrap_packets=lambda f, s, o: [(12847, b"owned-bootstrap")],
        )

    def test_two_sessions_share_fsm_and_ordered_native_outboxes(self):
        self.join()
        f = self.shared.fight
        self.assertEqual(f.actors[20].position, (1, 0, 0))
        first = self.registry.drain(99, self.one)
        second = self.registry.drain(99, self.two)
        self.assertEqual([p[0] for p in first[0].packets], [13091, 13026])
        self.assertEqual(decode_added(first[0].packets[0][1])["actor_id"], 20)
        self.assertEqual([p[0] for p in second[0].packets], [12847])
        self.assertEqual(first[0].sequence, second[0].sequence)
        self.registry.ready(99, self.one, True, lambda f, r: [])
        self.assertEqual(self.shared.fight.phase, "placement")
        self.registry.ready(99, self.two, True, lambda f, r: [])
        self.assertEqual(self.shared.fight.phase, "active")
        self.assertEqual(self.shared.fight.current.id, 10)
        with self.assertRaises(ValueError):
            self.registry.execute(99, self.two, 10, lambda f, r: [])
        with self.assertRaises(ValueError):
            self.registry.execute(99, self.two, 20, lambda f, r: [])
        seq = self.shared.sequence
        self.registry.execute(
            99,
            self.one,
            10,
            lambda f, r: (f.end_turn(1, 10, f.turn_id), [])[1],
            expected_sequence=seq,
        )
        with self.assertRaises(ValueError):
            self.registry.execute(
                99, self.one, 10, lambda f, r: [], expected_sequence=seq
            )

    def test_takeover_and_old_disconnect_do_not_remove_new_owner(self):
        self.join()
        self.live.remove(self.one)
        new = Session(1, 10, "replacement", 1134, 0)
        self.live.add(new)
        self.registry.takeover(
            99, new, lambda f, s, o: [(12847, b"new-owned-bootstrap")]
        )
        self.assertEqual(self.registry.disconnect(self.one), [])
        self.assertIn(1, self.shared.connected)
        with self.assertRaises(ValueError):
            self.registry.drain(99, self.one)
        self.assertEqual(
            self.registry.drain(99, new)[0].packets, ((12847, b"new-owned-bootstrap"),)
        )
        self.assertEqual(self.registry.disconnect(new), [99])
        self.assertIn(2, self.shared.connected)
        self.assertEqual(self.shared.group_lease, ("own-group",))

    def test_concurrent_last_free_cell_reserves_once(self):
        three = Session(3, 30, "third", 1134, 0)
        self.live.add(three)
        results = []

        def attempt(session):
            try:
                self.join(session)
                results.append(True)
            except ValueError:
                results.append(False)

        threads = [
            threading.Thread(target=attempt, args=(s,)) for s in (self.two, three)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(len(self.shared.fight.actors), 3)

    def test_serializer_failure_does_not_mutate_membership_or_placement(self):
        def fail(*args):
            raise ValueError("Invalid own codec")

        with self.assertRaises(ValueError):
            self.registry.join(
                self.two,
                struct.pack(">qB", 10, 0),
                Actor(20, 0, (0, 0, 0), 60, 6, 3, 90, 1, 2, True),
                actor_payload=fail,
                bootstrap_packets=lambda *args: [],
            )
        self.assertEqual(set(self.shared.fight.actors), {10, -200})
        self.assertNotIn(20, self.registry.by_character)

    def test_finish_retry_settles_all_owners_once(self):
        self.join()
        self.shared.fight.phase = "finished"
        seen = []

        def settle(shared):
            seen.append(tuple(shared.participants))

        self.assertTrue(self.registry.remove_finished(99, settle))
        self.assertFalse(self.registry.remove_finished(99, settle))
        self.assertEqual(seen, [(1, 2)])

    def test_foreign_map_and_native_join_flag_rejected(self):
        outsider = Session(3, 30, "outside", 1134, 5)
        self.live.add(outsider)
        with self.assertRaises(ValueError):
            self.join(outsider)
        with self.assertRaises(ValueError):
            decode_join(struct.pack(">qB", 10, 2))

    def test_external_codec_preserves_all_explicit_native_fields(self):
        value = dict(
            fight_id=99,
            kind=2,
            myo=1134,
            myp=123,
            jqi=6,
            myu=1000,
            myr=[10, -200],
            teams=[(10, 0), (-200, 1)],
            phase_code=0,
            flags=[False, False, False, False],
            mys=[(2, 3)],
            topology=b"own-native-topology",
        )
        opcode, body = external(value)
        self.assertEqual(opcode, 13753)
        self.assertEqual(decode_external(body), value)

    def test_failed_action_rolls_back_fsm_runtime_and_does_not_broadcast(self):
        self.registry.ready(99, self.one, True, lambda f, r: [])
        before = self.shared.sequence

        def invalid(fight, runtime):
            runtime["native"] = "corrupted"
            fight.current.hp = 1
            raise ValueError("Rejected native action")

        with self.assertRaises(ValueError):
            self.registry.execute(99, self.one, 10, invalid)
        self.assertEqual(self.shared.runtime, {"native": "own"})
        self.assertEqual(self.shared.fight.current.hp, 60)
        self.assertEqual(self.shared.sequence, before)

    def test_group_lease_survives_starter_socket_disconnect_until_settlement(self):
        self.join()
        self.registry.disconnect(self.one)
        self.assertTrue(self.registry.lease_active(("own-group",)))
        self.shared.fight.phase = "finished"
        self.registry.remove_finished(99, lambda shared: None)
        self.assertFalse(self.registry.lease_active(("own-group",)))

    def test_native_ack_waits_for_both_sessions_not_only_current_owner(self):
        self.join()
        self.registry.drain(99, self.one)
        self.registry.drain(99, self.two)
        self.registry.arm_ack(99, 7)
        calls = []

        def release(fight, runtime, body):
            calls.append(body)
            return [(13482, b"next-turn")]

        self.assertFalse(
            self.registry.acknowledge(99, self.one, struct.pack(">i", 7), release)
        )
        self.assertFalse(
            self.registry.acknowledge(99, self.one, struct.pack(">i", 7), release)
        )
        self.assertEqual(calls, [])
        self.assertEqual(self.registry.drain(99, self.two), [])
        with self.assertRaises(ValueError):
            self.registry.acknowledge(99, self.two, struct.pack(">i", 6), release)
        self.assertTrue(
            self.registry.acknowledge(99, self.two, struct.pack(">i", 7), release)
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            self.registry.drain(99, self.one)[0].packets, ((13482, b"next-turn"),)
        )

    def test_disconnect_does_not_synthesize_missing_turn_ack(self):
        self.join()
        self.registry.arm_ack(99, 7)
        self.registry.disconnect(self.two)
        self.assertFalse(
            self.registry.acknowledge(
                99, self.one, struct.pack(">i", 7), lambda *args: []
            )
        )
        self.assertEqual(self.shared.ack.expected, {1: "first", 2: "second"})
        self.assertFalse(self.shared.ack.complete)

    def test_runtime_fsm_reference_remains_same_authority_after_dispatch(self):
        self.shared.runtime = {"fight": self.shared.fight}
        self.registry.ready(99, self.one, True, lambda f, r: [])
        self.assertIs(self.shared.runtime["fight"], self.shared.fight)

        def action(f, r):
            self.assertIs(r["fight"], f)
            f.spend(1, 10, ap=1)
            return []

        self.registry.execute(99, self.one, 10, action)
        self.assertEqual(self.shared.runtime["fight"].current.ap, 5)
