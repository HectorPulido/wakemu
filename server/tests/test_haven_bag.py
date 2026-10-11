import struct
import unittest
from protocol_codec import Reader
from wakfu_server.haven_bag import (
    own_bag,
    entry_result,
    map_transition,
    HavenBagSession,
)


class HavenBagTests(unittest.TestCase):
    def test_effective_public_room_policy_preserves_stored_management_data(self):
        from wakfu_server.haven_bag import visit_permission_payload, decode_permissions

        config = {
            "locked": True,
            "access": {
                "groups": [{"group": 0, "rights": 1}],
                "characters": [{"id": 12, "name": "Visitor", "rights": 0}],
            },
        }
        body = visit_permission_payload(config)
        self.assertEqual(
            decode_permissions(struct.pack(">I", len(body)) + body),
            (False, {"groups": [{"group": 0, "rights": 255}], "characters": []}),
        )
        self.assertTrue(config["locked"])
        self.assertEqual(config["access"]["characters"][0]["rights"], 0)

    def test_occupied_optional_rooms_do_not_acquire_native_fixed_primary_flag(self):
        from wakfu_server.haven_bag_store import initial_layout

        rooms = initial_layout(3)
        for index in range(1, 9):
            rooms[index].update(enabled=True, primary_ref=4263, primary_uid=800 + index)
        r = Reader(
            own_bag(
                dict(
                    id=3,
                    account_id=2,
                    name="Owner",
                    haven_bag=dict(
                        rooms=rooms,
                        furniture=[],
                        appearance_id=408,
                        locked=False,
                        access={
                            "groups": [{"group": 0, "rights": 1}],
                            "characters": [],
                        },
                    ),
                )
            )
        )
        r.number("q")
        r.number("q")
        r.text("H")
        r.number("q")
        r.number("h")
        r.number("q")
        self.assertEqual(r.number("B"), 9)
        for index in range(9):
            self.assertEqual(
                (r.number("B"), r.number("H"), r.number("B")), (index, 0, 0)
            )
            self.assertEqual(r.number("B"), int(index == 0))
            self.assertEqual(r.number("i"), 4262 if index == 0 else 4263)
            r.number("q")
            self.assertEqual((r.number("i"), r.number("q")), (-1, -1))

    def test_occupied_optional_primary_can_move_and_fixed_entrance_cannot_swap(self):
        from wakfu_server.haven_bag_store import initial_layout, rearrange_rooms

        rooms = initial_layout(3)
        rooms[8].update(enabled=True, primary_ref=4266, primary_uid=900)
        config = dict(rooms=rooms, furniture=[])
        result = rearrange_rooms(config, bytes((1, 1, 8, 1)))
        self.assertEqual((result[8]["enabled"], result[8]["primary_uid"]), (False, 0))
        self.assertEqual((result[1]["enabled"], result[1]["primary_uid"]), (True, 900))
        for body in (bytes((1, 1, 0, 8)), bytes((1, 1, 8, 0))):
            with self.assertRaises(ValueError):
                rearrange_rooms(config, body)

    def test_local_ownership_empty_commerce_room_and_no_inherited_items(self):
        r = Reader(own_bag({"id": 3, "account_id": 2, "name": "Prueba local"}))
        self.assertEqual(
            (r.number("q"), r.number("q"), r.text("H")), (2, 3, "Prueba local")
        )
        self.assertEqual((r.number("q"), r.number("h"), r.number("q")), (0, 0, 0))
        self.assertEqual(r.number("B"), 9)
        self.assertEqual((r.number("B"), r.number("H"), r.number("B")), (0, 0, 0))
        self.assertEqual((r.number("B"), r.number("i"), r.number("q")), (1, 4262, 769))
        self.assertEqual((r.number("i"), r.number("q")), (-1, -1))
        for index in range(1, 9):
            self.assertEqual(
                (r.number("B"), r.number("H"), r.number("B")), (index, 0, 0)
            )
            self.assertEqual(
                (
                    r.number("B"),
                    r.number("i"),
                    r.number("q"),
                    r.number("i"),
                    r.number("q"),
                ),
                (0, -1, -1, -1, -1),
            )
        self.assertEqual(r.number("i"), 408)
        self.assertEqual((r.number("B"), r.number("B"), r.number("H")), (0, 0, 1))
        self.assertEqual(
            (r.number("B"), r.number("B"), r.number("H"), r.number("B")), (0, 255, 0, 0)
        )
        r.finish()

    def test_failure_marks_own_bag_so_client_removes_temporary_outside_object(self):
        self.assertEqual(
            entry_result(success=False), b"\x00\x01" + struct.pack(">i", 0)
        )
        self.assertEqual(
            entry_result(success=True), b"\x01\x01" + struct.pack(">i", 0) + b"\x00\x01"
        )
        with self.assertRaises(ValueError):
            entry_result(success=True, own=False)


class HavenBagSessionTests(unittest.TestCase):
    def test_interior_moves_leave_exterior_return_point_unchanged(self):
        outside = dict(id=3, account_id=2, map_id=1134, instance_id=0, x=7, y=14, z=-1)
        state = HavenBagSession(outside)
        inside = state.move(state.inside, dict(x=4, y=3, z=0))
        self.assertEqual((inside["map_id"], inside["instance_id"]), (9, 3))
        self.assertEqual(state.leave(inside), outside)
        self.assertEqual(outside["x"], 7)
        at_exit = state.move(inside, dict(x=-4, y=2, z=0))
        self.assertEqual(state.leave(at_exit), outside)
        with self.assertRaises(ValueError):
            state.leave({**inside, "id": 4})

    def test_transition_changes_actual_map_and_removes_captured_fight_lists(self):
        from wakfu_server.wire import TEMPLATE_ACCOUNT, TEMPLATE_CHARACTER

        entity = (
            b"\x1c"
            + struct.pack(">qBq", TEMPLATE_CHARACTER, 0, TEMPLATE_ACCOUNT)
            + struct.pack(">iihq", -12, -8, -1, 1134)
            + b"\x00" * 20
        )
        self.assertEqual(len(entity), 56)
        blocks = [
            entity,
            b"captured fight entities",
            b"captured fight context",
            b"\x00",
        ]
        template = b"".join(struct.pack(">H", len(block)) + block for block in blocks)
        character = dict(id=3, account_id=2, x=3, y=3, z=0)
        r = Reader(map_transition(template, character, 9))
        first = r.take(r.number("H"))
        self.assertEqual(struct.unpack(">q", first[1:9])[0], 3)
        self.assertEqual(struct.unpack(">q", first[10:18])[0], 2)
        self.assertEqual(struct.unpack(">iihq", first[18:36]), (3, 3, 0, 9))
        self.assertEqual(r.take(r.number("H")), b"\x00\x00")
        self.assertEqual(r.take(r.number("H")), b"\x00\x00")
        r.take(r.number("H"))
        r.finish()

    def test_build_save_preserves_active_interior_and_updates_returned_build(self):
        outside = dict(
            id=3, account_id=2, map_id=1134, instance_id=0, x=7, y=14, z=-1, builds={}
        )
        state = HavenBagSession(outside)
        inside = state.move(state.inside, dict(x=4, y=3, z=0))
        saved = {**outside, "builds": {0: {"deck": "updated"}}}
        refreshed = state.refresh(inside, saved)
        self.assertEqual(
            (refreshed["map_id"], refreshed["instance_id"], refreshed["x"]), (9, 3, 4)
        )
        self.assertEqual(state.leave(refreshed), saved)

    def test_enter_leave_reenter_sends_ui_cleanup_before_exterior_transition(self):
        from wakfu_server.haven_bag import entry_messages, leave_messages
        from wakfu_server.haven_bag_store import initial_layout
        from wakfu_server.wire import TEMPLATE_ACCOUNT, TEMPLATE_CHARACTER

        entity = (
            b"\x1c"
            + struct.pack(">qBq", TEMPLATE_CHARACTER, 0, TEMPLATE_ACCOUNT)
            + struct.pack(">iihq", -12, -8, -1, 1134)
            + b"\x00" * 20
        )
        template = b"".join(
            struct.pack(">H", len(block)) + block
            for block in (entity, b"\x00\x00", b"\x00\x00", b"\x00")
        )
        config = dict(
            appearance_id=408,
            rooms=initial_layout(3),
            locked=True,
            access={"groups": [], "characters": []},
            furniture=[],
        )
        outside = dict(
            id=3,
            account_id=2,
            name="Own",
            map_id=1134,
            instance_id=0,
            x=7,
            y=14,
            z=-1,
            haven_bag=config,
        )
        session = HavenBagSession(outside)
        enter = entry_messages(template, session.inside)
        self.assertEqual([opcode for opcode, _ in enter], [13256, 13307, 13974, 12318])
        self.assertEqual(enter[0][1], b"")
        self.assertEqual(enter[1][1], bytes.fromhex("0101000000000001"))
        self.assertEqual(enter[-1][1], struct.pack(">ii", 3, 3))
        at_door = session.move(session.inside, dict(x=-4, y=2, z=0))
        restored = session.leave(at_door)
        leave = leave_messages(template, restored)
        # 13959 alone is insufficient: source ciu's flag cleanup is 13019.
        self.assertEqual(
            [(opcode, body) for opcode, body in leave[:2]],
            [(13959, b"\x00"), (13019, b"")],
        )
        self.assertEqual(
            [opcode for opcode, _ in leave], [13959, 13019, 13256, 13974, 12318]
        )
        self.assertEqual(leave[2][1], b"")
        self.assertEqual(leave[-1][1], struct.pack(">ii", 7, 14))
        r = Reader(leave[-2][1])
        entity = r.take(r.number("H"))
        self.assertEqual(struct.unpack(">iihq", entity[18:36]), (7, 14, -1, 1134))
        reenter = HavenBagSession(restored)
        self.assertEqual(entry_messages(template, reenter.inside)[1][0], 13307)
        self.assertEqual(reenter.inside["haven_bag"], config)
        self.assertEqual(len(reenter.inside["haven_bag"]["rooms"]), 9)
        with self.assertRaises(ValueError):
            leave_messages(template, reenter.inside)
        with self.assertRaises(ValueError):
            entry_messages(template, restored)
