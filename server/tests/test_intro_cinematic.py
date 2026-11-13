import struct
import unittest
from unittest.mock import Mock

from wakfu_server.intro_cinematic import (
    IntroCinematic,
    scenario_event,
    callback_id,
    ogrest_actor,
    private_instance_id,
    assign_new_character,
)


class IntroCinematicTest(unittest.TestCase):
    def test_private_ogrest_spawn_has_native_scene_appearance(self):
        actor_id, (opcode, packet) = ogrest_actor(123)
        self.assertEqual(opcode, 12608)
        count, kind, identity, length = struct.unpack_from(">HBqH", packet)
        self.assertEqual((count, kind, identity, length), (1, 1, actor_id, 104))
        body = packet[13:]
        self.assertEqual(
            struct.unpack_from(">qBqHh", body, 1), (actor_id, 1, -1, 0, 5814)
        )
        self.assertEqual(
            struct.unpack_from(">iihqBB", body, 22), (0, -6, 40, 1465, 3, 0)
        )
        self.assertNotEqual(ogrest_actor(124)[0], actor_id)
        for invalid in (0, -1, True, 2**48):
            with self.assertRaises(ValueError):
                ogrest_actor(invalid)

    def test_intro_instance_is_stable_and_unique_per_character(self):
        self.assertEqual(private_instance_id(123), private_instance_id(123))
        self.assertNotEqual(private_instance_id(123), private_instance_id(124))
        self.assertLess(private_instance_id(2**48 - 1), 2**63)
        for invalid in (0, -1, True, 2**48):
            with self.assertRaises(ValueError):
                private_instance_id(invalid)

    def test_spawn_choice_targets_only_the_inserted_owned_character(self):
        db = Mock()
        db.execute.return_value.rowcount = 1
        assign_new_character(db, 42, 123, tutorial=None)
        db.execute.assert_not_called()
        assign_new_character(db, 42, 123, tutorial=True)
        query, args = db.execute.call_args.args
        self.assertIn("WHERE id=%s AND account_id=%s AND deleted_at IS NULL", query)
        self.assertEqual(args, (1465, private_instance_id(123), 0, 0, 40, 123, 42))
        assign_new_character(db, 42, 124, tutorial=False)
        self.assertEqual(db.execute.call_args.args[1], (1385, 0, 27, 1, 1, 124, 42))
        db.execute.return_value.rowcount = 0
        with self.assertRaises(ValueError):
            assign_new_character(db, 42, 123, tutorial=True)
        with self.assertRaises(ValueError):
            assign_new_character(db, 42, 123, tutorial=1)

    def test_character_creation_request_passes_native_tutorial_choice(self):
        from wakfu_server.creation import create

        store = Mock()
        store.current_session.return_value = True
        store.create_character.return_value = {"id": 123}
        for flag in (False, True):
            name = b"Testing"
            body = (
                struct.pack(">qhB", -1, 3, len(name))
                + name
                + bytes([flag])
                + b"\x00\x00"
            )
            self.assertEqual(create(store, 42, 9, body), (0, {"id": 123}))
            self.assertIs(store.create_character.call_args.kwargs["tutorial"], flag)

    def test_capture_sequence_and_scoped_callbacks(self):
        ogrest = -123456789
        scene = IntroCinematic(ogrest)
        self.assertEqual(
            scene.start(), (13411, struct.pack(">BiiB", 0, 23908, 2698, 0))
        )
        callback = lambda value: struct.pack(">i", value)
        self.assertIsNone(scene.receive(callback(23909), map_id=1465))
        self.assertIsNone(scene.receive(callback(23908), map_id=527))
        self.assertEqual(
            scene.receive(callback(23908), map_id=1465), scenario_event(23909, 2698)
        )
        self.assertEqual(
            scene.receive(callback(23909), map_id=1465),
            scenario_event(23910, 2698, ogrest),
        )
        self.assertEqual(
            scene.receive(callback(23910), map_id=1465), scenario_event(23912, 2698)
        )
        self.assertEqual(
            scene.receive(callback(23912), map_id=1465), ("enter_incarnam", 1361)
        )
        self.assertIsNone(scene.receive(callback(23912), map_id=1465))

    def test_rejects_malformed_and_too_many_arguments(self):
        for body in (b"", b"\x00" * 3, b"\x00" * 5):
            with self.assertRaises(ValueError):
                callback_id(body)
        with self.assertRaises(ValueError):
            scenario_event(1, 2, *range(256))

    def test_reconnect_restarts_and_duplicate_callbacks_do_not_repeat_events(self):
        callback = lambda value: struct.pack(">i", value)
        first = IntroCinematic(ogrest_actor(99)[0])
        self.assertEqual(first.start(), scenario_event(23908, 2698))
        first.receive(callback(23908), map_id=1465)
        first.receive(callback(23909), map_id=1465)
        self.assertIsNone(first.receive(callback(23909), map_id=1465))
        reconnected = IntroCinematic(ogrest_actor(99)[0])
        self.assertEqual(reconnected.start(), scenario_event(23908, 2698))
        self.assertIsNone(reconnected.receive(callback(23910), map_id=1465))
        self.assertEqual(
            reconnected.receive(callback(23908), map_id=1465),
            scenario_event(23909, 2698),
        )

    def test_failed_final_transition_can_retry_without_replaying_videos(self):
        callback = lambda value: struct.pack(">i", value)
        scene = IntroCinematic(ogrest_actor(99)[0])
        with self.assertRaises(ValueError):
            scene.retry_completion()
        for event in (23908, 23909, 23910):
            scene.receive(callback(event), map_id=1465)
        self.assertEqual(
            scene.receive(callback(23912), map_id=1465), ("enter_incarnam", 1361)
        )
        self.assertIsNone(scene.receive(callback(23912), map_id=1465))
        scene.retry_completion()
        self.assertEqual(
            scene.receive(callback(23912), map_id=1465), ("enter_incarnam", 1361)
        )


if __name__ == "__main__":
    unittest.main()
