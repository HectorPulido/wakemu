"""Explicit recovery publishes one coherent shared timeline without extending clocks."""
import struct
import unittest
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages


def decoded_timeline(body):
    state = memoryview(body)[15:]
    round_number, turn, phase, deadline = struct.unpack_from(">hiBq", state)
    offset = 15

    def ids():
        nonlocal offset
        count = struct.unpack_from(">b", state, offset)[0]
        offset += 1
        values = struct.unpack_from(">" + "q" * count, state, offset)
        offset += count * 8
        return values

    order, following = ids(), ids()
    count = struct.unpack_from(">b", state, offset)[0]
    offset += 1 + count * 10
    index = struct.unpack_from(">b", state, offset)[0]
    offset += 1
    count = struct.unpack_from(">b", state, offset)[0]
    offset += 1
    removed = []
    for _ in range(count):
        identity, progress, position, modifications = struct.unpack_from(
            ">qhih", state, offset
        )
        offset += 16
        if modifications:
            raise AssertionError("Unexpected removed-turn modifications")
        removed.append((identity, progress, position))
    return dict(
        current=order[index],
        order=order,
        following=following,
        round=round_number,
        turn=turn,
        phase=phase,
        deadline=deadline,
        removed=removed,
    )


class SharedTimelineRecoveryTests(unittest.TestCase):
    def state(self, *, pending=False, start_callback=None):
        sessions = [
            Session(11, 25, "osa", 1134, 0),
            Session(10, 65, "tina", 1134, 0),
            Session(23, 46, "peer", 1134, 0),
        ]
        live = set(sessions)
        registry = Registry(lambda session: session in live)
        actors = [
            Actor(25, 0, (0, 0, 0), 589, 6, 3, 10, 36, 11, True),
            Actor(1205, 0, (1, 0, 0), 237, 0, 4, 400, 36, 11, True),
            Actor(-200, 1, (5, 0, 0), 1000, 6, 3, 0, 36),
        ]
        fight = Fight(
            377,
            actors,
            {(x, 0, 0) for x in range(6)},
            {0: {(x, 0, 0) for x in range(5)}, 1: {(5, 0, 0)}},
        )
        clock = [10.0]
        runtime = RuntimeMessages(fight, clock=lambda: clock[0])
        shared = registry.register(fight, sessions[0], runtime=runtime)
        for session, position, initiative in (
            (sessions[1], 2, 300),
            (sessions[2], 3, 100),
        ):
            actor = Actor(
                session.character_id,
                0,
                (position, 0, 0),
                617,
                6,
                3,
                initiative,
                36,
                session.account_id,
                True,
            )
            registry.join(
                session,
                struct.pack(">qB", 25, 0),
                actor,
                actor_payload=lambda *args: (b"stats", b"effects"),
                bootstrap_packets=lambda *args: [(12847, b"bootstrap")],
            )
        fight, runtime = shared.fight, shared.runtime
        for session in sessions:
            fight.ready(session.account_id)
        self.assertEqual(fight.current.id, 1205)
        fight.apply_damage(1205, 1205, 237)
        self.assertEqual(fight.current.id, -200)
        previous_enemy_turn = fight.turn_id
        runtime.turn_start_provider = start_callback
        runtime.end_server_turn(-200, previous_enemy_turn)
        self.assertEqual(fight.current.id, 65)
        self.assertEqual(fight.actors[1205].hp, 0)
        # Exact bounded removal metadata observed in the reported production
        # checkpoint; native progress is distinct from Actor.turn_count.
        removed = next(
            row for row in fight.native_timeline_removed if row["actor_id"] == 1205
        )
        removed["progress"] = 5
        if pending:
            shared.ack.arm(previous_enemy_turn, sessions)
        else:
            runtime.acknowledge_turn(struct.pack(">i", previous_enemy_turn))
        for session in sessions:
            registry.drain(fight.id, session)
        return registry, shared, sessions, clock, live

    def recover(self, registry, shared, session, *, now_ms=20000):
        return registry.recover_timeline(
            shared.fight.id, session, struct.pack(">i", shared.fight.id), now_ms=now_ms
        )

    def test_foreign_recovery_broadcasts_same_current_owner_and_removed_summon(self):
        registry, shared, sessions, clock, _ = self.state()
        clock[0] = 20.0
        deadline = shared.runtime.turn_deadline
        self.assertTrue(self.recover(registry, shared, sessions[2]))
        batches = [registry.drain(377, session) for session in sessions]
        self.assertTrue(all(len(batch) == 1 for batch in batches))
        self.assertEqual(
            [batch[0].packets for batch in batches], [batches[0][0].packets] * 3
        )
        packets = batches[0][0].packets
        self.assertNotIn(12847, [opcode for opcode, _ in packets])
        timeline = decoded_timeline(
            next(body for opcode, body in packets if opcode == 12053)
        )
        self.assertEqual(timeline["current"], 65)
        self.assertNotIn(1205, timeline["order"])
        self.assertTrue(any(row[:2] == (1205, 5) for row in timeline["removed"]))
        self.assertEqual(shared.fight.actors[65].owner_id, 10)
        self.assertEqual(shared.fight.actors[46].owner_id, 23)
        self.assertEqual(shared.runtime.turn_deadline, deadline)

    def test_owner_then_foreign_recovery_keeps_original_armed_deadline(self):
        registry, shared, sessions, clock, _ = self.state()
        deadline = shared.runtime.turn_deadline
        for session, instant in ((sessions[1], 20.0), (sessions[2], 30.0)):
            clock[0] = instant
            self.recover(registry, shared, session, now_ms=int(instant * 1000))
            self.assertEqual(shared.runtime.turn_deadline, deadline)
            for peer in sessions:
                packet = next(
                    body
                    for opcode, body in registry.drain(377, peer)[0].packets
                    if opcode == 12053
                )
                self.assertEqual(
                    decoded_timeline(packet)["deadline"], int(deadline * 1000)
                )

    def test_pending_ack_is_superseded_only_with_replacement_for_every_peer(self):
        registry, shared, sessions, _, _ = self.state(pending=True)
        self.assertIsNotNone(shared.ack.turn)
        self.assertTrue(shared.runtime.pending)
        self.recover(registry, shared, sessions[2])
        self.assertIsNone(shared.ack.turn)
        self.assertEqual(shared.ack.received, set())
        self.assertIsNone(shared.runtime.awaiting_ack)
        self.assertEqual(shared.runtime.pending, [])
        self.assertEqual(shared.runtime.deadline_turn, shared.fight.turn_id)
        self.assertTrue(all(registry.drain(377, peer) for peer in sessions))

    def test_serializer_failure_preserves_shared_state_ack_clocks_and_outboxes(self):
        from copy import deepcopy
        from wakfu_server.combat_effect_area_codec import area_retirement

        def callback(preview, **boundary):
            return deepcopy(preview), [
                area_retirement(preview.id, boundary["action_id"], 911)
            ]

        registry, shared, sessions, _, _ = self.state(
            pending=True, start_callback=callback
        )
        original_pending = tuple(shared.runtime.pending)

        def fail(*args):
            raise ValueError("serializer failed")

        shared.runtime.runtime_stats_serializer = fail
        fight, runtime, ack = shared.fight, shared.runtime, shared.ack
        sequence = shared.sequence
        with self.assertRaisesRegex(ValueError, "serializer failed"):
            self.recover(registry, shared, sessions[1])
        self.assertIs(shared.fight, fight)
        self.assertIs(shared.runtime, runtime)
        self.assertIs(shared.ack, ack)
        self.assertEqual(shared.sequence, sequence)
        self.assertEqual(tuple(runtime.pending), original_pending)
        self.assertIn(13726, [opcode for opcode, _ in runtime.pending])
        self.assertTrue(all(not registry.drain(377, peer) for peer in sessions))

    def test_stale_lease_cannot_publish_recovery(self):
        registry, shared, sessions, _, live = self.state()
        live.remove(sessions[2])
        sequence = shared.sequence
        with self.assertRaises(ValueError):
            self.recover(registry, shared, sessions[2])
        self.assertEqual(shared.sequence, sequence)

    def test_expired_clock_is_not_refreshed(self):
        registry, shared, sessions, clock, _ = self.state()
        deadline = shared.runtime.turn_deadline
        clock[0] = deadline + 1
        self.recover(registry, shared, sessions[2], now_ms=80000)
        self.assertEqual(shared.runtime.turn_deadline, deadline)
        self.assertTrue(shared.runtime.expiration_due())
        packet = next(
            body
            for opcode, body in registry.drain(377, sessions[1])[0].packets
            if opcode == 12053
        )
        self.assertEqual(decoded_timeline(packet)["deadline"], 80000)

    def test_pending_start_callback_retirement_is_published_once_before_fresh_timeline(
        self,
    ):
        from copy import deepcopy
        from wakfu_server.combat_effect_area_codec import area_retirement

        calls = []

        def callback(preview, **boundary):
            calls.append((preview.turn_id, boundary["actor_id"]))
            candidate = deepcopy(preview)
            candidate.apply_effect_damage(65, -200, 1)
            return candidate, [
                area_retirement(candidate.id, boundary["action_id"], 911)
            ]

        registry, shared, sessions, _, _ = self.state(
            pending=True, start_callback=callback
        )
        self.assertEqual(len(calls), 1)
        original_turn_id = shared.fight.turn_id
        original_round = shared.fight.native_timeline_round
        original_members = deepcopy(shared.fight.native_timeline_member_counters)
        self.assertEqual(shared.fight.actors[-200].hp, 999)
        self.assertIn(13726, [opcode for opcode, _ in shared.runtime.pending])
        self.recover(registry, shared, sessions[2])
        for peer in sessions:
            packets = registry.drain(377, peer)[0].packets
            opcodes = [opcode for opcode, _ in packets]
            self.assertEqual(opcodes.count(13726), 1)
            self.assertLess(opcodes.index(13726), opcodes.index(12053))
            self.assertEqual(opcodes.count(12053), 1)
            self.assertEqual(opcodes.count(13482), 1)
            self.assertNotIn(12514, opcodes)
            self.assertNotIn(13337, opcodes)
            self.assertNotIn(13477, opcodes)
            self.assertLess(opcodes.index(12053), opcodes.index(13482))
            retired = next(body for opcode, body in packets if opcode == 13726)
            self.assertEqual(struct.unpack_from(">q", retired, 12)[0], 911)
            timeline = decoded_timeline(
                next(body for opcode, body in packets if opcode == 12053)
            )
            self.assertEqual(timeline["turn"], shared.fight.turn_id - 1)
        first_deadline = shared.runtime.turn_deadline
        self.assertEqual(shared.runtime.deadline_turn, shared.fight.turn_id)
        self.recover(registry, shared, sessions[1], now_ms=90000)
        self.assertEqual(shared.runtime.turn_deadline, first_deadline)
        self.assertEqual(shared.fight.turn_id, original_turn_id)
        self.assertEqual(shared.fight.native_timeline_round, original_round)
        self.assertEqual(shared.fight.native_timeline_member_counters, original_members)
        self.assertEqual(len(calls), 1)
        self.assertEqual(shared.fight.actors[-200].hp, 999)
        self.assertEqual(shared.runtime.pending, [])
        for peer in sessions:
            self.assertNotIn(
                13726, [opcode for opcode, _ in registry.drain(377, peer)[0].packets]
            )
