import unittest, struct
import os
import threading
from unittest.mock import patch
from tests.test_ai_service import service
from wakfu_ai.transport.framed_server import FramedServer
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_movement_runtime import apply_client, decode_request


class MovementRuntimeTests(unittest.TestCase):
    def test_player_area_ap_loss_is_not_reapplied_after_final_snapshot(self):
        from copy import deepcopy
        from wakfu_server.combat_wire import decode_actor_state

        runtime, original = self.setup_fight()
        self.assertTrue(original.controlled)
        self.assertEqual(original.owner_id, 7)

        def ap_loss(preview, **boundary):
            preview = deepcopy(preview)
            preview.actors[original.id].ap -= 4
            return preview, [(12613, b"evaluated-native-AP-loss-4")]

        packets, event = apply_client(
            runtime,
            7,
            struct.pack(">qiih", original.id, 1, 0, 0),
            lambda actor: struct.pack(">ii", actor.ap, actor.mp),
            area_provider=ap_loss,
        )
        final = next(packet for packet in packets if packet[0] == 12873)
        effect = next(packet for packet in packets if packet[0] == 12613)
        self.assertLess(packets.index(effect), packets.index(final))
        state = decode_actor_state(12873, final[1])
        self.assertEqual(state["actor_id"], original.id)
        self.assertEqual(struct.unpack(">ii", state["state"]), (2, 2))
        self.assertEqual((original.ap, original.mp, event["cost"]), (2, 2, 1))

    def test_area_resource_callbacks_precede_authoritative_final_snapshot(self):
        from copy import deepcopy
        from wakfu_server.combat_wire import decode_actor_state

        runtime, original = self.setup_fight()

        def reward(preview, **boundary):
            preview = deepcopy(preview)
            actor = preview.actors[boundary["actor_id"]]
            actor.ap += 1
            actor.max_ap += 1
            actor.mp += 2
            actor.max_mp += 2
            return preview, [(12613, b"evaluated-AP"), (12613, b"evaluated-MP")]

        packets, event = apply_client(
            runtime,
            7,
            struct.pack(">qiih", original.id, 1, 0, 0),
            lambda actor: struct.pack(">ii", actor.ap, actor.mp),
            area_provider=reward,
        )
        self.assertEqual((original.ap, original.mp, event["cost"]), (7, 4, 1))
        self.assertEqual(
            [opcode for opcode, _ in packets],
            [13624, 13420, 12613, 12613, 12873, 13420],
        )
        final = decode_actor_state(12873, packets[-2][1])
        self.assertEqual(final["actor_id"], original.id)
        self.assertEqual(struct.unpack(">ii", final["state"]), (7, 4))

    def test_partial_path_resource_callback_precedes_zero_mp_snapshot(self):
        from copy import deepcopy
        from wakfu_server.combat_wire import decode_actor_state

        runtime, original = self.setup_fight()
        calls = []

        def exhaust(preview, **boundary):
            preview = deepcopy(preview)
            calls.append(boundary["path"])
            preview.actors[original.id].mp = 0
            return preview, [(12613, b"evaluated-MP-loss")]

        body = struct.pack(">q", original.id) + b"".join(
            struct.pack(">iih", x, 0, 0) for x in (1, 2)
        )
        packets, event = apply_client(
            runtime,
            7,
            body,
            lambda actor: struct.pack(">ii", actor.ap, actor.mp),
            area_provider=exhaust,
        )
        self.assertEqual(calls, [[(1, 0, 0)]])
        self.assertEqual(event["path"], [(1, 0, 0)])
        self.assertEqual((original.position, original.mp), ((1, 0, 0), 0))
        self.assertEqual(
            [opcode for opcode, _ in packets],
            [13624, 13420, 12613, 12873, 13420],
        )
        final = decode_actor_state(12873, packets[-2][1])
        self.assertEqual(struct.unpack(">ii", final["state"]), (6, 0))

    def test_current_fight_serializer_receives_exact_movement_preview(self):
        runtime, original = self.setup_fight()
        body = struct.pack(">qiih", original.id, 1, 0, 0)
        seen = []

        def serialize(actor, state):
            self.assertIs(state.actors[actor.id], actor)
            self.assertIsNot(state, runtime.fight)
            self.assertEqual((actor.position, actor.mp), ((1, 0, 0), 2))
            self.assertEqual((original.position, original.mp), ((0, 0, 0), 3))
            seen.append(actor.id)
            return b"owned-current-preview"

        packets, _ = apply_client(
            runtime,
            7,
            body,
            lambda actor: self.fail("Unary source must not receive preview actor"),
            runtime_stats_serializer=serialize,
        )
        self.assertEqual(seen, [original.id])
        self.assertTrue(packets[-1][1].endswith(b"owned-current-preview"))
        self.assertEqual((original.position, original.mp), ((1, 0, 0), 2))

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
        from tests.test_combat_tackle_movement import Authority

        runtime.fight.native_rail_movement_authority = Authority()
        for candidate in runtime.fight.actors.values():
            candidate.effect_stats = {
                1: candidate.hp,
                2: candidate.ap,
                3: candidate.mp,
                7: 0,
                8: 0,
            }
            candidate.physical_radius = 0
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
        cls.channel = FramedServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.channel.serve_forever, daemon=True)
        cls.thread.start()
        cls.environment = patch.dict(
            os.environ,
            {
                "WAKFU_AI_URL": "tcp://127.0.0.1:" + str(cls.channel.server_address[1]),
            },
        )
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.environment.stop()
        finally:
            cls.channel.shutdown()
            cls.channel.server_close()
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
