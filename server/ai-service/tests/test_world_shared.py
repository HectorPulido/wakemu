from collections import deque
import gzip
from types import SimpleNamespace
import struct
import threading
import unittest

from wakfu_ai.bridge.world_shared import run_shared_turn
from wakfu_ai.context.native_context import NativeGraph
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
        self.assertIsInstance(self.shared.runtime.native_ai_shared_context, bytes)
        self.assertTrue(
            self.shared.runtime.native_ai_shared_context.startswith(b"\x1f\x8b")
        )
        graph = NativeGraph(self.shared.runtime.native_ai_shared_context)
        self.assertEqual(
            graph.data,
            NativeGraph(
                gzip.decompress(self.shared.runtime.native_ai_shared_context)
            ).data,
        )
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
            native.fight.actors[10].hp -= 5
            raise RuntimeError("unexpected native continuation failure")
            yield [], {}

        with self.assertRaisesRegex(RuntimeError, "unexpected native"):
            list(run_shared_turn(self.runtime, self.adapter, self.one, rejected))
        self.assertIs(self.shared.runtime, self.runtime)
        self.assertEqual(self.fight.actors[10].hp, 60)
        self.assertEqual(self.shared.sequence, 0)
        self.assertTrue(all(not queue for queue in self.shared.outboxes.values()))
        self.assertFalse(hasattr(self.shared.fight, "native_ai_team_context"))

    def test_move_is_published_before_post_move_search_and_deadline_is_shared(self):
        calls = []
        closed = []
        original_deadlines = []

        def progressive(native):
            calls.append(native)
            original_deadlines.append(native.native_ai_preparation_started_at)
            try:
                if len(calls) == 1:
                    native.fight.actors[-200].position = (1, 0, 0)
                    native.fight.actors[-200].mp = 0
                    yield [(123, b"native-move")], {"action": {"type": "move"}}
                    self.fail("Old private generator resumed after adoption")
                self.assertEqual(native.fight.actors[-200].position, (1, 0, 0))
                self.assertEqual(native.fight.actors[-200].mp, 0)
                self.assertIsNot(native, calls[0])
                native.fight.turn_index = 1
                native.awaiting_ack = 9
                yield [(12502, b"native-turn-end")], {"action": {"type": "end_turn"}}
            finally:
                closed.append(native)

        iterator = run_shared_turn(self.runtime, self.adapter, self.one, progressive)
        next(iterator)
        self.assertEqual(len(calls), 1)
        self.assertEqual(closed, calls)
        self.assertEqual(self.shared.sequence, 1)
        for session in (self.one, self.two):
            self.assertEqual(
                self.registry.drain(99, session)[0].packets,
                ((123, b"native-move"),),
            )
        next(iterator)
        self.assertEqual(len(calls), 2)
        self.assertEqual(original_deadlines[0], original_deadlines[1])
        self.assertEqual(self.shared.sequence, 2)
        for session in (self.one, self.two):
            self.assertEqual(
                self.registry.drain(99, session)[0].packets,
                ((12502, b"native-turn-end"),),
            )
        self.assertEqual(list(iterator), [])
        self.assertEqual(self.shared.runtime.awaiting_ack, 9)

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

    def test_six_vs_six_move_survives_next_search_failure_and_acks_fifo_barrier(self):
        """A published movement is durable even if replanning then fails."""
        one = Session(1, 10, "first", 1134, 0)
        two = Session(2, 20, "second", 1134, 0)
        registry = Registry(lambda session: session in (one, two))
        positions = [(index, 0, 0) for index in range(12)]
        actors = [Actor(10, 0, positions[0], 60, 6, 3, 100, 1, 1, True)]
        actors.extend(
            Actor(-100 - index, 0, positions[index + 1], 30, 6, 3, 50, 1)
            for index in range(5)
        )
        actors.append(Actor(20, 1, positions[6], 60, 6, 3, 100, 1, 2, True))
        actors.extend(
            Actor(-200 - index, 1, positions[index + 7], 30, 6, 3, 50, 1)
            for index in range(5)
        )
        fight = Fight(
            100,
            actors,
            set(positions),
            {0: set(positions[:6]), 1: set(positions[6:])},
        )

        class Runtime:
            def __init__(self, fight):
                self.fight = fight
                self.awaiting_ack = None
                self.pending = []
                self.tactical_encounter_id = "six-vs-six-publication"

            def end_server_turn(self, actor_id, turn_id):
                self.fight.turn_index = 1
                self.awaiting_ack = turn_id
                self.pending = [(12503, b"next-turn")]
                return [(12502, struct.pack(">i", turn_id))]

        runtime = Runtime(fight)
        shared = registry.register_duel(
            fight,
            (one, two),
            runtime=runtime,
            initial_packets={1: (), 2: ()},
        )
        self.assertEqual(len(shared.fight.actors), 12)
        for participant in (one, two):
            self.assertEqual(registry.drain(100, participant)[0].packets, ())
        fight.phase = "active"
        fight.order = [
            -100,
            20,
            -101,
            10,
            -102,
            -200,
            -103,
            -201,
            -104,
            -202,
            -203,
            -204,
        ]
        fight.turn_index = 0
        fight.turn_id = 37
        adapter = SimpleNamespace(registry=registry)
        calls = []
        competing_calls = []
        move_packets = ((123, b"published-native-move"),)

        def runner(native):
            calls.append(native)
            if len(calls) == 1:
                native.fight.actors[-100].position = (2, 1, 0)
                native.fight.actors[-100].mp -= 1
                yield move_packets, {"action": {"type": "move"}}
                self.fail("The adopted move search must not resume")
            raise ValueError("post-move search failed")

        def competing_runner(native):
            competing_calls.append(native)
            raise AssertionError("A second owner duplicated the claimed NPC turn")
            yield (), {}

        iterator = run_shared_turn(runtime, adapter, one, runner)
        first_delivery = next(iterator)
        self.assertEqual(first_delivery[1]["action"], {"type": "move"})
        self.assertEqual(shared.fight.actors[-100].position, (2, 1, 0))
        self.assertEqual(shared.sequence, 2)  # duel bootstrap plus published move
        self.assertFalse(shared.lock._is_owned(), "do not hold fight lock across yield")

        finished = threading.Event()
        errors = []

        def competing_turn():
            try:
                list(run_shared_turn(runtime, adapter, two, competing_runner))
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()

        thread = threading.Thread(target=competing_turn)
        thread.start()
        self.assertTrue(
            finished.wait(1), "another participant must not block on AI yield"
        )
        thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(competing_calls, [])

        # The second fresh search fails. The first movement must stay published,
        # and the native end-turn barrier must still be emitted for both owners.
        later = list(iterator)
        self.assertEqual(len(calls), 2)
        self.assertTrue(
            any(row[1].get("action", {}).get("type") == "end_turn" for row in later)
        )
        self.assertEqual(shared.fight.actors[-100].position, (2, 1, 0))
        self.assertEqual(shared.sequence, 3)
        self.assertEqual(shared.runtime.awaiting_ack, 37)
        for participant in (one, two):
            batches = registry.drain(100, participant)
            self.assertEqual([batch.sequence for batch in batches], [2, 3])
            self.assertEqual(batches[0].packets, move_packets)
            self.assertEqual(batches[1].packets, ((12502, struct.pack(">i", 37)),))

        released = []

        def release(candidate, candidate_runtime, body):
            released.append(body)
            packets = candidate_runtime.pending
            candidate_runtime.pending = []
            candidate_runtime.awaiting_ack = None
            return packets

        body = struct.pack(">i", 37)
        self.assertFalse(registry.acknowledge(100, one, body, release))
        self.assertEqual(released, [])
        self.assertTrue(registry.acknowledge(100, two, body, release))
        self.assertEqual(released, [body])
        self.assertIsNone(shared.runtime.awaiting_ack)
        for participant in (one, two):
            batches = registry.drain(100, participant)
            self.assertEqual(len(batches), 1)
            self.assertEqual(batches[0].packets, ((12503, b"next-turn"),))

    def test_runner_is_lock_free_and_stale_private_result_is_replanned(self):
        started = threading.Event()
        continue_search = threading.Event()
        calls = []
        deliveries = []
        errors = []
        original_position = self.shared.fight.actors[-200].position

        def runner(native):
            self.assertFalse(self.shared.lock._is_owned())
            calls.append(native)
            if len(calls) == 1:
                native.fight.actors[-200].position = (1, 1, 0)
                started.set()
                self.assertTrue(continue_search.wait(1))
                yield [(123, b"stale-private-move")], {"action": {"type": "move"}}
                return
            if len(calls) == 2:
                self.assertEqual(native.fight.actors[-200].position, original_position)
                native.fight.actors[-200].position = (1, 0, 0)
                yield [(123, b"fresh-move")], {"action": {"type": "move"}}
                return
            native.fight.turn_index = 1
            native.awaiting_ack = 9
            yield [(12502, b"native-turn-end")], {"action": {"type": "end_turn"}}

        def consume():
            try:
                deliveries.extend(
                    run_shared_turn(self.runtime, self.adapter, self.one, runner)
                )
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=consume)
        thread.start()
        self.assertTrue(started.wait(1))
        # This real registry publication advances the sequence during search.
        # The private movement planned against the older sequence must be lost.
        self.registry.publish(99, self.one, ((999, b"concurrent-publication"),))
        continue_search.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.shared.fight.actors[-200].position, (1, 0, 0))
        self.assertEqual(self.shared.runtime.awaiting_ack, 9)
        batches = self.registry.drain(99, self.one)
        self.assertEqual(
            [batch.packets for batch in batches],
            [
                ((999, b"concurrent-publication"),),
                ((123, b"fresh-move"),),
                ((12502, b"native-turn-end"),),
            ],
        )
        self.assertNotIn(
            ((123, b"stale-private-move"),),
            [batch.packets for batch in batches],
        )

    def test_close_after_move_publishes_native_barrier_for_remaining_owners(self):
        def end_server_turn(native, actor_id, turn_id):
            native.fight.turn_index = 1
            native.awaiting_ack = turn_id
            native.pending = [(12503, b"next-player-turn")]
            return [(12502, struct.pack(">i", turn_id))]

        self.runtime.end_server_turn = end_server_turn.__get__(
            self.runtime, type(self.runtime)
        )

        def runner(native):
            native.fight.actors[-200].position = (1, 0, 0)
            yield [(123, b"native-move")], {"action": {"type": "move"}}

        iterator = run_shared_turn(self.runtime, self.adapter, self.one, runner)
        next(iterator)
        iterator.close()
        self.assertEqual(self.shared.sequence, 2)
        self.assertEqual(self.shared.runtime.awaiting_ack, 9)
        for participant in (self.one, self.two):
            batches = self.registry.drain(99, participant)
            self.assertEqual(
                [batch.packets for batch in batches],
                [
                    ((123, b"native-move"),),
                    ((12502, struct.pack(">i", 9)),),
                ],
            )

    def test_empty_post_move_search_ends_turn_without_undoing_move(self):
        calls = []

        def end_server_turn(native, actor_id, turn_id):
            native.fight.turn_index = 1
            native.awaiting_ack = turn_id
            return [(12502, struct.pack(">i", turn_id))]

        self.runtime.end_server_turn = end_server_turn.__get__(
            self.runtime, type(self.runtime)
        )

        def runner(native):
            calls.append(native)
            if len(calls) == 1:
                native.fight.actors[-200].position = (1, 0, 0)
                yield [(123, b"native-move")], {"action": {"type": "move"}}
            else:
                return

        deliveries = list(run_shared_turn(self.runtime, self.adapter, self.one, runner))
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.shared.fight.actors[-200].position, (1, 0, 0))
        self.assertEqual(self.shared.runtime.awaiting_ack, 9)
        self.assertTrue(
            any(
                row[1].get("action", {}).get("type") == "end_turn" for row in deliveries
            )
        )
        for participant in (self.one, self.two):
            batches = self.registry.drain(99, participant)
            self.assertEqual(
                [batch.packets for batch in batches],
                [
                    ((123, b"native-move"),),
                    ((12502, struct.pack(">i", 9)),),
                ],
            )
