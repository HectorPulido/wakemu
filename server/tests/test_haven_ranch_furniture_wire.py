import struct
import unittest

from wakfu_server.items.haven_ranch_furniture_wire import (
    add,
    decode_deploy,
    furniture_record,
)


class RanchFurnitureWireTests(unittest.TestCase):
    def test_native_reference_request_has_no_inventory_identity(self):
        self.assertEqual(
            decode_deploy(struct.pack(">iiii", 126, 6, -7, 12)),
            dict(item_ref=126, direction=6, x=-7, y=12),
        )
        for body in (
            b"",
            bytes(15),
            bytes(17),
            struct.pack(">iiii", 0, 0, 0, 0),
            struct.pack(">iiii", 126, 8, 0, 0),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_deploy(body)

    def test_add_installs_owner_area_and_exact_instance_record(self):
        item = dict(item_uid=123456, item_ref=126, direction=6, x=-7, y=12, z=4)
        opcode, body = add(92, 3, item)
        self.assertEqual(opcode, 12259)
        self.assertEqual(len(body), 45)
        self.assertEqual(
            struct.unpack(">qBqqBiiihBi", body),
            (92, 1, 123456, 126, 0, 6, -7, 12, 4, 0, 3),
        )
        self.assertEqual(body[9:-4], furniture_record(item))

    def test_rejects_invalid_native_instances_and_overflow(self):
        item = dict(item_uid=123456, item_ref=126, direction=6, x=-7, y=12, z=4)
        for field, value in (
            ("item_uid", 0),
            ("item_ref", True),
            ("direction", -1),
            ("x", 131073),
            ("y", -131072),
            ("z", 513),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                furniture_record({**item, field: value})
        with self.assertRaises(ValueError):
            add(0, 3, item)

    def test_context_preserves_independent_native_bridge_states(self):
        from wakfu_server.items.haven_ranch_furniture_wire import context

        states = [dict(slot_id=i, state=int(i == 2)) for i in range(1, 5)]
        _, body = context(92, 1440, [1, 2, 3, 4], [], 1000, building_states=states)
        offset = 21 + 4 * 24
        self.assertEqual(struct.unpack_from(">i", body, offset)[0], 4)
        self.assertEqual(
            [struct.unpack_from(">iB", body, offset + 4 + i * 5) for i in range(4)],
            [(1, 0), (2, 1), (3, 0), (4, 0)],
        )
        self.assertEqual(body[-12:], struct.pack(">iq", 0, 1000))
        for invalid in ([states[0], states[0]], [dict(slot_id=1, state=2)]):
            with self.assertRaises(ValueError):
                context(92, 1440, [1], [], 1000, building_states=invalid)

    def test_context_has_all_native_areas_and_no_invented_buildings_or_animals(self):
        from wakfu_server.items.haven_ranch_furniture_wire import context

        item = dict(
            item_uid=123456, item_ref=126, direction=6, x=-7, y=12, z=4, area_id=3
        )
        opcode, body = context(92, 1440, [1, 2, 3, 4], [item], 1000)
        self.assertEqual(opcode, 13864)
        self.assertEqual(struct.unpack_from(">qqBi", body), (92, 1440, 1, 4))
        self.assertEqual(body[-16:], struct.pack(">iiq", 0, 0, 1000))
        self.assertEqual(len(body), 21 + 4 * 24 + 32 + 16)
        with self.assertRaises(ValueError):
            context(92, 1440, [1, 2], [item], 1000)
