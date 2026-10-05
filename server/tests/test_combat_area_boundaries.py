import struct, unittest
from copy import deepcopy
from test_combat_runtime_messages import RuntimeMessageTests
from test_combat_movement_runtime import MovementRuntimeTests
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_geometry_snapshot import source_snapshot


class AreaBoundaryTests(unittest.TestCase):
    def test_turn_callback_once_per_turn_and_ack_does_not_repeat(self):
        fight, _ = RuntimeMessageTests().state()
        calls = []

        def provider(preview, **boundary):
            calls.append((preview.turn_id, boundary["actor_id"]))
            return deepcopy(preview), ((12705, b"owned"),)

        runtime = RuntimeMessages(fight, turn_start_provider=provider)
        runtime.turn_started()
        runtime.turn_started()
        self.assertEqual(calls, [(1, 100)])
        runtime.end_turn(1, 100, 1)
        self.assertEqual(calls, [(1, 100), (2, -200)])
        runtime.acknowledge_turn(struct.pack(">i", 1))
        self.assertEqual(calls, [(1, 100), (2, -200)])
        self.assertIs(runtime.fight, fight)

    def test_lethal_turn_callback_returns_finished_without_clock_or_second_delivery(
        self,
    ):
        fight, _ = RuntimeMessageTests().state()
        calls = []

        def provider(preview, **boundary):
            calls.append(boundary["actor_id"])
            preview = deepcopy(preview)
            preview.apply_effect_damage(-200, 100, 60)
            return preview, ((12705, b"owned"),)

        runtime = RuntimeMessages(fight, turn_start_provider=provider)
        packets = runtime.turn_started()
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(calls, [100])
        self.assertIsNone(runtime.turn_deadline)
        self.assertNotIn(13337, [opcode for opcode, _ in packets])

    def test_next_turn_callback_failure_rolls_back_end_and_runtime(self):
        fight, _ = RuntimeMessageTests().state()

        def reject(preview, **boundary):
            preview.current.hp -= 1
            raise ValueError("area unknown")

        runtime = RuntimeMessages(fight, turn_start_provider=reject)
        before = source_snapshot(fight)
        with self.assertRaisesRegex(ValueError, "area unknown"):
            runtime.end_turn(1, 100, 1)
        self.assertEqual(source_snapshot(fight), before)
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.action_id, 0)
        self.assertEqual(runtime.pending, [])

    def test_movement_callbacks_receive_path_and_commit_on_same_fight(self):
        runtime, actor = MovementRuntimeTests().setup_fight()
        original = runtime.fight

        def provider(preview, **boundary):
            self.assertEqual(boundary["origin"], (0, 0, 0))
            self.assertEqual(boundary["path"], [(1, 0, 0), (2, 0, 0)])
            self.assertEqual(preview.actors[1].mp, 1)
            preview.actors[1].hp -= 2
            return preview, ((12705, b"owned"),)

        packets, _ = apply_client(
            runtime,
            7,
            struct.pack(">q", 1) + struct.pack(">iihiih", 1, 0, 0, 2, 0, 0),
            lambda a: b"owned",
            direction=2,
            area_provider=provider,
        )
        self.assertIs(runtime.fight, original)
        self.assertIs(runtime.fight.actors[1], actor)
        self.assertEqual((actor.position, actor.mp, actor.hp), ((2, 0, 0), 1, 58))
        self.assertEqual(packets[-2:], [(12705, b"owned"), runtime._flush()])

    def test_callback_failure_cannot_spend_mp_move_or_emit(self):
        runtime, actor = MovementRuntimeTests().setup_fight()
        before = source_snapshot(runtime.fight)

        def reject(preview, **boundary):
            preview.actors[1].hp -= 2
            raise ValueError("area unknown")

        with self.assertRaisesRegex(ValueError, "area unknown"):
            apply_client(
                runtime,
                7,
                struct.pack(">qiih", 1, 1, 0, 0),
                lambda a: b"owned",
                direction=2,
                area_provider=reject,
            )
        self.assertEqual(source_snapshot(runtime.fight), before)
        self.assertEqual(runtime.action_id, 0)
