import unittest, struct
import os
import threading
from unittest.mock import patch
from tests.test_ai_service import service
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_movement_runtime import apply_client, decode_request


class MovementRuntimeTests(unittest.TestCase):
    def test_direction_follows_last_planar_path_step_and_preserves_vertical_facing(
        self,
    ):
        from wakfu_server.combat_movement_runtime import direction_after_path

        vectors = (
            (1, -1),
            (1, 0),
            (1, 1),
            (0, 1),
            (-1, 1),
            (-1, 0),
            (-1, -1),
            (0, -1),
        )
        for direction, (dx, dy) in enumerate(vectors):
            with self.subTest(direction=direction):
                self.assertEqual(
                    direction_after_path((0, 0, 0), [(dx, dy, 0)], 6), direction
                )
        self.assertEqual(direction_after_path((0, 0, 0), [(1, 0, 0), (1, 0, 1)], 6), 1)
        self.assertEqual(direction_after_path((0, 0, 0), [(1, 0, 0), (1, 1, 0)], 6), 3)
        self.assertEqual(direction_after_path((0, 0, 0), [(0, 0, 1)], 6), 6)
        with self.assertRaisesRegex(ValueError, "native facing vector"):
            direction_after_path((0, 0, 0), [(2, 0, 0)], 6)

    def setup_fight(self):
        cells = {(x, 0, 0) for x in range(4)}
        p = Actor(1, 0, (0, 0, 0), 60, 6, 3, 9, 1, 7, True)
        n = Actor(-2, 1, (3, 0, 0), 12, 6, 3, 1, 1)
        edges = {(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1}
        f = Fight(2, [p, n], cells, {0: {p.position}, 1: {n.position}}, edges)
        f.ready(7)
        return RuntimeMessages(f), p

    def test_spends_mp_and_emits_native_animation_flush_stats(self):
        r, p = self.setup_fight()
        packets, event = apply_client(
            r,
            7,
            struct.pack(">qiih", 1, 1, 0, 0),
            lambda a: struct.pack(">i", a.mp),
        )
        self.assertEqual([n for n, _ in packets], [13624, 13420, 12873])
        self.assertEqual((p.position, p.mp), ((1, 0, 0), 2))
        self.assertEqual(packets[2][1][-4:], struct.pack(">i", 2))
        self.assertEqual(event["cost"], 1)
        self.assertEqual(p.direction, 1)
        self.assertEqual(packets[0][1][20], 1)

    def test_invalid_edge_does_not_mutate(self):
        r, p = self.setup_fight()
        with self.assertRaises(ValueError):
            apply_client(r, 7, struct.pack(">qiih", 1, 2, 0, 0), lambda a: b"own")
        self.assertEqual((p.position, p.mp, r.action_id), ((0, 0, 0), 3, 0))

    def test_rejects_malformed_owner_and_sync(self):
        r, p = self.setup_fight()
        body = struct.pack(">qiih", 1, 1, 0, 0)
        with self.assertRaises(ValueError):
            decode_request(body + b"\0")
        with self.assertRaises(ValueError):
            apply_client(r, 8, body, lambda a: b"own")
        r.awaiting_ack = 1
        with self.assertRaises(ValueError):
            apply_client(r, 7, body, lambda a: b"own")

    def test_preview_characteristics_sync_without_mutating_original_on_codec_failure(
        self,
    ):
        runtime, actor = self.setup_fight()
        actor.effect_stats = {1: 60, 2: 6, 3: 3}
        body = struct.pack(">qiih", 1, 1, 0, 0)

        def fail(candidate):
            self.assertEqual(candidate.effect_stats[3], 2)
            self.assertEqual(candidate.direction, 1)
            self.assertEqual(actor.effect_stats[3], 3)
            raise ValueError("codec failure")

        with self.assertRaises(ValueError):
            apply_client(runtime, 7, body, fail)
        self.assertEqual(
            (actor.mp, actor.effect_stats[3], runtime.action_id), (3, 3, 0)
        )
        self.assertEqual(actor.direction, 0)
        apply_client(runtime, 7, body, lambda candidate: b"own")
        self.assertEqual((actor.mp, actor.effect_stats[3]), (2, 2))


class AIMovementRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.environment = patch.dict(
            os.environ,
            {
                "WAKFU_AI_URL": "http://127.0.0.1:" + str(cls.http.server_port),
            },
        )
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.environment.stop()
        finally:
            cls.http.shutdown()
            cls.http.server_close()
            cls.thread.join(2)

    def setup_fight(self):
        cells = {(x, 0, 0) for x in range(6)}
        p = Actor(1, 0, (5, 0, 0), 60, 6, 3, 0, 1, 7, True)
        n = Actor(-2, 1, (0, 0, 0), 12, 6, 3, 9, 1)
        edges = {(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1}
        f = Fight(2, [p, n], cells, {0: {p.position}, 1: {n.position}}, edges)
        f.ready(7)
        return RuntimeMessages(f), n

    def test_ai_moves_and_spends_own_mp(self):
        from wakfu_server.combat_movement_runtime import apply_ai

        r, n = self.setup_fight()
        packets, result = apply_ai(
            r, lambda actor: struct.pack(">i", actor.mp), direction=2
        )
        self.assertEqual([opcode for opcode, _ in packets], [13624, 13420, 12873])
        self.assertEqual((n.position, n.mp), ((3, 0, 0), 0))
        self.assertEqual(result["event"]["cost"], 3)
        self.assertEqual(n.direction, 2)
        self.assertIsNone(result["attack"])

    def test_server_move_rejects_owned_actor_and_occupied_cell(self):
        r, n = self.setup_fight()
        with self.assertRaises(ValueError):
            r.fight.server_move(1, [(4, 0, 0)])
        with self.assertRaises(ValueError):
            r.fight.server_move(-2, [(x, 0, 0) for x in range(1, 6)])
        self.assertEqual((n.position, n.mp), ((0, 0, 0), 3))

    def test_serializer_failure_does_not_commit(self):
        from wakfu_server.combat_movement_runtime import apply_ai

        r, n = self.setup_fight()

        def fail(actor):
            raise ValueError("Invalid owned stats")

        with self.assertRaises(ValueError):
            apply_ai(r, fail, direction=2)
        self.assertEqual((n.position, n.mp, r.action_id), ((0, 0, 0), 3, 0))
