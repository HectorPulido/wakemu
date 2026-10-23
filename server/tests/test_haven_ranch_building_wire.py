"""Native JVM fixture parity and installed building-view catalog controls."""
import struct
import unittest

from wakfu_server import haven_ranch_building_catalog as catalog
from wakfu_server import haven_ranch_building_wire as wire


class RanchBuildingWireTests(unittest.TestCase):
    def test_original_place_request_record_and_response(self):
        request = bytes.fromhex("0000001000000000010000001c00000006")
        values = wire.decode_place(request)
        self.assertEqual(
            values, dict(building_ref=16, view_kind=0, view_value=1, x=28, y=6)
        )
        row = dict(
            values,
            uid=9001,
            mode_id=1,
            sector_id=1,
            contained_item_ref=-1,
            contained_quantity=0,
        )
        record = bytes.fromhex(
            "0000000000002329000000100000000100000000010000001c00000006ffffffff00000000"
        )
        self.assertEqual(wire.building_record(row), record)
        self.assertEqual(
            wire.placed(1440, row, scene_objects=()),
            (12558, struct.pack(">qB", 1440, 1) + record + struct.pack(">ib", 1, 0)),
        )

    def test_move_remove_and_failures_keep_real_uid(self):
        body = struct.pack(">qBiii", 9001, 0, 3, -10, 8)
        self.assertEqual(
            wire.decode_move(body),
            dict(uid=9001, view_kind=0, view_value=3, x=-10, y=8),
        )
        self.assertEqual(wire.decode_remove(struct.pack(">q", 9001)), 9001)
        self.assertEqual(
            wire.removed(1440, 9001, 2),
            (12950, struct.pack(">qBqiB", 1440, 1, 9001, 2, 1)),
        )
        self.assertEqual(
            wire.rejected(12671, 1440), (12558, struct.pack(">qB", 1440, 0))
        )
        self.assertEqual(
            wire.rejected(12662, 1440, uid=9001),
            (12530, struct.pack(">qBq", 1440, 0, 9001)),
        )
        self.assertEqual(
            wire.rejected(13480, 1440), (12950, struct.pack(">qB", 1440, 0))
        )
        for decode, length in (
            (wire.decode_place, 17),
            (wire.decode_move, 21),
            (wire.decode_remove, 8),
        ):
            for size in (0, length - 1, length + 1):
                with self.assertRaises(ValueError):
                    decode(bytes(size))

    def test_all_installed_modes_and_views_resolve_without_fabricated_models(self):
        self.assertEqual(len(catalog.definitions()), 112)
        for reference, definition in catalog.definitions().items():
            with self.subTest(reference=reference):
                self.assertIn(catalog.mode(definition), definition["epD"])
                for mode in definition["epD"]:
                    for kind, rows, key in (
                        (0, mode["epP"], "epS"),
                        (1, mode["epQ"], "epL"),
                    ):
                        for row in rows:
                            self.assertEqual(
                                catalog.view(definition, mode["p"], kind, row[key]),
                                row["epM"],
                            )
        for reference in range(131, 138):
            with self.assertRaisesRegex(
                ValueError, "no installed native building definition"
            ):
                catalog.definition(reference)
        with self.assertRaises(ValueError):
            catalog.view(catalog.definition(16), 1, 0, 99)
