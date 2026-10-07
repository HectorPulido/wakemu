from collections import deque
from types import SimpleNamespace
import struct
import threading
import unittest

from world_shared import run_shared_turn
from native_context import NativeGraph
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Registry, Session


class SharedNativeAiTests(unittest.TestCase):
    def setUp(self):
        self.one = Session(1, 10, "first", 1134, 0)
        self.two = Session(2, 20, "second", 1134, 0)
        self.registry = Registry(lambda session: session in (self.one, self.two))
        pc = Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True)
        npc = Actor(-200, 1, (2, 0, 0), 20, 4, 2, 1, 1)
        self.fight = Fight(
            99,
            [pc, npc],
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        self.runtime = SimpleNamespace(fight=self.fight, awaiting_ack=None, pending=[])
        self.runtime.tactical_encounter_id = "shared-instance-test"
        self.shared = self.registry.register(self.fight, self.one, runtime=self.runtime)
        # Registry membership is an independent native subsystem tested in
        # server/tests. Supply its second established participant here.
        self.shared.participants[2] = self.two
        self.shared.connected.add(2)
        self.shared.outboxes[2] = deque()
        self.shared.future_context = {"full": b"future-native-authority"}
        self.fight.phase = "active"
        self.fight.order, self.fight.turn_index = [-200, 10], 0
        self.fight.turn_id = 9
        self.adapter = SimpleNamespace(registry=self.registry)
        self.public = (
            (13420, b"FIFO-before"),
            (12588, b"native-cast"),
            (12873, b"native-statistics"),
            (13420, b"FIFO-after"),
            (12502, b"native-turn-end"),
        )

    def runner(self, native):
        self.assertFalse(hasattr(self.shared.fight, "native_ai_team_context"))
        self.assertIsNot(native, self.runtime)
        self.assertIsNot(native.fight, self.fight)
        native.fight.actors[10].hp -= 5
        native.fight.turn_index = 1
        native.awaiting_ack = 9
        native.pending = [(12503, b"next-player-turn")]
        yield self.public, dict(action={"type": "cast", "spellId": 7962})

    def test_staged_turn_broadcasts_same_fifo_once_and_requires_all_real_acks(self):
        diagnostics = list(
            run_shared_turn(self.runtime, self.adapter, self.one, self.runner)
        )
        self.assertEqual(self.fight.actors[10].hp, 60)
        self.assertEqual(self.shared.fight.actors[10].hp, 55)
        self.assertEqual(self.shared.fight.native_ai_team_context["1"]["focusId"], 10)
        self.assertIs(self.shared.runtime.fight, self.shared.fight)
        self.assertEqual(diagnostics[0][0], [])
        self.assertTrue(diagnostics[0][1]["shared"])
        graph = NativeGraph(self.shared.runtime.native_ai_shared_context)
        root = graph.resolve(graph.data["root"])
        fields = {graph.plain(key): value for key, value in root["entries"]}
        self.assertEqual(
            graph.plain(fields["future_context"]), {"full": b"future-native-authority"}
        )
        for session in (self.one, self.two):
            batches = self.registry.drain(99, session)
            self.assertEqual(len(batches), 1)
            self.assertEqual(batches[0].packets, self.public)
        calls = []

        def release(fight, runtime, body):
            calls.append(body)
            packets = runtime.pending
            runtime.pending, runtime.awaiting_ack = [], None
            return packets

        body = struct.pack(">i", 9)
        self.assertFalse(self.registry.acknowledge(99, self.one, body, release))
        self.assertEqual(self.shared.runtime.awaiting_ack, 9)
        self.assertEqual(calls, [])
        self.assertTrue(self.registry.acknowledge(99, self.two, body, release))
        self.assertEqual(calls, [body])
        self.assertIsNone(self.shared.runtime.awaiting_ack)

    def test_failed_native_turn_keeps_live_source_and_outboxes_unchanged(self):
        def rejected(native):
            yield from self.runner(native)
            raise ValueError("unsupported native continuation")

        with self.assertRaisesRegex(ValueError, "unsupported native"):
            list(run_shared_turn(self.runtime, self.adapter, self.one, rejected))
        self.assertIs(self.shared.runtime, self.runtime)
        self.assertEqual(self.fight.actors[10].hp, 60)
        self.assertEqual(self.shared.sequence, 0)
        self.assertTrue(all(not queue for queue in self.shared.outboxes.values()))
        self.assertFalse(hasattr(self.shared.fight, "native_ai_team_context"))

    def test_concurrent_participants_cannot_run_the_same_npc_turn_twice(self):
        errors = []

        def attempt(session):
            try:
                list(run_shared_turn(self.runtime, self.adapter, session, self.runner))
            except Exception as error:
                errors.append(error)

        threads = [
            threading.Thread(target=attempt, args=(session,))
            for session in (self.one, self.two)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.shared.sequence, 1)
        self.assertEqual(self.shared.fight.actors[10].hp, 55)

    def test_empty_publication_does_not_adopt_candidate_or_advance_sequence(self):
        def empty(native):
            native.fight.actors[10].hp = 1
            yield [], {"reason": "rejected"}

        self.assertEqual(
            list(run_shared_turn(self.runtime, self.adapter, self.one, empty)), []
        )
        self.assertIs(self.shared.runtime, self.runtime)
        self.assertEqual(self.shared.fight.actors[10].hp, 60)
        self.assertEqual(self.shared.sequence, 0)
        self.assertTrue(all(not queue for queue in self.shared.outboxes.values()))
