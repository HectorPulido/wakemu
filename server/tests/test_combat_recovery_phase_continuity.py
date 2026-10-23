"""Existing ACTION provenance survives queued recovery and serializer failure."""
from copy import deepcopy
import struct
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session, Transition


class RecoveryPhaseContinuityTests(unittest.TestCase):
    def setup_started(self):
        actors = (
            Actor(100, 0, (0, 0, 0), 60, 6, 3, 1000, 1, 1, True),
            Actor(200, 0, (1, 0, 0), 60, 6, 3, 900, 1, 1, True),
            Actor(-200, 1, (2, 0, 0), 60, 6, 3, 100, 1),
        )
        fight = Fight(
            91,
            actors,
            {actor.position for actor in actors},
            {0: {actors[0].position, actors[1].position}, 1: {actors[2].position}},
        )
        session = Session(1, 100, "current-session", 1134, 0)
        registry = Registry(lambda candidate: candidate == session)
        shared = registry.register(fight, session)

        def start(candidate, _):
            candidate.ready(1)
            runtime = RuntimeMessages(candidate, clock=lambda: 0.0)
            packets = runtime.combat_started(
                {actor.id: (b"baseline-stats", bytes(2)) for actor in actors}
            )
            return Transition(candidate, runtime, packets)

        registry.execute(91, session, 100, start, require_turn=False)
        return registry, shared, session

    def test_unflushed_initial_action_stays_ahead_of_recovery_for_same_transport(self):
        registry, shared, session = self.setup_started()
        shared.fight.native_spell_usage = {
            "100": {
                "turn": 1,
                "casts": {"4604": 2},
                "targets": {"4604": {"-200": 1}},
                "last": {"4604": 1},
            }
        }
        usage = deepcopy(shared.fight.native_spell_usage)
        registry.execute(
            91,
            session,
            100,
            lambda candidate, runtime: runtime.recover(
                1,
                struct.pack(">i", 91),
                now_ms=1000,
                preserve_armed_deadline=True,
            ),
            require_turn=False,
        )
        batches = registry.drain(91, session)
        self.assertEqual(len(batches), 2)
        self.assertLess(batches[0].sequence, batches[1].sequence)
        initial = [opcode for opcode, _ in batches[0].packets]
        recovery = [opcode for opcode, _ in batches[1].packets]
        self.assertEqual(initial.count(12514), 2)
        self.assertEqual(recovery.count(12053), 1)
        self.assertNotIn(12514, recovery)
        self.assertNotIn(13482, recovery)
        self.assertNotIn(13560, recovery)
        self.assertEqual(shared.fight.native_spell_usage, usage)
        self.assertEqual(shared.fight.turn_id, 1)

    def test_recovery_serializer_failure_preserves_pending_and_outbox(self):
        registry, shared, session = self.setup_started()
        shared.runtime.awaiting_ack = shared.fight.turn_id
        shared.runtime.pending = [(13827, b"unpublished-effect")]
        shared.runtime.native_timeline_restore_pending_turn = shared.fight.turn_id
        before = (
            deepcopy(shared.fight.native_spell_usage),
            shared.fight.turn_id,
            shared.runtime.awaiting_ack,
            deepcopy(shared.runtime.pending),
            shared.runtime.turn_deadline,
            shared.sequence,
            deepcopy(tuple(shared.outboxes[1])),
        )

        def reject(*_):
            raise ValueError("current stats unavailable")

        shared.runtime.runtime_stats_serializer = reject
        with self.assertRaisesRegex(ValueError, "current stats unavailable"):
            registry.execute(
                91,
                session,
                100,
                lambda candidate, runtime: runtime.recover(
                    1,
                    struct.pack(">i", 91),
                    now_ms=1000,
                ),
                require_turn=False,
            )
        after = (
            shared.fight.native_spell_usage,
            shared.fight.turn_id,
            shared.runtime.awaiting_ack,
            shared.runtime.pending,
            shared.runtime.turn_deadline,
            shared.sequence,
            tuple(shared.outboxes[1]),
        )
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
